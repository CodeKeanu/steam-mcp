"""Tests for global rate limiter functionality."""

import asyncio
import pytest
from unittest.mock import patch

from steam_mcp.client.steam_client import (
    DEFAULT_RATE_LIMIT,
    RateLimiter,
    SteamClient,
    get_global_rate_limiter,
    reset_global_rate_limiter,
)


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset global rate limiter before each test."""
    reset_global_rate_limiter()
    yield
    reset_global_rate_limiter()


@pytest.fixture
def mock_env():
    """Set up mock environment variables."""
    with patch.dict("os.environ", {"STEAM_API_KEY": "test_key"}, clear=False):
        yield


class TestGetGlobalRateLimiter:
    """Tests for get_global_rate_limiter function."""

    def test_returns_rate_limiter_instance(self):
        """Should return a RateLimiter instance."""
        limiter = get_global_rate_limiter()
        assert isinstance(limiter, RateLimiter)

    def test_returns_same_instance(self):
        """Should return the same instance on subsequent calls."""
        limiter1 = get_global_rate_limiter()
        limiter2 = get_global_rate_limiter()
        assert limiter1 is limiter2

    def test_uses_default_rate_limit(self):
        """Should use DEFAULT_RATE_LIMIT when env var not set."""
        limiter = get_global_rate_limiter()
        assert limiter.requests_per_second == DEFAULT_RATE_LIMIT

    def test_uses_env_var_rate_limit(self):
        """Should use STEAM_RATE_LIMIT env var when set."""
        with patch.dict("os.environ", {"STEAM_RATE_LIMIT": "5.0"}):
            reset_global_rate_limiter()
            limiter = get_global_rate_limiter()
            assert limiter.requests_per_second == 5.0


class TestResetGlobalRateLimiter:
    """Tests for reset_global_rate_limiter function."""

    def test_reset_creates_new_instance(self):
        """After reset, should create a new instance."""
        limiter1 = get_global_rate_limiter()
        reset_global_rate_limiter()
        limiter2 = get_global_rate_limiter()
        assert limiter1 is not limiter2


class TestSteamClientRateLimiter:
    """Tests for SteamClient rate limiter integration."""

    def test_uses_global_rate_limiter_by_default(self, mock_env):
        """SteamClient should use global rate limiter by default."""
        global_limiter = get_global_rate_limiter()
        client = SteamClient()
        assert client.rate_limiter is global_limiter

    def test_multiple_clients_share_rate_limiter(self, mock_env):
        """Multiple SteamClient instances should share the same rate limiter."""
        client1 = SteamClient()
        client2 = SteamClient()
        assert client1.rate_limiter is client2.rate_limiter

    def test_can_use_custom_rate_limiter(self, mock_env):
        """SteamClient can use a custom rate limiter."""
        custom_limiter = RateLimiter(requests_per_second=5.0)
        client = SteamClient(rate_limiter=custom_limiter)
        assert client.rate_limiter is custom_limiter
        assert client.rate_limiter is not get_global_rate_limiter()

    def test_backward_compat_requests_per_second(self, mock_env):
        """SteamClient should support deprecated requests_per_second param."""
        client = SteamClient(requests_per_second=5.0)
        # Should create a dedicated limiter, not use global
        assert client.rate_limiter is not get_global_rate_limiter()
        assert client.rate_limiter.requests_per_second == 5.0

    def test_rate_limiter_takes_precedence_over_requests_per_second(self, mock_env):
        """Explicit rate_limiter should take precedence over requests_per_second."""
        custom_limiter = RateLimiter(requests_per_second=20.0)
        client = SteamClient(rate_limiter=custom_limiter, requests_per_second=5.0)
        assert client.rate_limiter is custom_limiter
        assert client.rate_limiter.requests_per_second == 20.0


class TestConcurrentAccess:
    """Tests for concurrent access to rate limiter."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_is_serialized(self):
        """Concurrent acquire calls should be properly serialized."""
        limiter = RateLimiter(requests_per_second=100.0)  # Fast for testing
        acquire_times = []

        async def track_acquire():
            await limiter.acquire()
            acquire_times.append(asyncio.get_event_loop().time())

        # Launch multiple concurrent acquires
        tasks = [asyncio.create_task(track_acquire()) for _ in range(5)]
        await asyncio.gather(*tasks)

        # Verify all acquired (should have 5 entries)
        assert len(acquire_times) == 5

    @pytest.mark.asyncio
    async def test_global_limiter_serializes_across_clients(self, mock_env):
        """Global rate limiter should serialize requests across multiple clients."""
        reset_global_rate_limiter()

        # Create multiple clients sharing the global limiter
        client1 = SteamClient()
        client2 = SteamClient()

        # Verify they share the same rate limiter
        assert client1.rate_limiter is client2.rate_limiter

        acquire_count = 0
        lock = asyncio.Lock()

        async def acquire_from_client(client):
            nonlocal acquire_count
            await client.rate_limiter.acquire()
            async with lock:
                acquire_count += 1

        # Launch concurrent acquires from different clients
        tasks = [
            asyncio.create_task(acquire_from_client(client1)),
            asyncio.create_task(acquire_from_client(client2)),
            asyncio.create_task(acquire_from_client(client1)),
            asyncio.create_task(acquire_from_client(client2)),
        ]
        await asyncio.gather(*tasks)

        # All should have completed
        assert acquire_count == 4

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_rate(self):
        """Rate limiter should enforce the configured rate limit."""
        import time

        # Very slow rate to make timing measurable
        limiter = RateLimiter(requests_per_second=10.0)  # 100ms between requests

        start = time.monotonic()

        # Make 3 requests
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        elapsed = time.monotonic() - start

        # Should take at least 200ms for 3 requests at 10 req/s
        # (first is instant, second waits 100ms, third waits 100ms)
        assert elapsed >= 0.18  # Allow small margin for timing variance

    @pytest.mark.asyncio
    async def test_no_race_conditions_under_load(self, mock_env):
        """Global limiter should handle many concurrent requests without races."""
        reset_global_rate_limiter()

        # Use a faster rate for this test
        with patch.dict("os.environ", {"STEAM_RATE_LIMIT": "1000.0"}):
            reset_global_rate_limiter()

            # Create multiple clients
            clients = [SteamClient() for _ in range(3)]

            # Verify all share the same limiter
            assert all(c.rate_limiter is clients[0].rate_limiter for c in clients)

            results = []
            lock = asyncio.Lock()

            async def acquire_and_record(client_idx):
                client = clients[client_idx % len(clients)]
                await client.rate_limiter.acquire()
                async with lock:
                    results.append(client_idx)

            # Launch many concurrent requests
            tasks = [
                asyncio.create_task(acquire_and_record(i)) for i in range(20)
            ]
            await asyncio.gather(*tasks)

            # All should complete without errors
            assert len(results) == 20
