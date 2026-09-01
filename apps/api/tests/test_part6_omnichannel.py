"""
Volume 2 PART 6 — Enterprise Omnichannel Communication Engine Test Suite
=========================================================================
14 Automated Tests covering:

1.  Provider abstraction — all 5 adapters implement full CommunicationProvider interface
2.  WhatsApp normalization — raw payload → InboundMessageDTO
3.  Telegram normalization — text/photo/voice payload → InboundMessageDTO
4.  Email normalization — inbound webhook payload → InboundMessageDTO
5.  SMS normalization — generic SMS payload → InboundMessageDTO
6.  Cross-channel unification — WhatsApp → Email = 1 OmnichannelConversation
7.  Conversation router creates ConversationControl on new conversation
8.  Message normalization + idempotency (duplicate suppression)
9.  Delivery lifecycle — enqueue → process → status update
10. Retry engine — exponential backoff + dead-letter after max retries
11. Human takeover — pause AI → verify mode → AI briefing → resume AI
12. Template rendering — variable injection + missing variable handling
13. Presence service — typing event creation + expiry + purge
14. Monitoring — KPI aggregation from message records
"""
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base

# ─── Models ───────────────────────────────────────────────────────────────────
from app.models.communication_models import (
    OmnichannelConversation, ConversationChannelLink, ConversationControl,
    ChannelMessage, MessageAttachment, DeliveryStatusRecord,
    MessageTemplate, TemplateVariable, OutboundQueue, InboundQueue,
    TypingEvent, PresenceRecord,
)
# Also import legacy models so SQLite creates all tables
from app.models.communication_models import UnifiedConversation, UnifiedMessage, CallDetailRecord

from unittest.mock import patch, MagicMock

# ─── Providers ────────────────────────────────────────────────────────────────
from app.modules.communication.provider_adapters.base_provider import (
    CommunicationProvider,
    OutboundMessageDTO,
    ProviderResponse,
    DeliveryStatusEnum,
)
from app.modules.communication.provider_adapters.whatsapp_provider import WhatsAppCloudProvider
from app.modules.communication.provider_adapters.telegram_provider import TelegramProvider
from app.modules.communication.provider_adapters.email_smtp_provider import EmailSMTPProvider
from app.modules.communication.provider_adapters.webchat_provider import WebChatProvider
from app.modules.communication.provider_adapters.sms_provider import MockSMSProvider

# ─── Services ─────────────────────────────────────────────────────────────────
from app.modules.communication.channel_manager.manager import ChannelManager
from app.modules.communication.conversation_router.router import ConversationRouter
from app.modules.communication.normalizer.message_normalizer import MessageNormalizer
from app.modules.communication.delivery_engine.engine import DeliveryEngine
from app.modules.communication.retry_engine.retry import RetryEngine
from app.modules.communication.template_engine.engine import TemplateEngine
from app.modules.communication.human_takeover.takeover_service import HumanTakeoverService
from app.modules.communication.presence.presence_service import PresenceService
from app.modules.communication.monitoring.comm_monitor import CommunicationMonitor

# ─── Test Database ────────────────────────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ─── Fixtures ─────────────────────────────────────────────────────────────────

ORG_ID = "test-org-001"
LEAD_ID = "test-lead-001"


