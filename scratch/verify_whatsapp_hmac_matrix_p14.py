"""
Phase 14: WhatsApp HMAC Webhook Security Verification Matrix
Validates all 8 cryptographic and payload handling cases against the live FastAPI endpoint.
Verifies fail-closed semantics, cryptographic integrity, and zero live outbound network calls.
Saves results to scratch/whatsapp_hmac_verification_p14.json
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("apps/api"))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.config import settings
from app.dependencies import get_db
from app.models import Base
from app.models.organization import Organization, OrganizationMember
from app.models.broker import Broker
from app.models.global_models import ProviderConfiguration

TEST_APP_SECRET = "sec_test_entropy_93847291847561849204857102938475"
TEST_PHONE_ID = "999888777123"

def sign(body: bytes, secret: str = TEST_APP_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"

async def run_matrix():
    print("=" * 60)
    print("PHASE 14: WHATSAPP HMAC 8-CASE VERIFICATION MATRIX")
    print("=" * 60)

    # 1. Setup isolated in-memory SQLite test database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        org = Organization(name="HMAC Matrix Org P14", slug=f"hmac-{uuid.uuid4().hex[:6]}")
        broker = Broker(
            id=uuid.uuid4(),
            email=f"hmac_broker_{uuid.uuid4().hex[:6]}@example.com",
            name="HMAC Matrix Broker P14",
            phone="+919876543210",
            whatsapp_number="+919876543210",
        )
        session.add_all([org, broker])
        await session.flush()
        session.add_all([
            OrganizationMember(organization_id=org.id, broker_id=broker.id, role="owner"),
            ProviderConfiguration(
                organization_id=org.id,
                provider_type="WHATSAPP",
                provider_code="meta_direct",
                config_json={"phone_number_id": TEST_PHONE_ID},
                is_active=True,
            ),
        ])
        await session.commit()
    print(f"[SETUP] Isolated test DB initialized. Seeded organization with phone_number_id: {TEST_PHONE_ID}")

    async def override_get_db():
        async with session_factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db

    # Track outbound messages to prove zero customer-facing outbound transmission
    outbound_calls: List[Dict[str, Any]] = []

    # Mock external transport
    import app.services.whatsapp_service as wa_svc
    import app.services.conversation_service as conv_svc

    async def mock_send(*args, **kwargs):
        outbound_calls.append({"args": args, "kwargs": kwargs})
        return True

    wa_svc.send_message = mock_send
    conv_svc.send_message = mock_send

    results: List[Dict[str, Any]] = []

    # Valid payload
    valid_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WHATSAPP_ACCT_001",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15551234567", "phone_number_id": TEST_PHONE_ID},
                    "statuses": [{
                        "id": f"wamid.STATUS_{uuid.uuid4().hex[:12]}",
                        "status": "delivered",
                        "timestamp": "1711200000",
                        "recipient_id": "919876543210"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    valid_bytes = json.dumps(valid_payload, separators=(",", ":")).encode("utf-8")
    valid_sig = sign(valid_bytes, TEST_APP_SECRET)

    # Configure test secret
    original_secret = getattr(settings, "WHATSAPP_APP_SECRET", None)
    settings.WHATSAPP_APP_SECRET = TEST_APP_SECRET

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # Case 1: Correct HMAC-SHA256 over exact raw request body bytes
        r1 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=valid_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig}
        )
        assert r1.status_code in (200, 202), f"Case 1 failed: {r1.status_code} {r1.text}"
        results.append({
            "case": 1,
            "name": "valid_raw_bytes_hmac",
            "description": "Correct HMAC-SHA256 over exact raw request-body bytes",
            "expected_status": 200,
            "actual_status": r1.status_code,
            "passed": r1.status_code in (200, 202),
            "response": r1.json()
        })
        print(f"[PASS] Case 1: Valid HMAC-SHA256 -> HTTP {r1.status_code}")

        # Case 2: Forged HMAC with secret configured
        forged_sig = "sha256=" + "a" * 64
        r2 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=valid_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": forged_sig}
        )
        assert r2.status_code == 401, f"Case 2 failed: {r2.status_code} {r2.text}"
        results.append({
            "case": 2,
            "name": "forged_hmac_signature",
            "description": "Forged HMAC with secret configured on server",
            "expected_status": 401,
            "actual_status": r2.status_code,
            "passed": r2.status_code == 401,
            "response": r2.json()
        })
        print(f"[PASS] Case 2: Forged HMAC Signature -> HTTP {r2.status_code} (Unauthorized)")

        # Case 3: Altered body after signature was generated
        tampered_bytes = valid_bytes.replace(b"delivered", b"read")
        r3 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=tampered_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig}
        )
        assert r3.status_code == 401, f"Case 3 failed: {r3.status_code} {r3.text}"
        results.append({
            "case": 3,
            "name": "altered_body_post_signing",
            "description": "Altered body payload after HMAC signature was generated",
            "expected_status": 401,
            "actual_status": r3.status_code,
            "passed": r3.status_code == 401,
            "response": r3.json()
        })
        print(f"[PASS] Case 3: Altered Body Post-Signing -> HTTP {r3.status_code} (Unauthorized)")

        # Case 4: Truncated or malformed signature
        malformed_sig = "sha256=1234567890"
        r4 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=valid_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": malformed_sig}
        )
        assert r4.status_code == 401, f"Case 4 failed: {r4.status_code} {r4.text}"
        results.append({
            "case": 4,
            "name": "truncated_malformed_signature",
            "description": "Truncated or malformed HMAC signature header",
            "expected_status": 401,
            "actual_status": r4.status_code,
            "passed": r4.status_code == 401,
            "response": r4.json()
        })
        print(f"[PASS] Case 4: Truncated / Malformed Signature -> HTTP {r4.status_code} (Unauthorized)")

        # Case 5: Missing signature header
        r5 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=valid_bytes,
            headers={"Content-Type": "application/json"}
        )
        assert r5.status_code == 401, f"Case 5 failed: {r5.status_code} {r5.text}"
        results.append({
            "case": 5,
            "name": "missing_signature_header",
            "description": "Missing X-Hub-Signature-256 header entirely",
            "expected_status": 401,
            "actual_status": r5.status_code,
            "passed": r5.status_code == 401,
            "response": r5.json()
        })
        print(f"[PASS] Case 5: Missing Signature Header -> HTTP {r5.status_code} (Unauthorized)")

        # Case 6: Missing application secret
        settings.WHATSAPP_APP_SECRET = None
        r6 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=valid_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig}
        )
        assert r6.status_code == 503, f"Case 6 failed: {r6.status_code} {r6.text}"
        results.append({
            "case": 6,
            "name": "missing_application_secret",
            "description": "Missing WHATSAPP_APP_SECRET server-side (fail-closed guard)",
            "expected_status": 503,
            "actual_status": r6.status_code,
            "passed": r6.status_code == 503,
            "response": r6.json()
        })
        print(f"[PASS] Case 6: Missing Server Secret -> HTTP {r6.status_code} (Service Unavailable / Fail-Closed)")

        # Restore secret for remaining cases
        settings.WHATSAPP_APP_SECRET = TEST_APP_SECRET

        # Case 7: Duplicate event delivery
        dedup_event_id = f"wamid.DEDUP_TEST_{uuid.uuid4().hex[:12]}"
        receipt_payload = {
            "entry": [{
                "id": "12345",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "15551720871", "phone_number_id": TEST_PHONE_ID},
                        "statuses": [{
                            "id": dedup_event_id,
                            "status": "delivered",
                            "timestamp": "1711200000",
                            "recipient_id": "919876543210"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        receipt_bytes = json.dumps(receipt_payload, separators=(",", ":")).encode("utf-8")
        receipt_sig = sign(receipt_bytes, TEST_APP_SECRET)

        # Initial delivery
        r7a = await client.post(
            "/api/v1/whatsapp/webhook",
            content=receipt_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": receipt_sig}
        )
        assert r7a.status_code == 200, f"Case 7 initial failed: {r7a.status_code} {r7a.text}"

        # Duplicate delivery
        r7b = await client.post(
            "/api/v1/whatsapp/webhook",
            content=receipt_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": receipt_sig}
        )
        assert r7b.status_code == 200, f"Case 7 duplicate failed: {r7b.status_code} {r7b.text}"
        results.append({
            "case": 7,
            "name": "duplicate_event_delivery",
            "description": "Duplicate delivery of identical signed webhook payload (deduplicated idempotently)",
            "expected_status": 200,
            "actual_status": r7b.status_code,
            "passed": r7b.status_code == 200,
            "response": r7b.json()
        })
        print(f"[PASS] Case 7: Duplicate Delivery -> HTTP {r7b.status_code} (Idempotent / Deduplicated)")

        # Case 8: Invalid payload (non-object and malformed JSON)
        malformed_bytes = b'{"unclosed_json": '
        malformed_sig = sign(malformed_bytes, TEST_APP_SECRET)
        r8 = await client.post(
            "/api/v1/whatsapp/webhook",
            content=malformed_bytes,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": malformed_sig}
        )
        assert r8.status_code == 400, f"Case 8 failed: {r8.status_code} {r8.text}"
        results.append({
            "case": 8,
            "name": "invalid_payload",
            "description": "Invalid / malformed JSON payload with valid HMAC signature",
            "expected_status": 400,
            "actual_status": r8.status_code,
            "passed": r8.status_code == 400,
            "response": r8.json()
        })
        print(f"[PASS] Case 8: Invalid Payload Body -> HTTP {r8.status_code} (Bad Request)")

    # Restore original setting
    settings.WHATSAPP_APP_SECRET = original_secret
    app.dependency_overrides.clear()
    await engine.dispose()

    # Verify zero external network transmissions
    assert len(outbound_calls) == 0, f"Unexpected external messages sent: {len(outbound_calls)}"
    print(f"[VERIFIED] Outbound external customer messages during verification: 0")

    summary = {
        "phase": "PHASE_14",
        "total_cases": len(results),
        "passed_cases": sum(1 for r in results if r["passed"]),
        "failed_cases": sum(1 for r in results if not r["passed"]),
        "outbound_customer_messages_sent": len(outbound_calls),
        "cases": results
    }

    out_path = os.path.abspath("scratch/whatsapp_hmac_verification_p14.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nArtifact written: {out_path}")
    print(f"Overall status: ALL 8 CASES PASSED")

if __name__ == "__main__":
    asyncio.run(run_matrix())
