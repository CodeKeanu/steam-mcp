"""Steam Wishlist API endpoints.

This module provides MCP tools for Steam wishlist management and price tracking,
including wishlist retrieval, sale detection, and price comparisons.

Note: Wishlist data requires a public Steam profile.
"""

import asyncio
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint
from steam_mcp.utils import normalize_steam_id


class ISteamWishlist(BaseEndpoint):
    """Steam Wishlist API endpoints for wishlist management and price tracking."""

    async def _fetch_wishlist_data(self, steam_id: str) -> dict[str, Any]:
        """
        Fetch raw wishlist data from Steam.

        Args:
            steam_id: SteamID64 of the user

        Returns:
            Dict mapping app_id to wishlist item data

        Raises:
            Exception: If wishlist is private or unavailable
        """
        url = f"https://store.steampowered.com/wishlist/profiles/{steam_id}/wishlistdata/"
        params = {"p": 0}  # Start at page 0

        all_items: dict[str, Any] = {}
        page = 0

        while True:
            params["p"] = page
            result = await self.client.get_raw(url, params=params)

            # Empty result or success=2 means end of data
            if not result or result.get("success") == 2:
                break

            # Check for private wishlist
            if isinstance(result, dict) and result.get("success") is False:
                raise ValueError("Wishlist is private or unavailable")

            all_items.update(result)
            page += 1

            # Safety limit - most wishlists won't exceed 10 pages
            if page > 20:
                break

        return all_items

    async def _fetch_app_prices(
        self, app_ids: list[int], country_code: str = "us"
    ) -> dict[int, dict[str, Any]]:
        """
        Fetch price data for multiple apps.

        Args:
            app_ids: List of app IDs to fetch prices for
            country_code: Country code for pricing

        Returns:
            Dict mapping app_id to price info
        """
        prices: dict[int, dict[str, Any]] = {}

        # Batch fetch - Store API supports multiple appids
        # Process in batches of 50 to avoid URL length limits
        batch_size = 50

        async def fetch_batch(batch: list[int]) -> dict[int, dict[str, Any]]:
            batch_prices: dict[int, dict[str, Any]] = {}
            try:
                result = await self.client.get_store_api(
                    "appdetails",
                    params={
                        "appids": ",".join(str(a) for a in batch),
                        "cc": country_code.lower(),
                        "filters": "price_overview",
                    },
                )

                for app_id in batch:
                    app_data = result.get(str(app_id), {})
                    if app_data.get("success"):
                        data = app_data.get("data", {})
                        batch_prices[app_id] = {
                            "is_free": data.get("is_free", False),
                            "price_overview": data.get("price_overview"),
                        }
            except Exception:
                pass

            return batch_prices

        # Fetch all batches in parallel
        batches = [
            app_ids[i : i + batch_size] for i in range(0, len(app_ids), batch_size)
        ]
        results = await asyncio.gather(*[fetch_batch(b) for b in batches])

        for batch_result in results:
            prices.update(batch_result)

        return prices

    def _format_price(self, price_info: dict[str, Any] | None, is_free: bool) -> str:
        """Format price information for display."""
        if is_free:
            return "Free to Play"
        if not price_info:
            return "Price unavailable"

        final = price_info.get("final_formatted", "Unknown")
        discount = price_info.get("discount_percent", 0)

        if discount > 0:
            initial = price_info.get("initial_formatted", "")
            return f"{final} ({discount}% off, was {initial})"

        return final

    @endpoint(
        name="get_wishlist",
        description=(
            "Get a user's Steam wishlist with current pricing information. "
            "Returns wishlisted games with name, app ID, current price, discount %, "
            "and priority/rank. Requires the user's wishlist to be public."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format (SteamID64, vanity URL, profile URL). "
                    "Use 'me' or 'my' for the API key owner's wishlist."
                ),
                "required": True,
            },
            "country_code": {
                "type": "string",
                "description": "Country code for pricing (e.g., 'us', 'gb', 'de')",
                "required": False,
                "default": "us",
            },
        },
    )
    async def get_wishlist(
        self,
        steam_id: str,
        country_code: str = "us",
    ) -> str:
        """Get a user's Steam wishlist with current pricing."""
        # Normalize Steam ID
        try:
            normalized_id = await normalize_steam_id(steam_id, self.client)
        except Exception as e:
            return f"Error resolving Steam ID '{steam_id}': {e}"

        # Fetch wishlist data
        try:
            wishlist_data = await self._fetch_wishlist_data(normalized_id)
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Error fetching wishlist: {e}"

        if not wishlist_data:
            return "Wishlist is empty or unavailable."

        # Extract app IDs and fetch prices in parallel
        app_ids = [int(app_id) for app_id in wishlist_data.keys()]
        prices = await self._fetch_app_prices(app_ids, country_code)

        # Build output sorted by priority (lower = higher priority)
        items: list[tuple[int, str, dict[str, Any]]] = []
        for app_id_str, item_data in wishlist_data.items():
            app_id = int(app_id_str)
            name = item_data.get("name", f"App {app_id}")
            priority = item_data.get("priority", 999)
            items.append((priority, name, {"app_id": app_id, "data": item_data}))

        items.sort(key=lambda x: (x[0], x[1].lower()))

        output = [
            f"Steam Wishlist ({len(items)} games)",
            f"Prices shown for region: {country_code.upper()}",
            "",
        ]

        for priority, name, info in items:
            app_id = info["app_id"]
            price_data = prices.get(app_id, {})
            is_free = price_data.get("is_free", False)
            price_overview = price_data.get("price_overview")
            price_str = self._format_price(price_overview, is_free)

            discount = 0
            if price_overview:
                discount = price_overview.get("discount_percent", 0)

            # Format priority display
            priority_str = f"#{priority}" if priority < 999 else ""

            # Highlight discounts
            if discount > 0:
                output.append(f"  [{app_id}] {name}")
                output.append(f"    💰 {price_str}")
                if priority_str:
                    output.append(f"    Priority: {priority_str}")
            else:
                line = f"  [{app_id}] {name} - {price_str}"
                if priority_str:
                    line += f" (Priority: {priority_str})"
                output.append(line)

        return "\n".join(output)

    @endpoint(
        name="check_wishlist_sales",
        description=(
            "Check which games on a user's wishlist are currently on sale. "
            "Returns only discounted games, sorted by discount percentage (highest first). "
            "Useful for finding the best deals on wishlisted games."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format (SteamID64, vanity URL, profile URL). "
                    "Use 'me' or 'my' for the API key owner's wishlist."
                ),
                "required": True,
            },
            "min_discount": {
                "type": "integer",
                "description": "Minimum discount percentage to include (0-100)",
                "required": False,
                "default": 0,
                "minimum": 0,
                "maximum": 100,
            },
            "country_code": {
                "type": "string",
                "description": "Country code for pricing (e.g., 'us', 'gb', 'de')",
                "required": False,
                "default": "us",
            },
        },
    )
    async def check_wishlist_sales(
        self,
        steam_id: str,
        min_discount: int = 0,
        country_code: str = "us",
    ) -> str:
        """Check which wishlisted games are currently on sale."""
        # Normalize Steam ID
        try:
            normalized_id = await normalize_steam_id(steam_id, self.client)
        except Exception as e:
            return f"Error resolving Steam ID '{steam_id}': {e}"

        # Fetch wishlist data
        try:
            wishlist_data = await self._fetch_wishlist_data(normalized_id)
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Error fetching wishlist: {e}"

        if not wishlist_data:
            return "Wishlist is empty or unavailable."

        # Extract app IDs and fetch prices
        app_ids = [int(app_id) for app_id in wishlist_data.keys()]
        prices = await self._fetch_app_prices(app_ids, country_code)

        # Filter to only discounted games
        sales: list[tuple[int, str, int, dict[str, Any]]] = []
        for app_id_str, item_data in wishlist_data.items():
            app_id = int(app_id_str)
            name = item_data.get("name", f"App {app_id}")

            price_data = prices.get(app_id, {})
            price_overview = price_data.get("price_overview")

            if price_overview:
                discount = price_overview.get("discount_percent", 0)
                if discount > 0 and discount >= min_discount:
                    sales.append((discount, name, app_id, price_overview))

        if not sales:
            if min_discount > 0:
                return f"No wishlisted games found with {min_discount}%+ discount."
            return "No wishlisted games are currently on sale."

        # Sort by discount (highest first), then by name
        sales.sort(key=lambda x: (-x[0], x[1].lower()))

        output = [
            f"Wishlist Sales ({len(sales)} games on sale)",
            f"Region: {country_code.upper()}",
        ]
        if min_discount > 0:
            output.append(f"Showing discounts of {min_discount}% or more")
        output.append("")

        total_savings = 0.0
        for discount, name, app_id, price_info in sales:
            final = price_info.get("final_formatted", "?")
            initial = price_info.get("initial_formatted", "?")

            # Calculate savings (prices are in cents)
            initial_cents = price_info.get("initial", 0)
            final_cents = price_info.get("final", 0)
            saved_cents = initial_cents - final_cents
            total_savings += saved_cents / 100

            output.append(f"  [{app_id}] {name}")
            output.append(f"    🏷️  {discount}% OFF: {final} (was {initial})")

        output.append("")
        output.append(f"Total potential savings: ${total_savings:.2f}")

        return "\n".join(output)

    @endpoint(
        name="compare_prices",
        description=(
            "Compare current prices across multiple Steam games. "
            "Returns price, discount status, and value comparison. "
            "Useful for comparing deals or deciding between similar games."
        ),
        params={
            "app_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of Steam App IDs to compare",
                "required": True,
            },
            "country_code": {
                "type": "string",
                "description": "Country code for pricing (e.g., 'us', 'gb', 'de')",
                "required": False,
                "default": "us",
            },
        },
    )
    async def compare_prices(
        self,
        app_ids: list[int],
        country_code: str = "us",
    ) -> str:
        """Compare prices across multiple games."""
        if not app_ids:
            return "Error: At least one app ID is required."

        # Deduplicate
        app_ids = list(dict.fromkeys(app_ids))

        # Fetch detailed info for all apps
        async def fetch_app_info(app_id: int) -> tuple[int, dict[str, Any] | None]:
            try:
                result = await self.client.get_store_api(
                    "appdetails",
                    params={
                        "appids": str(app_id),
                        "cc": country_code.lower(),
                        "l": "english",
                    },
                )
                app_data = result.get(str(app_id), {})
                if app_data.get("success"):
                    return (app_id, app_data.get("data", {}))
            except Exception:
                pass
            return (app_id, None)

        results = await asyncio.gather(*[fetch_app_info(aid) for aid in app_ids])

        # Build comparison data
        games: list[dict[str, Any]] = []
        failed_ids: list[int] = []

        for app_id, data in results:
            if not data:
                failed_ids.append(app_id)
                continue

            name = data.get("name", f"App {app_id}")
            is_free = data.get("is_free", False)
            price_overview = data.get("price_overview")

            # Get review data for value assessment
            review_score = None
            try:
                url = f"https://store.steampowered.com/appreviews/{app_id}"
                review_result = await self.client.get_raw(
                    url,
                    params={"json": "1", "num_per_page": 0},
                )
                if review_result.get("success") == 1:
                    query = review_result.get("query_summary", {})
                    total = query.get("total_reviews", 0)
                    positive = query.get("total_positive", 0)
                    if total > 0:
                        review_score = round((positive / total) * 100)
            except Exception:
                pass

            # Calculate price in dollars
            price_dollars = 0.0
            if is_free:
                price_dollars = 0.0
            elif price_overview:
                price_dollars = price_overview.get("final", 0) / 100

            games.append({
                "app_id": app_id,
                "name": name,
                "is_free": is_free,
                "price_overview": price_overview,
                "price_dollars": price_dollars,
                "review_score": review_score,
            })

        if not games:
            return f"Could not fetch data for any of the provided app IDs: {app_ids}"

        # Sort by current price (ascending)
        games.sort(key=lambda g: g["price_dollars"])

        output = [
            f"Price Comparison ({len(games)} games)",
            f"Region: {country_code.upper()}",
            "",
        ]

        for game in games:
            name = game["name"]
            app_id = game["app_id"]
            is_free = game["is_free"]
            price_overview = game["price_overview"]
            review_score = game["review_score"]

            price_str = self._format_price(price_overview, is_free)

            output.append(f"[{app_id}] {name}")
            output.append(f"  Price: {price_str}")

            # Show discount if applicable
            if price_overview and price_overview.get("discount_percent", 0) > 0:
                discount = price_overview["discount_percent"]
                output.append(f"  Discount: {discount}% off")

            # Show review score if available
            if review_score is not None:
                if review_score >= 95:
                    rating = "Overwhelmingly Positive"
                elif review_score >= 80:
                    rating = "Very Positive"
                elif review_score >= 70:
                    rating = "Mostly Positive"
                elif review_score >= 50:
                    rating = "Mixed"
                else:
                    rating = "Negative"
                output.append(f"  Reviews: {review_score}% positive ({rating})")

            output.append("")

        if failed_ids:
            output.append(f"Note: Could not fetch data for app IDs: {failed_ids}")

        return "\n".join(output).strip()