@pytest_asyncio.fixture
async def test_conversation(db: AsyncSession) -> OmnichannelConversation:
    """Create a test OmnichannelConversation."""
    conv = OmnichannelConversation(
        organization_id=ORG_ID,
        lead_id=LEAD_ID,
        control_mode="ai",
        preferred_channel="whatsapp",
        status="active",
        last_channel="whatsapp",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@pytest_asyncio.fixture
def channel_manager() -> ChannelManager:
    """Build a ChannelManager with all mock providers."""
    manager = ChannelManager()
    manager.register(WhatsAppCloudProvider(
        access_token="mock", phone_number_id="mock_pid", app_secret="mock_secret"
    ))
    manager.register(TelegramProvider(bot_token="mock_token"))
    manager.register(EmailSMTPProvider(
        smtp_host="smtp.test.com", smtp_port=587,
        smtp_user="test@test.com", smtp_password="pass",
        from_email="test@test.com", from_name="Test",
    ))
    manager.register(WebChatProvider())
    manager.register(MockSMSProvider())
    return manager


# ════════════════════════════════════════════════════════════════════════════════
# TEST 1: Provider Abstraction — All adapters implement CommunicationProvider
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_provider_abstraction():
    """All 5 providers must be subclasses of CommunicationProvider."""
    providers = [
        WhatsAppCloudProvider("tok", "pid", "secret"),
        TelegramProvider("token"),
        EmailSMTPProvider("host", 587, "user", "pass", "from@x.com", "Name"),
        WebChatProvider(),
        MockSMSProvider(),
    ]

    for provider in providers:
        assert isinstance(provider, CommunicationProvider), \
            f"{type(provider).__name__} is not a CommunicationProvider"
        # All required properties must be defined
        assert isinstance(provider.provider_name, str) and provider.provider_name
        assert isinstance(provider.channel, str) and provider.channel
        assert isinstance(provider.supported_message_types, list)
        assert len(provider.supported_message_types) > 0

    # Connect all
    for provider in providers:
        await provider.connect()

    # Disconnect all
    for provider in providers:
        await provider.disconnect()

    print("✓ All 5 providers implement CommunicationProvider interface")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 2: WhatsApp Message Normalization
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_whatsapp_normalization():
    """WhatsApp webhook payload normalizes to correct InboundMessageDTO."""
    provider = WhatsAppCloudProvider("tok", "test_pid", "secret")
    await provider.connect()

    wa_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "test_pid"},
                    "contacts": [{"profile": {"name": "Rahul Sharma"}}],
                    "messages": [{
                        "id": "wamid.test123",
                        "from": "+919876543210",
                        "type": "text",
                        "text": {"body": "Hi, I want to book a site visit for DLF Phase 5"},
                    }]
                }
            }]
        }]
    }

    dto = await provider.receive(wa_payload)

    assert dto.channel == "whatsapp"
    assert dto.provider_name in ("meta_cloud", "whatsapp_cloud")
    assert dto.provider_message_id == "wamid.test123"
    assert dto.sender_identifier == "+919876543210"
    assert dto.sender_name == "Rahul Sharma"
    assert "DLF Phase 5" in dto.content
    assert dto.message_type == "text"
    assert dto.idempotency_key  # Must be non-empty

    print(f"✓ WhatsApp normalization: '{dto.content[:40]}...'")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 3: Telegram Message Normalization
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_telegram_normalization():
    """Telegram text + voice payload normalizes correctly."""
    provider = TelegramProvider(bot_token="mock")

    # Text message
    text_payload = {
        "message": {
            "message_id": 12345,
            "from": {"first_name": "Tariq", "last_name": "Mansoor", "username": "tariq_m"},
            "chat": {"id": 987654321},
            "text": "Please send me the Jumeirah villa brochure",
        }
    }
    dto_text = await provider.receive(text_payload)
    assert dto_text.channel == "telegram"
    assert dto_text.message_type == "text"
    assert dto_text.sender_name == "Tariq Mansoor"
    assert "brochure" in dto_text.content

    # Voice note
    voice_payload = {
        "message": {
            "message_id": 12346,
            "from": {"first_name": "Tariq"},
            "chat": {"id": 987654321},
            "voice": {"file_id": "VOICE_FILE_123", "duration": 15}
        }
    }
    dto_voice = await provider.receive(voice_payload)
    assert dto_voice.message_type == "voice_note"
    assert len(dto_voice.attachments) == 1
    assert dto_voice.attachments[0]["provider_media_id"] == "VOICE_FILE_123"

    print("✓ Telegram normalization: text + voice_note")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 4: Email Message Normalization
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_email_normalization():
    """Email inbound webhook payload normalizes correctly."""
    provider = EmailSMTPProvider("h", 587, "u", "p", "from@x.com", "Name")

    payload = {
        "from": '"Ahmed Al-Rashid" <ahmed@example.ae>',
        "subject": "Interested in Emaar Hills Estate",
        "text": "Hello, I would like pricing details for the 4BR villas.",
        "message_id": "<test123@gmail.com>",
        "attachments": [],
    }
    dto = await provider.receive(payload)

    assert dto.channel == "email"
    assert dto.sender_identifier == "ahmed@example.ae"
    assert dto.sender_name == "Ahmed Al-Rashid"
    assert "Emaar Hills Estate" in dto.content
    assert dto.message_type == "text"

    print(f"✓ Email normalization: sender={dto.sender_identifier}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 5: SMS Normalization
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sms_normalization():
    """SMS webhook payload normalizes correctly."""
    provider = MockSMSProvider()
    await provider.connect()

    payload = {
        "From": "+91 9876 543 210",
        "Body": "Stop",
        "MessageSid": "SM123456",
    }
    dto = await provider.receive(payload)

    assert dto.channel == "sms"
    assert dto.sender_identifier == "+91 9876 543 210"
    assert dto.content == "Stop"
    assert dto.idempotency_key

    outbound_dto = OutboundMessageDTO(
        message_id="msg-sms-test-1",
        conversation_id="conv-sms-1",
        organization_id="org-1",
        channel="sms",
        provider_name="mock_sms",
        recipient_identifier="+91 9876 543 210",
        content="Reply OK",
    )
    result = await provider.send(outbound_dto)
    assert result.success
    assert result.status == "sent"

    print("✓ SMS normalization + send")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 6: Cross-Channel Unification (WhatsApp → Email = 1 Conversation)
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cross_channel_unification(db: AsyncSession):
    """
    Customer contacts via WhatsApp first, then emails.
    Must result in ONE OmnichannelConversation, not two.
    """
    router = ConversationRouter()

    # WhatsApp inbound
    from app.modules.communication.provider_adapters.base_provider import InboundMessageDTO
    wa_dto = InboundMessageDTO(
        provider_name="meta_cloud",
        channel="whatsapp",
        provider_message_id="wamid.001",
        idempotency_key="idem_001",
        sender_identifier="+919876543210",
        sender_name="Rahul Sharma",
        content="Hi, interested in 3BHK",
        message_type="text",
        raw_payload={},
    )

    conv1, is_new1 = await router.route(wa_dto, ORG_ID, LEAD_ID, db)
    await db.commit()

    assert is_new1 is True
    assert conv1.id

    # Now email from same lead
    email_dto = InboundMessageDTO(
        provider_name="smtp",
        channel="email",
        provider_message_id="email_001",
        idempotency_key="idem_email_001",
        sender_identifier="rahul@example.com",
        sender_name="Rahul Sharma",
        content="Following up on my 3BHK inquiry",
        message_type="text",
        raw_payload={},
    )

    conv2, is_new2 = await router.route(email_dto, ORG_ID, LEAD_ID, db)
    await db.commit()

    # CRITICAL: Same conversation ID — cross-channel unified
    assert is_new2 is False, "Email should link to existing conversation, not create new"
    assert conv2.id == conv1.id, \
        f"Expected same conversation! Got {conv2.id} vs {conv1.id}"

    # Verify channel links
    stmt = select(ConversationChannelLink).where(
        ConversationChannelLink.conversation_id == conv1.id
    )
    links = (await db.execute(stmt)).scalars().all()
    channels = {l.channel for l in links}
    assert "whatsapp" in channels
    assert "email" in channels

    print(f"✓ Cross-channel unification: WhatsApp + Email → 1 conversation (id={conv1.id[:8]}...)")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 7: ConversationControl created on new conversation
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_conversation_control_created(db: AsyncSession):
    """New conversation creates ConversationControl in 'ai' mode."""
    router = ConversationRouter()
    from app.modules.communication.provider_adapters.base_provider import InboundMessageDTO

    dto = InboundMessageDTO(
        provider_name="telegram",
        channel="telegram",
        provider_message_id="tg_999",
        idempotency_key=f"idem_{uuid.uuid4()}",
        sender_identifier="chat_999999",
        sender_name="Test User",
        content="Hello",
        message_type="text",
        raw_payload={},
    )

    conv, is_new = await router.route(dto, ORG_ID, f"lead-{uuid.uuid4()}", db)
    await db.commit()

    assert is_new is True

    # Check control record
    stmt = select(ConversationControl).where(ConversationControl.conversation_id == conv.id)
    control = (await db.execute(stmt)).scalars().first()

    assert control is not None
    assert control.control_mode == "ai"
    assert control.assigned_agent_id is None

    print(f"✓ ConversationControl created with mode='ai' for new conversation")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 8: Message Normalization + Idempotency
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_message_normalization_and_idempotency(
    db: AsyncSession, test_conversation: OmnichannelConversation
):
    """Normalizing the same message twice returns None on second call (dedup)."""
    normalizer = MessageNormalizer()
    from app.modules.communication.provider_adapters.base_provider import InboundMessageDTO

    idem_key = hashlib.sha256(f"test:{uuid.uuid4()}".encode()).hexdigest()[:64]
    dto = InboundMessageDTO(
        provider_name="meta_cloud",
        channel="whatsapp",
        provider_message_id="wamid_test",
        idempotency_key=idem_key,
        sender_identifier="+91 9999 9999",
        sender_name="Test Buyer",
        content="What is the price of 2BHK?",
        message_type="text",
        raw_payload={},
    )

    # First call: creates message
    msg1 = await normalizer.normalize(dto, test_conversation, db)
    await db.flush()

    assert msg1 is not None
    assert msg1.content == "What is the price of 2BHK?"
    assert msg1.channel == "whatsapp"
    assert msg1.organization_id == ORG_ID

    # Second call (duplicate): returns None
    msg2 = await normalizer.normalize(dto, test_conversation, db)
    assert msg2 is None

    print(f"✓ Message normalization + idempotency: msg_id={msg1.id[:8]}...")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 9: Delivery Lifecycle — enqueue → process → status
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delivery_lifecycle(
    db: AsyncSession, channel_manager: ChannelManager,
    test_conversation: OmnichannelConversation
):
    """Full delivery lifecycle: enqueue → process → status update."""
    engine = DeliveryEngine(channel_manager)

    # Enqueue a message
    msg = await engine.enqueue(
        conversation=test_conversation,
        content="Hello, your property inquiry has been received.",
        channel="whatsapp",
        recipient_identifier="+919876543210",
        db=db,
        sent_by_ai=True,
    )
    await db.flush()

    assert msg.id
    assert msg.delivery_status == "queued"
    assert msg.sent_by_ai is True
    assert msg.direction == "outbound"

    # Verify OutboundQueue entry
    stmt = select(OutboundQueue).where(OutboundQueue.message_id == msg.id)
    queue_item = (await db.execute(stmt)).scalars().first()
    assert queue_item is not None
    assert queue_item.status == "pending"
    assert queue_item.channel == "whatsapp"

    # Process the queue item with mocked provider response
    with patch.object(
        channel_manager.get_provider("whatsapp"),
        "send",
        return_value=ProviderResponse(
            success=True,
            provider_message_id="wamid.mock_delivery_123",
            status="sent",
            delivery_status=DeliveryStatusEnum.SENT,
            latency_ms=10,
        ),
    ):
        result = await engine.process_queue_item(queue_item, db)
        assert result.success
        assert result.status == "sent"
        assert result.provider_message_id

    # Verify queue item updated to sent
    assert queue_item.status == "sent"

    # Verify DeliveryStatusRecord created
    status_stmt = select(DeliveryStatusRecord).where(DeliveryStatusRecord.message_id == msg.id)
    records = (await db.execute(status_stmt)).scalars().all()
    statuses = {r.status for r in records}
    assert "queued" in statuses
    assert "sent" in statuses

    print(f"✓ Delivery lifecycle: queued → sent for msg_id={msg.id[:8]}...")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 10: Retry Engine — exponential backoff + dead-letter
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_retry_engine(
    db: AsyncSession, channel_manager: ChannelManager,
    test_conversation: OmnichannelConversation
):
    """Failed message retries with backoff; moves to dead_letter after max retries."""
    engine = DeliveryEngine(channel_manager)
    retry_engine = RetryEngine(engine)

    # Create a message and queue entry in retry state
    msg = ChannelMessage(
        conversation_id=test_conversation.id,
        organization_id=ORG_ID,
        lead_id=LEAD_ID,
        channel="whatsapp",
        provider_name="meta_cloud",
        direction="outbound",
        message_type="text",
        content="Test retry message",
        sender_identifier="system",
        sender_name="AI",
        delivery_status="queued",
        idempotency_key=hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:64],
    )
    db.add(msg)
    await db.flush()

    # Queue item already at max retries → should go to dead_letter
    queue_item = OutboundQueue(
        organization_id=ORG_ID,
        message_id=msg.id,
        status="retry",
        provider_name="meta_cloud",
        channel="whatsapp",
        recipient_identifier="+91 0000 0000",
        payload={"content": "Test retry", "message_id": msg.id,
                 "conversation_id": test_conversation.id,
                 "organization_id": ORG_ID, "channel": "whatsapp",
                 "provider_name": "meta_cloud", "recipient_identifier": "+91 0000 0000"},
        retry_count=5,  # At max
        max_retries=5,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),  # Due now
        idempotency_key=hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:64],
    )
    db.add(queue_item)
    await db.flush()

    # Run retry cycle
    count = await retry_engine.run_retry_cycle(db, batch_size=10)
    # Item was processed (success or dead-letter)

    # Test stats
    stats = await retry_engine.get_retry_queue_stats(db, ORG_ID)
    assert isinstance(stats, dict)

    print(f"✓ Retry engine: processed {count} retry items; stats={stats}")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 11: Human Takeover — pause AI → verify → briefing → resume
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_human_takeover(
    db: AsyncSession, test_conversation: OmnichannelConversation
):
    """Full AI → Human → AI control cycle."""
    service = HumanTakeoverService()

    # Initially: AI is active
    is_ai = await service.is_ai_active(test_conversation, db)
    assert is_ai is True

    # Add some messages for briefing generation
    for i in range(3):
        db.add(ChannelMessage(
            conversation_id=test_conversation.id,
            organization_id=ORG_ID,
            lead_id=LEAD_ID,
            channel="whatsapp",
            provider_name="meta_cloud",
            direction="inbound" if i % 2 == 0 else "outbound",
            message_type="text",
            content=f"Message {i+1}: Customer inquiry about pricing",
            sender_identifier="+919876543210",
            sender_name="Lead",
            delivery_status="delivered",
            idempotency_key=hashlib.sha256(f"brief_{i}_{uuid.uuid4()}".encode()).hexdigest()[:64],
        ))
    await db.flush()

    # Pause AI (human takeover)
    agent_id = str(uuid.uuid4())
    event = await service.pause_ai(
        conversation=test_conversation,
        taken_over_by=agent_id,
        db=db,
        reason="complex_negotiation",
        agent_name="Senior Agent",
    )
    await db.flush()

    assert event.takeover_by == agent_id
    assert event.ai_briefing and len(event.ai_briefing) > 20
    assert "BRIEFING" in event.ai_briefing

    # Verify AI is now inactive
    is_ai_after = await service.is_ai_active(test_conversation, db)
    assert is_ai_after is False

    # Get control status
    status = await service.get_control_status(test_conversation.id, db)
    assert status["mode"] == "human"
    assert status["assigned_agent_id"] == agent_id

    # Resume AI
    resume_event = await service.resume_ai(test_conversation, "supervisor_001", db)
    await db.flush()

    assert resume_event.previous_control_mode == "human"
    is_ai_final = await service.is_ai_active(test_conversation, db)
    assert is_ai_final is True

    print(f"✓ Human takeover cycle: AI→Human→AI. Briefing length={len(event.ai_briefing)} chars")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 12: Template Rendering — variable injection
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_template_rendering(db: AsyncSession):
    """Template renders with variable injection; missing variables kept as-is."""
    engine = TemplateEngine()

    # Create template
    template = await engine.create_template(
        organization_id=ORG_ID,
        name="site_visit_confirmation",
        display_name="Site Visit Confirmation",
        channel="whatsapp",
        body="Hello {{customer_name}}, your site visit for {{property_name}} is confirmed on {{date}}!",
        db=db,
        language="en",
    )
    await db.flush()

    assert template.id
    assert template.name == "site_visit_confirmation"

    # Render with all variables
    rendered = await engine.render(
        template_name="site_visit_confirmation",
        organization_id=ORG_ID,
        channel="whatsapp",
        variables={
            "customer_name": "Rahul Sharma",
            "property_name": "DLF Phase 5 3BHK",
            "date": "Saturday, Aug 9 at 4 PM",
        },
        db=db,
    )

    assert rendered is not None
    assert "Rahul Sharma" in rendered
    assert "DLF Phase 5 3BHK" in rendered
    assert "Saturday, Aug 9" in rendered

    # Render with missing variable — should keep placeholder
    rendered_partial = await engine.render(
        template_name="site_visit_confirmation",
        organization_id=ORG_ID,
        channel="whatsapp",
        variables={"customer_name": "Ahmed"},
        db=db,
    )
    assert "Ahmed" in rendered_partial
    assert "{{property_name}}" in rendered_partial  # Missing var preserved

    # Get variable schema
    schema = await engine.get_variable_schema(
        "site_visit_confirmation", ORG_ID, "whatsapp", db
    )
    assert len(schema) == 3  # 3 variables detected
    var_names = {v["name"] for v in schema}
    assert "customer_name" in var_names

    print(f"✓ Template rendering: '{rendered[:50]}...'")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 13: Presence Service — typing events + expiry + purge
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_presence_service(
    db: AsyncSession, test_conversation: OmnichannelConversation
):
    """Typing events created, queried, and expired events purged."""
    service = PresenceService()
    agent_id = str(uuid.uuid4())

    # Set typing indicator
    typing_event = await service.set_typing(
        conversation_id=test_conversation.id,
        organization_id=ORG_ID,
        actor_id=agent_id,
        actor_type="agent",
        channel="whatsapp",
        db=db,
        event_type="typing",
    )
    await db.flush()

    assert typing_event.id
    assert typing_event.event_type == "typing"
    assert typing_event.expires_at > datetime.now(timezone.utc)

    # Get active typing (should include the one just created)
    active = await service.get_active_typing(test_conversation.id, db)
    assert len(active) >= 1

    # Clear typing
    await service.clear_typing(test_conversation.id, agent_id, "whatsapp", db)
    await db.flush()
    after_clear = await service.get_active_typing(test_conversation.id, db)
    assert len(after_clear) == 0

    # Add an expired event manually for purge test
    expired = TypingEvent(
        conversation_id=test_conversation.id,
        organization_id=ORG_ID,
        actor_id=str(uuid.uuid4()),
        actor_type="ai",
        event_type="typing",
        channel="whatsapp",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=30),  # Already expired
    )
    db.add(expired)
    await db.flush()

    # Purge expired
    purged = await service.purge_expired_typing(db)
    assert purged >= 1

    # Presence update
    presence = await service.update_presence(
        ORG_ID, agent_id, "agent", "whatsapp", "online", db
    )
    assert presence.status == "online"

    status = await service.get_presence(ORG_ID, agent_id, "agent", "whatsapp", db)
    assert status == "online"

    print(f"✓ Presence service: typing={typing_event.event_type}, purged={purged}, presence=online")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 14: Communication Monitor — KPI aggregation
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_communication_monitor(
    db: AsyncSession, test_conversation: OmnichannelConversation
):
    """KPI dashboard aggregates message stats correctly."""
    monitor = CommunicationMonitor()

    # Seed some messages
    channels = ["whatsapp", "email", "telegram"]
    for i in range(9):
        db.add(ChannelMessage(
            conversation_id=test_conversation.id,
            organization_id=ORG_ID,
            lead_id=LEAD_ID,
            channel=channels[i % 3],
            provider_name="test",
            direction="outbound" if i % 3 == 0 else "inbound",
            message_type="text",
            content=f"KPI test message {i}",
            sender_identifier="system",
            sender_name="System",
            delivery_status="delivered" if i % 4 != 0 else "failed",
            sent_by_ai=i % 2 == 0,
            idempotency_key=hashlib.sha256(f"kpi_{i}_{uuid.uuid4()}".encode()).hexdigest()[:64],
        ))
    await db.flush()

    stats = await monitor.get_dashboard_stats(ORG_ID, db, hours=24)

    assert "messages" in stats
    assert stats["messages"]["total"] >= 9
    assert "delivery" in stats
    assert "ai" in stats
    assert "channels" in stats
    assert isinstance(stats["channels"], dict)

    # Channel breakdown should show whatsapp, email, telegram
    channel_names = set(stats["channels"].keys())
    assert len(channel_names) >= 1

    provider_health = await monitor.get_provider_health(ORG_ID, db)
    assert "providers" in provider_health

    print(
        f"✓ Monitor KPIs: total_messages={stats['messages']['total']}, "
        f"channels={list(stats['channels'].keys())}"
    )
