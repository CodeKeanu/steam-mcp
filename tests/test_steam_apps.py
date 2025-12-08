"""Tests for ISteamApps endpoint - get_similar_games."""

import pytest
from unittest.mock import AsyncMock, MagicMock


from steam_mcp.endpoints.steam_apps import ISteamApps


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.get = AsyncMock()
    client.get_store_api = AsyncMock()
    return client


@pytest.fixture
def steam_apps(mock_client):
    """Create ISteamApps instance with mock client."""
    return ISteamApps(mock_client)


class TestGetSimilarGames:
    """Tests for get_similar_games endpoint."""

    @pytest.mark.asyncio
    async def test_empty_app_ids_returns_error(self, steam_apps):
        """Empty app_ids list should return error."""
        result = await steam_apps.get_similar_games(app_ids=[])

        assert "At least one app ID is required" in result

    @pytest.mark.asyncio
    async def test_app_not_found_returns_error(self, steam_apps, mock_client):
        """All app IDs not found should return error message."""
        mock_client.get_store_api.return_value = {
            "12345": {"success": False}
        }

        result = await steam_apps.get_similar_games(app_ids=[12345])

        assert "None of the provided app IDs could be found" in result

    @pytest.mark.asyncio
    async def test_app_with_no_genres_returns_error(self, steam_apps, mock_client):
        """App with no genre data should return error."""
        mock_client.get_store_api.return_value = {
            "12345": {
                "success": True,
                "data": {
                    "name": "Test Game",
                    "genres": [],
                    "categories": [],
                },
            }
        }

        result = await steam_apps.get_similar_games(app_ids=[12345])

        assert "No genre data available" in result
        assert "Test Game" in result

    @pytest.mark.asyncio
    async def test_finds_similar_games_by_genre_overlap(self, steam_apps, mock_client):
        """Should find games with matching genres."""
        # Source game
        source_details = {
            "440": {
                "success": True,
                "data": {
                    "name": "Team Fortress 2",
                    "steam_appid": 440,
                    "genres": [{"id": "1", "description": "Action"}],
                    "categories": [{"id": "1", "description": "Multi-player"}],
                },
            }
        }

        # Candidate game with matching genre
        candidate_details = {
            "730": {
                "success": True,
                "data": {
                    "name": "Counter-Strike 2",
                    "steam_appid": 730,
                    "is_free": True,
                    "genres": [{"id": "1", "description": "Action"}],
                    "categories": [{"id": "1", "description": "Multi-player"}],
                },
            }
        }

        mock_client.get_store_api.side_effect = [source_details, candidate_details]
        mock_client.get.return_value = {
            "response": {"apps": [{"appid": 730, "name": "Counter-Strike 2"}]}
        }

        result = await steam_apps.get_similar_games(app_ids=[440], max_results=5)

        assert "Games similar to 'Team Fortress 2'" in result
        assert "Counter-Strike 2" in result

    @pytest.mark.asyncio
    async def test_multiple_source_games(self, steam_apps, mock_client):
        """Should combine genres from multiple source games."""
        # Two source games with different genres
        def get_store_response(appid_str):
            responses = {
                "440": {
                    "440": {
                        "success": True,
                        "data": {
                            "name": "Team Fortress 2",
                            "steam_appid": 440,
                            "genres": [{"id": "1", "description": "Action"}],
                            "categories": [],
                        },
                    }
                },
                "570": {
                    "570": {
                        "success": True,
                        "data": {
                            "name": "Dota 2",
                            "steam_appid": 570,
                            "genres": [{"id": "2", "description": "Strategy"}],
                            "categories": [],
                        },
                    }
                },
                "730": {
                    "730": {
                        "success": True,
                        "data": {
                            "name": "Counter-Strike 2",
                            "steam_appid": 730,
                            "is_free": True,
                            "genres": [
                                {"id": "1", "description": "Action"},
                                {"id": "2", "description": "Strategy"},
                            ],
                            "categories": [],
                        },
                    }
                },
            }
            # Extract appid from params
            for key in responses:
                if key in appid_str.get("appids", ""):
                    return responses[key]
            return {}

        mock_client.get_store_api.side_effect = lambda endpoint, params: (
            get_store_response(params)
        )
        mock_client.get.return_value = {
            "response": {"apps": [{"appid": 730, "name": "Counter-Strike 2"}]}
        }

        result = await steam_apps.get_similar_games(app_ids=[440, 570], max_results=5)

        assert "Games similar to: Team Fortress 2, Dota 2" in result
        assert "Counter-Strike 2" in result

    @pytest.mark.asyncio
    async def test_respects_max_results_limit(self, steam_apps, mock_client):
        """Should limit output to max_results."""
        source_details = {
            "440": {
                "success": True,
                "data": {
                    "name": "Source Game",
                    "genres": [{"id": "1", "description": "Action"}],
                    "categories": [],
                },
            }
        }

        # Create 5 candidate games
        candidates = [{"appid": i, "name": f"Game {i}"} for i in range(100, 105)]

        def make_candidate_response(appid):
            return {
                str(appid): {
                    "success": True,
                    "data": {
                        "name": f"Game {appid}",
                        "steam_appid": appid,
                        "genres": [{"id": "1", "description": "Action"}],
                        "categories": [],
                    },
                }
            }

        mock_client.get_store_api.side_effect = [
            source_details,
            *[make_candidate_response(c["appid"]) for c in candidates],
        ]
        mock_client.get.return_value = {"response": {"apps": candidates}}

        result = await steam_apps.get_similar_games(app_ids=[440], max_results=2)

        # Count game entries (lines starting with "  [")
        game_lines = [line for line in result.split("\n") if line.strip().startswith("[")]
        assert len(game_lines) <= 2

    @pytest.mark.asyncio
    async def test_partial_failures_still_work(self, steam_apps, mock_client):
        """Should work if some app IDs fail but others succeed."""
        # First app fails, second succeeds
        mock_client.get_store_api.side_effect = [
            {"99999": {"success": False}},  # First app not found
            {
                "440": {
                    "success": True,
                    "data": {
                        "name": "Team Fortress 2",
                        "steam_appid": 440,
                        "genres": [{"id": "1", "description": "Action"}],
                        "categories": [],
                    },
                }
            },
            {
                "730": {
                    "success": True,
                    "data": {
                        "name": "Counter-Strike 2",
                        "steam_appid": 730,
                        "genres": [{"id": "1", "description": "Action"}],
                        "categories": [],
                    },
                }
            },
        ]
        mock_client.get.return_value = {
            "response": {"apps": [{"appid": 730}]}
        }

        result = await steam_apps.get_similar_games(app_ids=[99999, 440])

        assert "Team Fortress 2" in result
        assert "Counter-Strike 2" in result
        assert "Could not find app IDs: [99999]" in result

    @pytest.mark.asyncio
    async def test_empty_app_catalog_returns_error(self, steam_apps, mock_client):
        """Empty app catalog should return error."""
        source_details = {
            "440": {
                "success": True,
                "data": {
                    "name": "Test Game",
                    "genres": [{"id": "1", "description": "Action"}],
                    "categories": [],
                },
            }
        }

        mock_client.get_store_api.return_value = source_details
        mock_client.get.return_value = {"response": {"apps": []}}

        result = await steam_apps.get_similar_games(app_ids=[440])

        assert "Could not fetch game catalog" in result
