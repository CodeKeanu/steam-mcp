"""ISteamUser API endpoints.

This module provides MCP tools for the ISteamUser Steam API interface,
which handles player profiles, friends, bans, and identity resolution.

Reference: https://partner.steamgames.com/doc/webapi/ISteamUser
"""

import json
from datetime import datetime
from typing import Any

from steam_mcp.client import SteamAPIError
from steam_mcp.endpoints.base import BaseEndpoint, endpoint
from steam_mcp.utils.steam_id import normalize_steam_id, SteamIDError

# Maximum friends to display in output to avoid overwhelming responses
MAX_FRIENDS_DISPLAY = 50


class ISteamUser(BaseEndpoint):
    """ISteamUser API endpoints for player identity and profile data."""

    async def _resolve_steam_id(self, steam_id: str) -> str:
        """
        Resolve steam_id, handling 'me'/'my' shortcuts.

        Returns:
            Normalized SteamID64 or error message starting with "Error"
        """
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

    @endpoint(
        name="get_my_steam_id",
        description=(
            "Get the Steam ID of the API key owner. This returns the SteamID64 "
            "configured for this MCP server, allowing queries like 'show my profile' "
            "or 'what games do I own' without needing to specify a Steam ID."
        ),
        params={},
    )
    async def get_my_steam_id(self) -> str:
        """Get the configured owner Steam ID."""
        if not self.client.owner_steam_id:
            return (
                "No owner Steam ID configured. To enable 'my profile' queries, "
                "set the STEAM_USER_ID environment variable to your SteamID64.\n\n"
                "You can find your SteamID64 by:\n"
                "1. Using the resolve_vanity_url tool with your profile name\n"
                "2. Visiting https://steamid.io and entering your profile URL"
            )

        owner_id = self.client.owner_steam_id

        # Fetch profile info to provide a richer response
        players = await self.client.get_player_summaries([owner_id])

        if players:
            player = players[0]
            persona_name = player.get("personaname", "Unknown")
            profile_url = player.get("profileurl", "")
            return (
                f"Owner Steam ID configured:\n"
                f"  Display Name: {persona_name}\n"
                f"  SteamID64: {owner_id}\n"
                f"  Profile URL: {profile_url}\n\n"
                "You can now use 'my Steam ID' or reference this ID for other queries."
            )
        else:
            return (
                f"Owner Steam ID: {owner_id}\n"
                "(Could not fetch profile details - ID may be invalid)"
            )

    @endpoint(
        name="get_player_summary",
        description=(
            "Get Steam player profile information including display name, avatar, "
            "online status, and profile visibility. Accepts any Steam ID format "
            "(SteamID64, vanity URL, profile URL, etc.)."
        ),
        supports_json=True,
        params={
            "steam_id": {
                "type": "string",
                "description": (
                    "Steam ID in any format: SteamID64 (76561198000000000), "
                    "vanity URL (https://steamcommunity.com/id/username), "
                    "profile URL, or just the vanity name. Use 'me' or 'my' to query "
                    "your own profile (requires STEAM_USER_ID to be configured)."
                ),
                "required": True,
            },
        },
    )
    async def get_player_summary(self, steam_id: str, format: str = "text") -> str:
        """Get player summary for a Steam user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            if format == "json":
                return json.dumps({"error": normalized_id})
            return normalized_id

        players = await self.client.get_player_summaries([normalized_id])

        if not players:
            error_msg = f"Player not found for Steam ID: {steam_id}"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        player = players[0]
        data = self._build_player_data(player)

        if format == "json":
            return json.dumps(data, indent=2)
        return self._format_player_summary(player)

    @endpoint(
        name="get_player_summaries",
        description=(
            "Get Steam player profile information for multiple players at once. "
            "More efficient than calling get_player_summary multiple times. "
            "Maximum 100 Steam IDs per request."
        ),
        params={
            "steam_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of Steam IDs in any format. Maximum 100 IDs."
                ),
                "required": True,
            },
        },
    )
    async def get_player_summaries(self, steam_ids: list[str]) -> str:
        """Get player summaries for multiple Steam users."""
        if not steam_ids:
            return "Error: No Steam IDs provided"

        if len(steam_ids) > 100:
            return "Error: Maximum 100 Steam IDs per request"

        # Normalize all Steam IDs
        normalized_ids: list[str] = []
        errors: list[str] = []

        for sid in steam_ids:
            try:
                normalized = await normalize_steam_id(sid, self.client)
                normalized_ids.append(normalized)
            except SteamIDError as e:
                errors.append(f"  - {sid}: {e}")

        if not normalized_ids:
            return f"Error: Could not resolve any Steam IDs:\n" + "\n".join(errors)

        players = await self.client.get_player_summaries(normalized_ids)

        result_parts = [f"Found {len(players)} player(s):\n"]

        for player in players:
            result_parts.append(self._format_player_summary(player))
            result_parts.append("")  # Blank line between players

        if errors:
            result_parts.append("Errors resolving some IDs:")
            result_parts.extend(errors)

        return "\n".join(result_parts)

    @endpoint(
        name="resolve_vanity_url",
        description=(
            "Convert a Steam vanity URL or custom profile name to a SteamID64. "
            "Useful for converting human-readable profile names to the numeric "
            "Steam ID used by most API calls."
        ),
        params={
            "vanity_name": {
                "type": "string",
                "description": (
                    "The vanity URL name (e.g., 'gabelogannewell' from "
                    "steamcommunity.com/id/gabelogannewell)"
                ),
                "required": True,
            },
        },
    )
    async def resolve_vanity_url(self, vanity_name: str) -> str:
        """Resolve a vanity URL to SteamID64."""
        # Strip URL components if full URL provided
        if "/" in vanity_name:
            vanity_name = vanity_name.rstrip("/").split("/")[-1]

        result = await self.client.resolve_vanity_url(vanity_name)

        if result:
            return (
                f"Vanity URL '{vanity_name}' resolved to:\n"
                f"  SteamID64: {result}\n"
                f"  Profile URL: https://steamcommunity.com/profiles/{result}"
            )
        else:
            return f"Could not resolve vanity URL: '{vanity_name}'"

    @endpoint(
        name="get_friend_list",
        description=(
            "Get the friend list for a Steam user. Note: This only works for "
            "users with public profiles. Returns friend Steam IDs and relationship info."
        ),
        supports_json=True,
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
    async def get_friend_list(self, steam_id: str, format: str = "text") -> str:
        """Get friend list for a Steam user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            if format == "json":
                return json.dumps({"error": normalized_id})
            return normalized_id

        try:
            result = await self.client.get(
                "ISteamUser",
                "GetFriendList",
                version=1,
                params={"steamid": normalized_id, "relationship": "friend"},
            )
        except SteamAPIError as e:
            # 401 Unauthorized typically means private profile
            if e.status_code == 401:
                error_msg = (
                    f"Cannot access friend list for Steam ID {normalized_id}. "
                    "This profile's friend list is private."
                )
                if format == "json":
                    return json.dumps({"error": error_msg})
                return error_msg
            raise

        friends_list = result.get("friendslist", {}).get("friends", [])

        if not friends_list:
            error_msg = (
                f"No friends found for Steam ID {normalized_id}. "
                "This may indicate a private profile or an account with no friends."
            )
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        if format == "json":
            data = {
                "steam_id": normalized_id,
                "total_friends": len(friends_list),
                "friends": [
                    {
                        "steam_id": friend["steamid"],
                        "friend_since": friend.get("friend_since"),
                    }
                    for friend in friends_list
                ],
            }
            return json.dumps(data, indent=2)

        # Text format
        output = [f"Friend list for {normalized_id} ({len(friends_list)} friends):\n"]

        for friend in friends_list[:MAX_FRIENDS_DISPLAY]:
            friend_since = friend.get("friend_since", "Unknown")
            output.append(
                f"  - {friend['steamid']} (friends since: {friend_since})"
            )

        if len(friends_list) > MAX_FRIENDS_DISPLAY:
            output.append(f"\n  ... and {len(friends_list) - MAX_FRIENDS_DISPLAY} more friends")

        return "\n".join(output)

    @endpoint(
        name="get_player_bans",
        description=(
            "Get VAC ban, game ban, and community ban information for Steam users. "
            "Can check multiple users at once (max 100)."
        ),
        params={
            "steam_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Steam IDs to check (max 100)",
                "required": True,
            },
        },
    )
    async def get_player_bans(self, steam_ids: list[str]) -> str:
        """Get ban information for Steam users."""
        if not steam_ids:
            return "Error: No Steam IDs provided"

        if len(steam_ids) > 100:
            return "Error: Maximum 100 Steam IDs per request"

        # Normalize all Steam IDs
        normalized_ids: list[str] = []
        errors: list[str] = []
        for sid in steam_ids:
            try:
                normalized = await normalize_steam_id(sid, self.client)
                normalized_ids.append(normalized)
            except SteamIDError as e:
                errors.append(f"  - {sid}: {e}")

        if not normalized_ids:
            return "Error: Could not resolve any Steam IDs:\n" + "\n".join(errors)

        result = await self.client.get(
            "ISteamUser",
            "GetPlayerBans",
            version=1,
            params={"steamids": ",".join(normalized_ids)},
        )

        players = result.get("players", [])

        if not players:
            return "No ban information found"

        output = [f"Ban status for {len(players)} player(s):\n"]

        for player in players:
            steam_id = player.get("SteamId", "Unknown")
            vac_banned = player.get("VACBanned", False)
            num_vac = player.get("NumberOfVACBans", 0)
            days_since_vac = player.get("DaysSinceLastBan", 0)
            num_game_bans = player.get("NumberOfGameBans", 0)
            community_banned = player.get("CommunityBanned", False)
            trade_banned = player.get("EconomyBan", "none")

            output.append(f"Player: {steam_id}")

            if vac_banned:
                output.append(f"  VAC Banned: Yes ({num_vac} ban(s), {days_since_vac} days ago)")
            else:
                output.append("  VAC Banned: No")

            if num_game_bans > 0:
                output.append(f"  Game Bans: {num_game_bans}")
            else:
                output.append("  Game Bans: None")

            output.append(f"  Community Banned: {'Yes' if community_banned else 'No'}")
            output.append(f"  Trade Ban: {trade_banned}")
            output.append("")

        if errors:
            output.append("Could not resolve some Steam IDs:")
            output.extend(errors)

        return "\n".join(output)

    def _build_player_data(self, player: dict[str, Any]) -> dict[str, Any]:
        """Build structured player data for JSON output."""
        visibility_map = {1: "private", 2: "friends_only", 3: "public"}
        status_map = {
            0: "offline",
            1: "online",
            2: "busy",
            3: "away",
            4: "snooze",
            5: "looking_to_trade",
            6: "looking_to_play",
        }

        data: dict[str, Any] = {
            "steam_id": player.get("steamid", "Unknown"),
            "persona_name": player.get("personaname", "Unknown"),
            "profile_url": player.get("profileurl", ""),
            "visibility": visibility_map.get(
                player.get("communityvisibilitystate", 1), "unknown"
            ),
            "status": status_map.get(player.get("personastate", 0), "unknown"),
            "avatar_url": player.get("avatarfull", ""),
        }

        # Additional fields only available for public profiles
        if player.get("communityvisibilitystate") == 3:
            if player.get("realname"):
                data["real_name"] = player["realname"]
            if player.get("loccountrycode"):
                data["country"] = player["loccountrycode"]
            if player.get("gameextrainfo"):
                data["currently_playing"] = {
                    "name": player["gameextrainfo"],
                    "app_id": player.get("gameid", ""),
                }
            if player.get("timecreated"):
                data["account_created"] = player["timecreated"]

        return data

    def _format_player_summary(self, player: dict[str, Any]) -> str:
        """Format a player summary for display."""
        steam_id = player.get("steamid", "Unknown")
        persona_name = player.get("personaname", "Unknown")
        profile_url = player.get("profileurl", "")

        # Profile visibility: 1=private, 2=friends only, 3=public
        visibility_map = {1: "Private", 2: "Friends Only", 3: "Public"}
        visibility = visibility_map.get(
            player.get("communityvisibilitystate", 1), "Unknown"
        )

        # Online status
        status_map = {
            0: "Offline",
            1: "Online",
            2: "Busy",
            3: "Away",
            4: "Snooze",
            5: "Looking to trade",
            6: "Looking to play",
        }
        persona_state = status_map.get(player.get("personastate", 0), "Unknown")

        lines = [
            f"Player: {persona_name}",
            f"  SteamID64: {steam_id}",
            f"  Profile URL: {profile_url}",
            f"  Visibility: {visibility}",
            f"  Status: {persona_state}",
        ]

        # Additional fields only available for public profiles
        if player.get("communityvisibilitystate") == 3:
            if player.get("realname"):
                lines.append(f"  Real Name: {player['realname']}")

            if player.get("loccountrycode"):
                lines.append(f"  Country: {player['loccountrycode']}")

            if player.get("gameextrainfo"):
                game_name = player["gameextrainfo"]
                game_id = player.get("gameid", "")
                lines.append(f"  Currently Playing: {game_name} (App ID: {game_id})")

            if player.get("timecreated"):
                created = datetime.fromtimestamp(player["timecreated"])
                lines.append(f"  Account Created: {created.strftime('%Y-%m-%d')}")

        # Avatar (always available)
        if player.get("avatarfull"):
            lines.append(f"  Avatar: {player['avatarfull']}")

        return "\n".join(lines)
