"""Tests for IFamilyGroupsService endpoint - family sharing features."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from steam_mcp.endpoints.family_groups import IFamilyGroupsService
from steam_mcp.utils.steam_id import SteamIDError


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    return client


@pytest.fixture
def family_service(mock_client):
    """Create IFamilyGroupsService instance with mock client."""
    return IFamilyGroupsService(mock_client)


class TestGetFamilyGroup:
    """Tests for get_family_group endpoint."""

    @pytest.mark.asyncio
    async def test_returns_family_group_info(self, family_service, mock_client):
        """Should return formatted family group information."""
        mock_client.get.return_value = {
            "response": {
                "family_group": {
                    "family_groupid": "12345",
                    "name": "Test Family",
                    "members": [
                        {"steamid": "76561198000000001", "role": 1},
                        {"steamid": "76561198000000002", "role": 2},
                    ],
                    "free_spots": 3,
                }
            }
        }

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_family_group(steam_id="76561198000000001")

        assert "Test Family" in result
        assert "12345" in result
        assert "Total Members: 2" in result
        assert "76561198000000001" in result
        assert "Adult" in result
        assert "Child" in result
        assert "Available Slots: 3" in result

    @pytest.mark.asyncio
    async def test_no_family_group_returns_message(self, family_service, mock_client):
        """Should return message when user has no family group."""
        mock_client.get.return_value = {"response": {}}

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_family_group(steam_id="76561198000000001")

        assert "No family group found" in result
        assert "not a member" in result

    @pytest.mark.asyncio
    async def test_handles_private_profile(self, family_service, mock_client):
        """Should handle 401/403 errors gracefully."""
        mock_client.get.side_effect = Exception("401 Unauthorized")

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_family_group(steam_id="76561198000000001")

        assert "Could not access" in result
        assert "private" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_steam_id_returns_error(self, family_service):
        """Invalid Steam ID should return error."""
        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await family_service.get_family_group(steam_id="invalid_id")

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_me_shortcut_without_config_returns_error(self, family_service, mock_client):
        """Using 'me' without STEAM_USER_ID configured should return error."""
        mock_client.owner_steam_id = None

        result = await family_service.get_family_group(steam_id="me")

        assert "Error" in result
        assert "STEAM_USER_ID" in result

    @pytest.mark.asyncio
    async def test_me_shortcut_with_config_works(self, family_service, mock_client):
        """Using 'me' with STEAM_USER_ID configured should work."""
        mock_client.owner_steam_id = "76561198000000001"
        mock_client.get.return_value = {
            "response": {
                "family_group": {
                    "family_groupid": "12345",
                    "name": "My Family",
                    "members": [{"steamid": "76561198000000001", "role": 1}],
                }
            }
        }

        result = await family_service.get_family_group(steam_id="my")

        assert "My Family" in result

    @pytest.mark.asyncio
    async def test_cooldown_displayed(self, family_service, mock_client):
        """Should display cooldown time for members."""
        mock_client.get.return_value = {
            "response": {
                "family_group": {
                    "family_groupid": "12345",
                    "name": "Test Family",
                    "members": [
                        {
                            "steamid": "76561198000000001",
                            "role": 1,
                            "cooldown_seconds_remaining": 7200,  # 2 hours
                        },
                    ],
                }
            }
        }

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_family_group(steam_id="76561198000000001")

        assert "Cooldown: 2h 0m" in result


class TestGetSharedLibraryApps:
    """Tests for get_shared_library_apps endpoint."""

    @pytest.mark.asyncio
    async def test_returns_shared_apps(self, family_service, mock_client):
        """Should return formatted shared library apps."""
        mock_client.get.return_value = {
            "response": {
                "apps": [
                    {
                        "appid": 440,
                        "name": "Team Fortress 2",
                        "owner_steamids": ["76561198000000002"],
                        "exclude_reason": 0,
                    },
                    {
                        "appid": 570,
                        "name": "Dota 2",
                        "owner_steamids": ["76561198000000002"],
                        "exclude_reason": 0,
                    },
                ]
            }
        }

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_shared_library_apps(steam_id="76561198000000001")

        assert "Shared Library" in result
        assert "Total Shared Apps: 2" in result
        assert "Team Fortress 2" in result
        assert "Dota 2" in result
        assert "76561198000000002" in result

    @pytest.mark.asyncio
    async def test_no_shared_apps_returns_message(self, family_service, mock_client):
        """Should return message when no shared apps."""
        mock_client.get.return_value = {"response": {"apps": []}}

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_shared_library_apps(steam_id="76561198000000001")

        assert "No shared library apps found" in result

    @pytest.mark.asyncio
    async def test_handles_private_profile(self, family_service, mock_client):
        """Should handle 401/403 errors gracefully."""
        mock_client.get.side_effect = Exception("403 Forbidden")

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_shared_library_apps(steam_id="76561198000000001")

        assert "Could not access" in result

    @pytest.mark.asyncio
    async def test_exclusion_reason_displayed(self, family_service, mock_client):
        """Should display exclusion reason for apps."""
        mock_client.get.return_value = {
            "response": {
                "apps": [
                    {
                        "appid": 440,
                        "name": "Some Game",
                        "owner_steamids": ["76561198000000002"],
                        "exclude_reason": 4,  # Already owned
                    },
                ]
            }
        }

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_shared_library_apps(steam_id="76561198000000001")

        assert "Already owned" in result

    @pytest.mark.asyncio
    async def test_include_own_parameter(self, family_service, mock_client):
        """Should pass include_own parameter to API."""
        mock_client.get.return_value = {"response": {"apps": []}}

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            await family_service.get_shared_library_apps(
                steam_id="76561198000000001",
                include_own=True,
            )

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args.kwargs["params"]["include_own"] is True

    @pytest.mark.asyncio
    async def test_multiple_owners_grouped(self, family_service, mock_client):
        """Should group apps by owner."""
        mock_client.get.return_value = {
            "response": {
                "apps": [
                    {
                        "appid": 440,
                        "name": "Game A",
                        "owner_steamids": ["76561198000000002"],
                    },
                    {
                        "appid": 570,
                        "name": "Game B",
                        "owner_steamids": ["76561198000000003"],
                    },
                    {
                        "appid": 730,
                        "name": "Game C",
                        "owner_steamids": ["76561198000000002"],
                    },
                ]
            }
        }

        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await family_service.get_shared_library_apps(steam_id="76561198000000001")

        # Owner with 2 apps should appear first
        assert result.index("76561198000000002") < result.index("76561198000000003")

    @pytest.mark.asyncio
    async def test_invalid_steam_id_returns_error(self, family_service):
        """Invalid Steam ID should return error."""
        with patch(
            "steam_mcp.endpoints.family_groups.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await family_service.get_shared_library_apps(steam_id="invalid_id")

        assert "Error" in result
