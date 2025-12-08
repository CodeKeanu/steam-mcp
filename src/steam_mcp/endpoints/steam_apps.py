"""ISteamApps and IStoreService API endpoints.

This module provides MCP tools for Steam app/game metadata,
including app lists and version checking.

References:
- https://partner.steamgames.com/doc/webapi/ISteamApps
- https://partner.steamgames.com/doc/webapi/IStoreService
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


class ISteamApps(BaseEndpoint):
    """ISteamApps API endpoints for app metadata and version info."""

    @endpoint(
        name="get_app_list",
        description=(
            "Search for Steam apps (games, software, DLC) by name. "
            "Returns App IDs and names matching the search query. "
            "Useful for finding the App ID of a game by its name."
        ),
        params={
            "search": {
                "type": "string",
                "description": "Search term to filter apps by name (case-insensitive)",
                "required": True,
            },
            "include_games": {
                "type": "boolean",
                "description": "Include games in results",
                "required": False,
                "default": True,
            },
            "include_dlc": {
                "type": "boolean",
                "description": "Include DLC in results",
                "required": False,
                "default": False,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "required": False,
                "default": 25,
                "minimum": 1,
                "maximum": 100,
            },
        },
    )
    async def get_app_list(
        self,
        search: str,
        include_games: bool = True,
        include_dlc: bool = False,
        max_results: int = 25,
    ) -> str:
        """Search for Steam apps by name."""
        # Use IStoreService for filtered results
        result = await self.client.get(
            "IStoreService",
            "GetAppList",
            version=1,
            params={
                "include_games": include_games,
                "include_dlc": include_dlc,
                "include_software": False,
                "include_videos": False,
                "include_hardware": False,
                "max_results": 50000,  # Get a large batch to filter
            },
        )

        response = result.get("response", {})
        apps = response.get("apps", [])

        if not apps:
            return "No apps found. The API may be temporarily unavailable."

        # Filter by search term (case-insensitive)
        search_lower = search.lower()
        matching = [
            app for app in apps
            if search_lower in app.get("name", "").lower()
        ]

        if not matching:
            return f"No apps found matching '{search}'."

        # Sort by relevance (exact match first, then starts with, then contains)
        def sort_key(app: dict[str, Any]) -> tuple[int, str]:
            name = app.get("name", "").lower()
            if name == search_lower:
                return (0, name)
            elif name.startswith(search_lower):
                return (1, name)
            else:
                return (2, name)

        matching.sort(key=sort_key)

        # Limit results
        matching = matching[:max_results]

        output = [
            f"Apps matching '{search}':",
            f"Found {len(matching)} result(s)",
            "",
        ]

        for app in matching:
            appid = app.get("appid", "?")
            name = app.get("name", "Unknown")
            output.append(f"  [{appid}] {name}")

        return "\n".join(output)

    @endpoint(
        name="check_app_up_to_date",
        description=(
            "Check if a specific version of a game/app is up to date. "
            "Useful for game servers to verify they're running the latest version."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game/app",
                "required": True,
            },
            "version": {
                "type": "integer",
                "description": "Current version number to check",
                "required": True,
            },
        },
    )
    async def check_app_up_to_date(
        self,
        app_id: int,
        version: int,
    ) -> str:
        """Check if an app version is up to date."""
        result = await self.client.get(
            "ISteamApps",
            "UpToDateCheck",
            version=1,
            params={
                "appid": app_id,
                "version": version,
            },
        )

        response = result.get("response", {})

        if not response.get("success", False):
            return f"Could not check version for App ID {app_id}. App may not support version checking."

        up_to_date = response.get("up_to_date", False)
        version_is_listable = response.get("version_is_listable", False)
        required_version = response.get("required_version")
        message = response.get("message", "")

        output = [f"Version Check for App ID {app_id}"]

        if up_to_date:
            output.append(f"✓ Version {version} is UP TO DATE")
        else:
            output.append(f"✗ Version {version} is OUTDATED")
            if required_version:
                output.append(f"  Required version: {required_version}")

        if message:
            output.append(f"  Message: {message}")

        if not version_is_listable:
            output.append("  Note: This version is not publicly listable")

        return "\n".join(output)

    @endpoint(
        name="get_app_details",
        description=(
            "Get detailed information about a Steam app including description, "
            "price, genres, release date, and more. Uses the Steam Store API."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game/app",
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
    async def get_app_details(
        self,
        app_id: int,
        country_code: str = "us",
    ) -> str:
        """Get detailed app information from the Store API."""
        try:
            result = await self.client.get_store_api(
                "appdetails",
                params={
                    "appids": str(app_id),
                    "cc": country_code.lower(),
                    "l": "english",
                },
            )
        except Exception as e:
            return f"Error fetching app details: {e}"

        app_data = result.get(str(app_id), {})

        if not app_data.get("success", False):
            return f"App ID {app_id} not found or unavailable in region '{country_code}'."

        data = app_data.get("data", {})

        if not data:
            return f"No data available for App ID {app_id}."

        name = data.get("name", "Unknown")
        app_type = data.get("type", "unknown")
        is_free = data.get("is_free", False)
        short_desc = data.get("short_description", "")
        developers = ", ".join(data.get("developers", ["Unknown"]))
        publishers = ", ".join(data.get("publishers", ["Unknown"]))

        # Release date
        release_info = data.get("release_date", {})
        if release_info.get("coming_soon"):
            release_date = "Coming Soon"
        else:
            release_date = release_info.get("date", "Unknown")

        # Price
        price_info = data.get("price_overview", {})
        if is_free:
            price_str = "Free to Play"
        elif price_info:
            price_str = price_info.get("final_formatted", "Unknown")
            if price_info.get("discount_percent", 0) > 0:
                discount = price_info["discount_percent"]
                original = price_info.get("initial_formatted", "")
                price_str = f"{price_str} ({discount}% off, was {original})"
        else:
            price_str = "Price not available"

        # Genres
        genres = [g.get("description", "") for g in data.get("genres", [])]
        genres_str = ", ".join(genres) if genres else "Unknown"

        # Categories (multiplayer, achievements, etc.)
        categories = [c.get("description", "") for c in data.get("categories", [])]

        # Platforms
        platforms = data.get("platforms", {})
        platform_list = []
        if platforms.get("windows"):
            platform_list.append("Windows")
        if platforms.get("mac"):
            platform_list.append("macOS")
        if platforms.get("linux"):
            platform_list.append("Linux")
        platforms_str = ", ".join(platform_list) if platform_list else "Unknown"

        # Metacritic
        metacritic = data.get("metacritic", {})
        metacritic_str = ""
        if metacritic:
            score = metacritic.get("score", "N/A")
            metacritic_str = f"\nMetacritic: {score}"

        output = [
            f"{name}",
            f"App ID: {app_id} | Type: {app_type.title()}",
            f"Developer: {developers}",
            f"Publisher: {publishers}",
            f"Release Date: {release_date}",
            f"Price: {price_str}",
            f"Platforms: {platforms_str}",
            f"Genres: {genres_str}",
        ]

        if metacritic_str:
            output.append(metacritic_str)

        if categories:
            output.append(f"Features: {', '.join(categories[:5])}")
            if len(categories) > 5:
                output.append(f"  ... and {len(categories) - 5} more features")

        if short_desc:
            output.append("")
            output.append(f"Description: {short_desc}")

        # Store URL
        output.append("")
        output.append(f"Store: https://store.steampowered.com/app/{app_id}")

        return "\n".join(output)

    @endpoint(
        name="get_similar_games",
        description=(
            "Get game recommendations similar to one or more games based on shared tags and genres. "
            "Accepts multiple app IDs to find games matching all of them. "
            "Useful for finding games like ones you already enjoy."
        ),
        params={
            "app_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of Steam App IDs to find similar games for",
                "required": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of recommendations to return (default: 10)",
                "required": False,
                "default": 10,
                "minimum": 1,
                "maximum": 25,
            },
        },
    )
    async def get_similar_games(
        self,
        app_ids: list[int],
        max_results: int = 10,
    ) -> str:
        """Get similar game recommendations based on tags and genres."""
        if not app_ids:
            return "Error: At least one app ID is required."

        # Deduplicate and validate
        app_ids = list(dict.fromkeys(app_ids))
        max_results = max(1, min(max_results, 25))

        # Step 1: Fetch all source games in parallel
        async def fetch_source(appid: int) -> tuple[int, dict[str, Any] | None]:
            try:
                result = await self.client.get_store_api(
                    "appdetails",
                    params={"appids": str(appid), "l": "english"},
                )
                data = result.get(str(appid), {})
                if data.get("success"):
                    return (appid, data.get("data", {}))
            except Exception:
                pass
            return (appid, None)

        source_results = await asyncio.gather(*[fetch_source(aid) for aid in app_ids])

        # Collect genres/categories from all valid source games
        source_genres: set[str] = set()
        source_categories: set[str] = set()
        source_names: list[str] = []
        source_app_ids: set[int] = set()
        failed_ids: list[int] = []

        for appid, data in source_results:
            if not data:
                failed_ids.append(appid)
                continue
            source_app_ids.add(appid)
            source_names.append(data.get("name", f"App {appid}"))
            source_genres.update(
                g.get("id") for g in data.get("genres", []) if g.get("id")
            )
            source_categories.update(
                c.get("id") for c in data.get("categories", []) if c.get("id")
            )

        if not source_names:
            return f"None of the provided app IDs could be found: {app_ids}"

        if not source_genres:
            return f"No genre data available for {source_names} to find similar games."

        # Step 2: Get a batch of games to compare
        try:
            apps_result = await self.client.get(
                "IStoreService",
                "GetAppList",
                version=1,
                params={
                    "include_games": True,
                    "include_dlc": False,
                    "include_software": False,
                    "include_videos": False,
                    "include_hardware": False,
                    "max_results": 10000,
                },
            )
        except Exception as e:
            return f"Error fetching app list: {e}"

        candidate_apps = apps_result.get("response", {}).get("apps", [])
        if not candidate_apps:
            return "Could not fetch game catalog."

        # Step 3: Fetch details for candidates in parallel batches
        # Filter to reasonable candidates first (exclude source games)
        candidates = [a for a in candidate_apps if a.get("appid") not in source_app_ids][:500]

        # Fetch details in batches of 50 (Store API limit)
        async def fetch_app_details(appid: int) -> dict[str, Any] | None:
            try:
                result = await self.client.get_store_api(
                    "appdetails",
                    params={"appids": str(appid), "l": "english"},
                )
                app_data = result.get(str(appid), {})
                if app_data.get("success"):
                    data: dict[str, Any] = app_data.get("data", {})
                    return data
            except Exception:
                pass
            return None

        # Score candidates by fetching their details
        scored_games: list[tuple[int, dict[str, Any]]] = []

        # Fetch in smaller batches to respect rate limits
        batch_size = 20
        for i in range(0, min(len(candidates), 200), batch_size):
            batch = candidates[i : i + batch_size]
            tasks = [fetch_app_details(c["appid"]) for c in batch]
            results = await asyncio.gather(*tasks)

            for details in results:
                if not details:
                    continue

                # Calculate similarity score
                game_genres = {g.get("id") for g in details.get("genres", []) if g.get("id")}
                game_categories = {c.get("id") for c in details.get("categories", []) if c.get("id")}

                genre_overlap = len(source_genres & game_genres)
                category_overlap = len(source_categories & game_categories)

                # Weight genres more heavily than categories
                score = (genre_overlap * 3) + category_overlap

                if score > 0:
                    scored_games.append((score, details))

            # Stop early if we have enough high-quality matches
            if len(scored_games) >= max_results * 3:
                break

        if not scored_games:
            return f"No similar games found for: {', '.join(source_names)}"

        # Sort by score descending
        scored_games.sort(key=lambda x: x[0], reverse=True)

        # Format output
        if len(source_names) == 1:
            header = f"Games similar to '{source_names[0]}':"
        else:
            header = f"Games similar to: {', '.join(source_names)}"

        output = [header, ""]

        for _score, game in scored_games[:max_results]:
            name = game.get("name", "Unknown")
            gid = game.get("steam_appid", "?")
            is_free = game.get("is_free", False)

            price_info = game.get("price_overview", {})
            if is_free:
                price_str = "Free"
            elif price_info:
                price_str = price_info.get("final_formatted", "")
            else:
                price_str = ""

            genres = [g.get("description", "") for g in game.get("genres", [])][:3]
            genre_str = ", ".join(genres) if genres else ""

            line = f"  [{gid}] {name}"
            if price_str:
                line += f" - {price_str}"
            if genre_str:
                line += f" ({genre_str})"
            output.append(line)

        output.append("")
        if len(source_names) == 1:
            output.append(f"Based on shared genres with '{source_names[0]}'")
        else:
            output.append(f"Based on shared genres across {len(source_names)} games")

        if failed_ids:
            output.append(f"Note: Could not find app IDs: {failed_ids}")

        return "\n".join(output)

    @endpoint(
        name="get_game_reviews",
        description=(
            "Get user reviews for one or more Steam games. "
            "Returns review scores (e.g., 'Mostly Positive'), statistics, and sample reviews. "
            "Supports summary or detailed view modes."
        ),
        params={
            "app_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of Steam App IDs to get reviews for",
                "required": True,
            },
            "view_mode": {
                "type": "string",
                "enum": ["summary", "standard", "detailed"],
                "description": (
                    "Level of detail: 'summary' (scores only), "
                    "'standard' (scores + 3 reviews), 'detailed' (scores + 10 reviews with full text)"
                ),
                "required": False,
                "default": "standard",
            },
            "review_type": {
                "type": "string",
                "enum": ["all", "positive", "negative"],
                "description": "Filter by recommendation type",
                "required": False,
                "default": "all",
            },
            "language": {
                "type": "string",
                "description": "Language filter (e.g., 'english', 'all')",
                "required": False,
                "default": "english",
            },
        },
    )
    async def get_game_reviews(
        self,
        app_ids: list[int],
        view_mode: str = "standard",
        review_type: str = "all",
        language: str = "english",
    ) -> str:
        """Get user reviews for Steam games."""
        if not app_ids:
            return "Error: At least one app ID is required."

        # Deduplicate
        app_ids = list(dict.fromkeys(app_ids))

        # Validate view_mode
        valid_modes = ("summary", "standard", "detailed")
        if view_mode not in valid_modes:
            view_mode = "standard"

        # Determine number of reviews to fetch based on view mode
        reviews_per_game = {"summary": 0, "standard": 3, "detailed": 10}[view_mode]

        async def fetch_reviews(appid: int) -> tuple[int, dict[str, Any] | None]:
            """Fetch reviews for a single app."""
            try:
                # Use store API for reviews (no auth required)
                url = f"https://store.steampowered.com/appreviews/{appid}"
                params = {
                    "json": "1",
                    "filter": "all",  # Sort by helpfulness
                    "language": language,
                    "review_type": review_type,
                    "purchase_type": "all",
                    "num_per_page": max(1, reviews_per_game),
                    "filter_offtopic_activity": "1",  # Exclude review bombs
                }
                result = await self.client.get_raw(url, params=params)
                if result.get("success") == 1:
                    return (appid, result)
            except Exception:
                pass
            return (appid, None)

        # Fetch all reviews in parallel
        results = await asyncio.gather(*[fetch_reviews(aid) for aid in app_ids])

        output: list[str] = []
        failed_ids: list[int] = []

        for appid, data in results:
            if not data:
                failed_ids.append(appid)
                continue

            query = data.get("query_summary", {})
            reviews = data.get("reviews", [])

            # Extract summary stats
            total_reviews = query.get("total_reviews", 0)
            total_positive = query.get("total_positive", 0)
            total_negative = query.get("total_negative", 0)
            score_desc = query.get("review_score_desc", "No Reviews")

            # Calculate percentage
            if total_reviews > 0:
                positive_pct = round((total_positive / total_reviews) * 100)
            else:
                positive_pct = 0

            # Game header
            output.append(f"=== App {appid} ===")
            output.append(f"Rating: {score_desc}")
            output.append(f"Reviews: {total_reviews:,} ({positive_pct}% positive)")
            output.append(f"  Positive: {total_positive:,} | Negative: {total_negative:,}")

            # Add reviews based on view mode
            if view_mode != "summary" and reviews:
                output.append("")
                output.append("Sample Reviews:")

                for i, review in enumerate(reviews[:reviews_per_game]):
                    author = review.get("author", {})
                    voted_up = review.get("voted_up", False)
                    text = review.get("review", "").strip()
                    votes_up = review.get("votes_up", 0)
                    playtime = author.get("playtime_forever", 0)
                    playtime_hrs = round(playtime / 60, 1)

                    # Truncate text based on view mode
                    max_len = 200 if view_mode == "standard" else 500

                    if len(text) > max_len:
                        text = text[:max_len].rsplit(" ", 1)[0] + "..."

                    recommendation = "👍 Recommended" if voted_up else "👎 Not Recommended"
                    output.append(f"  [{i + 1}] {recommendation}")
                    output.append(f"      Playtime: {playtime_hrs}h | Helpful: {votes_up}")

                    # Format review text with indentation
                    if text:
                        # Split into lines for readability
                        words = text.split()
                        lines: list[str] = []
                        current_line = "      "
                        for word in words:
                            if len(current_line) + len(word) + 1 > 80:
                                lines.append(current_line)
                                current_line = "      " + word
                            else:
                                current_line += (" " if current_line.strip() else "") + word
                        if current_line.strip():
                            lines.append(current_line)
                        output.extend(lines)
                    output.append("")

            output.append("")

        if failed_ids:
            output.append(f"Note: Could not fetch reviews for app IDs: {failed_ids}")

        if not output or all(aid in failed_ids for aid in app_ids):
            return f"Could not fetch reviews for any of the provided app IDs: {app_ids}"

        return "\n".join(output).strip()

    # =========================================================================
    # Aggregate Endpoint: Full Game Details
    # =========================================================================

    @dataclass
    class _AppDetails:
        """Parsed app details from Store API."""

        name: str
        app_id: int
        app_type: str
        is_free: bool
        short_description: str
        developers: list[str]
        publishers: list[str]
        release_date: str
        price_str: str
        platforms: list[str]
        genres: list[str]
        categories: list[str]
        metacritic_score: int | None

    @dataclass
    class _ReviewSummary:
        """Parsed review summary from reviews API."""

        total_reviews: int
        total_positive: int
        total_negative: int
        positive_pct: int
        score_desc: str
        sample_reviews: list[dict[str, Any]]

    @dataclass
    class _AchievementSummary:
        """Parsed achievement data."""

        total_count: int
        rarest: list[tuple[str, float]]  # (name, percent)
        most_common: list[tuple[str, float]]

    @dataclass
    class _NewsSummary:
        """Parsed news data."""

        items: list[dict[str, Any]]

    async def _fetch_app_details(self, app_id: int) -> "_AppDetails | None":
        """Fetch and parse app details from Store API."""
        try:
            result = await self.client.get_store_api(
                "appdetails",
                params={"appids": str(app_id), "cc": "us", "l": "english"},
            )
        except Exception:
            return None

        app_data = result.get(str(app_id), {})
        if not app_data.get("success"):
            return None

        data = app_data.get("data", {})
        if not data:
            return None

        # Parse price
        is_free = data.get("is_free", False)
        price_info = data.get("price_overview", {})
        if is_free:
            price_str = "Free to Play"
        elif price_info:
            price_str = price_info.get("final_formatted", "Unknown")
            if price_info.get("discount_percent", 0) > 0:
                discount = price_info["discount_percent"]
                original = price_info.get("initial_formatted", "")
                price_str = f"{price_str} ({discount}% off, was {original})"
        else:
            price_str = "Price not available"

        # Parse release date
        release_info = data.get("release_date", {})
        if release_info.get("coming_soon"):
            release_date = "Coming Soon"
        else:
            release_date = release_info.get("date", "Unknown")

        # Parse platforms
        platforms = data.get("platforms", {})
        platform_list = []
        if platforms.get("windows"):
            platform_list.append("Windows")
        if platforms.get("mac"):
            platform_list.append("macOS")
        if platforms.get("linux"):
            platform_list.append("Linux")

        return ISteamApps._AppDetails(
            name=data.get("name", f"App {app_id}"),
            app_id=app_id,
            app_type=data.get("type", "unknown"),
            is_free=is_free,
            short_description=data.get("short_description", ""),
            developers=data.get("developers", []),
            publishers=data.get("publishers", []),
            release_date=release_date,
            price_str=price_str,
            platforms=platform_list,
            genres=[g.get("description", "") for g in data.get("genres", [])],
            categories=[c.get("description", "") for c in data.get("categories", [])],
            metacritic_score=data.get("metacritic", {}).get("score"),
        )

    async def _fetch_review_summary(
        self, app_id: int, num_reviews: int = 3
    ) -> "_ReviewSummary | None":
        """Fetch and parse review summary."""
        try:
            url = f"https://store.steampowered.com/appreviews/{app_id}"
            result = await self.client.get_raw(
                url,
                params={
                    "json": "1",
                    "filter": "all",
                    "language": "english",
                    "review_type": "all",
                    "purchase_type": "all",
                    "num_per_page": max(1, num_reviews),
                    "filter_offtopic_activity": "1",
                },
            )
            if result.get("success") != 1:
                return None
        except Exception:
            return None

        query = result.get("query_summary", {})
        total_reviews = query.get("total_reviews", 0)
        total_positive = query.get("total_positive", 0)
        total_negative = query.get("total_negative", 0)
        positive_pct = (
            round((total_positive / total_reviews) * 100) if total_reviews > 0 else 0
        )

        # Parse sample reviews
        sample_reviews: list[dict[str, Any]] = []
        for review in result.get("reviews", [])[:num_reviews]:
            author = review.get("author", {})
            sample_reviews.append({
                "voted_up": review.get("voted_up", False),
                "text": review.get("review", "").strip()[:200],
                "playtime_hours": round(author.get("playtime_forever", 0) / 60, 1),
                "helpful_votes": review.get("votes_up", 0),
            })

        return ISteamApps._ReviewSummary(
            total_reviews=total_reviews,
            total_positive=total_positive,
            total_negative=total_negative,
            positive_pct=positive_pct,
            score_desc=query.get("review_score_desc", "No Reviews"),
            sample_reviews=sample_reviews,
        )

    async def _fetch_player_count(self, app_id: int) -> int | None:
        """Fetch current player count from ISteamUserStats."""
        try:
            result = await self.client.get(
                "ISteamUserStats",
                "GetNumberOfCurrentPlayers",
                version=1,
                params={"appid": app_id},
            )
            response = result.get("response", {})
            if response.get("result") == 1:
                player_count: int | None = response.get("player_count")
                return player_count
        except Exception:
            pass
        return None

    async def _fetch_achievement_summary(
        self, app_id: int
    ) -> "_AchievementSummary | None":
        """Fetch global achievement percentages."""
        try:
            result = await self.client.get(
                "ISteamUserStats",
                "GetGlobalAchievementPercentagesForApp",
                version=2,
                params={"gameid": app_id},
            )
        except Exception:
            return None

        achievement_data = result.get("achievementpercentages", {})
        achievements = achievement_data.get("achievements", [])

        if not achievements:
            return None

        # Sort by percentage (convert to float as API may return strings)
        achievements_sorted = sorted(
            achievements, key=lambda a: float(a.get("percent", 0))
        )

        # Extract rarest and most common
        rarest = [
            (a.get("name", "Unknown"), round(float(a.get("percent", 0)), 1))
            for a in achievements_sorted[:5]
        ]
        most_common = [
            (a.get("name", "Unknown"), round(float(a.get("percent", 0)), 1))
            for a in reversed(achievements_sorted[-3:])
        ]

        return ISteamApps._AchievementSummary(
            total_count=len(achievements),
            rarest=rarest,
            most_common=most_common,
        )

    async def _fetch_news_summary(
        self, app_id: int, count: int = 3
    ) -> "_NewsSummary | None":
        """Fetch recent news for an app."""
        try:
            result = await self.client.get(
                "ISteamNews",
                "GetNewsForApp",
                version=2,
                params={"appid": app_id, "count": count, "maxlength": 200},
            )
        except Exception:
            return None

        appnews = result.get("appnews", {})
        news_items = appnews.get("newsitems", [])

        if not news_items:
            return None

        # Parse news items
        items: list[dict[str, Any]] = []
        for item in news_items[:count]:
            title = item.get("title", "Untitled")
            date_ts = item.get("date", 0)
            date_str = (
                datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d")
                if date_ts
                else "Unknown"
            )
            contents = item.get("contents", "")
            # Clean HTML
            clean = re.sub(r"<[^>]+>", " ", contents)
            clean = re.sub(r"\s+", " ", clean).strip()[:150]

            items.append({
                "title": title,
                "date": date_str,
                "excerpt": clean,
                "url": item.get("url", ""),
            })

        return ISteamApps._NewsSummary(items=items)

    @endpoint(
        name="get_full_game_details",
        description=(
            "Get comprehensive details for a Steam game in a single call. "
            "Combines app details, user reviews, current player count, "
            "achievement statistics, and recent news. "
            "Ideal for getting a complete overview of a game."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game",
                "required": True,
            },
            "include_reviews": {
                "type": "boolean",
                "description": "Include review summary and sample reviews",
                "required": False,
                "default": True,
            },
            "include_achievements": {
                "type": "boolean",
                "description": "Include achievement statistics",
                "required": False,
                "default": True,
            },
            "include_news": {
                "type": "boolean",
                "description": "Include recent news articles",
                "required": False,
                "default": True,
            },
            "num_sample_reviews": {
                "type": "integer",
                "description": "Number of sample reviews to include (1-5)",
                "required": False,
                "default": 3,
                "minimum": 1,
                "maximum": 5,
            },
            "num_news_items": {
                "type": "integer",
                "description": "Number of news items to include (1-5)",
                "required": False,
                "default": 3,
                "minimum": 1,
                "maximum": 5,
            },
        },
    )
    async def get_full_game_details(
        self,
        app_id: int,
        include_reviews: bool = True,
        include_achievements: bool = True,
        include_news: bool = True,
        num_sample_reviews: int = 3,
        num_news_items: int = 3,
    ) -> str:
        """Get comprehensive game details in a single call."""
        # Clamp parameters
        num_sample_reviews = max(1, min(num_sample_reviews, 5))
        num_news_items = max(1, min(num_news_items, 5))

        # Build list of async tasks to run in parallel
        tasks: dict[str, Any] = {
            "details": self._fetch_app_details(app_id),
            "player_count": self._fetch_player_count(app_id),
        }
        if include_reviews:
            tasks["reviews"] = self._fetch_review_summary(app_id, num_sample_reviews)
        if include_achievements:
            tasks["achievements"] = self._fetch_achievement_summary(app_id)
        if include_news:
            tasks["news"] = self._fetch_news_summary(app_id, num_news_items)

        # Execute all tasks in parallel
        task_keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        data: dict[str, Any] = {}
        for i, key in enumerate(task_keys):
            result = results[i]
            if isinstance(result, Exception):
                data[key] = None
            else:
                data[key] = result

        # Check if we got app details (required)
        details: ISteamApps._AppDetails | None = data.get("details")
        if not details:
            return f"Could not fetch details for App ID {app_id}. Game may not exist."

        # Build output
        output: list[str] = []

        # === Header ===
        output.append(f"{'=' * 60}")
        output.append(f"{details.name}")
        output.append(f"{'=' * 60}")
        output.append("")

        # === Basic Info ===
        output.append("BASIC INFO")
        output.append(f"  App ID: {details.app_id}")
        output.append(f"  Type: {details.app_type.title()}")
        output.append(f"  Developer: {', '.join(details.developers) or 'Unknown'}")
        output.append(f"  Publisher: {', '.join(details.publishers) or 'Unknown'}")
        output.append(f"  Release Date: {details.release_date}")
        output.append(f"  Price: {details.price_str}")
        output.append(f"  Platforms: {', '.join(details.platforms) or 'Unknown'}")
        if details.genres:
            output.append(f"  Genres: {', '.join(details.genres)}")
        if details.metacritic_score:
            output.append(f"  Metacritic: {details.metacritic_score}")
        output.append("")

        # === Current Players ===
        player_count: int | None = data.get("player_count")
        output.append("CURRENT PLAYERS")
        if player_count is not None:
            output.append(f"  {player_count:,} playing now")
        else:
            output.append("  Player count unavailable")
        output.append("")

        # === Reviews ===
        if include_reviews:
            reviews: ISteamApps._ReviewSummary | None = data.get("reviews")
            output.append("USER REVIEWS")
            if reviews:
                output.append(f"  Rating: {reviews.score_desc}")
                output.append(
                    f"  Total: {reviews.total_reviews:,} reviews "
                    f"({reviews.positive_pct}% positive)"
                )
                output.append(
                    f"  Breakdown: {reviews.total_positive:,} positive / "
                    f"{reviews.total_negative:,} negative"
                )
                if reviews.sample_reviews:
                    output.append("")
                    output.append("  Sample Reviews:")
                    for rev in reviews.sample_reviews:
                        rec = "+" if rev["voted_up"] else "-"
                        text = rev["text"]
                        if len(text) > 150:
                            text = text[:150].rsplit(" ", 1)[0] + "..."
                        output.append(
                            f"    [{rec}] ({rev['playtime_hours']}h) {text}"
                        )
            else:
                output.append("  No review data available")
            output.append("")

        # === Achievements ===
        if include_achievements:
            achievements: ISteamApps._AchievementSummary | None = data.get(
                "achievements"
            )
            output.append("ACHIEVEMENTS")
            if achievements:
                output.append(f"  Total: {achievements.total_count} achievements")
                output.append("")
                output.append("  Rarest:")
                for name, pct in achievements.rarest:
                    if pct < 1:
                        rarity = "ULTRA RARE"
                    elif pct < 5:
                        rarity = "VERY RARE"
                    elif pct < 10:
                        rarity = "RARE"
                    else:
                        rarity = ""
                    rarity_tag = f" [{rarity}]" if rarity else ""
                    output.append(f"    {pct:5.1f}% - {name}{rarity_tag}")
                output.append("")
                output.append("  Most Common:")
                for name, pct in achievements.most_common:
                    output.append(f"    {pct:5.1f}% - {name}")
            else:
                output.append("  No achievement data available")
            output.append("")

        # === News ===
        if include_news:
            news: ISteamApps._NewsSummary | None = data.get("news")
            output.append("RECENT NEWS")
            if news and news.items:
                for item in news.items:
                    output.append(f"  [{item['date']}] {item['title']}")
                    if item["excerpt"]:
                        output.append(f"    {item['excerpt']}...")
            else:
                output.append("  No recent news")
            output.append("")

        # === Description ===
        if details.short_description:
            output.append("DESCRIPTION")
            # Wrap description text
            desc = details.short_description
            words = desc.split()
            lines: list[str] = []
            current_line = "  "
            for word in words:
                if len(current_line) + len(word) + 1 > 75:
                    lines.append(current_line)
                    current_line = "  " + word
                else:
                    current_line += (" " if current_line.strip() else "") + word
            if current_line.strip():
                lines.append(current_line)
            output.extend(lines)
            output.append("")

        # === Store Link ===
        output.append(f"Store: https://store.steampowered.com/app/{app_id}")

        return "\n".join(output)
