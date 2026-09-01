import asyncio
import logging
import re
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

def normalize_to_digits_only(phone: str) -> str:
    """Strips all non-digit characters and ensures country code."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10 and digits[0] in "6789":
        digits = f"91{digits}"
    return digits

async def send_message(to_phone: str, message: str, message_type: str = "text") -> bool:
    """
    Sends a WhatsApp message via Meta Cloud API Direct (Free 1,000 conversations/month)
    or 360dialog WABA API as fallback.
    Retries once after 5 seconds if an error occurs.
    """
    recipient_digits = normalize_to_digits_only(to_phone)
    
    if settings.ENV in ("testing", "test"):
        logger.info(f"[Test Mode WhatsApp Dispatch] To: {recipient_digits} | Message: {message[:30]}...")
        return True

    # 1. Prefer Meta Cloud API Direct (Free 1,000 convos/mo) if credentials configured
    if settings.WHATSAPP_ACCESS_TOKEN and settings.PHONE_NUMBER_ID:
        url = f"https://graph.facebook.com/v25.0/{settings.PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_digits,
            "type": "text",
            "text": {"body": message}
        }

        logger.info(
            f"[Meta Cloud API] WABA: {settings.WABA_ID} | "
            f"Phone ID: {settings.PHONE_NUMBER_ID} | To: {recipient_digits}"
        )

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code in (200, 201, 202):
                        logger.info(f"[Meta Direct Sent] To: {recipient_digits} | Status: {response.status_code}")
                        return True
                    else:
                        logger.warning(f"[Meta Direct Error] Attempt {attempt+1}: Status {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"[Meta Direct Exception] Attempt {attempt+1}: {e}")
            
            if attempt == 0:
                await asyncio.sleep(5)
        return False


    # 2. Fallback to 360dialog API or simulated mode
    url = f"{settings.DIALOG360_API_BASE.rstrip('/')}/messages"
    headers = {
        "D360-API-KEY": settings.DIALOG360_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_digits,
        "type": "text",
        "text": {"body": message}
    }

    if settings.DIALOG360_API_KEY == "d360_key_placeholder" or settings.ENV == "testing":
        logger.info(f"[WhatsApp Simulated Send] To: {recipient_digits} | Msg: {message}")
        return True

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code in (200, 201, 202):
                    logger.info(f"[360dialog Sent] To: {recipient_digits} | Status: {response.status_code}")
                    return True
                else:
                    logger.warning(f"[360dialog Error] Attempt {attempt+1}: Status {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[360dialog Exception] Attempt {attempt+1}: {e}")
        
        if attempt == 0:
            await asyncio.sleep(5)

    return False
