"""Tests for IPlayerService endpoint - find_unplayed_games_with_friends."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from steam_mcp.endpoints.player_service import IPlayerService
from steam_mcp.utils.steam_id import SteamIDError


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    return client


@pytest.fixture
def player_service(mock_client):
    """Create IPlayerService instance with mock client."""
    return IPlayerService(mock_client)


# --- Unit Tests ---


class TestFindUnplayedGamesWithFriendsValidation:
    """Input validation tests."""

    @pytest.mark.asyncio
    async def test_empty_friend_list_returns_error(self, player_service):
        """Empty friend list should return error."""
        result = await player_service.find_unplayed_games_with_friends(
            my_steam_id="76561198000000001",
            friend_steam_ids=[],
        )
        assert "Error" in result
        assert "at least one friend" in result.lower()

    @pytest.mark.asyncio
    async def test_self_comparison_rejected(self, player_service, mock_client):
        """Friend ID matching user ID should be rejected."""
        # Both resolve to same ID
        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000001"],
            )
        assert "Error" in result
        assert "Cannot compare with yourself" in result

    @pytest.mark.asyncio
    async def test_invalid_steam_id_returns_error(self, player_service):
        """Invalid Steam ID should return error."""
        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="invalid_id",
                friend_steam_ids=["76561198000000002"],
            )
        assert "Error" in result


class TestFindUnplayedGamesWithFriendsLogic:
    """Core logic tests."""

    @pytest.mark.asyncio
    async def test_finds_shared_unplayed_games(self, player_service, mock_client):
        """Should find games owned by all with zero playtime."""
        my_games = [
            {"appid": 100, "name": "Unplayed Game", "playtime_forever": 0},
            {"appid": 200, "name": "Played Game", "playtime_forever": 60},
        ]
        friend_games = [
            {"appid": 100, "name": "Unplayed Game", "playtime_forever": 0},
            {"appid": 200, "name": "Played Game", "playtime_forever": 0},
        ]

        mock_client.get.side_effect = [
            {"response": {"games": my_games}},
            {"response": {"games": friend_games}},
        ]

        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002"],
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000002"],
            )

        assert "1 unplayed games" in result
        assert "Unplayed Game" in result
        assert "Played Game" not in result

    @pytest.mark.asyncio
    async def test_no_unplayed_games_message(self, player_service, mock_client):
        """Should report when no shared unplayed games exist."""
        my_games = [{"appid": 100, "name": "Game A", "playtime_forever": 120}]
        friend_games = [{"appid": 100, "name": "Game A", "playtime_forever": 0}]

        mock_client.get.side_effect = [
            {"response": {"games": my_games}},
            {"response": {"games": friend_games}},
        ]

        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002"],
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000002"],
            )

        assert "No unplayed shared games" in result
        assert "Games you all own: 1" in result

    @pytest.mark.asyncio
    async def test_private_profile_handled_gracefully(self, player_service, mock_client):
        """Private friend profile should continue with available data."""
        my_games = [{"appid": 100, "name": "Game", "playtime_forever": 0}]
        friend1_games = [{"appid": 100, "name": "Game", "playtime_forever": 0}]
        # Friend 2 is private (empty response)

        mock_client.get.side_effect = [
            {"response": {"games": my_games}},
            {"response": {"games": friend1_games}},
            {"response": {}},  # Private profile
        ]

        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002", "76561198000000003"],
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000002", "76561198000000003"],
            )

        assert "1 unplayed games" in result
        assert "private profile" in result.lower()

    @pytest.mark.asyncio
    async def test_multiple_friends_all_must_own(self, player_service, mock_client):
        """Game must be owned by ALL friends to appear in results."""
        my_games = [
            {"appid": 100, "name": "All Own", "playtime_forever": 0},
            {"appid": 200, "name": "Only Friend1", "playtime_forever": 0},
        ]
        friend1_games = [
            {"appid": 100, "name": "All Own", "playtime_forever": 0},
            {"appid": 200, "name": "Only Friend1", "playtime_forever": 0},
        ]
        friend2_games = [
            {"appid": 100, "name": "All Own", "playtime_forever": 0},
            # Does NOT own appid 200
        ]

        mock_client.get.side_effect = [
            {"response": {"games": my_games}},
            {"response": {"games": friend1_games}},
            {"response": {"games": friend2_games}},
        ]

        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002", "76561198000000003"],
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000002", "76561198000000003"],
            )

        assert "1 unplayed games" in result
        assert "All Own" in result
        assert "Only Friend1" not in result

    @pytest.mark.asyncio
    async def test_all_friends_must_have_zero_playtime(self, player_service, mock_client):
        """Game is excluded if any participant has played it."""
        my_games = [{"appid": 100, "name": "Game", "playtime_forever": 0}]
        friend1_games = [{"appid": 100, "name": "Game", "playtime_forever": 0}]
        friend2_games = [{"appid": 100, "name": "Game", "playtime_forever": 5}]  # Played!

        mock_client.get.side_effect = [
            {"response": {"games": my_games}},
            {"response": {"games": friend1_games}},
            {"response": {"games": friend2_games}},
        ]

        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002", "76561198000000003"],
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000002", "76561198000000003"],
            )

        assert "No unplayed shared games" in result

    @pytest.mark.asyncio
    async def test_my_profile_private_returns_error(self, player_service, mock_client):
        """User's own private profile should return informative error."""
        mock_client.get.side_effect = [
            {"response": {}},  # Empty = private
            {"response": {"games": [{"appid": 1, "name": "X", "playtime_forever": 0}]}},
        ]

        with patch(
            "steam_mcp.endpoints.player_service.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=["76561198000000001", "76561198000000002"],
        ):
            result = await player_service.find_unplayed_games_with_friends(
                my_steam_id="76561198000000001",
                friend_steam_ids=["76561198000000002"],
            )

        assert "No games found for your profile" in result
        assert "private" in result.lower()


class TestFetchGamesRawHelper:
    """Tests for _fetch_games_raw helper method."""

    @pytest.mark.asyncio
    async def test_fetch_games_raw_returns_games_list(self, player_service, mock_client):
        """Should return list of games from API response."""
        expected_games = [{"appid": 100, "name": "Test"}]
        mock_client.get.return_value = {"response": {"games": expected_games}}

        result = await player_service._fetch_games_raw("76561198000000001")

        assert result == expected_games
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_games_raw_empty_response(self, player_service, mock_client):
        """Should return empty list for private/empty profiles."""
        mock_client.get.return_value = {"response": {}}

        result = await player_service._fetch_games_raw("76561198000000001")

        assert result == []
