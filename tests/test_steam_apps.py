"""Tests for ISteamApps endpoints - get_similar_games, get_game_reviews, get_full_game_details."""

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


class TestGetGameReviews:
    """Tests for get_game_reviews endpoint."""

    @pytest.mark.asyncio
    async def test_empty_app_ids_returns_error(self, steam_apps):
        """Empty app_ids list should return error."""
        result = await steam_apps.get_game_reviews(app_ids=[])

        assert "At least one app ID is required" in result

    @pytest.mark.asyncio
    async def test_summary_mode_returns_scores_only(self, steam_apps, mock_client):
        """Summary mode should return only rating and counts."""
        mock_client.get_raw = AsyncMock(return_value={
            "success": 1,
            "query_summary": {
                "total_reviews": 1000,
                "total_positive": 850,
                "total_negative": 150,
                "review_score_desc": "Very Positive",
            },
            "reviews": [],
        })

        result = await steam_apps.get_game_reviews(app_ids=[440], view_mode="summary")

        assert "Very Positive" in result
        assert "1,000" in result
        assert "85% positive" in result
        assert "Sample Reviews" not in result

    @pytest.mark.asyncio
    async def test_standard_mode_includes_reviews(self, steam_apps, mock_client):
        """Standard mode should include sample reviews."""
        mock_client.get_raw = AsyncMock(return_value={
            "success": 1,
            "query_summary": {
                "total_reviews": 500,
                "total_positive": 400,
                "total_negative": 100,
                "review_score_desc": "Mostly Positive",
            },
            "reviews": [
                {
                    "voted_up": True,
                    "review": "Great game!",
                    "votes_up": 10,
                    "author": {"playtime_forever": 120},
                },
                {
                    "voted_up": False,
                    "review": "Not for me.",
                    "votes_up": 5,
                    "author": {"playtime_forever": 60},
                },
            ],
        })

        result = await steam_apps.get_game_reviews(app_ids=[440], view_mode="standard")

        assert "Mostly Positive" in result
        assert "Sample Reviews" in result
        assert "Recommended" in result
        assert "Great game!" in result

    @pytest.mark.asyncio
    async def test_detailed_mode_shows_more_text(self, steam_apps, mock_client):
        """Detailed mode should show more review text."""
        long_review = "A" * 400  # 400 chars
        mock_client.get_raw = AsyncMock(return_value={
            "success": 1,
            "query_summary": {
                "total_reviews": 100,
                "total_positive": 90,
                "total_negative": 10,
                "review_score_desc": "Very Positive",
            },
            "reviews": [
                {
                    "voted_up": True,
                    "review": long_review,
                    "votes_up": 50,
                    "author": {"playtime_forever": 600},
                },
            ],
        })

        # Standard mode truncates at 200 chars
        result_standard = await steam_apps.get_game_reviews(
            app_ids=[440], view_mode="standard"
        )
        # Detailed mode allows up to 500 chars
        result_detailed = await steam_apps.get_game_reviews(
            app_ids=[440], view_mode="detailed"
        )

        # Standard should have truncated (200 + "...")
        assert "..." in result_standard
        # Detailed should have full text (400 < 500)
        assert long_review in result_detailed

    @pytest.mark.asyncio
    async def test_multiple_games(self, steam_apps, mock_client):
        """Should fetch reviews for multiple games."""
        mock_client.get_raw = AsyncMock(side_effect=[
            {
                "success": 1,
                "query_summary": {
                    "total_reviews": 100,
                    "total_positive": 80,
                    "total_negative": 20,
                    "review_score_desc": "Mostly Positive",
                },
                "reviews": [],
            },
            {
                "success": 1,
                "query_summary": {
                    "total_reviews": 200,
                    "total_positive": 50,
                    "total_negative": 150,
                    "review_score_desc": "Mostly Negative",
                },
                "reviews": [],
            },
        ])

        result = await steam_apps.get_game_reviews(
            app_ids=[440, 730], view_mode="summary"
        )

        assert "App 440" in result
        assert "App 730" in result
        assert "Mostly Positive" in result
        assert "Mostly Negative" in result

    @pytest.mark.asyncio
    async def test_review_type_filter(self, steam_apps, mock_client):
        """Should pass review_type filter to API."""
        mock_client.get_raw = AsyncMock(return_value={
            "success": 1,
            "query_summary": {
                "total_reviews": 50,
                "total_positive": 0,
                "total_negative": 50,
                "review_score_desc": "Negative",
            },
            "reviews": [],
        })

        await steam_apps.get_game_reviews(
            app_ids=[440], review_type="negative", view_mode="summary"
        )

        # Verify the call was made with correct params
        call_args = mock_client.get_raw.call_args
        assert call_args[1]["params"]["review_type"] == "negative"

    @pytest.mark.asyncio
    async def test_failed_fetch_reports_error(self, steam_apps, mock_client):
        """Should report failed app IDs."""
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_game_reviews(app_ids=[99999], view_mode="summary")

        assert "Could not fetch reviews" in result

    @pytest.mark.asyncio
    async def test_partial_failure_still_returns_data(self, steam_apps, mock_client):
        """Should return data for successful fetches even if some fail."""
        mock_client.get_raw = AsyncMock(side_effect=[
            {"success": 0},  # First fails
            {
                "success": 1,
                "query_summary": {
                    "total_reviews": 100,
                    "total_positive": 90,
                    "total_negative": 10,
                    "review_score_desc": "Very Positive",
                },
                "reviews": [],
            },
        ])

        result = await steam_apps.get_game_reviews(
            app_ids=[99999, 440], view_mode="summary"
        )

        assert "App 440" in result
        assert "Very Positive" in result
        assert "Could not fetch reviews for app IDs: [99999]" in result


