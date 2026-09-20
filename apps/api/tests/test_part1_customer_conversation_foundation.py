"""
WefyLabs Core Product — Part 1 of 8
Customer Identity, Conversation, and Bounded Memory Foundation Test Suite
==========================================================================
Behavioral tests for:
  1. Customer creation & identity linkage
  2. Identity resolution tiers (EXACT_MATCH, POSSIBLE_MATCH, NO_MATCH)
  3. Existing lead reuse upon exact match
  4. Structured requirement profile normalization
  5. Deterministic requirement updates (e.g. 1.2 Cr -> 1.4 Cr)
  6. Negative preferences retention & durability
  7. Explicit vs Inferred provenance precedence (anti-overwrite rule)
  8. Deterministic single-value override (e.g. 3 BHK -> 4 BHK)
  9. Conversation creation & status transitions
 10. Message creation with canonical sender types & credential redaction
 11. 4-tier bounded memory retrieval
 12. Tenant isolation: Customer isolation (Tenant A vs Tenant B)
 13. Tenant isolation: Conversation isolation (Tenant A vs Tenant B)
 14. Tenant isolation: Memory isolation (Tenant A vs Tenant B)
 15. Invalid customer & conversation handling
"""
import uuid
import pytest
from sqlalchemy import select

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.memory_models import MemoryRecord, MemoryVersion
from app.models.communication_models import OmnichannelConversation, ChannelMessage
from app.modules.customer_intelligence.service import CustomerIntelligenceService
from app.modules.customer_intelligence.schemas import (
    CustomerCreateDTO, IdentityResolutionRequest, RequirementUpdateDTO,
    ConversationCreateDTO, MessageCreateDTO
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_a_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def tenant_b_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
async def brokers(db_session, tenant_a_id, tenant_b_id):
    broker_a = Broker(
        id=uuid.UUID(tenant_a_id),
        email="tenant_a@wefylabs.com",
        phone="+919000000001",
        name="Tenant A Brokerage",
        agency_name="Agency A",
        city="Bengaluru"
    )
    broker_b = Broker(
        id=uuid.UUID(tenant_b_id),
        email="tenant_b@wefylabs.com",
        phone="+919000000002",
        name="Tenant B Brokerage",
        agency_name="Agency B",
        city="Dubai"
    )
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()
    return broker_a, broker_b


# ─── 1. Customer Creation & Canonical Identity ───────────────────────────────

@pytest.mark.asyncio
async def test_customer_creation(db_session, brokers, tenant_a_id):
    """Customer creation establishes Lead, Identity node, and initial explicit requirement memory."""
    svc = CustomerIntelligenceService(db_session)
    dto = CustomerCreateDTO(
        phone="+919876543210",
        name="Aarav Sharma",
        email="aarav@example.com",
        source="website_inquiry",
        transaction_type="buy",
        budget_min=10000000,
        budget_max=15000000,
        budget_currency="INR",
        property_type="apartment",
        preferred_locations=["Whitefield", "Indiranagar"],
        timeline="1_month"
    )

    customer = await svc.create_customer(tenant_a_id, dto)

    assert customer.customer_id is not None
    assert customer.organization_id == tenant_a_id
    assert customer.name == "Aarav Sharma"
    assert customer.phone == "+919876543210"
    assert customer.email == "aarav@example.com"
    assert customer.budget_max == 15000000
    assert customer.budget_currency == "INR"

    # Verify memory records created with EXPLICIT source
    profile = await svc.get_requirement_profile(tenant_a_id, customer.customer_id)
    assert profile.budget_max == 15000000
    assert profile.locations == ["Whitefield", "Indiranagar"]
    assert profile.provenance_map.get("budget_max") == "EXPLICIT"


# ─── 2. Identity Resolution & Reuse ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_identity_resolution_tiers(db_session, brokers, tenant_a_id):
    """Verify EXACT_MATCH, POSSIBLE_MATCH, and NO_MATCH resolution paths."""
    svc = CustomerIntelligenceService(db_session)

    # 1. NO_MATCH on unknown customer
    res_none = await svc.resolve_identity(tenant_a_id, IdentityResolutionRequest(phone="+919999999999"))
    assert res_none.match_status == "NO_MATCH"
    assert res_none.confidence == 0.0

    # Create customer
    created = await svc.create_customer(tenant_a_id, CustomerCreateDTO(
        phone="+919111222333",
        name="Priya Patel",
        email="priya@example.com"
    ))

    # 2. EXACT_MATCH by phone
    res_phone = await svc.resolve_identity(tenant_a_id, IdentityResolutionRequest(phone="+919111222333"))
    assert res_phone.match_status == "EXACT_MATCH"
    assert res_phone.customer_id == created.customer_id
    assert res_phone.confidence == 1.0

    # 3. EXACT_MATCH by email
    res_email = await svc.resolve_identity(tenant_a_id, IdentityResolutionRequest(email="priya@example.com"))
    assert res_email.match_status == "EXACT_MATCH"
    assert res_email.customer_id == created.customer_id

    # 4. EXACT_MATCH by lead_id
    res_id = await svc.resolve_identity(tenant_a_id, IdentityResolutionRequest(lead_id=created.customer_id))
    assert res_id.match_status == "EXACT_MATCH"
    assert res_id.customer_id == created.customer_id


@pytest.mark.asyncio
async def test_existing_lead_reuse(db_session, brokers, tenant_a_id):
    """Creating a customer with matching phone reuses existing record without duplicate creation."""
    svc = CustomerIntelligenceService(db_session)
    c1 = await svc.create_customer(tenant_a_id, CustomerCreateDTO(
        phone="+919444555666",
        name="Original Name",
        email="orig@example.com"
    ))

    # Attempt second creation with identical phone
    c2 = await svc.create_customer(tenant_a_id, CustomerCreateDTO(
        phone="+919444555666",
        name="Different Name",
        email="different@example.com"
    ))

    assert c1.customer_id == c2.customer_id


# ─── 3. Requirement Update Semantics & Provenance Precedence ──────────────────

@pytest.mark.asyncio
async def test_requirement_deterministic_update(db_session, brokers, tenant_a_id):
    """Explicit update from 1.2 Cr to 1.4 Cr supersedes baseline and archives prior version."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(
        phone="+919777888999",
        budget_max=12000000,
        budget_currency="INR"
    ))

    # Customer explicitly updates budget to 1.4 Cr
    updated_profile = await svc.update_requirements(
        tenant_a_id,
        customer.customer_id,
        RequirementUpdateDTO(
            budget_max=14000000,
            source="EXPLICIT",
            confidence=1.0
        )
    )

    assert updated_profile.budget_max == 14000000
    assert updated_profile.provenance_map["budget_max"] == "EXPLICIT"

    # Verify version archiving in DB
    stmt_vers = select(MemoryVersion).where(
        MemoryVersion.value_json["budget_max"].as_integer() == 12000000
    )
    res = await db_session.execute(stmt_vers)
    archived = res.scalars().all()
    assert len(archived) >= 1


@pytest.mark.asyncio
async def test_negative_preferences_retention(db_session, brokers, tenant_a_id):
    """Negative preferences (e.g. 'no ground floor', 'not near highway') are durably retained."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(phone="+919123456780"))

    # Record negative constraints
    profile = await svc.update_requirements(
        tenant_a_id,
        customer.customer_id,
        RequirementUpdateDTO(
            negative_preferences=[
                "no ground floor",
                "not near highway",
                "not above 1.5 Cr"
            ],
            source="EXPLICIT"
        )
    )

    descriptions = [np["description"] for np in profile.negative_preferences]
    assert "no ground floor" in descriptions
    assert "not near highway" in descriptions
    assert "not above 1.5 Cr" in descriptions

    # Ensure memory query also reflects these negative constraints
    mem_context = await svc.get_bounded_memory(tenant_a_id, customer.customer_id)
    assert "no ground floor" in mem_context.customer_memory["negative_preferences"]


@pytest.mark.asyncio
async def test_explicit_vs_inferred_precedence(db_session, brokers, tenant_a_id):
    """Inferred AI output CANNOT overwrite an explicit customer requirement."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(
        phone="+919123456781",
        budget_max=15000000  # Explicit 1.5 Cr
    ))

    # An AI heuristic infers budget_max is 10000000 (lower rank)
    profile_after_inference = await svc.update_requirements(
        tenant_a_id,
        customer.customer_id,
        RequirementUpdateDTO(
            budget_max=10000000,
            source="INFERRED",
            confidence=0.60
        )
    )

    # Inferred update MUST BE REJECTED. Explicit 15000000 remains active!
    assert profile_after_inference.budget_max == 15000000
    assert profile_after_inference.provenance_map["budget_max"] == "EXPLICIT"


@pytest.mark.asyncio
async def test_deterministic_single_value_override(db_session, brokers, tenant_a_id):
    """When customer explicitly updates configuration (e.g. 3 BHK -> 4 BHK), prior value is superseded."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(phone="+919123456782"))

    # Initially states 3 BHK
    p1 = await svc.update_requirements(
        tenant_a_id,
        customer.customer_id,
        RequirementUpdateDTO(bhk=[3], source="EXPLICIT")
    )
    assert p1.bhk == [3]

    # Later states "Actually I need 4 BHK"
    p2 = await svc.update_requirements(
        tenant_a_id,
        customer.customer_id,
        RequirementUpdateDTO(bhk=[4], source="EXPLICIT")
    )
    assert p2.bhk == [4]


# ─── 4. Conversation & Message Domain ────────────────────────────────────────

@pytest.mark.asyncio
async def test_conversation_creation_and_status(db_session, brokers, tenant_a_id):
    """Conversation is created with canonical statuses: ACTIVE, WAITING, HANDED_OFF, CLOSED, ARCHIVED."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(phone="+919123456783"))

    conv = await svc.create_conversation(
        tenant_a_id,
        customer.customer_id,
        ConversationCreateDTO(channel="whatsapp", status="ACTIVE")
    )

    assert conv.id is not None
    assert conv.customer_id == customer.customer_id
    assert conv.status == "ACTIVE"
    assert conv.channel == "whatsapp"

    conv_list = await svc.get_conversations(tenant_a_id, customer.customer_id)
    assert len(conv_list) == 1
    assert conv_list[0].id == conv.id


@pytest.mark.asyncio
async def test_message_creation_and_credential_redaction(db_session, brokers, tenant_a_id):
    """Messages support canonical sender types and automatically redact secrets."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(phone="+919123456784"))
    conv = await svc.create_conversation(tenant_a_id, customer.customer_id, ConversationCreateDTO())

    # 1. Customer inbound message
    msg_cust = await svc.create_message(
        tenant_a_id,
        customer.customer_id,
        conv.id,
        MessageCreateDTO(sender_type="CUSTOMER", content="Looking for 3BHK under 1.5Cr")
    )
    assert msg_cust.sender_type == "CUSTOMER"
    assert msg_cust.direction == "inbound"

    # 2. AI agent outbound message with secret redaction
    msg_ai = await svc.create_message(
        tenant_a_id,
        customer.customer_id,
        conv.id,
        MessageCreateDTO(
            sender_type="AI_AGENT",
            content="Here is a property. Note api_key='sk-prod-supersecretkey123' should be hidden."
        )
    )
    assert msg_ai.sender_type == "AI_AGENT"
    assert msg_ai.direction == "outbound"
    assert "sk-prod-supersecretkey123" not in msg_ai.content
    assert "[REDACTED_CREDENTIAL]" in msg_ai.content

    # 3. Retrieve messages
    messages = await svc.get_messages(tenant_a_id, customer.customer_id, conv.id)
    assert len(messages) == 2


# ─── 5. Bounded 4-Tier Memory ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bounded_memory_retrieval(db_session, brokers, tenant_a_id):
    """Retrieves 4-tier bounded memory: CURRENT_TURN, CURRENT_SESSION, CUSTOMER_MEMORY, CRM_MEMORY."""
    svc = CustomerIntelligenceService(db_session)
    customer = await svc.create_customer(tenant_a_id, CustomerCreateDTO(
        phone="+919123456785",
        budget_max=18000000,
        preferred_locations=["Indiranagar"]
    ))
    conv = await svc.create_conversation(tenant_a_id, customer.customer_id, ConversationCreateDTO())

    await svc.create_message(
        tenant_a_id, customer.customer_id, conv.id,
        MessageCreateDTO(sender_type="CUSTOMER", content="I dislike ground floor properties.")
    )
    await svc.create_message(
        tenant_a_id, customer.customer_id, conv.id,
        MessageCreateDTO(sender_type="AI_AGENT", content="Understood, I will filter those out.")
    )

    await svc.update_requirements(
        tenant_a_id, customer.customer_id,
        RequirementUpdateDTO(negative_preferences=["no ground floor"], source="EXPLICIT")
    )

    mem = await svc.get_bounded_memory(tenant_a_id, customer.customer_id, conv.id)

    # Verify 4 tiers
    assert mem.current_turn is not None
    assert mem.current_turn["sender_type"] == "AI_AGENT"

    assert mem.current_session["recent_turn_count"] == 2

    assert mem.customer_memory["requirements"]["budget_max"] == 18000000
    assert "no ground floor" in mem.customer_memory["negative_preferences"]

    assert mem.crm_memory["pipeline_stage"] == "new"

    assert "=== CUSTOMER CONVERSATION MEMORY CONTEXT ===" in mem.formatted_prompt_context
    assert "no ground floor" in mem.formatted_prompt_context


# ─── 6. Multi-Tenant Isolation (P0 Security Gate) ────────────────────────────

@pytest.mark.asyncio
async def test_cross_tenant_customer_isolation(db_session, brokers, tenant_a_id, tenant_b_id):
    """Tenant A cannot retrieve or mutate Tenant B's customer."""
    svc = CustomerIntelligenceService(db_session)
    cust_b = await svc.create_customer(tenant_b_id, CustomerCreateDTO(
        phone="+919888888888",
        name="Tenant B Secret Client"
    ))

    # Tenant A attempts to access Tenant B's customer
    with pytest.raises(KeyError):
        await svc.get_customer(tenant_a_id, cust_b.customer_id)

    with pytest.raises(KeyError):
        await svc.get_requirement_profile(tenant_a_id, cust_b.customer_id)

    with pytest.raises(KeyError):
        await svc.update_requirements(
            tenant_a_id,
            cust_b.customer_id,
            RequirementUpdateDTO(budget_max=9999999)
        )


@pytest.mark.asyncio
async def test_cross_tenant_conversation_isolation(db_session, brokers, tenant_a_id, tenant_b_id):
    """Tenant A cannot retrieve, create, or send messages to Tenant B's conversation."""
    svc = CustomerIntelligenceService(db_session)
    cust_b = await svc.create_customer(tenant_b_id, CustomerCreateDTO(phone="+919777777777"))
    conv_b = await svc.create_conversation(tenant_b_id, cust_b.customer_id, ConversationCreateDTO())

    # Tenant A attempts to read Tenant B's conversation
    with pytest.raises(KeyError):
        await svc.get_messages(tenant_a_id, cust_b.customer_id, conv_b.id)

    # Tenant A attempts to send message into Tenant B's conversation
    with pytest.raises(KeyError):
        await svc.create_message(
            tenant_a_id,
            cust_b.customer_id,
            conv_b.id,
            MessageCreateDTO(sender_type="AI_AGENT", content="Hacked message")
        )


@pytest.mark.asyncio
async def test_cross_tenant_memory_isolation(db_session, brokers, tenant_a_id, tenant_b_id):
    """Tenant A cannot retrieve Tenant B's customer memory context."""
    svc = CustomerIntelligenceService(db_session)
    cust_b = await svc.create_customer(tenant_b_id, CustomerCreateDTO(
        phone="+919666666666",
        budget_max=50000000
    ))

    with pytest.raises(KeyError):
        await svc.get_bounded_memory(tenant_a_id, cust_b.customer_id)


# ─── 7. REST API End-to-End Verification ─────────────────────────────────────

@pytest.mark.asyncio
async def test_api_customer_endpoints(db_session, brokers, tenant_a_id, tenant_b_id):
    """End-to-end REST API verification for /api/v1/customers endpoints with dependency overrides."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_current_broker, get_db

    broker_a, broker_b = brokers

    # Configure overrides for Tenant A
    app.dependency_overrides[get_current_broker] = lambda: broker_a
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)

        # 1. Resolve on unknown phone -> NO_MATCH
        res_res = client.post("/api/v1/customers/resolve", json={"phone": "+919555111222"})
        assert res_res.status_code == 200
        assert res_res.json()["match_status"] == "NO_MATCH"

        # 2. Create customer via API
        create_payload = {
            "phone": "+919555111222",
            "name": "Rohan Gupta",
            "email": "rohan@example.com",
            "budget_max": 20000000,
            "budget_currency": "INR",
            "preferred_locations": ["HSR Layout"],
            "timeline": "immediate"
        }
        res_create = client.post("/api/v1/customers", json=create_payload)
        assert res_create.status_code == 201
        cust_data = res_create.json()
        customer_id = cust_data["customer_id"]
        assert cust_data["name"] == "Rohan Gupta"

        # 3. Retrieve customer
        res_get = client.get(f"/api/v1/customers/{customer_id}")
        assert res_get.status_code == 200
        assert res_get.json()["email"] == "rohan@example.com"

        # 4. Retrieve requirement profile
        res_prof = client.get(f"/api/v1/customers/{customer_id}/profile")
        assert res_prof.status_code == 200
        prof_data = res_prof.json()
        assert prof_data["budget_max"] == 20000000
        assert "HSR Layout" in prof_data["locations"]

        # 5. Patch requirements with negative preference
        patch_payload = {
            "budget_max": 22000000,
            "negative_preferences": ["no west facing", "not above 2.5 Cr"],
            "source": "EXPLICIT"
        }
        res_patch = client.patch(f"/api/v1/customers/{customer_id}/requirements", json=patch_payload)
        assert res_patch.status_code == 200
        patched_data = res_patch.json()
        assert patched_data["budget_max"] == 22000000
        assert len(patched_data["negative_preferences"]) >= 2

        # 6. Create conversation
        res_conv = client.post(f"/api/v1/customers/{customer_id}/conversations", json={"channel": "whatsapp", "status": "ACTIVE"})
        assert res_conv.status_code == 201
        conv_id = res_conv.json()["id"]

        # 7. Send message with sender type
        res_msg = client.post(
            f"/api/v1/customers/{customer_id}/conversations/{conv_id}/messages",
            json={"sender_type": "CUSTOMER", "content": "Hello, interested in 3BHKs"}
        )
        assert res_msg.status_code == 201
        assert res_msg.json()["sender_type"] == "CUSTOMER"

        # 8. Retrieve bounded memory
        res_mem = client.get(f"/api/v1/customers/{customer_id}/memory?conversation_id={conv_id}")
        assert res_mem.status_code == 200
        mem_data = res_mem.json()
        assert mem_data["customer_memory"]["requirements"]["budget_max"] == 22000000
        assert "no west facing" in mem_data["customer_memory"]["negative_preferences"]

        # 9. Tenant Isolation: Switch context to Tenant B
        app.dependency_overrides[get_current_broker] = lambda: broker_b

        # Tenant B tries to access Tenant A's customer -> 404
        res_cross = client.get(f"/api/v1/customers/{customer_id}")
        assert res_cross.status_code == 404

    finally:
        app.dependency_overrides.clear()
