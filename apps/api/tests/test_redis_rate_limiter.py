"""
Tests for Redis-backed distributed rate limiter.

Tests cover:
1. In-memory fallback when Redis is unavailable
2. Allow/deny behaviour
3. Key namespacing (different prefixes don't interfere)
4. Window expiration (conceptual, using direct store manipulation)
5. clear_rate_limits() reset for test isolation
6. Custom limit/window parameters
"""
import time
import pytest
from unittest.mock import patch, MagicMock


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fresh_module():
    """Re-imports the rate_limiter module with a clean state."""
    import importlib
    import app.common.redis.rate_limiter as mod
    importlib.reload(mod)
    return mod


# ─── 1. In-memory fallback ────────────────────────────────────────────────────

class TestInMemoryFallback:
    """Rate limiter must fall back to in-memory when Redis is unavailable."""

    def setup_method(self):
        import app.common.redis.rate_limiter as mod
        mod.clear_rate_limits()
        # Force Redis unavailable so all tests use in-memory
        mod._redis_client = None
        mod._redis_unavailable = True

    def teardown_method(self):
        import app.common.redis.rate_limiter as mod
        mod.clear_rate_limits()
        mod._redis_unavailable = False

    def test_allows_requests_under_limit(self):
        from app.common.redis.rate_limiter import check_rate_limit
        for _ in range(5):
            assert check_rate_limit("test_ip", limit=5, window_seconds=60) is True

    def test_blocks_request_over_limit(self):
        from app.common.redis.rate_limiter import check_rate_limit
        for _ in range(5):
            check_rate_limit("test_ip_limit", limit=5, window_seconds=60)
        # 6th request should be denied
        assert check_rate_limit("test_ip_limit", limit=5, window_seconds=60) is False

    def test_different_ips_dont_interfere(self):
        from app.common.redis.rate_limiter import check_rate_limit
        for _ in range(5):
            check_rate_limit("ip_a", limit=5, window_seconds=60)
        # ip_a is exhausted, ip_b should still be allowed
        assert check_rate_limit("ip_b", limit=5, window_seconds=60) is True

    def test_different_prefixes_dont_interfere(self):
        from app.common.redis.rate_limiter import check_rate_limit
        for _ in range(5):
            check_rate_limit("shared_ip", prefix="rl:auth", limit=5, window_seconds=60)
        # Same IP but different prefix should be independent
        assert check_rate_limit("shared_ip", prefix="rl:api", limit=5, window_seconds=60) is True

    def test_clear_rate_limits_resets_store(self):
        from app.common.redis.rate_limiter import check_rate_limit, clear_rate_limits
        for _ in range(5):
            check_rate_limit("reset_ip", limit=5, window_seconds=60)
        assert check_rate_limit("reset_ip", limit=5, window_seconds=60) is False

        clear_rate_limits()
        # After clear, should be allowed again
        assert check_rate_limit("reset_ip", limit=5, window_seconds=60) is True

    def test_custom_limit(self):
        from app.common.redis.rate_limiter import check_rate_limit
        # Should allow 10 requests before blocking
        for _ in range(10):
            assert check_rate_limit("custom_limit_ip", prefix="rl:custom", limit=10, window_seconds=60) is True
        assert check_rate_limit("custom_limit_ip", prefix="rl:custom", limit=10, window_seconds=60) is False

    def test_expired_timestamps_not_counted(self):
        """Timestamps older than the window should not count against the limit."""
        from app.common.redis.rate_limiter import _fallback_store, check_rate_limit
        import app.common.redis.rate_limiter as mod

        key = "rl:expire:expire_test_ip"
        # Manually inject old timestamps (older than window)
        old_time = time.time() - 120  # 2 minutes ago (beyond 60s window)
        _fallback_store[key] = [old_time] * 5

        # Even though there are 5 entries, they're expired — should be allowed
        assert check_rate_limit("expire_test_ip", prefix="rl:expire", limit=5, window_seconds=60) is True


# ─── 2. Redis-backed path ────────────────────────────────────────────────────

