"""ISteamApps and IStoreService API endpoints.

This module provides MCP tools for Steam app/game metadata,
including app lists and version checking.

References:
- https://partner.steamgames.com/doc/webapi/ISteamApps
- https://partner.steamgames.com/doc/webapi/IStoreService
"""

import asyncio
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
                    return app_data.get("data", {})
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

            for j, details in enumerate(results):
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

        for score, game in scored_games[:max_results]:
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
