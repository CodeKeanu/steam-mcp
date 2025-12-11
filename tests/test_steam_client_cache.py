"""Tests for SteamClient caching integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from steam_mcp.client.steam_client import SteamClient
from steam_mcp.client.cache import CacheCategory


@pytest.fixture
def mock_env():
    """Set up mock environment variables."""
    with patch.dict("os.environ", {"STEAM_API_KEY": "test_key"}):
        yield


@pytest.fixture
def client_with_cache(mock_env):
    """Create a SteamClient with caching enabled."""
    return SteamClient(enable_cache=True)


@pytest.fixture
def client_without_cache(mock_env):
    """Create a SteamClient with caching disabled."""
    return SteamClient(enable_cache=False)


class TestSteamClientCacheInit:
    """Tests for cache initialization."""

    def test_cache_enabled_by_default(self, mock_env):
        """Cache should be enabled by default."""
        client = SteamClient()
        assert client._cache is not None

    def test_cache_can_be_disabled(self, mock_env):
        """Cache can be disabled via parameter."""
        client = SteamClient(enable_cache=False)
        assert client._cache is None

    def test_cache_max_size_configurable(self, mock_env):
        """Cache max_size should be configurable."""
        client = SteamClient(enable_cache=True, cache_max_size=500)
        assert client._cache is not None
        assert client._cache._max_size == 500


class TestSteamClientCacheStats:
    """Tests for cache_stats property."""

    def test_cache_stats_returns_stats_when_enabled(self, client_with_cache):
        """cache_stats should return dict when caching is enabled."""
        stats = client_with_cache.cache_stats
        assert stats is not None
        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats

    def test_cache_stats_returns_none_when_disabled(self, client_without_cache):
        """cache_stats should return None when caching is disabled."""
        stats = client_without_cache.cache_stats
        assert stats is None


class TestSteamClientClearCache:
    """Tests for clear_cache method."""

    @pytest.mark.asyncio
    async def test_clear_cache_returns_count(self, client_with_cache):
        """clear_cache should return number of entries cleared."""
        # Manually add some entries
        await client_with_cache._cache.set("key1", None, {"data": 1})
        await client_with_cache._cache.set("key2", None, {"data": 2})

        count = await client_with_cache.clear_cache()

        assert count == 2

    @pytest.mark.asyncio
    async def test_clear_cache_returns_zero_when_disabled(self, client_without_cache):
        """clear_cache should return 0 when caching is disabled."""
        count = await client_without_cache.clear_cache()
        assert count == 0


class TestSteamClientGetCaching:
    """Tests for get() method caching."""

    @pytest.mark.asyncio
    async def test_get_caches_response(self, client_with_cache):
        """get() should cache successful responses."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"data": "test"}}

        with patch.object(
            client_with_cache._client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            # First call - should make request
            result1 = await client_with_cache.get(
                "ISteamUser", "GetPlayerSummaries", version=2, params={"steamids": "123"}
            )
            assert mock_request.call_count == 1

            # Second call - should use cache
            result2 = await client_with_cache.get(
                "ISteamUser", "GetPlayerSummaries", version=2, params={"steamids": "123"}
            )
            assert mock_request.call_count == 1  # Still 1, used cache
            assert result1 == result2

    @pytest.mark.asyncio
    async def test_get_bypass_cache(self, client_with_cache):
        """get() with bypass_cache=True should skip cache."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"data": "test"}}

        with patch.object(
            client_with_cache._client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            # First call
            await client_with_cache.get(
                "ISteamUser", "GetPlayerSummaries", version=2
            )
            assert mock_request.call_count == 1

            # Second call with bypass - should make new request
            await client_with_cache.get(
                "ISteamUser", "GetPlayerSummaries", version=2, bypass_cache=True
            )
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_different_params_not_cached(self, client_with_cache):
        """get() with different params should not use cached response."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"data": "test"}}

        with patch.object(
            client_with_cache._client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            await client_with_cache.get(
                "ISteamUser", "GetPlayerSummaries", params={"steamids": "123"}
            )
            await client_with_cache.get(
                "ISteamUser", "GetPlayerSummaries", params={"steamids": "456"}
            )

            assert mock_request.call_count == 2  # Different params = different requests


class TestSteamClientGetStoreApiCaching:
    """Tests for get_store_api() method caching."""

    @pytest.mark.asyncio
    async def test_get_store_api_caches_response(self, client_with_cache):
        """get_store_api() should cache successful responses."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"440": {"success": True, "data": {}}}

        with patch.object(
            client_with_cache._client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            # First call
            result1 = await client_with_cache.get_store_api(
                "appdetails", params={"appids": "440"}
            )
            assert mock_get.call_count == 1

            # Second call - should use cache
            result2 = await client_with_cache.get_store_api(
                "appdetails", params={"appids": "440"}
            )
            assert mock_get.call_count == 1  # Still 1
            assert result1 == result2

    @pytest.mark.asyncio
    async def test_get_store_api_bypass_cache(self, client_with_cache):
        """get_store_api() with bypass_cache=True should skip cache."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"440": {"success": True}}

        with patch.object(
            client_with_cache._client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            await client_with_cache.get_store_api("appdetails", params={"appids": "440"})
            await client_with_cache.get_store_api(
                "appdetails", params={"appids": "440"}, bypass_cache=True
            )

            assert mock_get.call_count == 2


class TestSteamClientCacheTTLs:
    """Tests for cache TTL configuration."""

    def test_default_cache_ttls_defined(self, mock_env):
        """DEFAULT_CACHE_TTLS should have expected endpoints."""
        client = SteamClient()

        assert "appdetails" in client.DEFAULT_CACHE_TTLS
        assert "GetPlayerSummaries" in client.DEFAULT_CACHE_TTLS
        assert "GetNumberOfCurrentPlayers" in client.DEFAULT_CACHE_TTLS

    def test_app_details_ttl_is_1_hour(self, mock_env):
        """appdetails should have 1 hour TTL."""
        client = SteamClient()
        assert client.DEFAULT_CACHE_TTLS["appdetails"] == 3600

    def test_current_players_ttl_is_1_minute(self, mock_env):
        """GetNumberOfCurrentPlayers should have 1 minute TTL."""
        client = SteamClient()
        assert client.DEFAULT_CACHE_TTLS["GetNumberOfCurrentPlayers"] == 60

    def test_player_summaries_ttl_is_5_minutes(self, mock_env):
        """GetPlayerSummaries should have 5 minute TTL."""
        client = SteamClient()
        assert client.DEFAULT_CACHE_TTLS["GetPlayerSummaries"] == 300

    def test_get_cache_ttl_returns_configured_ttl(self, mock_env):
        """_get_cache_ttl should return configured TTL."""
        client = SteamClient()

        ttl = client._get_cache_ttl("GetPlayerSummaries")
        assert ttl == 300

    def test_get_cache_ttl_returns_default_for_unknown(self, mock_env):
        """_get_cache_ttl should return default for unknown methods."""
        client = SteamClient()

        ttl = client._get_cache_ttl("UnknownMethod")
        assert ttl == CacheCategory.DEFAULT.value
