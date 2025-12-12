"""IFamilyGroupsService API endpoints.

This module provides MCP tools for the IFamilyGroupsService Steam API interface,
which handles family group membership and shared library information.

Reference: https://partner.steamgames.com/doc/webapi/IFamilyGroupsService
"""

from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint
from steam_mcp.utils.steam_id import normalize_steam_id, SteamIDError


class IFamilyGroupsService(BaseEndpoint):
    """IFamilyGroupsService API endpoints for family sharing features."""

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
        name="get_family_group",
        description=(
            "Get family group membership information for a Steam user. "
            "Returns family members, their roles, and shared library status. "
            "Note: Only works for users who are part of a Steam family group."
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
        },
    )
    async def get_family_group(self, steam_id: str) -> str:
        """Get family group information for a Steam user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "IFamilyGroupsService",
                "GetFamilyGroup",
                version=1,
                params={"steamid": normalized_id},
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "401" in error_msg or "forbidden" in error_msg or "403" in error_msg:
                return (
                    f"Could not access family group for Steam ID {normalized_id}.\n"
                    "This user may not be in a family group, or their profile is private."
                )
            raise

        response = result.get("response", {})
        family_group = response.get("family_group", {})

        if not family_group:
            return (
                f"No family group found for Steam ID {normalized_id}.\n"
                "This user is not a member of any Steam family group."
            )

        # Extract family information
        family_groupid = family_group.get("family_groupid", "Unknown")
        name = family_group.get("name", "Unnamed Family")
        members = family_group.get("members", [])

        output = [
            f"Family Group: {name}",
            f"Family Group ID: {family_groupid}",
            f"Total Members: {len(members)}",
            "",
            "Members:",
        ]

        for member in members:
            member_steamid = member.get("steamid", "Unknown")
            role = member.get("role", 0)

            # Role mapping based on Steam's family sharing roles
            role_name = {
                0: "Member",
                1: "Adult",
                2: "Child",
            }.get(role, f"Unknown ({role})")

            # Check cooldown status
            cooldown_seconds = member.get("cooldown_seconds_remaining", 0)
            cooldown_str = ""
            if cooldown_seconds > 0:
                hours = cooldown_seconds // 3600
                minutes = (cooldown_seconds % 3600) // 60
                cooldown_str = f" (Cooldown: {hours}h {minutes}m remaining)"

            output.append(f"  - {member_steamid}: {role_name}{cooldown_str}")

        # Include slot information if available
        free_spots = family_group.get("free_spots", None)
        if free_spots is not None:
            output.append("")
            output.append(f"Available Slots: {free_spots}")

        return "\n".join(output)

    @endpoint(
        name="get_shared_library_apps",
        description=(
            "Get games available through family sharing for a Steam user. "
            "Returns shared games with owner information and availability status. "
            "Note: Only works for users who are part of a Steam family group."
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
            "include_own": {
                "type": "boolean",
                "description": "Include apps the user owns directly (not just shared). Default is false.",
                "required": False,
                "default": False,
            },
        },
    )
    async def get_shared_library_apps(
        self,
        steam_id: str,
        include_own: bool = False,
    ) -> str:
        """Get shared library apps for a Steam user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "IFamilyGroupsService",
                "GetSharedLibraryApps",
                version=1,
                params={
                    "steamid": normalized_id,
                    "include_own": include_own,
                },
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "401" in error_msg or "forbidden" in error_msg or "403" in error_msg:
                return (
                    f"Could not access shared library for Steam ID {normalized_id}.\n"
                    "This user may not be in a family group, or their profile is private."
                )
            raise

        response = result.get("response", {})
        apps = response.get("apps", [])

        if not apps:
            suffix = " (including owned apps)" if include_own else ""
            return (
                f"No shared library apps found for Steam ID {normalized_id}{suffix}.\n"
                "This user may not be in a family group, or no games are shared."
            )

        # Group apps by owner
        apps_by_owner: dict[str, list[dict[str, Any]]] = {}
        for app in apps:
            owner_steamids = app.get("owner_steamids", [])
            app_info = {
                "appid": app.get("appid"),
                "name": app.get("name", f"App {app.get('appid', 'Unknown')}"),
                "rt_time_acquired": app.get("rt_time_acquired", 0),
                "exclude_reason": app.get("exclude_reason", 0),
            }

            for owner_id in owner_steamids:
                if owner_id not in apps_by_owner:
                    apps_by_owner[owner_id] = []
                apps_by_owner[owner_id].append(app_info)

        total_apps = len(apps)
        output = [
            f"Shared Library for {normalized_id}",
            f"Total Shared Apps: {total_apps}",
            "",
        ]

        # Sort owners by number of apps shared
        sorted_owners = sorted(
            apps_by_owner.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for owner_id, owner_apps in sorted_owners:
            output.append(f"From {owner_id} ({len(owner_apps)} apps):")

            # Sort apps by name
            owner_apps.sort(key=lambda a: a.get("name", "").lower())

            # Show first 10 apps per owner
            for app in owner_apps[:10]:
                appid = app.get("appid", "?")
                name = app.get("name", "Unknown")

                # Check exclusion status
                exclude_reason = app.get("exclude_reason", 0)
                status = ""
                if exclude_reason > 0:
                    # Common exclusion reasons
                    reason_map = {
                        1: " [Excluded: Not shareable]",
                        2: " [Excluded: Free game]",
                        3: " [Excluded: Region lock]",
                        4: " [Excluded: Already owned]",
                    }
                    status = reason_map.get(exclude_reason, f" [Excluded: {exclude_reason}]")

                output.append(f"  [{appid}] {name}{status}")

            if len(owner_apps) > 10:
                output.append(f"  ... and {len(owner_apps) - 10} more")
            output.append("")

        return "\n".join(output).rstrip()
