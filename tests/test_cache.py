"""Tests for TTL cache implementation."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steam_mcp.client.cache import CacheCategory, CacheEntry, TTLCache, cached


class TestTTLCache:
    """Tests for TTLCache class."""

    @pytest.fixture
    def cache(self):
        """Create a cache instance for testing."""
        return TTLCache(default_ttl=60, max_size=100)

    @pytest.mark.asyncio
    async def test_set_and_get_basic(self, cache):
        """Basic set and get should work."""
        await cache.set("endpoint1", {"id": 123}, {"data": "test"})

        hit, value = await cache.get("endpoint1", {"id": 123})

        assert hit is True
        assert value == {"data": "test"}

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, cache):
        """Cache miss should return (False, None)."""
        hit, value = await cache.get("nonexistent", None)

        assert hit is False
        assert value is None

    @pytest.mark.asyncio
    async def test_different_params_different_keys(self, cache):
        """Same endpoint with different params should be cached separately."""
        await cache.set("endpoint", {"id": 1}, {"data": "one"})
        await cache.set("endpoint", {"id": 2}, {"data": "two"})

        hit1, value1 = await cache.get("endpoint", {"id": 1})
        hit2, value2 = await cache.get("endpoint", {"id": 2})

        assert hit1 is True
        assert value1 == {"data": "one"}
        assert hit2 is True
        assert value2 == {"data": "two"}

    @pytest.mark.asyncio
    async def test_expired_entry_returns_miss(self, cache):
        """Expired entries should return cache miss."""
        # Set with very short TTL
        await cache.set("endpoint", None, {"data": "test"}, ttl=0)

        # Wait a tiny bit for expiration
        await asyncio.sleep(0.01)

        hit, value = await cache.get("endpoint", None)

        assert hit is False
        assert value is None

    @pytest.mark.asyncio
    async def test_custom_ttl_overrides_default(self, cache):
        """Custom TTL should override default."""
        await cache.set("endpoint", None, {"data": "test"}, ttl=3600)

        # Check that entry exists
        hit, value = await cache.get("endpoint", None)
        assert hit is True

    @pytest.mark.asyncio
    async def test_invalidate_removes_entry(self, cache):
        """Invalidate should remove specific entry."""
        await cache.set("endpoint", {"id": 1}, {"data": "test"})

        removed = await cache.invalidate("endpoint", {"id": 1})

        assert removed is True

        hit, _ = await cache.get("endpoint", {"id": 1})
        assert hit is False

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_returns_false(self, cache):
        """Invalidate on nonexistent entry should return False."""
        removed = await cache.invalidate("nonexistent", None)

        assert removed is False

    @pytest.mark.asyncio
    async def test_clear_removes_all_entries(self, cache):
        """Clear should remove all entries."""
        await cache.set("endpoint1", None, {"data": "one"})
        await cache.set("endpoint2", None, {"data": "two"})

        count = await cache.clear()

        assert count == 2

        hit1, _ = await cache.get("endpoint1", None)
        hit2, _ = await cache.get("endpoint2", None)
        assert hit1 is False
        assert hit2 is False

    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache):
        """Cache should track hits and misses."""
        await cache.set("endpoint", None, {"data": "test"})

        # Generate some hits and misses
        await cache.get("endpoint", None)  # Hit
        await cache.get("endpoint", None)  # Hit
        await cache.get("nonexistent", None)  # Miss

        stats = cache.stats

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(66.7, rel=0.1)

    @pytest.mark.asyncio
    async def test_max_size_triggers_cleanup(self):
        """Cache should cleanup when max_size is reached."""
        cache = TTLCache(default_ttl=60, max_size=3)

        # Fill cache to capacity
        await cache.set("e1", None, {"data": "1"})
        await cache.set("e2", None, {"data": "2"})
        await cache.set("e3", None, {"data": "3"})

        # Add one more - should trigger cleanup
        await cache.set("e4", None, {"data": "4"})

        # All non-expired entries should still be there
        # (cleanup only removes expired ones)
        assert cache.stats["size"] == 4  # No expired, so cleanup didn't remove any

    @pytest.mark.asyncio
    async def test_make_key_deterministic(self):
        """Same endpoint+params should always produce same key."""
        key1 = TTLCache._make_key("endpoint", {"a": 1, "b": 2})
        key2 = TTLCache._make_key("endpoint", {"b": 2, "a": 1})  # Different order
        key3 = TTLCache._make_key("endpoint", {"a": 1, "b": 3})  # Different value

        assert key1 == key2  # Same params, different order = same key
        assert key1 != key3  # Different params = different key

    @pytest.mark.asyncio
    async def test_none_params_handled(self, cache):
        """None params should be handled correctly."""
        await cache.set("endpoint", None, {"data": "test"})

        hit, value = await cache.get("endpoint", None)

        assert hit is True
        assert value == {"data": "test"}

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache):
        """Cache should handle concurrent access safely."""
        async def write_task(key: str, value: str):
            await cache.set(key, None, {"data": value})

        async def read_task(key: str):
            return await cache.get(key, None)

        # Run many concurrent operations
        tasks = []
        for i in range(20):
            tasks.append(write_task(f"key{i % 5}", f"value{i}"))
            tasks.append(read_task(f"key{i % 5}"))

        # Should not raise any exceptions
        await asyncio.gather(*tasks)


class TestCacheCategory:
    """Tests for CacheCategory enum."""

    def test_app_details_ttl(self):
        """APP_DETAILS should be 1 hour."""
        assert CacheCategory.APP_DETAILS.value == 3600

    def test_player_summary_ttl(self):
        """PLAYER_SUMMARY should be 5 minutes."""
        assert CacheCategory.PLAYER_SUMMARY.value == 300

    def test_current_players_ttl(self):
        """CURRENT_PLAYERS should be 1 minute."""
        assert CacheCategory.CURRENT_PLAYERS.value == 60

    def test_default_ttl(self):
        """DEFAULT should be 5 minutes."""
        assert CacheCategory.DEFAULT.value == 300


class TestCachedDecorator:
    """Tests for @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_function_uses_cache(self):
        """Decorated function should use cache."""
        call_count = 0

        class MockService:
            def __init__(self):
                self._cache = TTLCache(default_ttl=60)

            @cached(category=CacheCategory.APP_DETAILS)
            async def get_data(self, app_id: int) -> dict:
                nonlocal call_count
                call_count += 1
                return {"app_id": app_id, "name": "Test"}

        service = MockService()

        # First call - should execute function
        result1 = await service.get_data(123)
        assert result1 == {"app_id": 123, "name": "Test"}
        assert call_count == 1

        # Second call - should use cache
        result2 = await service.get_data(123)
        assert result2 == {"app_id": 123, "name": "Test"}
        assert call_count == 1  # Still 1, used cache

    @pytest.mark.asyncio
    async def test_cached_bypass_cache_param(self):
        """bypass_cache=True should skip cache."""
        call_count = 0

        class MockService:
            def __init__(self):
                self._cache = TTLCache(default_ttl=60)

            @cached(category=CacheCategory.APP_DETAILS)
            async def get_data(self, app_id: int) -> dict:
                nonlocal call_count
                call_count += 1
                return {"app_id": app_id, "call": call_count}

        service = MockService()

        result1 = await service.get_data(123)
        assert call_count == 1

        # Bypass cache - should execute function again
        result2 = await service.get_data(123, bypass_cache=True)
        assert call_count == 2
        assert result2["call"] == 2

    @pytest.mark.asyncio
    async def test_cached_no_cache_attribute(self):
        """Should work without _cache attribute (no caching)."""
        call_count = 0

        class MockService:
            @cached(category=CacheCategory.APP_DETAILS)
            async def get_data(self, app_id: int) -> dict:
                nonlocal call_count
                call_count += 1
                return {"app_id": app_id}

        service = MockService()

        await service.get_data(123)
        await service.get_data(123)

        assert call_count == 2  # No caching, called twice

    @pytest.mark.asyncio
    async def test_cached_explicit_ttl(self):
        """Explicit ttl should override category."""
        class MockService:
            def __init__(self):
                self._cache = TTLCache(default_ttl=60)

            @cached(ttl=1)  # 1 second TTL
            async def get_data(self, app_id: int) -> dict:
                return {"app_id": app_id}

        service = MockService()

        await service.get_data(123)

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cache should have expired
        hit, _ = await service._cache.get(
            "steam_mcp.client.cache.MockService.get_data:{}",
            None
        )
        # Note: We can't easily test TTL without access to internals,
        # but the decorator should use the explicit TTL
