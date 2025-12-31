"""Tests for ISteamRemoteStorage endpoint - cloud saves management."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from steam_mcp.endpoints.cloud_saves import ISteamRemoteStorage
from steam_mcp.endpoints.base import SteamIDError


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    return client


@pytest.fixture
def cloud_service(mock_client):
    """Create ISteamRemoteStorage instance with mock client."""
    return ISteamRemoteStorage(mock_client)


class TestListCloudFiles:
    """Tests for list_cloud_files endpoint."""

    @pytest.mark.asyncio
    async def test_returns_cloud_files_list(self, cloud_service, mock_client):
        """Should return formatted list of cloud files."""
        mock_client.get.return_value = {
            "response": {
                "totalcount": 2,
                "files": [
                    {
                        "filename": "save_slot_1.sav",
                        "file_size": 1024,
                        "timestamp": 1704067200,  # 2024-01-01 00:00:00 UTC
                    },
                    {
                        "filename": "config.cfg",
                        "file_size": 256,
                        "timestamp": 1704153600,
                    },
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.list_cloud_files(
                steam_id="76561198000000001", app_id=440
            )

        assert "Cloud Files for App 440" in result
        assert "Total Files: 2" in result
        assert "save_slot_1.sav" in result
        assert "config.cfg" in result
        assert "1.0 KB" in result
        assert "256 B" in result

    @pytest.mark.asyncio
    async def test_no_cloud_files_returns_message(self, cloud_service, mock_client):
        """Should return message when no cloud files exist."""
        mock_client.get.return_value = {"response": {"files": [], "totalcount": 0}}

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.list_cloud_files(
                steam_id="76561198000000001", app_id=440
            )

        assert "No cloud files found" in result
        assert "app 440" in result

    @pytest.mark.asyncio
    async def test_handles_private_profile(self, cloud_service, mock_client):
        """Should handle 401/403 errors gracefully."""
        mock_client.get.side_effect = Exception("401 Unauthorized")

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.list_cloud_files(
                steam_id="76561198000000001", app_id=440
            )

        assert "Could not access" in result
        assert "private" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_steam_id_returns_error(self, cloud_service):
        """Invalid Steam ID should return error."""
        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await cloud_service.list_cloud_files(
                steam_id="invalid_id", app_id=440
            )

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_me_shortcut_without_config_returns_error(
        self, cloud_service, mock_client
    ):
        """Using 'me' without STEAM_USER_ID configured should return error."""
        mock_client.owner_steam_id = None

        result = await cloud_service.list_cloud_files(steam_id="me", app_id=440)

        assert "Error" in result
        assert "STEAM_USER_ID" in result

    @pytest.mark.asyncio
    async def test_me_shortcut_with_config_works(self, cloud_service, mock_client):
        """Using 'me' with STEAM_USER_ID configured should work."""
        mock_client.owner_steam_id = "76561198000000001"
        mock_client.get.return_value = {
            "response": {
                "files": [{"filename": "test.sav", "file_size": 100, "timestamp": 0}],
                "totalcount": 1,
            }
        }

        result = await cloud_service.list_cloud_files(steam_id="my", app_id=440)

        assert "Cloud Files" in result
        assert "test.sav" in result

    @pytest.mark.asyncio
    async def test_calculates_total_size(self, cloud_service, mock_client):
        """Should calculate and display total size of all files."""
        mock_client.get.return_value = {
            "response": {
                "files": [
                    {"filename": "a.sav", "file_size": 1024 * 1024, "timestamp": 0},
                    {"filename": "b.sav", "file_size": 1024 * 1024, "timestamp": 0},
                ],
                "totalcount": 2,
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.list_cloud_files(
                steam_id="76561198000000001", app_id=440
            )

        assert "Total Size: 2.0 MB" in result


class TestGetCloudQuota:
    """Tests for get_cloud_quota endpoint."""

    @pytest.mark.asyncio
    async def test_returns_quota_info(self, cloud_service, mock_client):
        """Should return formatted quota information."""
        mock_client.get.return_value = {
            "response": {
                "quota_bytes": 1024 * 1024 * 100,  # 100 MB
                "used_bytes": 1024 * 1024 * 25,  # 25 MB
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.get_cloud_quota(steam_id="76561198000000001")

        assert "Steam Cloud Storage" in result
        assert "Total Quota: 100.0 MB" in result
        assert "Used Space: 25.0 MB" in result
        assert "25.0%" in result
        assert "Available: 75.0 MB" in result

    @pytest.mark.asyncio
    async def test_no_quota_returns_message(self, cloud_service, mock_client):
        """Should return message when no quota info available."""
        mock_client.get.return_value = {"response": {}}

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.get_cloud_quota(steam_id="76561198000000001")

        assert "No cloud quota information" in result

    @pytest.mark.asyncio
    async def test_handles_private_profile(self, cloud_service, mock_client):
        """Should handle 401/403 errors gracefully."""
        mock_client.get.side_effect = Exception("403 Forbidden")

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.get_cloud_quota(steam_id="76561198000000001")

        assert "Could not access" in result

    @pytest.mark.asyncio
    async def test_invalid_steam_id_returns_error(self, cloud_service):
        """Invalid Steam ID should return error."""
        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await cloud_service.get_cloud_quota(steam_id="invalid_id")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_me_shortcut_without_config_returns_error(
        self, cloud_service, mock_client
    ):
        """Using 'me' without STEAM_USER_ID configured should return error."""
        mock_client.owner_steam_id = None

        result = await cloud_service.get_cloud_quota(steam_id="me")

        assert "Error" in result
        assert "STEAM_USER_ID" in result

    @pytest.mark.asyncio
    async def test_usage_bar_visualization(self, cloud_service, mock_client):
        """Should display usage bar visualization."""
        mock_client.get.return_value = {
            "response": {
                "quota_bytes": 1000,
                "used_bytes": 500,  # 50%
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await cloud_service.get_cloud_quota(steam_id="76561198000000001")

        assert "[" in result
        assert "]" in result
        assert "=" in result


class TestFormatBytes:
    """Tests for _format_bytes helper method."""

    def test_formats_bytes(self, cloud_service):
        """Should format bytes correctly."""
        assert cloud_service._format_bytes(512) == "512 B"

    def test_formats_kilobytes(self, cloud_service):
        """Should format kilobytes correctly."""
        assert cloud_service._format_bytes(1024) == "1.0 KB"
        assert cloud_service._format_bytes(2048) == "2.0 KB"

    def test_formats_megabytes(self, cloud_service):
        """Should format megabytes correctly."""
        assert cloud_service._format_bytes(1024 * 1024) == "1.0 MB"
        assert cloud_service._format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_formats_gigabytes(self, cloud_service):
        """Should format gigabytes correctly."""
        assert cloud_service._format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert cloud_service._format_bytes(2 * 1024 * 1024 * 1024) == "2.00 GB"
