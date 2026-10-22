"""
Live Cross-Worker OAuth Verification Script
===========================================
Tests live communication between:
- Worker A: http://127.0.0.1:8000
- Worker B: http://127.0.0.1:8001
- Shared Redis: Upstash / settings.REDIS_URL
"""
import http.client
import json
import os
import sys
import time
import urllib.parse
import urllib.request
sys.path.insert(0, os.path.abspath("apps/api"))
import redis

from app.config import settings

def main():
    print("=" * 60)
    print("WEFYLABS MULTI-WORKER OAUTH LIVE VERIFICATION")
    print("=" * 60)

    # Connect to shared Redis
    r = redis.from_url(settings.REDIS_URL, socket_timeout=3.0, decode_responses=True)
    r.ping()
    print("[1] Redis connection verified: OK")

    # 1. Start OAuth on Worker A
    req_a = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/google/url")
    with urllib.request.urlopen(req_a) as resp:
        assert resp.status == 200
        set_cookie = resp.headers.get("Set-Cookie")
        body = json.loads(resp.read().decode())
        state = body["state"]
        auth_url = body["auth_url"]

    print(f"[2] Worker A (port 8000) issued state: {state[:12]}...")
    assert set_cookie is not None, "Worker A did not return Set-Cookie"
    print(f"[2] Worker A returned Set-Cookie: {set_cookie}")
    assert "wefylabs_oauth_sid=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()

    # Extract session_id from cookie
    cookie_part = [p for p in set_cookie.split(";") if "wefylabs_oauth_sid=" in p][0].strip()
    session_id = cookie_part.split("wefylabs_oauth_sid=")[1]
    print(f"[2] Extracted session_id: {session_id[:12]}...")

    # 2. Verify state is stored in shared Redis
    redis_key = f"oauth:state:{state}"
    redis_val = r.get(redis_key)
    print(f"[3] Looked up Redis key '{redis_key}' -> {redis_val[:12]}...")
    assert redis_val == session_id, f"Redis value {redis_val} did not match session_id {session_id}"
    ttl = r.ttl(redis_key)
    print(f"[3] Redis state TTL: {ttl}s (target: 600s)")
    assert 500 <= ttl <= 600, f"TTL out of expected range: {ttl}"

    # 3. Worker B receives callback with valid session cookie and state
    exchange_payload = json.dumps({
        "code": "4/0AeanS0_dummy_code_for_google_exchange",
        "state": state,
        "redirect_uri": "http://localhost:3000/auth/callback"
    }).encode("utf-8")

    req_b = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/auth/google/exchange",
        data=exchange_payload,
        headers={
            "Content-Type": "application/json",
            "Cookie": f"wefylabs_oauth_sid={session_id}",
        },
        method="POST"
    )

    try:
        urllib.request.urlopen(req_b)
        print("[4] Worker B exchange returned 200")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        print(f"[4] Worker B responded with HTTP {exc.code}: {err_body}")
        # Expected: state validation PASSED on Worker B, failed at Google token exchange (401/502)
        # It must NOT be a state mismatch error!
        assert "OAuth state does not belong to this session" not in err_body
        assert exc.code in (401, 502)
        print("[4] Verified: Worker B validated cross-worker state from Worker A and proceeded to provider exchange!")

    # 4. Verify atomic consumption in Redis
    assert r.get(redis_key) is None, "State key must be deleted from Redis after consumption"
    dead_val = r.get(f"oauth:statedead:{state}")
    assert dead_val is not None, "Dead state tombstone must exist in Redis"
    print("[5] Verified: State was atomically consumed and dead tombstone registered in Redis.")

    # 5. Replay attack on Worker A (state already used)
    req_replay = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/google/exchange",
        data=exchange_payload,
        headers={
            "Content-Type": "application/json",
            "Cookie": f"wefylabs_oauth_sid={session_id}",
        },
        method="POST"
    )
    try:
        urllib.request.urlopen(req_replay)
        raise AssertionError("Replayed state should have been rejected!")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        print(f"[6] Replay rejected by Worker A with HTTP {exc.code}: {err_body}")
        assert exc.code == 400
        assert "already been used" in err_body.lower() or "missing" in err_body.lower()
        print("[6] Verified: Replay protection rejected replayed state across workers!")

    # 6. Wrong session attack
    # Issue state for Session 1 on Worker A
    req_s1 = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/google/url")
    with urllib.request.urlopen(req_s1) as resp:
        state_s1 = json.loads(resp.read().decode())["state"]

    # Attempt to present state_s1 with Session 2 cookie on Worker B
    req_wrong_session = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/auth/google/exchange",
        data=json.dumps({"code": "some_code", "state": state_s1}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Cookie": "wefylabs_oauth_sid=different_attacker_session_cookie_12345678",
        },
        method="POST"
    )
    try:
        urllib.request.urlopen(req_wrong_session)
        raise AssertionError("Wrong session should have been rejected!")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        print(f"[7] Wrong session rejected by Worker B with HTTP {exc.code}: {err_body}")
        assert exc.code == 400
        assert "OAuth state does not belong to this session" in err_body
        print("[7] Verified: Cross-session state tampering rejected across workers!")

    # 7. Invalid state attack
    req_invalid_state = urllib.request.Request(
        "http://127.0.0.1:8001/api/v1/auth/google/exchange",
        data=json.dumps({"code": "some_code", "state": "totally_invalid_nonexistent_state"}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Cookie": f"wefylabs_oauth_sid={session_id}",
        },
        method="POST"
    )
    try:
        urllib.request.urlopen(req_invalid_state)
        raise AssertionError("Invalid state should have been rejected!")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        print(f"[8] Invalid state rejected by Worker B with HTTP {exc.code}: {err_body}")
        assert exc.code == 400
        assert "Missing, unknown, or invalid OAuth state" in err_body
        print("[8] Verified: Non-existent state rejected across workers!")

    print("=" * 60)
    print("ALL LIVE CROSS-WORKER OAUTH SECURITY TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    main()
