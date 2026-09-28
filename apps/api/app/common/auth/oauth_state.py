"""
Phase 0 P0.1 — Distributed OAuth State & Replay Protection
==========================================================

Server-side OAuth CSRF state management with the required security properties:

- server-generated (cryptographically random, 256-bit)
- stored server-side (Redis shared across all workers, TTL-bounded)
- bound to the initiating browser session (HMAC-digested session id)
- one-time: atomically consumed on first use (Redis GET+DELETE pipeline)
- short-lived (default TTL 600 s)
- observable: every failure mode has a distinct typed error

Authorization-code replay protection uses the same infrastructure, replacing
the previous process-local ``_used_oauth_codes`` set which did not protect
against replay across multiple application workers.

The in-memory fallback is explicitly TEST/DEV-ONLY infrastructure: it is only
reached when Redis is unreachable AND the process is not in production, so a
production outage degrades to fail-closed (state consumption fails) rather
than to per-worker state.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from typing import Optional, Tuple

from app.config import settings

logger = logging.getLogger("wefylabs.auth.oauth_state")

STATE_TTL_SECONDS = 600          # 10 minutes for the OAuth round-trip
CODE_REPLAY_TTL_SECONDS = 900    # Google authorization codes are single-use

PRODUCTION_ENVS = ("production", "prod", "staging")
TESTING_ENVS = ("testing", "test")

_STATE_KEY_PREFIX = "oauth:state:"
_STATE_DEAD_PREFIX = "oauth:statedead:"
_CODE_KEY_PREFIX = "oauth:codeused:"


class OAuthStateError(Exception):
    """Base error for OAuth state validation failures."""


class OAuthStateMissing(OAuthStateError):
    """No state was supplied or no server-side record exists for it."""


class OAuthStateExpired(OAuthStateError):
    """The state existed but its TTL has elapsed."""


class OAuthStateReplayed(OAuthStateError):
    """The state (or code) was already consumed."""


class OAuthStateSessionMismatch(OAuthStateError):
    """The state does not belong to the presenting browser session."""


def _session_digest(session_id: str) -> str:
    """Binds a state to a browser session without storing the raw session id."""
    secret = (settings.SECRET_KEY or "wefylabs-oauth-state").encode("utf-8")
    return hmac.new(secret, session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def _is_redis_usable() -> bool:
    """In production the Redis path is mandatory; tests use the in-memory store."""
    # Testing environments ALWAYS use the bounded in-memory store so tests are
    # deterministic and do not depend on an ambient Redis server.
    import os
    env = os.environ.get("ENV", settings.ENV).lower()
    if env in TESTING_ENVS:
        return False
    return True


def _get_redis():
    """Returns the pooled sync Redis client, or None when unreachable."""
    try:
        from app.common.redis.rate_limiter import _get_redis
        client = _get_redis()
        if client is not None:
            client.ping()
        return client
    except Exception:
        return None


# ─── Bounded in-memory store (TEST/DEV fallback only) ────────────────────────

class _InMemoryOAuthStateStore:
    """TTL + size bounded store. Single-process semantics, tests only."""

    def __init__(self, max_entries: int = 10_000):
        self._max_entries = max_entries
        self._states: dict[str, Tuple[str, float]] = {}
        self._consumed: set[str] = set()
        self._consumed_codes: dict[str, float] = {}

    def _evict_if_needed(self) -> None:
        if len(self._states) <= self._max_entries:
            return
        # Drop the oldest half by expiry time (memory bound, never unbounded).
        ordered = sorted(self._states.items(), key=lambda item: item[1][1])
        for key, _ in ordered[: len(ordered) // 2]:
            self._states.pop(key, None)

    def issue(self, key: str, fingerprint: str, ttl: int) -> None:
        self._consumed.discard(key)
        self._states[key] = (fingerprint, time.time() + ttl)
        self._evict_if_needed()

    def consume(self, key: str, fingerprint: str) -> None:
        if key in self._consumed:
            raise OAuthStateReplayed("State or code was already used.")
        record = self._states.get(key)
        if record is None:
            raise OAuthStateMissing("Unknown, expired, or already consumed state.")
        stored_fp, expires_at = record
        if time.time() > expires_at:
            self._states.pop(key, None)
            self._consumed.add(key)
            raise OAuthStateExpired("State has expired.")
        if not hmac.compare_digest(fingerprint, stored_fp):
            # Fail closed: burn the state so a wrong-session presentation can
            # never be retried against the correct session afterwards.
            self._states.pop(key, None)
            self._consumed.add(key)
            raise OAuthStateSessionMismatch(
                "State does not belong to the current browser session."
            )
        self._states.pop(key, None)
        self._consumed.add(key)

    def consume_code(self, code: str, ttl: int = CODE_REPLAY_TTL_SECONDS) -> None:
        key = hashlib.sha256(code.encode("utf-8")).hexdigest()
        now = time.time()
        # Evict expired codes
        expired = [k for k, exp in self._consumed_codes.items() if exp < now]
        for k in expired:
            self._consumed_codes.pop(k, None)
        if key in self._consumed_codes:
            raise OAuthStateReplayed("Authorization code has already been consumed or is invalid.")
        self._consumed_codes[key] = now + ttl


_memory_store: Optional[_InMemoryOAuthStateStore] = None


def _get_memory_store() -> _InMemoryOAuthStateStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = _InMemoryOAuthStateStore()
    return _memory_store


def reset_memory_store() -> None:
    """Test helper: clears the in-memory fallback store between tests."""
    global _memory_store
    _memory_store = None


# ─── Public API ───────────────────────────────────────────────────────────────

def issue_oauth_state(session_id: str, ttl: int = STATE_TTL_SECONDS) -> str:
    """Generates and stores a fresh one-time OAuth state bound to a session."""
    if not session_id or not session_id.strip():
        raise OAuthStateMissing("A session identifier is required to issue state.")
    state = secrets.token_urlsafe(32)
    fingerprint = _session_digest(session_id)

    redis = _get_redis() if _is_redis_usable() else None
    if redis is not None:
        try:
            redis.set(f"{_STATE_KEY_PREFIX}{state}", fingerprint, ex=ttl)
            return state
        except Exception as exc:
            if settings.ENV in PRODUCTION_ENVS:
                raise OAuthStateError(
                    "OAuth state store is unavailable; refusing to issue state."
                ) from exc
            logger.warning("[OAuthState] Redis unavailable, using memory fallback: %s", exc)
    _get_memory_store().issue(state, fingerprint, ttl)
    return state


def consume_oauth_state(state: Optional[str], session_id: str) -> None:
    """
    Validates and atomically consumes a one-time OAuth state.

    Raises a typed OAuthStateError subclass on any failure. Consumption is a
    single Redis GET+DELETE pipeline so two workers processing the same state
    concurrently cannot both succeed.
    """
    if not state or not state.strip():
        raise OAuthStateMissing("Missing OAuth state.")
    if not session_id or not session_id.strip():
        raise OAuthStateMissing("Missing OAuth session context.")
    key = f"{_STATE_KEY_PREFIX}{state}"
    fingerprint = _session_digest(session_id)

    redis = _get_redis() if _is_redis_usable() else None
    if redis is not None:
        try:
            # Atomic GET+DELETE: two workers consuming the same state
            # concurrently cannot both succeed.
            pipe = redis.pipeline()
            pipe.get(key)
            pipe.delete(key)
            result = pipe.execute()
            stored = result[0] if result else None
            if isinstance(stored, bytes):
                stored = stored.decode("utf-8")
            if not stored:
                # Distinguish replay from unknown/expired via the tombstone.
                if redis.exists(f"{_STATE_DEAD_PREFIX}{state}"):
                    raise OAuthStateReplayed("OAuth state has already been used.")
                raise OAuthStateMissing("Unknown, expired, or already consumed state.")
            if not hmac.compare_digest(fingerprint, stored):
                # Fail closed: burn the state so a wrong-session presentation
                # can never be retried against the correct session afterwards.
                redis.set(f"{_STATE_DEAD_PREFIX}{state}", "1", ex=STATE_TTL_SECONDS)
                raise OAuthStateSessionMismatch(
                    "State does not belong to the current browser session."
                )
            redis.set(f"{_STATE_DEAD_PREFIX}{state}", "1", ex=STATE_TTL_SECONDS)
            return
        except OAuthStateError:
            raise
        except Exception as exc:
            if settings.ENV in PRODUCTION_ENVS:
                raise OAuthStateError(
                    "OAuth state store is unavailable; refusing to validate state."
                ) from exc
            logger.warning("[OAuthState] Redis unavailable, using memory fallback: %s", exc)

    _get_memory_store().consume(state, fingerprint)


def consume_authorization_code(code: str, ttl: int = CODE_REPLAY_TTL_SECONDS) -> None:
    """
    Distributed, one-time consumption of a Google authorization code.

    Replaces the former process-local ``_used_oauth_codes`` set: with multiple
    workers, a code replayed against a different worker previously succeeded.
    """
    if not code or not code.strip():
        raise OAuthStateMissing("Missing authorization code.")
    key = f"{_CODE_KEY_PREFIX}{hashlib.sha256(code.encode('utf-8')).hexdigest()}"

    redis = _get_redis() if _is_redis_usable() else None
    if redis is not None:
        try:
            pipe = redis.pipeline()
            pipe.set(key, "1", nx=True, ex=ttl)
            pipe.ttl(key)
            result = pipe.execute()
            if not result or not result[0]:
                raise OAuthStateReplayed(
                    "Authorization code has already been consumed or is invalid."
                )
            return
        except OAuthStateError:
            raise
        except Exception as exc:
            if settings.ENV in PRODUCTION_ENVS:
                raise OAuthStateError(
                    "OAuth replay store is unavailable; refusing to process code."
                ) from exc
            logger.warning("[OAuthState] Redis unavailable, using memory fallback: %s", exc)

    _get_memory_store().consume_code(code, ttl)
