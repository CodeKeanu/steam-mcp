"""Tests for IEconService endpoint - trading and market functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from steam_mcp.endpoints.steam_trading import IEconService
from steam_mcp.utils.steam_id import SteamIDError


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    client.get_raw = AsyncMock()
    return client


@pytest.fixture
def econ_service(mock_client):
    """Create IEconService instance with mock client."""
    return IEconService(mock_client)


# --- get_trade_offers Tests ---


class TestGetTradeOffers:
    """Tests for get_trade_offers endpoint."""

    @pytest.mark.asyncio
    async def test_returns_incoming_offers(self, econ_service, mock_client):
        """Should display incoming trade offers."""
        mock_client.get.return_value = {
            "response": {
                "trade_offers_received": [
                    {
                        "tradeofferid": "12345",
                        "accountid_other": 123456789,
                        "trade_offer_state": 2,
                        "items_to_give": [],
                        "items_to_receive": [
                            {"appid": 730, "classid": "111", "assetid": "999"}
                        ],
                    }
                ],
                "trade_offers_sent": [],
                "descriptions": [
                    {
                        "appid": 730,
                        "classid": "111",
                        "instanceid": "0",
                        "market_name": "AK-47 | Redline",
                    }
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.get_trade_offers(
                steam_id="76561198000000001",
                offer_filter="active",
            )

        assert "Incoming Offers (1)" in result
        assert "Offer #12345" in result
        assert "AK-47 | Redline" in result

    @pytest.mark.asyncio
    async def test_returns_outgoing_offers(self, econ_service, mock_client):
        """Should display outgoing trade offers."""
        mock_client.get.return_value = {
            "response": {
                "trade_offers_received": [],
                "trade_offers_sent": [
                    {
                        "tradeofferid": "67890",
                        "accountid_other": 987654321,
                        "trade_offer_state": 2,
                        "items_to_give": [
                            {"appid": 570, "classid": "222", "assetid": "888"}
                        ],
                        "items_to_receive": [],
                    }
                ],
                "descriptions": [
                    {
                        "appid": 570,
                        "classid": "222",
                        "instanceid": "0",
                        "name": "Immortal Sword",
                    }
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.get_trade_offers(
                steam_id="76561198000000001",
                offer_filter="outgoing",
            )

        assert "Outgoing Offers (1)" in result
        assert "Offer #67890" in result
        assert "Immortal Sword" in result

    @pytest.mark.asyncio
    async def test_no_offers_found(self, econ_service, mock_client):
        """Should handle empty offers gracefully."""
        mock_client.get.return_value = {
            "response": {
                "trade_offers_received": [],
                "trade_offers_sent": [],
                "descriptions": [],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.get_trade_offers(
                steam_id="76561198000000001",
            )

        assert "No active trade offers found" in result

    @pytest.mark.asyncio
    async def test_invalid_steam_id(self, econ_service):
        """Should return error for invalid Steam ID."""
        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await econ_service.get_trade_offers(
                steam_id="invalid",
            )

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_me_shortcut_without_config(self, econ_service, mock_client):
        """Should error when using 'me' without STEAM_USER_ID configured."""
        mock_client.owner_steam_id = None

        result = await econ_service.get_trade_offers(steam_id="me")

        assert "Error" in result
        assert "STEAM_USER_ID" in result


# --- get_trade_history Tests ---


class TestGetTradeHistory:
    """Tests for get_trade_history endpoint."""

    @pytest.mark.asyncio
    async def test_returns_trade_history(self, econ_service, mock_client):
        """Should display completed trades."""
        mock_client.get.return_value = {
            "response": {
                "trades": [
                    {
                        "tradeid": "999888777",
                        "steamid_other": "76561198000000002",
                        "status": 3,
                        "time_init": 1700000000,
                        "assets_given": [
                            {"appid": 730, "classid": "333", "assetid": "777"}
                        ],
                        "assets_received": [
                            {"appid": 730, "classid": "444", "assetid": "666"}
                        ],
                    }
                ],
                "total_trades": 100,
                "descriptions": [
                    {"appid": 730, "classid": "333", "instanceid": "0", "name": "Item A"},
                    {"appid": 730, "classid": "444", "instanceid": "0", "name": "Item B"},
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.get_trade_history(
                steam_id="76561198000000001",
                max_trades=20,
            )

        assert "Trade History" in result
        assert "Total Trades: 100" in result
        assert "Trade #999888777" in result
        assert "Complete" in result

    @pytest.mark.asyncio
    async def test_empty_trade_history(self, econ_service, mock_client):
        """Should handle empty history gracefully."""
        mock_client.get.return_value = {
            "response": {
                "trades": [],
                "total_trades": 0,
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.get_trade_history(
                steam_id="76561198000000001",
            )

        assert "No trade history found" in result


# --- get_market_listings Tests ---


class TestGetMarketListings:
    """Tests for get_market_listings endpoint."""

    @pytest.mark.asyncio
    async def test_returns_market_data(self, econ_service, mock_client):
        """Should display market listing information."""
        mock_client.get_raw.return_value = {
            "success": True,
            "lowest_price": "$12.34",
            "median_price": "$13.50",
            "volume": "1,234",
        }

        result = await econ_service.get_market_listings(
            app_id=730,
            item_name="AK-47 | Redline (Field-Tested)",
        )

        assert "Market Listings" in result
        assert "AK-47 | Redline" in result
        assert "Lowest Price: $12.34" in result
        assert "Median Price: $13.50" in result
        assert "Volume (24h): 1,234 sold" in result

    @pytest.mark.asyncio
    async def test_item_not_found(self, econ_service, mock_client):
        """Should handle item not found."""
        mock_client.get_raw.return_value = {"success": False}

        result = await econ_service.get_market_listings(
            app_id=730,
            item_name="Nonexistent Item",
        )

        assert "Item not found" in result

    @pytest.mark.asyncio
    async def test_api_error_handled(self, econ_service, mock_client):
        """Should handle API errors gracefully."""
        mock_client.get_raw.side_effect = Exception("Network error")

        result = await econ_service.get_market_listings(
            app_id=730,
            item_name="Test Item",
        )

        assert "Error" in result


# --- check_market_eligibility Tests ---


class TestCheckMarketEligibility:
    """Tests for check_market_eligibility endpoint."""

    @pytest.mark.asyncio
    async def test_eligible_user(self, econ_service, mock_client):
        """Should display eligibility for allowed users."""
        mock_client.get.return_value = {
            "response": {
                "allowed": True,
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.check_market_eligibility(
                steam_id="76561198000000001",
            )

        assert "Market Eligibility" in result
        assert "Eligible" in result

    @pytest.mark.asyncio
    async def test_ineligible_user_with_reason(self, econ_service, mock_client):
        """Should display restriction reason for ineligible users."""
        mock_client.get.return_value = {
            "response": {
                "allowed": False,
                "reason": 7,
                "expiration": 1700000000,
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.check_market_eligibility(
                steam_id="76561198000000001",
            )

        assert "Not Eligible" in result
        assert "Trade Ban" in result
        assert "Restriction Expires" in result

    @pytest.mark.asyncio
    async def test_empty_response_handled(self, econ_service, mock_client):
        """Should handle empty response gracefully."""
        mock_client.get.return_value = {"response": {}}

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await econ_service.check_market_eligibility(
                steam_id="76561198000000001",
            )

        assert "No eligibility information" in result


# --- Helper Method Tests ---


class TestTradeStateFormatting:
    """Tests for trade state formatting helpers."""

    def test_trade_offer_states(self, econ_service):
        """Should correctly format trade offer states."""
        assert econ_service._get_trade_state(2) == "Active"
        assert econ_service._get_trade_state(3) == "Accepted"
        assert econ_service._get_trade_state(7) == "Declined"
        assert "Unknown" in econ_service._get_trade_state(999)

    def test_trade_status_codes(self, econ_service):
        """Should correctly format trade status codes."""
        assert econ_service._get_trade_status(3) == "Complete"
        assert econ_service._get_trade_status(4) == "Failed"
        assert "Unknown" in econ_service._get_trade_status(999)

    def test_eligibility_reasons(self, econ_service):
        """Should correctly format eligibility reasons."""
        assert econ_service._get_eligibility_reason(7) == "Trade Ban"
        assert econ_service._get_eligibility_reason(1) == "Region Locked"
        assert "Unknown" in econ_service._get_eligibility_reason(999)


class TestItemNameResolution:
    """Tests for item name resolution from descriptions."""

    def test_get_item_name_with_market_name(self, econ_service):
        """Should prefer market_name over name."""
        item = {"appid": 730, "classid": "111", "instanceid": "0"}
        desc_lookup = {
            "730_111_0": {
                "market_name": "AK-47 | Redline",
                "name": "AK-47",
            }
        }
        assert econ_service._get_item_name(item, desc_lookup) == "AK-47 | Redline"

    def test_get_item_name_fallback_to_name(self, econ_service):
        """Should fall back to name if no market_name."""
        item = {"appid": 730, "classid": "111", "instanceid": "0"}
        desc_lookup = {
            "730_111_0": {"name": "Some Item"}
        }
        assert econ_service._get_item_name(item, desc_lookup) == "Some Item"

    def test_get_item_name_no_description(self, econ_service):
        """Should use asset ID if no description found."""
        item = {"appid": 730, "classid": "111", "assetid": "12345"}
        desc_lookup = {}
        assert "12345" in econ_service._get_item_name(item, desc_lookup)
