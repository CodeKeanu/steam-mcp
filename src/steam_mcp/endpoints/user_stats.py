"""ISteamUserStats API endpoints.

This module provides MCP tools for the ISteamUserStats Steam API interface,
which handles achievements, game stats, and global achievement percentages.

Reference: https://partner.steamgames.com/doc/webapi/ISteamUserStats
"""

from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint
from steam_mcp.utils.steam_id import normalize_steam_id, SteamIDError


# Maximum achievements to display in detailed output
MAX_ACHIEVEMENTS_DISPLAY = 30


class ISteamUserStats(BaseEndpoint):
    """ISteamUserStats API endpoints for achievements and game statistics."""

    @endpoint(
        name="get_player_achievements",
        description=(
            "Get a player's achievement progress for a specific game. "
            "Shows which achievements are unlocked and when. "
            "Note: Requires the player's game details to be public."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format. Use 'me' or 'my' to query your own profile."
                ),
                "required": True,
            },
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game (e.g., 440 for TF2, 730 for CS2)",
                "required": True,
            },
            "language": {
                "type": "string",
                "description": "Language for achievement names/descriptions (e.g., 'english', 'german', 'french')",
                "required": False,
                "default": "english",
            },
        },
    )
    async def get_player_achievements(
        self,
        steam_id: str,
        app_id: int,
        language: str = "english",
    ) -> str:
        """Get player achievements for a specific game."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "ISteamUserStats",
                "GetPlayerAchievements",
                version=1,
                params={
                    "steamid": normalized_id,
                    "appid": app_id,
                    "l": language.lower(),
                },
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "profile is not public" in error_msg or "private" in error_msg:
                return (
                    f"Cannot access achievements for Steam ID {normalized_id}.\n"
                    "This player's game details are set to private."
                )
            raise

        playerstats = result.get("playerstats", {})

        if not playerstats.get("success", False):
            return (
                f"Could not retrieve achievements for App ID {app_id}.\n"
                "The game may not have achievements or the profile is private."
            )

        game_name = playerstats.get("gameName", f"App {app_id}")
        achievements = playerstats.get("achievements", [])

        if not achievements:
            return f"No achievements found for {game_name}."

        # Count unlocked
        unlocked = [a for a in achievements if a.get("achieved", 0) == 1]
        locked = [a for a in achievements if a.get("achieved", 0) == 0]

        completion_pct = (len(unlocked) / len(achievements)) * 100 if achievements else 0

        output = [
            f"Achievements for {game_name}",
            f"Player: {normalized_id}",
            f"Progress: {len(unlocked)}/{len(achievements)} ({completion_pct:.1f}%)",
            "",
        ]

        # Show unlocked achievements first (most recent first by unlock time)
        if unlocked:
            unlocked_sorted = sorted(
                unlocked,
                key=lambda a: a.get("unlocktime", 0),
                reverse=True
            )
            output.append(f"Unlocked ({len(unlocked)}):")
            for ach in unlocked_sorted[:MAX_ACHIEVEMENTS_DISPLAY]:
                name = ach.get("name", ach.get("apiname", "Unknown"))
                desc = ach.get("description", "")
                unlock_time = ach.get("unlocktime", 0)

                if unlock_time:
                    from datetime import datetime
                    unlock_str = datetime.fromtimestamp(unlock_time).strftime("%Y-%m-%d")
                else:
                    unlock_str = "Unknown date"

                if desc:
                    output.append(f"  ✓ {name} - {desc} [{unlock_str}]")
                else:
                    output.append(f"  ✓ {name} [{unlock_str}]")

            if len(unlocked) > MAX_ACHIEVEMENTS_DISPLAY:
                output.append(f"  ... and {len(unlocked) - MAX_ACHIEVEMENTS_DISPLAY} more unlocked")
            output.append("")

        # Show a few locked achievements
        if locked:
            output.append(f"Locked ({len(locked)}):")
            for ach in locked[:10]:
                name = ach.get("name", ach.get("apiname", "Unknown"))
                desc = ach.get("description", "")

                if desc:
                    output.append(f"  ○ {name} - {desc}")
                else:
                    output.append(f"  ○ {name}")

            if len(locked) > 10:
                output.append(f"  ... and {len(locked) - 10} more locked")

        return "\n".join(output)

    @endpoint(
        name="get_game_schema",
        description=(
            "Get achievement definitions and stats schema for a game. "
            "Returns achievement names, descriptions, icons, and hidden status. "
            "Useful for understanding what achievements exist before querying player progress."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game",
                "required": True,
            },
            "language": {
                "type": "string",
                "description": "Language for localized text",
                "required": False,
                "default": "english",
            },
        },
    )
    async def get_game_schema(
        self,
        app_id: int,
        language: str = "english",
    ) -> str:
        """Get achievement schema for a game."""
        result = await self.client.get(
            "ISteamUserStats",
            "GetSchemaForGame",
            version=2,
            params={
                "appid": app_id,
                "l": language.lower(),
            },
        )

        game = result.get("game", {})

        if not game:
            return f"No schema found for App ID {app_id}. The game may not exist or have no stats."

        game_name = game.get("gameName", f"App {app_id}")
        available_stats = game.get("availableGameStats", {})

        achievements = available_stats.get("achievements", [])
        stats = available_stats.get("stats", [])

        output = [
            f"Game Schema: {game_name}",
            f"App ID: {app_id}",
            "",
        ]

        if achievements:
            hidden_count = sum(1 for a in achievements if a.get("hidden", 0) == 1)
            output.append(f"Achievements: {len(achievements)} total ({hidden_count} hidden)")
            output.append("")

            for ach in achievements[:MAX_ACHIEVEMENTS_DISPLAY]:
                name = ach.get("displayName", ach.get("name", "Unknown"))
                desc = ach.get("description", "")
                hidden = ach.get("hidden", 0) == 1

                hidden_tag = " [HIDDEN]" if hidden else ""
                if desc:
                    output.append(f"  • {name}{hidden_tag}: {desc}")
                else:
                    output.append(f"  • {name}{hidden_tag}")

            if len(achievements) > MAX_ACHIEVEMENTS_DISPLAY:
                output.append(f"  ... and {len(achievements) - MAX_ACHIEVEMENTS_DISPLAY} more achievements")
        else:
            output.append("No achievements for this game.")

        if stats:
            output.append("")
            output.append(f"Stats tracked: {len(stats)}")
            for stat in stats[:10]:
                stat_name = stat.get("displayName", stat.get("name", "Unknown"))
                output.append(f"  • {stat_name}")
            if len(stats) > 10:
                output.append(f"  ... and {len(stats) - 10} more stats")

        return "\n".join(output)

    @endpoint(
        name="get_global_achievement_percentages",
        description=(
            "Get global achievement unlock percentages for a game. "
            "Shows what percentage of players have unlocked each achievement. "
            "Useful for finding rare achievements. No API key required."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game",
                "required": True,
            },
        },
    )
    async def get_global_achievement_percentages(self, app_id: int) -> str:
        """Get global achievement percentages for a game."""
        result = await self.client.get(
            "ISteamUserStats",
            "GetGlobalAchievementPercentagesForApp",
            version=2,
            params={"gameid": app_id},
        )

        achievement_data = result.get("achievementpercentages", {})
        achievements = achievement_data.get("achievements", [])

        if not achievements:
            return f"No global achievement data for App ID {app_id}."

        # Sort by percentage (rarest first)
        achievements_sorted = sorted(
            achievements,
            key=lambda a: a.get("percent", 0)
        )

        output = [
            f"Global Achievement Percentages for App ID {app_id}",
            f"Total achievements: {len(achievements)}",
            "",
            "Rarest achievements:",
        ]

        for ach in achievements_sorted[:20]:
            name = ach.get("name", "Unknown")
            percent = ach.get("percent", 0)

            # Visual rarity indicator
            if percent < 1:
                rarity = "🏆"  # Ultra rare
            elif percent < 5:
                rarity = "💎"  # Very rare
            elif percent < 10:
                rarity = "⭐"  # Rare
            else:
                rarity = "  "

            output.append(f"  {rarity} {percent:5.1f}% - {name}")

        if len(achievements) > 20:
            # Show most common as well
            output.append("")
            output.append("Most common achievements:")
            for ach in reversed(achievements_sorted[-5:]):
                name = ach.get("name", "Unknown")
                percent = ach.get("percent", 0)
                output.append(f"     {percent:5.1f}% - {name}")

        return "\n".join(output)

    @endpoint(
        name="get_user_stats_for_game",
        description=(
            "Get a player's statistics for a specific game. "
            "Returns game-specific stats like kills, deaths, playtime, etc. "
            "Stats vary by game."
        ),
        params={
            "steam_id": {
                "type": "string",
                "description": "Steam ID in any format. Use 'me' or 'my' for your profile.",
                "required": True,
            },
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game",
                "required": True,
            },
        },
    )
    async def get_user_stats_for_game(
        self,
        steam_id: str,
        app_id: int,
    ) -> str:
        """Get user stats for a specific game."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "ISteamUserStats",
                "GetUserStatsForGame",
                version=2,
                params={
                    "steamid": normalized_id,
                    "appid": app_id,
                },
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "private" in error_msg:
                return (
                    f"Cannot access stats for Steam ID {normalized_id}.\n"
                    "This player's game details are private."
                )
            raise

        playerstats = result.get("playerstats", {})

        if not playerstats:
            return (
                f"No stats found for App ID {app_id}.\n"
                "The game may not track stats or the profile is private."
            )

        game_name = playerstats.get("gameName", f"App {app_id}")
        stats = playerstats.get("stats", [])
        achievements = playerstats.get("achievements", [])

        output = [
            f"Player Stats for {game_name}",
            f"Steam ID: {normalized_id}",
            "",
        ]

        if stats:
            output.append(f"Statistics ({len(stats)}):")
            for stat in stats[:30]:
                name = stat.get("name", "Unknown")
                value = stat.get("value", 0)

                # Format large numbers with commas
                if isinstance(value, (int, float)):
                    if value >= 1000:
                        value_str = f"{value:,.0f}"
                    elif isinstance(value, float):
                        value_str = f"{value:.2f}"
                    else:
                        value_str = str(value)
                else:
                    value_str = str(value)

                output.append(f"  {name}: {value_str}")

            if len(stats) > 30:
                output.append(f"  ... and {len(stats) - 30} more stats")

        if achievements:
            unlocked = sum(1 for a in achievements if a.get("achieved", 0) == 1)
            output.append("")
            output.append(f"Achievements: {unlocked}/{len(achievements)} unlocked")

        return "\n".join(output)

    async def _resolve_steam_id(self, steam_id: str) -> str:
        """Resolve steam_id, handling 'me'/'my' shortcuts."""
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
