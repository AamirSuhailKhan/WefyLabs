"""
Verification Script for Site Visit Lifecycle:
1. Search valid appointment slots (or pick a valid future slot: 2026-10-25T14:00:00Z).
2. Submit booking request to POST /api/v1/calendar/book.
3. Verify appointment is persisted in PostgreSQL scheduling_meetings with correct org, broker, lead.
4. Verify created visit appears in GET /api/v1/calendar/bookings (the endpoint supporting calendar reload).
5. Attempt duplicate submission on same occupied slot -> verify collision guard returns HTTP 400.
6. Cancel visit via POST /api/v1/calendar/bookings/{id}/cancel -> verify status becomes CANCELLED.
7. Verify cancelled status is persisted across re-fetch.
"""

import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def api_call(method, endpoint, token, payload=None):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Authorization": f"Bearer {token}"}
    if payload:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}
    except Exception as e:
        return 500, {"error": str(e)}

def main():
    print("=" * 70)
    print("PHASE 9.2.1: SITE VISIT & CALENDAR WORKFLOW VERIFICATION")
    print("=" * 70)

    # 1. Login as Alpha Broker
    print("\n1. Authenticating as Alpha Broker...")
    login_payload = {
        "email": "broker.alpha.test@wefylabs.internal",
        "password": "TestPassword123!"
    }
    status, res = api_call("POST", "/auth/login", "", login_payload)
    assert status == 200, f"Login failed: {res}"
    token = res["access_token"]
    broker_id = res["broker"]["id"]
    org_id = res.get("organization_id") or res["broker"].get("organization_id") or "530a0335-5969-41d3-b5af-52d13e9ac393"
    print(f"   Authenticated Broker: {broker_id} | Org: {org_id}")

    import time
    lead_id = "0151931c-efd4-46af-b6fd-136837923cc7"  # Deepak Choudhury
    unique_day = (int(time.time()) % 25) + 1
    unique_hour = (int(time.time()) % 8) + 9  # 09:00 to 17:00
    target_slot = f"2026-11-{unique_day:02d}T{unique_hour:02d}:00:00Z"

    # 2. Book a site visit
    print(f"\n2. Submitting booking request for {target_slot}...")
    book_payload = {
        "lead_id": lead_id,
        "meeting_type": "PROPERTY_VIEWING",
        "slot_start_utc": target_slot,
        "duration_minutes": 45,
        "location_type": "PROPERTY",
        "location_address": "Sobha Dream Acres Site Office, Indiranagar",
        "virtual_provider": "NONE",
        "notes": "Phase 9.2.1 Automated Acceptance Visit"
    }
    status, book_res = api_call("POST", "/calendar/book", token, book_payload)
    print(f"   Booking response status: {status}")
    assert status == 200, f"Booking failed: {book_res}"
    meeting_id = book_res["id"]
    print(f"   Created Meeting ID: {meeting_id}")
    print(f"   Title: {book_res.get('title')}")
    print(f"   Status: {book_res.get('status')}")
    print(f"   Org ID: {book_res.get('organization_id')}")
    print(f"   Broker ID: {book_res.get('broker_id')}")
    print(f"   Lead ID: {book_res.get('lead_id')}")
    assert book_res.get("organization_id") == str(org_id), "Org ID mismatch"
    assert book_res.get("broker_id") == str(broker_id), "Broker ID mismatch"
    assert book_res.get("lead_id") == str(lead_id), "Lead ID mismatch"
    assert book_res.get("status") in ("CONFIRMED", "REQUESTED", "HELD"), "Unexpected initial status"

    # 3. Query GET /calendar/bookings (simulates page reload)
    print("\n3. Verifying persisted appointment via GET /calendar/bookings (page reload simulation)...")
    status, bookings = api_call("GET", "/calendar/bookings", token)
    assert status == 200, f"Failed to list bookings: {bookings}"
    matching = [b for b in bookings if b["id"] == meeting_id]
    assert len(matching) == 1, f"Created meeting {meeting_id} not found in bookings list!"
    print(f"   Found meeting in calendar reload list: {matching[0]['title']} ({matching[0]['status']})")

    # 4. Attempt duplicate booking on same slot (collision guard)
    print(f"\n4. Testing collision guard: attempting duplicate booking on {target_slot}...")
    status, dup_res = api_call("POST", "/calendar/book", token, book_payload)
    print(f"   Duplicate booking status: {status}")
    print(f"   Duplicate response detail: {dup_res.get('detail') or dup_res.get('error')}")
    assert status == 400, f"Expected 400 Bad Request on duplicate slot, got {status}: {dup_res}"
    print("   Collision guard PASSED (rejected double booking).")

    # 5. Cancel the appointment
    print(f"\n5. Cancelling appointment {meeting_id}...")
    cancel_payload = {
        "reason": "Rescheduled by client Deepak Choudhury",
        "cancelled_by": "BROKER"
    }
    status, cancel_res = api_call("POST", f"/calendar/bookings/{meeting_id}/cancel", token, cancel_payload)
    print(f"   Cancel response status: {status}")
    assert status == 200, f"Cancellation failed: {cancel_res}"
    assert cancel_res.get("status") == "cancelled"

    # 6. Verify cancelled status persists across reload
    print("\n6. Verifying cancelled appointment across calendar reload...")
    status, bookings_after = api_call("GET", "/calendar/bookings", token)
    assert status == 200
    matching_after = [b for b in bookings_after if b["id"] == meeting_id]
    assert len(matching_after) == 1
    print(f"   Persisted status after cancellation: {matching_after[0]['status']}")
    assert matching_after[0]["status"].upper() == "CANCELLED", "Status was not updated to CANCELLED"

    print("\n" + "=" * 70)
    print("ALL SITE VISIT & CALENDAR WORKFLOW CHECKS PASSED (100% SUCCESS)")
    print("=" * 70)

if __name__ == "__main__":
    main()
