"""Tests for ISteamUser endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steam_mcp.client import SteamAPIError
from steam_mcp.endpoints.steam_user import ISteamUser
from steam_mcp.utils.steam_id import SteamIDError


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    client.get_player_summaries = AsyncMock()
    client.resolve_vanity_url = AsyncMock()
    return client


@pytest.fixture
def steam_user(mock_client):
    """Create ISteamUser instance with mock client."""
    return ISteamUser(mock_client)


class TestGetMySteamId:
    """Tests for get_my_steam_id endpoint."""

    @pytest.mark.asyncio
    async def test_no_owner_configured(self, steam_user):
        """Should return instructions when no owner ID is set."""
        result = await steam_user.get_my_steam_id()

        assert "No owner Steam ID configured" in result
        assert "STEAM_USER_ID" in result

    @pytest.mark.asyncio
    async def test_owner_configured_with_profile(self, steam_user, mock_client):
        """Should return owner info when ID is configured."""
        mock_client.owner_steam_id = "76561198000000001"
        mock_client.get_player_summaries.return_value = [
            {
                "steamid": "76561198000000001",
                "personaname": "TestUser",
                "profileurl": "https://steamcommunity.com/profiles/76561198000000001",
            }
        ]

        result = await steam_user.get_my_steam_id()

        assert "Owner Steam ID configured" in result
        assert "TestUser" in result
        assert "76561198000000001" in result

    @pytest.mark.asyncio
    async def test_owner_configured_profile_fetch_fails(self, steam_user, mock_client):
        """Should return basic info if profile fetch fails."""
        mock_client.owner_steam_id = "76561198000000001"
        mock_client.get_player_summaries.return_value = []

        result = await steam_user.get_my_steam_id()

        assert "76561198000000001" in result
        assert "Could not fetch profile details" in result


class TestGetPlayerSummary:
    """Tests for get_player_summary endpoint."""

    @pytest.mark.asyncio
    async def test_valid_steam_id(self, steam_user, mock_client):
        """Should return player summary for valid ID."""
        mock_client.get_player_summaries.return_value = [
            {
                "steamid": "76561198000000001",
                "personaname": "TestPlayer",
                "profileurl": "https://steamcommunity.com/profiles/76561198000000001",
                "communityvisibilitystate": 3,
                "personastate": 1,
            }
        ]

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_player_summary(steam_id="76561198000000001")

        assert "TestPlayer" in result
        assert "76561198000000001" in result
        assert "Online" in result

    @pytest.mark.asyncio
    async def test_player_not_found(self, steam_user, mock_client):
        """Should return error when player not found."""
        mock_client.get_player_summaries.return_value = []

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_player_summary(steam_id="76561198000000001")

        assert "Player not found" in result

    @pytest.mark.asyncio
    async def test_json_format(self, steam_user, mock_client):
        """Should return JSON when format is json."""
        mock_client.get_player_summaries.return_value = [
            {
                "steamid": "76561198000000001",
                "personaname": "TestPlayer",
                "profileurl": "https://steamcommunity.com/profiles/76561198000000001",
                "communityvisibilitystate": 3,
                "personastate": 1,
            }
        ]

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_player_summary(
                steam_id="76561198000000001", format="json"
            )

        assert '"steam_id"' in result
        assert '"persona_name"' in result

    @pytest.mark.asyncio
    async def test_invalid_steam_id(self, steam_user):
        """Should return error for invalid Steam ID."""
        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await steam_user.get_player_summary(steam_id="invalid")

        assert "Error" in result


class TestGetPlayerSummaries:
    """Tests for get_player_summaries endpoint."""

    @pytest.mark.asyncio
    async def test_empty_list(self, steam_user):
        """Should return error for empty list."""
        result = await steam_user.get_player_summaries(steam_ids=[])

        assert "Error" in result
        assert "No Steam IDs provided" in result

    @pytest.mark.asyncio
    async def test_exceeds_max_limit(self, steam_user):
        """Should return error when exceeding 100 IDs."""
        result = await steam_user.get_player_summaries(steam_ids=["id"] * 101)

        assert "Error" in result
        assert "Maximum 100" in result

    @pytest.mark.asyncio
    async def test_multiple_players(self, steam_user, mock_client):
        """Should return summaries for multiple players."""
        mock_client.get_player_summaries.return_value = [
            {
                "steamid": "76561198000000001",
                "personaname": "Player1",
                "profileurl": "url1",
                "communityvisibilitystate": 3,
                "personastate": 1,
            },
            {
                "steamid": "76561198000000002",
                "personaname": "Player2",
                "profileurl": "url2",
                "communityvisibilitystate": 3,
                "personastate": 0,
            },
        ]

        with patch(
            "steam_mcp.endpoints.steam_user.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002"],
        ):
            result = await steam_user.get_player_summaries(
                steam_ids=["76561198000000001", "76561198000000002"]
            )

        assert "Found 2 player(s)" in result
        assert "Player1" in result
        assert "Player2" in result

    @pytest.mark.asyncio
    async def test_partial_resolution_failure(self, steam_user, mock_client):
        """Should continue with valid IDs when some fail."""
        mock_client.get_player_summaries.return_value = [
            {
                "steamid": "76561198000000001",
                "personaname": "ValidPlayer",
                "profileurl": "url",
                "communityvisibilitystate": 3,
                "personastate": 1,
            }
        ]

        with patch(
            "steam_mcp.endpoints.steam_user.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", SteamIDError("Invalid")],
        ):
            result = await steam_user.get_player_summaries(
                steam_ids=["76561198000000001", "invalid_id"]
            )

        assert "Found 1 player(s)" in result
        assert "ValidPlayer" in result
        assert "Errors" in result


class TestResolveVanityUrl:
    """Tests for resolve_vanity_url endpoint."""

    @pytest.mark.asyncio
    async def test_valid_vanity_name(self, steam_user, mock_client):
        """Should resolve vanity name to Steam ID."""
        mock_client.resolve_vanity_url.return_value = "76561198000000001"

        result = await steam_user.resolve_vanity_url(vanity_name="testuser")

        assert "76561198000000001" in result
        assert "testuser" in result
        mock_client.resolve_vanity_url.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_full_url_input(self, steam_user, mock_client):
        """Should extract vanity name from full URL."""
        mock_client.resolve_vanity_url.return_value = "76561198000000001"

        await steam_user.resolve_vanity_url(
            vanity_name="https://steamcommunity.com/id/testuser/"
        )

        mock_client.resolve_vanity_url.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_vanity_not_found(self, steam_user, mock_client):
        """Should return error when vanity not found."""
        mock_client.resolve_vanity_url.return_value = None

        result = await steam_user.resolve_vanity_url(vanity_name="nonexistent")

        assert "Could not resolve" in result


class TestGetFriendList:
    """Tests for get_friend_list endpoint."""

    @pytest.mark.asyncio
    async def test_public_profile_with_friends(self, steam_user, mock_client):
        """Should return friend list for public profile."""
        mock_client.get.return_value = {
            "friendslist": {
                "friends": [
                    {"steamid": "76561198000000002", "friend_since": 1600000000},
                    {"steamid": "76561198000000003", "friend_since": 1700000000},
                ]
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_friend_list(steam_id="76561198000000001")

        assert "2 friends" in result
        assert "76561198000000002" in result
        assert "76561198000000003" in result

    @pytest.mark.asyncio
    async def test_private_profile(self, steam_user, mock_client):
        """Should return error for private profile."""
        mock_client.get.side_effect = SteamAPIError("Unauthorized", status_code=401)

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_friend_list(steam_id="76561198000000001")

        assert "private" in result.lower()

    @pytest.mark.asyncio
    async def test_no_friends(self, steam_user, mock_client):
        """Should handle empty friend list."""
        mock_client.get.return_value = {"friendslist": {"friends": []}}

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_friend_list(steam_id="76561198000000001")

        assert "No friends found" in result

    @pytest.mark.asyncio
    async def test_json_format(self, steam_user, mock_client):
        """Should return JSON when format is json."""
        mock_client.get.return_value = {
            "friendslist": {
                "friends": [
                    {"steamid": "76561198000000002", "friend_since": 1600000000}
                ]
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_friend_list(
                steam_id="76561198000000001", format="json"
            )

        assert '"steam_id"' in result
        assert '"total_friends"' in result


class TestGetPlayerBans:
    """Tests for get_player_bans endpoint."""

    @pytest.mark.asyncio
    async def test_empty_list(self, steam_user):
        """Should return error for empty list."""
        result = await steam_user.get_player_bans(steam_ids=[])

        assert "Error" in result
        assert "No Steam IDs provided" in result

    @pytest.mark.asyncio
    async def test_exceeds_max_limit(self, steam_user):
        """Should return error when exceeding 100 IDs."""
        result = await steam_user.get_player_bans(steam_ids=["id"] * 101)

        assert "Error" in result
        assert "Maximum 100" in result

    @pytest.mark.asyncio
    async def test_clean_player(self, steam_user, mock_client):
        """Should show clean status for unbanned player."""
        mock_client.get.return_value = {
            "players": [
                {
                    "SteamId": "76561198000000001",
                    "VACBanned": False,
                    "NumberOfVACBans": 0,
                    "NumberOfGameBans": 0,
                    "CommunityBanned": False,
                    "EconomyBan": "none",
                }
            ]
        }

        with patch(
            "steam_mcp.endpoints.steam_user.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_player_bans(steam_ids=["76561198000000001"])

        assert "VAC Banned: No" in result
        assert "Game Bans: None" in result
        assert "Community Banned: No" in result

    @pytest.mark.asyncio
    async def test_banned_player(self, steam_user, mock_client):
        """Should show ban details for banned player."""
        mock_client.get.return_value = {
            "players": [
                {
                    "SteamId": "76561198000000001",
                    "VACBanned": True,
                    "NumberOfVACBans": 2,
                    "DaysSinceLastBan": 365,
                    "NumberOfGameBans": 1,
                    "CommunityBanned": True,
                    "EconomyBan": "banned",
                }
            ]
        }

        with patch(
            "steam_mcp.endpoints.steam_user.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await steam_user.get_player_bans(steam_ids=["76561198000000001"])

        assert "VAC Banned: Yes" in result
        assert "2 ban(s)" in result
        assert "365 days ago" in result
        assert "Game Bans: 1" in result
        assert "Community Banned: Yes" in result

    @pytest.mark.asyncio
    async def test_multiple_players(self, steam_user, mock_client):
        """Should return ban info for multiple players."""
        mock_client.get.return_value = {
            "players": [
                {
                    "SteamId": "76561198000000001",
                    "VACBanned": False,
                    "NumberOfVACBans": 0,
                    "NumberOfGameBans": 0,
                    "CommunityBanned": False,
                    "EconomyBan": "none",
                },
                {
                    "SteamId": "76561198000000002",
                    "VACBanned": True,
                    "NumberOfVACBans": 1,
                    "DaysSinceLastBan": 100,
                    "NumberOfGameBans": 0,
                    "CommunityBanned": False,
                    "EconomyBan": "none",
                },
            ]
        }

        with patch(
            "steam_mcp.endpoints.steam_user.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002"],
        ):
            result = await steam_user.get_player_bans(
                steam_ids=["76561198000000001", "76561198000000002"]
            )

        assert "2 player(s)" in result
        assert "76561198000000001" in result
        assert "76561198000000002" in result
