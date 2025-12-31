"""ISteamRemoteStorage and ICloudService API endpoints.

This module provides MCP tools for Steam Cloud save management,
including listing cloud files and checking storage quotas.

Reference: https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage
"""

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


class ISteamRemoteStorage(BaseEndpoint):
    """Steam Cloud save management endpoints."""

    @endpoint(
        name="list_cloud_files",
        description=(
            "List cloud save files for a specific game. "
            "Returns file names, sizes, and timestamps. "
            "Note: Requires user authentication context."
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
            "app_id": {
                "type": "integer",
                "description": "Game app ID to list cloud files for",
                "required": True,
            },
        },
    )
    async def list_cloud_files(self, steam_id: str, app_id: int) -> str:
        """List cloud save files for a game."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "ISteamRemoteStorage",
                "EnumerateUserFiles",
                version=1,
                params={
                    "steamid": normalized_id,
                    "appid": app_id,
                },
            )
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "403" in error_str or "unauthorized" in error_str:
                return (
                    f"Could not access cloud files for Steam ID {normalized_id}.\n"
                    "This may require owner authentication or the profile is private."
                )
            return f"Error fetching cloud files: {e}"

        response = result.get("response", {})
        files = response.get("files", [])
        total_count = response.get("totalcount", len(files))

        if not files:
            return (
                f"No cloud files found for app {app_id} (Steam ID: {normalized_id}).\n"
                "This game may not use Steam Cloud, or no saves exist yet."
            )

        # Calculate total size
        total_bytes = sum(f.get("file_size", 0) for f in files)

        output = [
            f"Cloud Files for App {app_id}",
            f"Steam ID: {normalized_id}",
            f"Total Files: {total_count}",
            f"Total Size: {self._format_bytes(total_bytes)}",
            "",
        ]

        for f in files:
            filename = f.get("filename", "Unknown")
            size = f.get("file_size", 0)
            timestamp = f.get("timestamp", 0)

            # Format timestamp
            if timestamp:
                from datetime import datetime
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = "Unknown"

            output.append(
                f"  {filename}\n"
                f"    Size: {self._format_bytes(size)} | Modified: {time_str}"
            )

        return "\n".join(output)

    @endpoint(
        name="get_cloud_quota",
        description=(
            "Get Steam Cloud storage usage and limits for a user. "
            "Shows total quota, used space, and available space."
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
    async def get_cloud_quota(self, steam_id: str) -> str:
        """Get cloud storage quota for a user."""
        normalized_id = await self._resolve_steam_id(steam_id)
        if normalized_id.startswith("Error"):
            return normalized_id

        try:
            result = await self.client.get(
                "ICloudService",
                "GetUploadServerInfo",
                version=1,
                params={"steamid": normalized_id},
            )
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "403" in error_str or "unauthorized" in error_str:
                return (
                    f"Could not access cloud quota for Steam ID {normalized_id}.\n"
                    "This may require owner authentication or the profile is private."
                )
            return f"Error fetching cloud quota: {e}"

        response = result.get("response", {})

        # Extract quota information
        total_bytes = response.get("quota_bytes", 0)
        used_bytes = response.get("used_bytes", 0)

        if total_bytes == 0 and used_bytes == 0:
            return (
                f"No cloud quota information available for Steam ID {normalized_id}.\n"
                "This may indicate restricted access or no cloud usage."
            )

        available_bytes = total_bytes - used_bytes
        usage_percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0

        output = [
            f"Steam Cloud Storage for {normalized_id}",
            "",
            f"Total Quota: {self._format_bytes(total_bytes)}",
            f"Used Space: {self._format_bytes(used_bytes)} ({usage_percent:.1f}%)",
            f"Available: {self._format_bytes(available_bytes)}",
        ]

        # Add usage bar visualization
        bar_length = 20
        filled = int(bar_length * usage_percent / 100)
        bar = "[" + "=" * filled + "-" * (bar_length - filled) + "]"
        output.append(f"\n{bar} {usage_percent:.1f}% used")

        return "\n".join(output)

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format bytes into human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
