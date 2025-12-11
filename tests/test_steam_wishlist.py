"""Tests for ISteamWishlist endpoint - wishlist management and price tracking."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from steam_mcp.endpoints.steam_wishlist import ISteamWishlist


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get_raw = AsyncMock()
    client.get_store_api = AsyncMock()
    return client


@pytest.fixture
def wishlist_endpoint(mock_client):
    """Create ISteamWishlist instance with mock client."""
    return ISteamWishlist(mock_client)


# --- get_wishlist Tests ---


class TestGetWishlist:
    """Tests for get_wishlist endpoint."""

    @pytest.mark.asyncio
    async def test_get_wishlist_success(self, wishlist_endpoint, mock_client):
        """Should return formatted wishlist with prices."""
        wishlist_data = {
            "730": {"name": "Counter-Strike 2", "priority": 1},
            "570": {"name": "Dota 2", "priority": 2},
        }

        price_data = {
            "730": {
                "success": True,
                "data": {
                    "is_free": True,
                },
            },
            "570": {
                "success": True,
                "data": {
                    "is_free": True,
                },
            },
        }

        mock_client.get_raw.return_value = wishlist_data
        mock_client.get_store_api.return_value = price_data

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.get_wishlist(
                steam_id="76561198000000001"
            )

        assert "Steam Wishlist (2 games)" in result
        assert "Counter-Strike 2" in result
        assert "Dota 2" in result

    @pytest.mark.asyncio
    async def test_get_wishlist_empty(self, wishlist_endpoint, mock_client):
        """Should handle empty wishlist."""
        mock_client.get_raw.return_value = {}

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.get_wishlist(
                steam_id="76561198000000001"
            )

        assert "empty or unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_get_wishlist_private(self, wishlist_endpoint, mock_client):
        """Should handle private wishlist."""
        mock_client.get_raw.return_value = {"success": False}

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.get_wishlist(
                steam_id="76561198000000001"
            )

        assert "private" in result.lower() or "unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_get_wishlist_invalid_steam_id(self, wishlist_endpoint):
        """Should return error for invalid Steam ID."""
        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=Exception("Invalid Steam ID"),
        ):
            result = await wishlist_endpoint.get_wishlist(
                steam_id="invalid"
            )

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_get_wishlist_shows_discounted_games(self, wishlist_endpoint, mock_client):
        """Should highlight discounted games."""
        wishlist_data = {
            "440": {"name": "Team Fortress 2", "priority": 1},
        }

        price_data = {
            "440": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$4.99",
                        "initial_formatted": "$9.99",
                        "discount_percent": 50,
                        "final": 499,
                        "initial": 999,
                    },
                },
            },
        }

        mock_client.get_raw.return_value = wishlist_data
        mock_client.get_store_api.return_value = price_data

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.get_wishlist(
                steam_id="76561198000000001"
            )

        assert "50% off" in result
        assert "$4.99" in result


# --- check_wishlist_sales Tests ---


class TestCheckWishlistSales:
    """Tests for check_wishlist_sales endpoint."""

    @pytest.mark.asyncio
    async def test_check_sales_finds_discounted(self, wishlist_endpoint, mock_client):
        """Should find games on sale."""
        wishlist_data = {
            "730": {"name": "Game A", "priority": 1},
            "570": {"name": "Game B", "priority": 2},
        }

        price_data = {
            "730": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$14.99",
                        "initial_formatted": "$29.99",
                        "discount_percent": 50,
                        "final": 1499,
                        "initial": 2999,
                    },
                },
            },
            "570": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$19.99",
                        "initial_formatted": "$19.99",
                        "discount_percent": 0,
                        "final": 1999,
                        "initial": 1999,
                    },
                },
            },
        }

        mock_client.get_raw.return_value = wishlist_data
        mock_client.get_store_api.return_value = price_data

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.check_wishlist_sales(
                steam_id="76561198000000001"
            )

        assert "1 games on sale" in result
        assert "Game A" in result
        assert "50% OFF" in result
        assert "Game B" not in result  # Not on sale

    @pytest.mark.asyncio
    async def test_check_sales_min_discount_filter(self, wishlist_endpoint, mock_client):
        """Should filter by minimum discount."""
        wishlist_data = {
            "100": {"name": "Small Discount", "priority": 1},
            "200": {"name": "Big Discount", "priority": 2},
        }

        price_data = {
            "100": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$9.49",
                        "initial_formatted": "$9.99",
                        "discount_percent": 5,
                        "final": 949,
                        "initial": 999,
                    },
                },
            },
            "200": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$9.99",
                        "initial_formatted": "$49.99",
                        "discount_percent": 80,
                        "final": 999,
                        "initial": 4999,
                    },
                },
            },
        }

        mock_client.get_raw.return_value = wishlist_data
        mock_client.get_store_api.return_value = price_data

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.check_wishlist_sales(
                steam_id="76561198000000001",
                min_discount=50,
            )

        assert "Big Discount" in result
        assert "Small Discount" not in result

    @pytest.mark.asyncio
    async def test_check_sales_no_sales(self, wishlist_endpoint, mock_client):
        """Should report when nothing is on sale."""
        wishlist_data = {
            "100": {"name": "Full Price Game", "priority": 1},
        }

        price_data = {
            "100": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$59.99",
                        "initial_formatted": "$59.99",
                        "discount_percent": 0,
                        "final": 5999,
                        "initial": 5999,
                    },
                },
            },
        }

        mock_client.get_raw.return_value = wishlist_data
        mock_client.get_store_api.return_value = price_data

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.check_wishlist_sales(
                steam_id="76561198000000001"
            )

        assert "not" in result.lower() or "no" in result.lower()

    @pytest.mark.asyncio
    async def test_check_sales_calculates_savings(self, wishlist_endpoint, mock_client):
        """Should calculate total potential savings."""
        wishlist_data = {
            "100": {"name": "Game 1", "priority": 1},
            "200": {"name": "Game 2", "priority": 2},
        }

        price_data = {
            "100": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$10.00",
                        "initial_formatted": "$20.00",
                        "discount_percent": 50,
                        "final": 1000,
                        "initial": 2000,
                    },
                },
            },
            "200": {
                "success": True,
                "data": {
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$15.00",
                        "initial_formatted": "$30.00",
                        "discount_percent": 50,
                        "final": 1500,
                        "initial": 3000,
                    },
                },
            },
        }

        mock_client.get_raw.return_value = wishlist_data
        mock_client.get_store_api.return_value = price_data

        with patch(
            "steam_mcp.endpoints.steam_wishlist.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await wishlist_endpoint.check_wishlist_sales(
                steam_id="76561198000000001"
            )

        assert "$25.00" in result  # $10 + $15 savings


# --- compare_prices Tests ---


class TestComparePrices:
    """Tests for compare_prices endpoint."""

    @pytest.mark.asyncio
    async def test_compare_prices_success(self, wishlist_endpoint, mock_client):
        """Should compare prices for multiple games."""
        mock_client.get_store_api.side_effect = [
            {
                "100": {
                    "success": True,
                    "data": {
                        "name": "Cheap Game",
                        "is_free": False,
                        "price_overview": {
                            "final_formatted": "$9.99",
                            "discount_percent": 0,
                            "final": 999,
                        },
                    },
                },
            },
            {
                "200": {
                    "success": True,
                    "data": {
                        "name": "Expensive Game",
                        "is_free": False,
                        "price_overview": {
                            "final_formatted": "$59.99",
                            "discount_percent": 0,
                            "final": 5999,
                        },
                    },
                },
            },
        ]

        # Mock review API calls
        mock_client.get_raw.side_effect = [
            {"success": 1, "query_summary": {"total_reviews": 100, "total_positive": 80}},
            {"success": 1, "query_summary": {"total_reviews": 50, "total_positive": 45}},
        ]

        result = await wishlist_endpoint.compare_prices(
            app_ids=[100, 200]
        )

        assert "Price Comparison" in result
        assert "Cheap Game" in result
        assert "Expensive Game" in result
        assert "$9.99" in result
        assert "$59.99" in result

    @pytest.mark.asyncio
    async def test_compare_prices_empty_list(self, wishlist_endpoint):
        """Should return error for empty app list."""
        result = await wishlist_endpoint.compare_prices(app_ids=[])

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_compare_prices_shows_discount(self, wishlist_endpoint, mock_client):
        """Should show discount info when applicable."""
        mock_client.get_store_api.return_value = {
            "100": {
                "success": True,
                "data": {
                    "name": "Discounted Game",
                    "is_free": False,
                    "price_overview": {
                        "final_formatted": "$14.99",
                        "initial_formatted": "$29.99",
                        "discount_percent": 50,
                        "final": 1499,
                    },
                },
            },
        }

        mock_client.get_raw.return_value = {"success": 0}

        result = await wishlist_endpoint.compare_prices(app_ids=[100])

        assert "50% off" in result

    @pytest.mark.asyncio
    async def test_compare_prices_sorts_by_price(self, wishlist_endpoint, mock_client):
        """Should sort games by price (ascending)."""
        # Return both games in one call
        mock_client.get_store_api.side_effect = [
            {
                "200": {
                    "success": True,
                    "data": {
                        "name": "Expensive",
                        "is_free": False,
                        "price_overview": {"final": 5999, "final_formatted": "$59.99"},
                    },
                },
            },
            {
                "100": {
                    "success": True,
                    "data": {
                        "name": "Cheap",
                        "is_free": False,
                        "price_overview": {"final": 999, "final_formatted": "$9.99"},
                    },
                },
            },
        ]

        mock_client.get_raw.return_value = {"success": 0}

        result = await wishlist_endpoint.compare_prices(app_ids=[200, 100])

        # Cheap should appear before Expensive
        cheap_pos = result.find("Cheap")
        expensive_pos = result.find("Expensive")
        assert cheap_pos < expensive_pos

    @pytest.mark.asyncio
    async def test_compare_prices_handles_free_games(self, wishlist_endpoint, mock_client):
        """Should handle free-to-play games."""
        mock_client.get_store_api.return_value = {
            "730": {
                "success": True,
                "data": {
                    "name": "Free Game",
                    "is_free": True,
                },
            },
        }

        mock_client.get_raw.return_value = {"success": 0}

        result = await wishlist_endpoint.compare_prices(app_ids=[730])

        assert "Free to Play" in result

    @pytest.mark.asyncio
    async def test_compare_prices_shows_reviews(self, wishlist_endpoint, mock_client):
        """Should include review scores when available."""
        mock_client.get_store_api.return_value = {
            "100": {
                "success": True,
                "data": {
                    "name": "Popular Game",
                    "is_free": False,
                    "price_overview": {"final": 1999, "final_formatted": "$19.99"},
                },
            },
        }

        mock_client.get_raw.return_value = {
            "success": 1,
            "query_summary": {
                "total_reviews": 1000,
                "total_positive": 950,
            },
        }

        result = await wishlist_endpoint.compare_prices(app_ids=[100])

        assert "95%" in result
        assert "positive" in result.lower()

    @pytest.mark.asyncio
    async def test_compare_prices_failed_ids(self, wishlist_endpoint, mock_client):
        """Should report failed app IDs."""
        mock_client.get_store_api.return_value = {
            "99999": {"success": False},
        }

        result = await wishlist_endpoint.compare_prices(app_ids=[99999])

        assert "Could not fetch" in result


# --- Helper Method Tests ---


class TestFormatPrice:
    """Tests for _format_price helper."""

    def test_format_price_free(self, wishlist_endpoint):
        """Should format free games."""
        result = wishlist_endpoint._format_price(None, is_free=True)
        assert result == "Free to Play"

    def test_format_price_no_info(self, wishlist_endpoint):
        """Should handle missing price info."""
        result = wishlist_endpoint._format_price(None, is_free=False)
        assert result == "Price unavailable"

    def test_format_price_normal(self, wishlist_endpoint):
        """Should format normal price."""
        price_info = {"final_formatted": "$19.99", "discount_percent": 0}
        result = wishlist_endpoint._format_price(price_info, is_free=False)
        assert result == "$19.99"

    def test_format_price_discounted(self, wishlist_endpoint):
        """Should format discounted price."""
        price_info = {
            "final_formatted": "$9.99",
            "initial_formatted": "$19.99",
            "discount_percent": 50,
        }
        result = wishlist_endpoint._format_price(price_info, is_free=False)
        assert "$9.99" in result
        assert "50% off" in result
        assert "$19.99" in result
