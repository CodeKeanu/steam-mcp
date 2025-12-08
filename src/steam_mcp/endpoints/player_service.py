"""IPlayerService API endpoints.

This module provides MCP tools for the IPlayerService Steam API interface,
which handles player game libraries, playtime, badges, and Steam level.

Reference: https://partner.steamgames.com/doc/webapi/IPlayerService
"""

import asyncio
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint
from steam_mcp.utils.steam_id import normalize_steam_id, SteamIDError


# Default games to display in detailed output
DEFAULT_GAMES_DISPLAY = 25


class IPlayerService(BaseEndpoint):
    """IPlayerService API endpoints for player game data and stats."""

    @endpoint(
        name="get_owned_games",
        description=(
            "Get a player's owned games with playtime information. "
            "Returns game names, App IDs, and total playtime. "
            "Note: Only works for public profiles unless querying your own profile."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format. Use 'me' or 'my' to query your own profile "
                    "(requires STEAM_USER_ID to be configured)."
                ),
                "required": True,
            },
            "include_free_games": {
                "type": "boolean",
                "description": "Include free-to-play games like TF2, Dota 2, etc.",
                "required": False,
                "default": True,
            },
            "sort_by": {
                "type": "string",
                "description": "Sort games by: 'playtime' (most played first), 'name' (alphabetical), or 'recent' (recently played first)",
                "required": False,
                "default": "playtime",
                "enum": ["playtime", "name", "recent"],
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of games to display in output. Use 0 for all games. Default is 25.",
                "required": False,
                "default": 25,
                "minimum": 0,
            },
        },
    )
    async def get_owned_games(
        self,
        steam_id: str,
        include_free_games: bool = True,
        sort_by: str = "playtime",
        limit: int = 25,
    ) -> str:
        """Get owned games for a Steam user."""
        # Handle "me" / "my" shortcut
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        result = await self.client.get(
            "IPlayerService",
            "GetOwnedGames",
            version=1,
            params={
                "steamid": normalized_id,
                "include_appinfo": True,
                "include_played_free_games": include_free_games,
            },
        )

        response = result.get("response", {})
        games = response.get("games", [])
        game_count = response.get("game_count", len(games))

        if not games:
            return (
                f"No games found for Steam ID {normalized_id}.\n"
                "This may indicate a private profile or an account with no games."
            )

        # Sort games
        if sort_by == "playtime":
            games.sort(key=lambda g: g.get("playtime_forever", 0), reverse=True)
        elif sort_by == "name":
            games.sort(key=lambda g: g.get("name", "").lower())
        elif sort_by == "recent":
            games.sort(key=lambda g: g.get("rtime_last_played", 0), reverse=True)

        # Calculate total playtime
        total_minutes = sum(g.get("playtime_forever", 0) for g in games)
        total_hours = total_minutes / 60

        # Determine display limit (0 = show all)
        display_limit = limit if limit > 0 else len(games)

        output = [
            f"Game Library for {normalized_id}",
            f"Total Games: {game_count}",
            f"Total Playtime: {total_hours:,.1f} hours",
            "",
        ]

        if display_limit < len(games):
            output.append(f"Top {display_limit} games (sorted by {sort_by}):")
        else:
            output.append(f"All games (sorted by {sort_by}):")
        output.append("")

        for game in games[:display_limit]:
            name = game.get("name", f"App {game.get('appid', 'Unknown')}")
            appid = game.get("appid", "?")
            playtime_mins = game.get("playtime_forever", 0)
            playtime_hours = playtime_mins / 60

            # Format playtime
            if playtime_hours >= 1:
                playtime_str = f"{playtime_hours:,.1f}h"
            elif playtime_mins > 0:
                playtime_str = f"{playtime_mins}m"
            else:
                playtime_str = "Never played"

            # Recent playtime (last 2 weeks)
            recent_mins = game.get("playtime_2weeks", 0)
            recent_str = ""
            if recent_mins > 0:
                recent_hours = recent_mins / 60
                if recent_hours >= 1:
                    recent_str = f" (recent: {recent_hours:.1f}h)"
                else:
                    recent_str = f" (recent: {recent_mins}m)"

            output.append(f"  [{appid}] {name}: {playtime_str}{recent_str}")

        if len(games) > display_limit:
            output.append(f"\n  ... and {len(games) - display_limit} more games")

        return "\n".join(output)

    @endpoint(
        name="get_recently_played_games",
        description=(
            "Get games a player has played in the last 2 weeks. "
            "Shows recent playtime and total playtime for each game."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format. Use 'me' or 'my' to query your own profile."
                ),
                "required": True,
            },
            "count": {
                "type": "integer",
                "description": "Maximum number of games to return (0 = all)",
                "required": False,
                "default": 0,
                "minimum": 0,
            },
        },
    )
    async def get_recently_played_games(
        self,
        steam_id: str,
        count: int = 0,
    ) -> str:
        """Get recently played games for a Steam user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        params: dict[str, Any] = {"steamid": normalized_id}
        if count > 0:
            params["count"] = count

        result = await self.client.get(
            "IPlayerService",
            "GetRecentlyPlayedGames",
            version=1,
            params=params,
        )

        response = result.get("response", {})
        games = response.get("games", [])
        total_count = response.get("total_count", len(games))

        if not games:
            return (
                f"No recently played games for Steam ID {normalized_id}.\n"
                "This user hasn't played any games in the last 2 weeks, "
                "or their profile is private."
            )

        # Calculate total recent playtime
        total_recent_mins = sum(g.get("playtime_2weeks", 0) for g in games)
        total_recent_hours = total_recent_mins / 60

        output = [
            f"Recently Played Games for {normalized_id}",
            f"Games played in last 2 weeks: {total_count}",
            f"Total recent playtime: {total_recent_hours:,.1f} hours",
            "",
        ]

        for game in games:
            name = game.get("name", f"App {game.get('appid', 'Unknown')}")
            appid = game.get("appid", "?")

            recent_mins = game.get("playtime_2weeks", 0)
            recent_hours = recent_mins / 60

            total_mins = game.get("playtime_forever", 0)
            total_hours = total_mins / 60

            output.append(
                f"  [{appid}] {name}\n"
                f"       Last 2 weeks: {recent_hours:.1f}h | "
                f"Total: {total_hours:,.1f}h"
            )

        return "\n".join(output)

    @endpoint(
        name="get_steam_level",
        description="Get a player's Steam level.",
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
    async def get_steam_level(self, steam_id: str) -> str:
        """Get Steam level for a user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        result = await self.client.get(
            "IPlayerService",
            "GetSteamLevel",
            version=1,
            params={"steamid": normalized_id},
        )

        response = result.get("response", {})
        level = response.get("player_level")

        if level is None:
            return (
                f"Could not retrieve Steam level for {normalized_id}.\n"
                "This profile may be private."
            )

        # Provide some context on the level
        if level < 10:
            tier = "Newcomer"
        elif level < 25:
            tier = "Regular"
        elif level < 50:
            tier = "Experienced"
        elif level < 100:
            tier = "Veteran"
        elif level < 200:
            tier = "Elite"
        else:
            tier = "Legendary"

        return f"Steam Level for {normalized_id}: {level} ({tier})"

    async def _resolve_steam_id(self, steam_id: str) -> str:
        """
        Resolve steam_id, handling 'me'/'my' shortcuts.

        Returns:
            Normalized SteamID64 or error message starting with "Error"
        """
        # Handle "me" / "my" shortcuts
        steam_id_lower = steam_id.strip().lower()
        if steam_id_lower in ("me", "my", "myself", "mine"):
            if not self.client.owner_steam_id:
                return (
                    "Error: No owner Steam ID configured. "
                    "Set STEAM_USER_ID environment variable to use 'me'/'my' shortcuts."
                )
            return self.client.owner_steam_id

        try:
            return await normalize_steam_id(steam_id, self.client)
        except SteamIDError as e:
            return f"Error resolving Steam ID: {e}"

    async def _fetch_games_raw(
        self, steam_id: str, include_free: bool = True
    ) -> list[dict[str, Any]]:
        """Fetch raw games list for a Steam ID (internal helper)."""
        result = await self.client.get(
            "IPlayerService",
            "GetOwnedGames",
            version=1,
            params={
                "steamid": steam_id,
                "include_appinfo": True,
                "include_played_free_games": include_free,
            },
        )
        return result.get("response", {}).get("games", [])

    @endpoint(
        name="find_unplayed_games_with_friends",
        description=(
            "Find games you and your friends all own but none have played. "
            "Perfect for finding co-op games to try together."
        ),
        params={
            "my_steam_id": {
                "type": "string",
                "description": "Your Steam ID (any format, or 'me')",
                "required": True,
            },
            "friend_steam_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of friend Steam IDs to compare against",
                "required": True,
            },
            "include_free_games": {
                "type": "boolean",
                "description": "Include free-to-play games (default: false)",
                "required": False,
            },
        },
    )
    async def find_unplayed_games_with_friends(
        self,
        my_steam_id: str,
        friend_steam_ids: list[str],
        include_free_games: bool = False,
    ) -> str:
        """Find games all users own but none have played."""
        if not friend_steam_ids:
            return "Error: Provide at least one friend Steam ID"

        # Resolve all Steam IDs
        my_id = await self._resolve_steam_id(my_steam_id)
        if my_id.startswith("Error"):
            return my_id

        friend_ids: list[str] = []
        errors: list[str] = []
        for fid in friend_steam_ids:
            resolved = await self._resolve_steam_id(fid)
            if resolved.startswith("Error"):
                errors.append(f"  - {fid}: {resolved}")
            elif resolved == my_id:
                errors.append(f"  - {fid}: Cannot compare with yourself")
            else:
                friend_ids.append(resolved)

        if not friend_ids:
            return "Error: No valid friend IDs:\n" + "\n".join(errors)

        # Fetch all libraries in parallel
        all_ids = [my_id] + friend_ids
        try:
            all_games = await asyncio.gather(
                *[self._fetch_games_raw(sid, include_free_games) for sid in all_ids]
            )
        except Exception as e:
            return f"Error fetching game libraries: {e}"

        my_games = all_games[0]
        friend_games_list = all_games[1:]

        if not my_games:
            return f"No games found for your profile ({my_id}). Profile may be private."

        # Build lookup for each friend: {appid: playtime}
        friend_lookups: list[dict[int, int]] = []
        for i, games in enumerate(friend_games_list):
            if not games:
                errors.append(f"  - {friend_ids[i]}: No games (private profile?)")
                continue
            friend_lookups.append({
                g["appid"]: g.get("playtime_forever", 0) for g in games
            })

        if not friend_lookups:
            return "Error: Could not fetch any friend libraries:\n" + "\n".join(errors)

        # Find shared unplayed games
        shared_unplayed: list[dict[str, Any]] = []
        for game in my_games:
            appid = game["appid"]
            my_playtime = game.get("playtime_forever", 0)

            # Check if ALL friends own this game
            all_own = all(appid in fl for fl in friend_lookups)
            if not all_own:
                continue

            # Check if NOBODY has played (me + all friends)
            friend_playtimes = [fl[appid] for fl in friend_lookups]
            if my_playtime == 0 and all(pt == 0 for pt in friend_playtimes):
                shared_unplayed.append(game)

        # Format output
        num_friends = len(friend_lookups)
        output = [f"Comparing your library with {num_friends} friend(s)...", ""]

        if shared_unplayed:
            shared_unplayed.sort(key=lambda g: g.get("name", "").lower())
            output.append(f"Found {len(shared_unplayed)} unplayed games you all own:")
            output.append("")
            for game in shared_unplayed[:50]:
                name = game.get("name", f"App {game['appid']}")
                output.append(f"  [{game['appid']}] {name}")
            if len(shared_unplayed) > 50:
                output.append(f"  ... and {len(shared_unplayed) - 50} more")
        else:
            # Count shared games for context
            shared_count = sum(
                1 for g in my_games
                if all(g["appid"] in fl for fl in friend_lookups)
            )
            output.append("No unplayed shared games found.")
            output.append(f"  - Games you all own: {shared_count}")
            output.append("  - All have been played by at least one person")

        if errors:
            output.append("")
            output.append("Warnings:")
            output.extend(errors)

        return "\n".join(output)
