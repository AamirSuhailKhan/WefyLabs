import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score
from app.schemas.broker import validate_and_normalize_indian_phone
from app.services.whatsapp_service import send_message
from app.services.ai_service import generate_ai_qualification_response
from app.services.lead_scorer import calculate_lead_score
from app.services.followup_service import schedule_followup_sequence, cancel_pending_followups

logger = logging.getLogger(__name__)

INDIAN_PHONE_EXTRACT_REGEX = re.compile(r"(\+91)?([6-9]\d{9})")

def extract_indian_phone(text: str) -> Optional[str]:
    """Extracts 10-digit Indian phone number from message body and normalizes to +91XXXXXXXXXX."""
    match = INDIAN_PHONE_EXTRACT_REGEX.search(text)
    if match:
        ten_digits = match.group(2)
        return f"+91{ten_digits}"
    return None

async def process_incoming_whatsapp_message(db: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes incoming 360dialog WhatsApp webhook message payload.
    Supports both Meta Cloud API webhook format and 360dialog direct messages array.
    """
    # 1. Parse message details from webhook payload
    from_phone = None
    message_text = ""
    message_id = None

    if "entry" in payload:
        # Standard Meta / 360dialog Cloud API format
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                val = change.get("value", {})
                statuses = val.get("statuses", [])
                if statuses:
                    st = statuses[0]
                    msg_id = st.get("id")
                    status_val = st.get("status")
                    recipient_id = st.get("recipient_id")
                    logger.info(f"[Meta Status Update] Msg ID: {msg_id} | Status: {status_val} | Recipient: {recipient_id}")
                    return {"status": "success", "action": "status_update_processed", "message_id": msg_id, "message_status": status_val}
                
                messages = val.get("messages", [])
                if messages:
                    msg = messages[0]
                    from_phone = msg.get("from")
                    message_id = msg.get("id")
                    if msg.get("type") == "text":
                        message_text = msg.get("text", {}).get("body", "")
                    elif msg.get("type") in ("image", "audio", "voice", "document", "location"):
                        message_text = f"[{msg.get('type').upper()} attachment received]"
    elif "messages" in payload:
        # 360dialog direct format
        messages = payload.get("messages", [])
        if messages:
            msg = messages[0]
            from_phone = msg.get("from")
            message_id = msg.get("id")
            if msg.get("type") == "text":
                message_text = msg.get("text", {}).get("body", "")
            elif msg.get("type") in ("image", "audio", "voice", "document", "location"):
                message_text = f"[{msg.get('type').upper()} attachment received]"

    if not from_phone or not message_text:
        return {"status": "ignored", "reason": "No valid text message found"}

    try:
        normalized_from = validate_and_normalize_indian_phone(from_phone)
    except ValueError:
        normalized_from = from_phone if from_phone.startswith("+") else f"+{from_phone}"

    # 2. Check if sender is a registered Broker
    broker_stmt = select(Broker).where(
        (Broker.whatsapp_number == normalized_from) | (Broker.phone == normalized_from)
    )
    broker = (await db.execute(broker_stmt)).scalars().first()

    if broker:
        # Broker message handling: check if forwarding a lead phone number
        forwarded_phone = extract_indian_phone(message_text)
        if forwarded_phone:
            # Query or create Lead
            lead_stmt = select(Lead).where(
                Lead.phone == forwarded_phone,
                Lead.broker_id == broker.id,
                Lead.deleted_at.is_(None)
            )
            existing_lead = (await db.execute(lead_stmt)).scalars().first()

            if not existing_lead:
                existing_lead = Lead(
                    broker_id=broker.id,
                    phone=forwarded_phone,
                    source="whatsapp_forward",
                    score="pending",
                    score_confidence=0.0,
                    status="pending",
                    pipeline_stage="new"
                )
                db.add(existing_lead)
                await db.commit()

            # Reply to Broker
            broker_reply = f"Got it! I'll chat with {forwarded_phone} and update you shortly."
            await send_message(broker.whatsapp_number, broker_reply)

            # Initiate qualification message to Lead
            welcome_msg = (
                f"Hi! I'm assisting {broker.name} from {broker.agency_name or 'Apex Realty'} in {broker.city}. "
                f"Are you looking to buy or rent a property?"
            )
            await send_message(forwarded_phone, welcome_msg)

            # Save bot outbound conversation record
            conv = Conversation(
                lead_id=existing_lead.id,
                direction="outbound",
                sender_type="bot",
                message=welcome_msg,
                message_type="text"
            )
            db.add(conv)
            await db.commit()

            return {"status": "success", "action": "lead_created_and_contacted", "lead_id": str(existing_lead.id)}
        else:
            # Send instructions to Broker
            guide_msg = "To register a new lead, please forward or send their 10-digit phone number (e.g., +919876543210)."
            await send_message(broker.whatsapp_number, guide_msg)
            return {"status": "success", "action": "broker_guided"}

    # 3. Check if sender is an existing Lead
    lead_stmt = (
        select(Lead)
        .where(Lead.phone == normalized_from, Lead.deleted_at.is_(None))
        .options(
            selectinload(Lead.conversations),
            selectinload(Lead.scores)
        )
    )
    lead = (await db.execute(lead_stmt)).scalars().first()

    if lead:
        # Cancel any pending follow-ups since lead replied!
        await cancel_pending_followups(db, lead.id)

        # Fetch lead's broker
        broker_stmt = select(Broker).where(Broker.id == lead.broker_id)
        broker = (await db.execute(broker_stmt)).scalars().first()
        broker_name = broker.name if broker else "our team"
        agency_name = broker.agency_name if broker else "Premier Realty"
        city = broker.city if broker else "Bengaluru"

        # Save inbound lead conversation
        inbound_conv = Conversation(
            lead_id=lead.id,
            direction="inbound",
            sender_type="lead",
            message=message_text,
            message_type="text",
            whatsapp_message_id=message_id
        )
        db.add(inbound_conv)
        lead.last_message_at = datetime.now(timezone.utc)
        await db.commit()

        # Re-fetch lead with conversations loaded to avoid expired relationship attributes
        lead_stmt = (
            select(Lead)
            .where(Lead.id == lead.id)
            .options(
                selectinload(Lead.conversations),
                selectinload(Lead.scores)
            )
        )
        lead = (await db.execute(lead_stmt)).scalars().first()

        # Check max bot messages guard
        bot_message_count = len([c for c in lead.conversations if c.sender_type == "bot"])
        if bot_message_count >= 8:
            lead.score = "unqualified"
            await db.commit()
            bot_limit_msg = f"Thanks! {broker_name} will call you directly with options."
            await send_message(lead.phone, bot_limit_msg)
            if broker:
                await send_message(broker.whatsapp_number, f"Lead {lead.phone} reached max bot attempts. Please call directly.")
            return {"status": "success", "action": "max_bot_limit_reached"}

        # Format history for AI
        history = [{"sender": c.sender_type, "text": c.message} for c in lead.conversations[-5:]]

        # Call AI Qualification Service
        ai_resp = await generate_ai_qualification_response(
            broker_name=broker_name,
            agency_name=agency_name,
            city=city,
            current_extracted_data={
                "budget_min": lead.budget_min,
                "budget_max": lead.budget_max,
                "property_type": lead.property_type,
                "transaction_type": lead.transaction_type,
                "preferred_locations": lead.preferred_locations,
                "timeline": lead.timeline,
                "loan_status": lead.loan_status
            },
            history=history,
            latest_message=message_text
        )

        resp_msg = ai_resp.get("response_message", f"Thanks! {broker_name} will call you shortly.")
        extracted = ai_resp.get("extracted_data", {})

        # Update lead extracted fields
        if extracted.get("budget_min") is not None:
            lead.budget_min = extracted["budget_min"]
        if extracted.get("budget_max") is not None:
            lead.budget_max = extracted["budget_max"]
        if extracted.get("property_type"):
            lead.property_type = extracted["property_type"]
        if extracted.get("transaction_type"):
            lead.transaction_type = extracted["transaction_type"]
        if extracted.get("preferred_locations"):
            lead.preferred_locations = extracted["preferred_locations"]
        if extracted.get("timeline"):
            lead.timeline = extracted["timeline"]
        if extracted.get("loan_status"):
            lead.loan_status = extracted["loan_status"]

        # Save outbound bot conversation
        outbound_conv = Conversation(
            lead_id=lead.id,
            direction="outbound",
            sender_type="bot",
            message=resp_msg,
            message_type="text"
        )
        db.add(outbound_conv)
        await db.commit()

        # Send response to lead via WhatsApp
        await send_message(lead.phone, resp_msg)

        # Check qualification complete
        if ai_resp.get("qualification_complete") or ai_resp.get("end_conversation"):
            current_dict = {
                "budget_min": lead.budget_min,
                "budget_max": lead.budget_max,
                "property_type": lead.property_type or "2bhk",
                "transaction_type": lead.transaction_type or "buy",
                "preferred_locations": lead.preferred_locations or ["Bengaluru Core"],
                "timeline": lead.timeline or "1_month",
                "loan_status": lead.loan_status or "in_process"
            }
            score_val, confidence_val, reasoning_val = calculate_lead_score(current_dict)
            lead.score = score_val
            lead.score_confidence = confidence_val
            lead.status = "qualified"
            lead.qualified_at = datetime.now(timezone.utc)

            score_record = Score(
                lead_id=lead.id,
                score=score_val,
                confidence=confidence_val,
                reasoning=reasoning_val,
                extracted_data=current_dict
            )
            db.add(score_record)
            await db.commit()

            # Schedule follow-up sequence
            await schedule_followup_sequence(db, lead)

            # Notify Broker
            if broker:
                loc_str = ", ".join(lead.preferred_locations or ["Bengaluru Core"])
                b_min = f"₹{lead.budget_min/100000:.0f}L" if lead.budget_min else "N/A"
                b_max = f"₹{lead.budget_max/100000:.0f}L" if lead.budget_max else "N/A"
                broker_alert = (
                    f"🔥 {score_val.upper()} LEAD — {lead.phone} | "
                    f"Budget: {b_min}-{b_max} | Location: {loc_str} | "
                    f"Ready to view. Call now!"
                )
                await send_message(broker.whatsapp_number, broker_alert)

        return {"status": "success", "action": "lead_responded", "lead_id": str(lead.id)}

    # 4. Unknown Sender
    await send_message(normalized_from, "Please sign up at beetlelabs.ai first.")
    return {"status": "success", "action": "unknown_sender_notified"}
