"""Tests for ISteamUserStats endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from steam_mcp.endpoints.user_stats import ISteamUserStats
from steam_mcp.utils.steam_id import SteamIDError


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    return client


@pytest.fixture
def user_stats(mock_client):
    """Create ISteamUserStats instance with mock client."""
    return ISteamUserStats(mock_client)


class TestGetPlayerAchievements:
    """Tests for get_player_achievements endpoint."""

    @pytest.mark.asyncio
    async def test_returns_achievements(self, user_stats, mock_client):
        """Should return achievements for a player."""
        mock_client.get.return_value = {
            "playerstats": {
                "success": True,
                "steamID": "76561198000000001",
                "gameName": "Test Game",
                "achievements": [
                    {"apiname": "ACH_1", "name": "First Achievement", "achieved": 1, "unlocktime": 1700000000},
                    {"apiname": "ACH_2", "name": "Second Achievement", "achieved": 0},
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_player_achievements(
                steam_id="76561198000000001", app_id=440
            )

        assert "Test Game" in result
        assert "1/2" in result
        assert "First Achievement" in result
        assert "✓" in result  # Unlocked marker

    @pytest.mark.asyncio
    async def test_json_format(self, user_stats, mock_client):
        """Should return JSON when format is json."""
        mock_client.get.return_value = {
            "playerstats": {
                "success": True,
                "steamID": "76561198000000001",
                "gameName": "Test Game",
                "achievements": [
                    {"apiname": "ACH_1", "name": "Test", "achieved": 1},
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_player_achievements(
                steam_id="76561198000000001", app_id=440, format="json"
            )

        assert '"steam_id"' in result
        assert '"game_name"' in result
        assert '"achievements"' in result

    @pytest.mark.asyncio
    async def test_private_profile_error(self, user_stats, mock_client):
        """Should return error for private profile."""
        mock_client.get.side_effect = Exception("Profile is not public")

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_player_achievements(
                steam_id="76561198000000001", app_id=440
            )

        assert "private" in result.lower()

    @pytest.mark.asyncio
    async def test_no_achievements(self, user_stats, mock_client):
        """Should handle game with no achievements."""
        mock_client.get.return_value = {
            "playerstats": {
                "success": True,
                "steamID": "76561198000000001",
                "gameName": "No Achievements Game",
                "achievements": [],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_player_achievements(
                steam_id="76561198000000001", app_id=440
            )

        assert "No achievements found" in result

    @pytest.mark.asyncio
    async def test_invalid_steam_id(self, user_stats):
        """Should return error for invalid Steam ID."""
        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            side_effect=SteamIDError("Invalid Steam ID"),
        ):
            result = await user_stats.get_player_achievements(
                steam_id="invalid", app_id=440
            )

        assert "Error" in result


class TestGetGameSchema:
    """Tests for get_game_schema endpoint."""

    @pytest.mark.asyncio
    async def test_returns_schema(self, user_stats, mock_client):
        """Should return game schema."""
        mock_client.get.return_value = {
            "game": {
                "gameName": "Test Game",
                "availableGameStats": {
                    "achievements": [
                        {"name": "ACH_1", "displayName": "First", "hidden": 0},
                        {"name": "ACH_2", "displayName": "Second", "hidden": 1},
                    ],
                    "stats": [
                        {"name": "kills", "displayName": "Total Kills"},
                    ],
                },
            }
        }

        result = await user_stats.get_game_schema(app_id=440)

        assert "Test Game" in result
        assert "2 total" in result
        assert "1 hidden" in result
        assert "First" in result
        assert "[HIDDEN]" in result

    @pytest.mark.asyncio
    async def test_no_schema_found(self, user_stats, mock_client):
        """Should handle missing schema."""
        mock_client.get.return_value = {"game": {}}

        result = await user_stats.get_game_schema(app_id=99999)

        assert "No schema found" in result

    @pytest.mark.asyncio
    async def test_no_achievements(self, user_stats, mock_client):
        """Should handle game with no achievements."""
        mock_client.get.return_value = {
            "game": {
                "gameName": "No Achievements",
                "availableGameStats": {
                    "achievements": [],
                    "stats": [],
                },
            }
        }

        result = await user_stats.get_game_schema(app_id=440)

        assert "No achievements for this game" in result


class TestGetGlobalAchievementPercentages:
    """Tests for get_global_achievement_percentages endpoint."""

    @pytest.mark.asyncio
    async def test_returns_percentages(self, user_stats, mock_client):
        """Should return achievement percentages sorted by rarity."""
        mock_client.get.return_value = {
            "achievementpercentages": {
                "achievements": [
                    {"name": "Common", "percent": 80.0},
                    {"name": "Ultra Rare", "percent": 0.5},
                    {"name": "Rare", "percent": 5.0},
                ]
            }
        }

        result = await user_stats.get_global_achievement_percentages(app_id=440)

        assert "Ultra Rare" in result
        assert "0.5%" in result
        assert "Rarest achievements" in result

    @pytest.mark.asyncio
    async def test_rarity_indicators(self, user_stats, mock_client):
        """Should show rarity indicators."""
        mock_client.get.return_value = {
            "achievementpercentages": {
                "achievements": [
                    {"name": "Ultra", "percent": 0.5},
                    {"name": "Very Rare", "percent": 3.0},
                    {"name": "Rare", "percent": 8.0},
                ]
            }
        }

        result = await user_stats.get_global_achievement_percentages(app_id=440)

        assert "🏆" in result  # Ultra rare
        assert "💎" in result  # Very rare
        assert "⭐" in result  # Rare

    @pytest.mark.asyncio
    async def test_no_data(self, user_stats, mock_client):
        """Should handle no achievement data."""
        mock_client.get.return_value = {
            "achievementpercentages": {"achievements": []}
        }

        result = await user_stats.get_global_achievement_percentages(app_id=99999)

        assert "No global achievement data" in result


class TestGetUserStatsForGame:
    """Tests for get_user_stats_for_game endpoint."""

    @pytest.mark.asyncio
    async def test_returns_stats(self, user_stats, mock_client):
        """Should return player stats."""
        mock_client.get.return_value = {
            "playerstats": {
                "steamID": "76561198000000001",
                "gameName": "Test Game",
                "stats": [
                    {"name": "total_kills", "value": 1234567},
                    {"name": "accuracy", "value": 0.75},
                ],
                "achievements": [
                    {"name": "ACH_1", "achieved": 1},
                    {"name": "ACH_2", "achieved": 0},
                ],
            }
        }

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_user_stats_for_game(
                steam_id="76561198000000001", app_id=440
            )

        assert "Test Game" in result
        assert "total_kills" in result
        assert "1,234,567" in result
        assert "1/2 unlocked" in result

    @pytest.mark.asyncio
    async def test_private_profile(self, user_stats, mock_client):
        """Should handle private profile."""
        mock_client.get.side_effect = Exception("private profile")

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_user_stats_for_game(
                steam_id="76561198000000001", app_id=440
            )

        assert "private" in result.lower()

    @pytest.mark.asyncio
    async def test_no_stats(self, user_stats, mock_client):
        """Should handle no stats found."""
        mock_client.get.return_value = {"playerstats": {}}

        with patch(
            "steam_mcp.endpoints.base.normalize_steam_id",
            new_callable=AsyncMock,
            return_value="76561198000000001",
        ):
            result = await user_stats.get_user_stats_for_game(
                steam_id="76561198000000001", app_id=440
            )

        assert "No stats found" in result


class TestGetCurrentPlayers:
    """Tests for get_current_players endpoint."""

    @pytest.mark.asyncio
    async def test_returns_player_count(self, user_stats, mock_client):
        """Should return current player count."""
        mock_client.get.return_value = {
            "response": {"result": 1, "player_count": 50000}
        }

        result = await user_stats.get_current_players(app_id=440)

        assert "50,000" in result
        assert "440" in result

    @pytest.mark.asyncio
    async def test_popularity_indicators(self, user_stats, mock_client):
        """Should show popularity indicators based on count."""
        # Extremely popular
        mock_client.get.return_value = {
            "response": {"result": 1, "player_count": 150000}
        }
        result = await user_stats.get_current_players(app_id=440)
        assert "Extremely Popular" in result

        # Very active
        mock_client.get.return_value = {
            "response": {"result": 1, "player_count": 15000}
        }
        result = await user_stats.get_current_players(app_id=440)
        assert "Very Active" in result

        # Low
        mock_client.get.return_value = {
            "response": {"result": 1, "player_count": 50}
        }
        result = await user_stats.get_current_players(app_id=440)
        assert "Low" in result

    @pytest.mark.asyncio
    async def test_invalid_app(self, user_stats, mock_client):
        """Should handle invalid app ID."""
        mock_client.get.return_value = {"response": {"result": 0}}

        result = await user_stats.get_current_players(app_id=99999)

        assert "Could not get player count" in result


class TestGetGlobalStatsForGame:
    """Tests for get_global_stats_for_game endpoint."""

    @pytest.mark.asyncio
    async def test_returns_global_stats(self, user_stats, mock_client):
        """Should return global stats."""
        mock_client.get.return_value = {
            "response": {
                "result": 1,
                "globalstats": {
                    "total_kills": {"total": 1000000000},
                    "total_deaths": {"total": 500000000},
                },
            }
        }

        result = await user_stats.get_global_stats_for_game(
            app_id=440, stat_names=["total_kills", "total_deaths"]
        )

        assert "total_kills" in result
        assert "1,000,000,000" in result
        assert "total_deaths" in result

    @pytest.mark.asyncio
    async def test_empty_stat_names(self, user_stats):
        """Should return error for empty stat names."""
        result = await user_stats.get_global_stats_for_game(
            app_id=440, stat_names=[]
        )

        assert "Error" in result
        assert "at least one stat name" in result

    @pytest.mark.asyncio
    async def test_invalid_stats(self, user_stats, mock_client):
        """Should handle invalid stat names."""
        mock_client.get.return_value = {"response": {"result": 0}}

        result = await user_stats.get_global_stats_for_game(
            app_id=440, stat_names=["invalid_stat"]
        )

        assert "Could not get global stats" in result

    @pytest.mark.asyncio
    async def test_no_stats_returned(self, user_stats, mock_client):
        """Should handle empty globalstats response."""
        mock_client.get.return_value = {
            "response": {"result": 1, "globalstats": {}}
        }

        result = await user_stats.get_global_stats_for_game(
            app_id=440, stat_names=["some_stat"]
        )

        assert "No global stats returned" in result