class TestRedisBackedRateLimiter:
    """Tests the Redis-backed code path with a mocked Redis client."""

    def setup_method(self):
        import app.common.redis.rate_limiter as mod
        mod._redis_unavailable = False
        mod._redis_client = None
        mod._fallback_store.clear()

    def teardown_method(self):
        import app.common.redis.rate_limiter as mod
        mod.clear_rate_limits()
        mod._redis_unavailable = False
        mod._redis_client = None

    def _make_redis_mock(self, counters=None):
        """Creates a mock Redis client that simulates INCR+EXPIRE pipeline."""
        counters = counters or {}
        mock_pipeline = MagicMock()
        mock_pipeline.__enter__ = MagicMock(return_value=mock_pipeline)
        mock_pipeline.__exit__ = MagicMock(return_value=False)

        def pipeline_execute():
            key = mock_pipeline._last_key
            counters[key] = counters.get(key, 0) + 1
            return [counters[key], True]

        def pipeline_incr(key):
            mock_pipeline._last_key = key
            return mock_pipeline

        mock_pipeline.incr = pipeline_incr
        mock_pipeline.expire = MagicMock(return_value=mock_pipeline)
        mock_pipeline.execute = pipeline_execute

        mock_redis = MagicMock()
        mock_redis.ping = MagicMock(return_value=True)
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_redis.get = MagicMock(return_value=None)

        return mock_redis, counters

    def test_redis_allows_under_limit(self):
        import app.common.redis.rate_limiter as mod
        mock_redis, counters = self._make_redis_mock()
        mod._redis_client = mock_redis
        mod._redis_unavailable = False

        from app.common.redis.rate_limiter import check_rate_limit
        result = check_rate_limit("redis_ip", prefix="rl:test", limit=5, window_seconds=60)
        assert result is True

    def test_redis_blocks_over_limit(self):
        import app.common.redis.rate_limiter as mod
        counters = {"rl:test:over_limit_ip": 5}  # Already at limit
        mock_redis, _ = self._make_redis_mock(counters)
        mod._redis_client = mock_redis
        mod._redis_unavailable = False

        from app.common.redis.rate_limiter import check_rate_limit
        # Counter returns 6 (over limit of 5) → denied
        result = check_rate_limit("over_limit_ip", prefix="rl:test", limit=5, window_seconds=60)
        assert result is False

    def test_redis_error_falls_back_to_memory(self):
        """When Redis throws during rate check, fall back to in-memory gracefully."""
        import app.common.redis.rate_limiter as mod
        mock_redis = MagicMock()
        mock_redis.ping = MagicMock(return_value=True)

        mock_pipeline = MagicMock()
        mock_pipeline.incr = MagicMock(return_value=mock_pipeline)
        mock_pipeline.expire = MagicMock(return_value=mock_pipeline)
        mock_pipeline.execute = MagicMock(side_effect=Exception("Redis connection lost"))
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mod._redis_client = mock_redis
        mod._redis_unavailable = False

        from app.common.redis.rate_limiter import check_rate_limit
        # Should not raise — should fall back to in-memory and allow
        result = check_rate_limit("fallback_ip", prefix="rl:err", limit=5, window_seconds=60)
        assert isinstance(result, bool)


# ─── 3. check_auth_rate_limit FastAPI dependency ──────────────────────────────

class TestCheckAuthRateLimitDependency:
    """
    Tests the FastAPI dependency check_auth_rate_limit using a mocked request.
    Verifies HTTP 429 is raised when limit is exceeded.
    """

    def setup_method(self):
        import app.common.redis.rate_limiter as mod
        mod.clear_rate_limits()
        mod._redis_client = None
        mod._redis_unavailable = True  # Use in-memory for speed

    def teardown_method(self):
        import app.common.redis.rate_limiter as mod
        mod.clear_rate_limits()
        mod._redis_unavailable = False

    @pytest.mark.asyncio
    async def test_testing_env_bypasses_rate_limit(self):
        """In testing ENV, rate limiting is completely bypassed."""
        from fastapi import Request
        from app.dependencies import check_auth_rate_limit

        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"

        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.ENV = "testing"
            # Should not raise, even with many calls
            for _ in range(20):
                await check_auth_rate_limit(mock_request)

    @pytest.mark.asyncio
    async def test_rate_limit_enforced_in_production_mode(self):
        """In non-testing ENV, rate limit is enforced."""
        from fastapi import Request, HTTPException
        from app.dependencies import check_auth_rate_limit

        mock_request = MagicMock(spec=Request)
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.100"

        with patch("app.dependencies.settings") as mock_settings:
            mock_settings.ENV = "development"
            with patch("app.dependencies.check_rate_limit") as mock_check:
                mock_check.return_value = False  # Simulate limit exceeded
                with pytest.raises(HTTPException) as exc_info:
                    await check_auth_rate_limit(mock_request)
                assert exc_info.value.status_code == 429
                assert "Retry-After" in exc_info.value.headers
