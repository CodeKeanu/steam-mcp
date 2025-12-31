"""IEconService and IEconMarketService API endpoints.

This module provides MCP tools for Steam trading and market functionality,
including trade offers, trade history, and market eligibility.

IMPORTANT: Trade offer and history APIs (IEconService) only return data for the
Steam account that owns the API key. The steam_id parameter is validated but
the API will only return results for the authenticated account.

Reference: https://partner.steamgames.com/doc/webapi/IEconService
"""

from datetime import datetime
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


class IEconService(BaseEndpoint):
    """Steam Economy Service API endpoints for trading and market data."""

    @endpoint(
        name="get_trade_offers",
        description=(
            "Get incoming and outgoing trade offers for a user. "
            "Shows active, historical, or filtered trade offers with item details."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format. Use 'me' or 'my' for your profile. "
                    "Note: This API only returns data for the API key owner's account."
                ),
                "required": True,
            },
            "offer_filter": {
                "type": "string",
                "description": (
                    "Filter trade offers: 'active' (pending), 'incoming', 'outgoing', "
                    "or 'historical' (completed/declined)"
                ),
                "required": False,
                "default": "active",
                "enum": ["active", "incoming", "outgoing", "historical"],
            },
            "include_descriptions": {
                "type": "boolean",
                "description": "Include item descriptions in the response",
                "required": False,
                "default": True,
            },
        },
    )
    async def get_trade_offers(
        self,
        steam_id: str,
        offer_filter: str = "active",
        include_descriptions: bool = True,
    ) -> str:
        """Get trade offers for a Steam user.

        Note: This API only returns data for the API key owner's account.
        """
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        # Build request params based on filter
        params: dict[str, Any] = {
            "get_descriptions": include_descriptions,
            "language": "english",
            "active_only": offer_filter in ("active", "incoming", "outgoing"),
            "historical_only": offer_filter == "historical",
        }

        # For incoming/outgoing filters, we need both but will filter the result
        if offer_filter in ("active", "incoming", "outgoing"):
            params["get_sent_offers"] = True
            params["get_received_offers"] = True
        elif offer_filter == "historical":
            params["get_sent_offers"] = True
            params["get_received_offers"] = True

        try:
            result = await self.client.get(
                "IEconService",
                "GetTradeOffers",
                version=1,
                params=params,
            )
        except Exception as e:
            return f"Error fetching trade offers: {e}"

        response = result.get("response", {})
        sent_offers = response.get("trade_offers_sent", [])
        received_offers = response.get("trade_offers_received", [])
        descriptions = response.get("descriptions", [])

        # Build description lookup
        desc_lookup: dict[str, dict[str, Any]] = {}
        for desc in descriptions:
            key = f"{desc.get('appid')}_{desc.get('classid')}_{desc.get('instanceid', '0')}"
            desc_lookup[key] = desc

        # Filter based on user request
        if offer_filter == "incoming":
            sent_offers = []
        elif offer_filter == "outgoing":
            received_offers = []

        # Format output
        output = [f"Trade Offers for {normalized_id}", ""]

        # Received (incoming) offers
        if received_offers:
            output.append(f"Incoming Offers ({len(received_offers)}):")
            output.append("")
            for offer in received_offers[:10]:
                output.extend(self._format_offer(offer, desc_lookup, "incoming"))
            if len(received_offers) > 10:
                output.append(f"  ... and {len(received_offers) - 10} more incoming offers")
            output.append("")

        # Sent (outgoing) offers
        if sent_offers:
            output.append(f"Outgoing Offers ({len(sent_offers)}):")
            output.append("")
            for offer in sent_offers[:10]:
                output.extend(self._format_offer(offer, desc_lookup, "outgoing"))
            if len(sent_offers) > 10:
                output.append(f"  ... and {len(sent_offers) - 10} more outgoing offers")
            output.append("")

        if not sent_offers and not received_offers:
            output.append(f"No {offer_filter} trade offers found.")

        return "\n".join(output)

    def _format_offer(
        self,
        offer: dict[str, Any],
        desc_lookup: dict[str, dict[str, Any]],
        direction: str,
    ) -> list[str]:
        """Format a single trade offer for display."""
        lines = []
        offer_id = offer.get("tradeofferid", "Unknown")
        partner_id = offer.get("accountid_other", "Unknown")
        state = self._get_trade_state(offer.get("trade_offer_state", 0))

        lines.append(f"  Offer #{offer_id} ({state})")
        lines.append(f"    Partner: {partner_id}")

        # Items to give
        items_give = offer.get("items_to_give", [])
        if items_give:
            lines.append(f"    You give ({len(items_give)} items):")
            for item in items_give[:5]:
                name = self._get_item_name(item, desc_lookup)
                lines.append(f"      - {name}")
            if len(items_give) > 5:
                lines.append(f"      ... and {len(items_give) - 5} more")

        # Items to receive
        items_receive = offer.get("items_to_receive", [])
        if items_receive:
            lines.append(f"    You receive ({len(items_receive)} items):")
            for item in items_receive[:5]:
                name = self._get_item_name(item, desc_lookup)
                lines.append(f"      - {name}")
            if len(items_receive) > 5:
                lines.append(f"      ... and {len(items_receive) - 5} more")

        lines.append("")
        return lines

    def _get_item_name(
        self, item: dict[str, Any], desc_lookup: dict[str, dict[str, Any]]
    ) -> str:
        """Get item name from descriptions lookup."""
        key = f"{item.get('appid')}_{item.get('classid')}_{item.get('instanceid', '0')}"
        desc = desc_lookup.get(key, {})
        return desc.get("market_name") or desc.get("name") or f"Item {item.get('assetid', 'Unknown')}"

    def _get_trade_state(self, state: int) -> str:
        """Convert trade offer state code to readable string."""
        states = {
            1: "Invalid",
            2: "Active",
            3: "Accepted",
            4: "Countered",
            5: "Expired",
            6: "Canceled",
            7: "Declined",
            8: "InvalidItems",
            9: "NeedsConfirmation",
            10: "CanceledBySecondFactor",
            11: "InEscrow",
        }
        return states.get(state, f"Unknown({state})")

    @endpoint(
        name="get_trade_history",
        description=(
            "Get completed trade history for a user. "
            "Shows past trades with items exchanged and trade partners."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format. Use 'me' or 'my' for your profile. "
                    "Note: This API only returns data for the API key owner's account."
                ),
                "required": True,
            },
            "max_trades": {
                "type": "integer",
                "description": "Maximum number of trades to retrieve (default: 20)",
                "required": False,
                "default": 20,
                "minimum": 1,
                "maximum": 500,
            },
            "include_failed": {
                "type": "boolean",
                "description": "Include failed trades in the history",
                "required": False,
                "default": False,
            },
        },
    )
    async def get_trade_history(
        self,
        steam_id: str,
        max_trades: int = 20,
        include_failed: bool = False,
    ) -> str:
        """Get trade history for a Steam user.

        Note: This API only returns data for the API key owner's account.
        """
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "IEconService",
                "GetTradeHistory",
                version=1,
                params={
                    "max_trades": max_trades,
                    "get_descriptions": True,
                    "language": "english",
                    "include_failed": include_failed,
                    "include_total": True,
                },
            )
        except Exception as e:
            return f"Error fetching trade history: {e}"

        response = result.get("response", {})
        trades = response.get("trades", [])
        total_trades = response.get("total_trades", len(trades))
        descriptions = response.get("descriptions", [])

        # Build description lookup
        desc_lookup: dict[str, dict[str, Any]] = {}
        for desc in descriptions:
            key = f"{desc.get('appid')}_{desc.get('classid')}_{desc.get('instanceid', '0')}"
            desc_lookup[key] = desc

        output = [
            f"Trade History for {normalized_id}",
            f"Total Trades: {total_trades}",
            f"Showing: {len(trades)} trades",
            "",
        ]

        if not trades:
            output.append("No trade history found.")
            return "\n".join(output)

        for trade in trades:
            trade_id = trade.get("tradeid", "Unknown")
            partner_id = trade.get("steamid_other", "Unknown")
            status = trade.get("status", 0)
            time_init = trade.get("time_init", 0)

            output.append(f"Trade #{trade_id}")
            output.append(f"  Partner: {partner_id}")
            output.append(f"  Status: {self._get_trade_status(status)}")
            if time_init:
                dt = datetime.fromtimestamp(time_init)
                output.append(f"  Date: {dt.strftime('%Y-%m-%d %H:%M')}")

            # Assets given
            assets_given = trade.get("assets_given", [])
            if assets_given:
                output.append(f"  Given ({len(assets_given)} items):")
                for asset in assets_given[:3]:
                    name = self._get_item_name(asset, desc_lookup)
                    output.append(f"    - {name}")
                if len(assets_given) > 3:
                    output.append(f"    ... and {len(assets_given) - 3} more")

            # Assets received
            assets_received = trade.get("assets_received", [])
            if assets_received:
                output.append(f"  Received ({len(assets_received)} items):")
                for asset in assets_received[:3]:
                    name = self._get_item_name(asset, desc_lookup)
                    output.append(f"    - {name}")
                if len(assets_received) > 3:
                    output.append(f"    ... and {len(assets_received) - 3} more")

            output.append("")

        return "\n".join(output)

    def _get_trade_status(self, status: int) -> str:
        """Convert trade status code to readable string."""
        statuses = {
            0: "Init",
            1: "PreCommitted",
            2: "Committed",
            3: "Complete",
            4: "Failed",
            5: "PartialSupportRollback",
            6: "FullSupportRollback",
            7: "SupportRollbackSelective",
            8: "RollbackFailed",
            9: "RollbackAbandoned",
            10: "InEscrow",
            11: "EscrowRollback",
        }
        return statuses.get(status, f"Unknown({status})")

    @endpoint(
        name="get_market_listings",
        description=(
            "Get active Steam Community Market listings for an item. "
            "Shows current prices, quantities, and recent price history."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Game App ID (e.g., 730 for CS2, 570 for Dota 2)",
                "required": True,
            },
            "item_name": {
                "type": "string",
                "description": "Market hash name of the item (exact match required)",
                "required": True,
            },
            "currency": {
                "type": "integer",
                "description": "Currency code (1=USD, 2=GBP, 3=EUR). Default: 1 (USD)",
                "required": False,
                "default": 1,
            },
        },
    )
    async def get_market_listings(
        self,
        app_id: int,
        item_name: str,
        currency: int = 1,
    ) -> str:
        """Get market listings for an item."""
        # Use the Steam Community Market API (unofficial but stable)
        url = f"https://steamcommunity.com/market/priceoverview/"

        try:
            result = await self.client.get_raw(
                url,
                params={
                    "appid": app_id,
                    "market_hash_name": item_name,
                    "currency": currency,
                },
            )
        except Exception as e:
            return f"Error fetching market data: {e}"

        if not result.get("success"):
            return f"Item not found: '{item_name}' (App ID: {app_id})"

        output = [
            f"Market Listings for: {item_name}",
            f"App ID: {app_id}",
            "",
        ]

        lowest_price = result.get("lowest_price", "N/A")
        median_price = result.get("median_price", "N/A")
        volume = result.get("volume", "N/A")

        output.append(f"Lowest Price: {lowest_price}")
        output.append(f"Median Price: {median_price}")
        output.append(f"Volume (24h): {volume} sold")

        return "\n".join(output)

    @endpoint(
        name="check_market_eligibility",
        description=(
            "Check if a user is eligible to use the Steam Community Market. "
            "Shows any restrictions and requirements."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format. Use 'me' or 'my' to query your own profile."
                ),
                "required": True,
            },
        },
    )
    async def check_market_eligibility(self, steam_id: str) -> str:
        """Check market eligibility for a Steam user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "IEconMarketService",
                "GetMarketEligibility",
                version=1,
                params={"steamid": normalized_id},
            )
        except Exception as e:
            return f"Error checking market eligibility: {e}"

        response = result.get("response", {})

        output = [
            f"Market Eligibility for {normalized_id}",
            "",
        ]

        # Check various eligibility fields
        allowed = response.get("allowed", None)
        if allowed is not None:
            status = "Eligible" if allowed else "Not Eligible"
            output.append(f"Status: {status}")

        reason = response.get("reason", None)
        if reason:
            output.append(f"Reason: {self._get_eligibility_reason(reason)}")

        expiration = response.get("expiration", None)
        if expiration:
            dt = datetime.fromtimestamp(expiration)
            output.append(f"Restriction Expires: {dt.strftime('%Y-%m-%d %H:%M')}")

        allowed_at = response.get("allowed_at_time", None)
        if allowed_at:
            dt = datetime.fromtimestamp(allowed_at)
            output.append(f"Eligible From: {dt.strftime('%Y-%m-%d %H:%M')}")

        steamguard_required_days = response.get("steamguard_required_days", None)
        if steamguard_required_days is not None:
            output.append(f"Steam Guard Required: {steamguard_required_days} days")

        forms_required = response.get("forms_require", None)
        if forms_required is not None:
            output.append(f"Tax Forms Required: {'Yes' if forms_required else 'No'}")

        # If response is empty or minimal
        if len(output) <= 2:
            output.append("No eligibility information available.")
            output.append("This may indicate a private profile or API restrictions.")

        return "\n".join(output)

    def _get_eligibility_reason(self, reason: int) -> str:
        """Convert eligibility reason code to readable string."""
        reasons = {
            0: "None",
            1: "Region Locked",
            2: "Account Activity",
            3: "Age Verification",
            4: "Game Ban",
            5: "VAC Ban",
            6: "Community Ban",
            7: "Trade Ban",
            8: "Account Not Verified",
        }
        return reasons.get(reason, f"Unknown({reason})")