class TestGetFullGameDetails:
    """Tests for get_full_game_details aggregate endpoint."""

    @pytest.mark.asyncio
    async def test_returns_error_when_app_not_found(self, steam_apps, mock_client):
        """Should return error when app details cannot be fetched."""
        mock_client.get_store_api.return_value = {
            "12345": {"success": False}
        }
        mock_client.get.return_value = {"response": {}}
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(app_id=12345)

        assert "Could not fetch details for App ID 12345" in result

    @pytest.mark.asyncio
    async def test_returns_basic_info_section(self, steam_apps, mock_client):
        """Should include basic info section with app details."""
        mock_client.get_store_api.return_value = {
            "440": {
                "success": True,
                "data": {
                    "name": "Team Fortress 2",
                    "steam_appid": 440,
                    "type": "game",
                    "is_free": True,
                    "short_description": "A team-based multiplayer shooter.",
                    "developers": ["Valve"],
                    "publishers": ["Valve"],
                    "release_date": {"coming_soon": False, "date": "Oct 10, 2007"},
                    "platforms": {"windows": True, "mac": True, "linux": True},
                    "genres": [{"description": "Action"}, {"description": "Free to Play"}],
                    "categories": [{"description": "Multi-player"}],
                },
            }
        }
        mock_client.get.return_value = {"response": {"result": 1, "player_count": 50000}}
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(
            app_id=440,
            include_reviews=False,
            include_achievements=False,
            include_news=False,
        )

        assert "Team Fortress 2" in result
        assert "BASIC INFO" in result
        assert "App ID: 440" in result
        assert "Valve" in result
        assert "Free to Play" in result
        assert "Windows" in result

    @pytest.mark.asyncio
    async def test_includes_player_count(self, steam_apps, mock_client):
        """Should include current player count section."""
        mock_client.get_store_api.return_value = {
            "730": {
                "success": True,
                "data": {
                    "name": "Counter-Strike 2",
                    "steam_appid": 730,
                    "type": "game",
                    "is_free": True,
                    "developers": ["Valve"],
                    "publishers": ["Valve"],
                    "release_date": {"coming_soon": False, "date": "Aug 21, 2012"},
                    "platforms": {"windows": True, "mac": False, "linux": True},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        mock_client.get.return_value = {
            "response": {"result": 1, "player_count": 1234567}
        }
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(
            app_id=730,
            include_reviews=False,
            include_achievements=False,
            include_news=False,
        )

        assert "CURRENT PLAYERS" in result
        assert "1,234,567 playing now" in result

    @pytest.mark.asyncio
    async def test_includes_reviews_section(self, steam_apps, mock_client):
        """Should include reviews section when enabled."""
        mock_client.get_store_api.return_value = {
            "440": {
                "success": True,
                "data": {
                    "name": "Team Fortress 2",
                    "steam_appid": 440,
                    "type": "game",
                    "is_free": True,
                    "developers": [],
                    "publishers": [],
                    "release_date": {},
                    "platforms": {},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        mock_client.get.return_value = {"response": {}}
        mock_client.get_raw = AsyncMock(return_value={
            "success": 1,
            "query_summary": {
                "total_reviews": 1000000,
                "total_positive": 950000,
                "total_negative": 50000,
                "review_score_desc": "Overwhelmingly Positive",
            },
            "reviews": [
                {
                    "voted_up": True,
                    "review": "Best game ever!",
                    "votes_up": 100,
                    "author": {"playtime_forever": 6000},
                },
            ],
        })

        result = await steam_apps.get_full_game_details(
            app_id=440,
            include_reviews=True,
            include_achievements=False,
            include_news=False,
        )

        assert "USER REVIEWS" in result
        assert "Overwhelmingly Positive" in result
        assert "1,000,000 reviews" in result
        assert "95% positive" in result
        assert "Sample Reviews:" in result

    @pytest.mark.asyncio
    async def test_includes_achievements_section(self, steam_apps, mock_client):
        """Should include achievements section when enabled."""
        mock_client.get_store_api.return_value = {
            "440": {
                "success": True,
                "data": {
                    "name": "Team Fortress 2",
                    "steam_appid": 440,
                    "type": "game",
                    "is_free": True,
                    "developers": [],
                    "publishers": [],
                    "release_date": {},
                    "platforms": {},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        mock_client.get.side_effect = [
            {"response": {}},  # player count
            {
                "achievementpercentages": {
                    "achievements": [
                        {"name": "Super Rare", "percent": 0.5},
                        {"name": "Very Rare", "percent": 2.0},
                        {"name": "Common", "percent": 80.0},
                        {"name": "Very Common", "percent": 95.0},
                    ]
                }
            },
        ]
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(
            app_id=440,
            include_reviews=False,
            include_achievements=True,
            include_news=False,
        )

        assert "ACHIEVEMENTS" in result
        assert "Total: 4 achievements" in result
        assert "Rarest:" in result
        assert "Super Rare" in result
        assert "ULTRA RARE" in result
        assert "Most Common:" in result

    @pytest.mark.asyncio
    async def test_includes_news_section(self, steam_apps, mock_client):
        """Should include news section when enabled."""
        mock_client.get_store_api.return_value = {
            "440": {
                "success": True,
                "data": {
                    "name": "Team Fortress 2",
                    "steam_appid": 440,
                    "type": "game",
                    "is_free": True,
                    "developers": [],
                    "publishers": [],
                    "release_date": {},
                    "platforms": {},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        mock_client.get.side_effect = [
            {"response": {}},  # player count
            {
                "appnews": {
                    "newsitems": [
                        {
                            "title": "Big Update Coming",
                            "date": 1702000000,
                            "contents": "Exciting news about the update!",
                            "url": "https://example.com/news",
                        },
                    ]
                }
            },
        ]
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(
            app_id=440,
            include_reviews=False,
            include_achievements=False,
            include_news=True,
        )

        assert "RECENT NEWS" in result
        assert "Big Update Coming" in result

    @pytest.mark.asyncio
    async def test_handles_partial_api_failures_gracefully(self, steam_apps, mock_client):
        """Should still return results when some APIs fail."""
        mock_client.get_store_api.return_value = {
            "440": {
                "success": True,
                "data": {
                    "name": "Team Fortress 2",
                    "steam_appid": 440,
                    "type": "game",
                    "is_free": True,
                    "developers": ["Valve"],
                    "publishers": ["Valve"],
                    "release_date": {},
                    "platforms": {"windows": True},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        # Player count fails, achievements fail, news fails
        mock_client.get.return_value = {"response": {}}
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(app_id=440)

        # Should still have basic info
        assert "Team Fortress 2" in result
        assert "BASIC INFO" in result
        # Graceful handling of missing data
        assert "Player count unavailable" in result
        assert "No review data available" in result
        assert "No achievement data available" in result
        assert "No recent news" in result

    @pytest.mark.asyncio
    async def test_respects_num_sample_reviews_param(self, steam_apps, mock_client):
        """Should respect the num_sample_reviews parameter."""
        mock_client.get_store_api.return_value = {
            "440": {
                "success": True,
                "data": {
                    "name": "Test Game",
                    "steam_appid": 440,
                    "type": "game",
                    "is_free": True,
                    "developers": [],
                    "publishers": [],
                    "release_date": {},
                    "platforms": {},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        mock_client.get.return_value = {"response": {}}
        mock_client.get_raw = AsyncMock(return_value={
            "success": 1,
            "query_summary": {
                "total_reviews": 100,
                "total_positive": 80,
                "total_negative": 20,
                "review_score_desc": "Positive",
            },
            "reviews": [
                {"voted_up": True, "review": f"Review {i}", "votes_up": 10, "author": {"playtime_forever": 60}}
                for i in range(10)
            ],
        })

        result = await steam_apps.get_full_game_details(
            app_id=440,
            include_achievements=False,
            include_news=False,
            num_sample_reviews=2,
        )

        # Check that get_raw was called with num_per_page=2
        call_args = mock_client.get_raw.call_args
        assert call_args[1]["params"]["num_per_page"] == 2

    @pytest.mark.asyncio
    async def test_includes_store_link(self, steam_apps, mock_client):
        """Should include Steam store link."""
        mock_client.get_store_api.return_value = {
            "1234": {
                "success": True,
                "data": {
                    "name": "Test Game",
                    "steam_appid": 1234,
                    "type": "game",
                    "is_free": False,
                    "developers": [],
                    "publishers": [],
                    "release_date": {},
                    "platforms": {},
                    "genres": [],
                    "categories": [],
                },
            }
        }
        mock_client.get.return_value = {"response": {}}
        mock_client.get_raw = AsyncMock(return_value={"success": 0})

        result = await steam_apps.get_full_game_details(
            app_id=1234,
            include_reviews=False,
            include_achievements=False,
            include_news=False,
        )

        assert "https://store.steampowered.com/app/1234" in result
