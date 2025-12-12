"""Tests for Steam Workshop endpoint (IPublishedFileService)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from steam_mcp.endpoints.steam_workshop import IPublishedFileService


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    return client


@pytest.fixture
def workshop_service(mock_client):
    """Create IPublishedFileService instance with mock client."""
    return IPublishedFileService(mock_client)


# --- search_workshop_items tests ---


class TestSearchWorkshopItems:
    """Tests for search_workshop_items endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_items(self, workshop_service, mock_client):
        """Should return Workshop items for a game."""
        mock_client.get.return_value = {
            "response": {
                "total": 2,
                "publishedfiledetails": [
                    {
                        "publishedfileid": "123456",
                        "title": "Test Mod",
                        "creator": "76561198000000001",
                        "subscriptions": 1000,
                        "favorited": 500,
                        "views": 5000,
                        "file_size": 1048576,  # 1 MB
                        "vote_data": {"score": 0.95, "votes_up": 100, "votes_down": 5},
                        "tags": [{"tag": "Maps"}, {"tag": "Multiplayer"}],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                    },
                    {
                        "publishedfileid": "789012",
                        "title": "Another Mod",
                        "creator": "76561198000000002",
                        "subscriptions": 500,
                        "favorited": 200,
                        "views": 2000,
                        "file_size": 524288,  # 512 KB
                        "vote_data": {"score": 0.80, "votes_up": 80, "votes_down": 20},
                        "tags": [{"tag": "Weapons"}],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                    },
                ],
            }
        }

        result = await workshop_service.search_workshop_items(app_id=730)

        assert "Test Mod" in result
        assert "Another Mod" in result
        assert "1,000" in result  # Subscriber count
        assert "Maps" in result

    @pytest.mark.asyncio
    async def test_search_with_query(self, workshop_service, mock_client):
        """Should pass search query to API."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        await workshop_service.search_workshop_items(app_id=730, search_query="awp skin")

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["search_text"] == "awp skin"

    @pytest.mark.asyncio
    async def test_search_with_tags(self, workshop_service, mock_client):
        """Should pass tags to API."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        await workshop_service.search_workshop_items(app_id=730, tags=["Maps", "Competitive"])

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["requiredtags[0]"] == "Maps"
        assert call_args[1]["params"]["requiredtags[1]"] == "Competitive"

    @pytest.mark.asyncio
    async def test_search_empty_results(self, workshop_service, mock_client):
        """Should handle no results gracefully."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        result = await workshop_service.search_workshop_items(app_id=99999)

        assert "No Workshop items found" in result
        assert "may not have Workshop support" in result

    @pytest.mark.asyncio
    async def test_search_json_format(self, workshop_service, mock_client):
        """Should return JSON when format='json'."""
        mock_client.get.return_value = {
            "response": {
                "total": 1,
                "publishedfiledetails": [
                    {
                        "publishedfileid": "123",
                        "title": "Test",
                        "subscriptions": 100,
                        "file_size": 1024,
                        "vote_data": {"score": 0.9},
                        "tags": [],
                    }
                ],
            }
        }

        result = await workshop_service.search_workshop_items(app_id=730, format="json")

        data = json.loads(result)
        assert data["app_id"] == 730
        assert data["total_results"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["workshop_id"] == "123"

    @pytest.mark.asyncio
    async def test_search_sort_by_options(self, workshop_service, mock_client):
        """Should map sort_by to correct query_type."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        # Test different sort options
        for sort_by, expected_type in [("popular", 0), ("trend", 1), ("recent", 2), ("rating", 3)]:
            await workshop_service.search_workshop_items(app_id=730, sort_by=sort_by)
            call_args = mock_client.get.call_args
            assert call_args[1]["params"]["query_type"] == expected_type

    @pytest.mark.asyncio
    async def test_search_max_results_limit(self, workshop_service, mock_client):
        """Should cap max_results at 50."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        await workshop_service.search_workshop_items(app_id=730, max_results=100)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["numperpage"] == 50

    @pytest.mark.asyncio
    async def test_search_api_error(self, workshop_service, mock_client):
        """Should handle API errors gracefully."""
        mock_client.get.side_effect = Exception("API connection failed")

        result = await workshop_service.search_workshop_items(app_id=730)

        assert "Error" in result
        assert "API connection failed" in result


# --- search_workshop_collections tests ---


class TestSearchWorkshopCollections:
    """Tests for search_workshop_collections endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_collections(self, workshop_service, mock_client):
        """Should return Workshop collections for a game."""
        mock_client.get.return_value = {
            "response": {
                "total": 2,
                "publishedfiledetails": [
                    {
                        "publishedfileid": "111111",
                        "title": "Ultimate Modpack",
                        "file_description": "Collection of essential mods",
                        "creator": "76561198000000001",
                        "creator_name": "CollectorOne",
                        "subscriptions": 10000,
                        "favorited": 5000,
                        "file_type": 2,  # Collection
                        "vote_data": {"score": 0.95, "votes_up": 950, "votes_down": 50},
                        "children": [
                            {"publishedfileid": "1"},
                            {"publishedfileid": "2"},
                            {"publishedfileid": "3"},
                        ],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                    },
                    {
                        "publishedfileid": "222222",
                        "title": "Starter Pack",
                        "file_description": "Beginner collection",
                        "creator": "76561198000000002",
                        "creator_name": "CollectorTwo",
                        "subscriptions": 5000,
                        "favorited": 2000,
                        "file_type": 2,
                        "vote_data": {"score": 0.80, "votes_up": 80, "votes_down": 20},
                        "children": [{"publishedfileid": "4"}],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                    },
                ],
            }
        }

        result = await workshop_service.search_workshop_collections(app_id=730)

        assert "Ultimate Modpack" in result
        assert "Starter Pack" in result
        assert "10,000" in result  # Subscriber count
        assert "Items: 3" in result  # Item count
        assert "CollectorOne" in result

    @pytest.mark.asyncio
    async def test_search_collections_with_query(self, workshop_service, mock_client):
        """Should pass search query to API."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        await workshop_service.search_workshop_collections(
            app_id=730, search_query="weapon skins"
        )

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["search_text"] == "weapon skins"
        assert call_args[1]["params"]["filetype"] == 2  # Collections only

    @pytest.mark.asyncio
    async def test_search_collections_empty_results(self, workshop_service, mock_client):
        """Should handle no results gracefully."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        result = await workshop_service.search_workshop_collections(app_id=99999)

        assert "No Workshop collections found" in result
        assert "may not have Workshop collections" in result

    @pytest.mark.asyncio
    async def test_search_collections_json_format(self, workshop_service, mock_client):
        """Should return JSON when format='json'."""
        mock_client.get.return_value = {
            "response": {
                "total": 1,
                "publishedfiledetails": [
                    {
                        "publishedfileid": "123",
                        "title": "Test Collection",
                        "file_description": "A test",
                        "creator": "76561198000000001",
                        "creator_name": "Tester",
                        "subscriptions": 100,
                        "favorited": 50,
                        "file_type": 2,
                        "vote_data": {"score": 0.9, "votes_up": 90, "votes_down": 10},
                        "children": [{"publishedfileid": "1"}, {"publishedfileid": "2"}],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                    }
                ],
            }
        }

        result = await workshop_service.search_workshop_collections(
            app_id=730, format="json"
        )

        data = json.loads(result)
        assert data["app_id"] == 730
        assert data["total_results"] == 1
        assert len(data["collections"]) == 1
        assert data["collections"][0]["collection_id"] == "123"
        assert data["collections"][0]["name"] == "Test Collection"
        assert data["collections"][0]["item_count"] == 2

    @pytest.mark.asyncio
    async def test_search_collections_sort_options(self, workshop_service, mock_client):
        """Should map sort_by to correct query_type."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        for sort_by, expected_type in [
            ("popular", 0),
            ("trend", 1),
            ("recent", 2),
            ("rating", 3),
        ]:
            await workshop_service.search_workshop_collections(
                app_id=730, sort_by=sort_by
            )
            call_args = mock_client.get.call_args
            assert call_args[1]["params"]["query_type"] == expected_type

    @pytest.mark.asyncio
    async def test_search_collections_max_results_limit(
        self, workshop_service, mock_client
    ):
        """Should cap max_results at 50."""
        mock_client.get.return_value = {
            "response": {"total": 0, "publishedfiledetails": []}
        }

        await workshop_service.search_workshop_collections(app_id=730, max_results=100)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["numperpage"] == 50

    @pytest.mark.asyncio
    async def test_search_collections_api_error(self, workshop_service, mock_client):
        """Should handle API errors gracefully."""
        mock_client.get.side_effect = Exception("API connection failed")

        result = await workshop_service.search_workshop_collections(app_id=730)

        assert "Error" in result
        assert "API connection failed" in result

    @pytest.mark.asyncio
    async def test_search_collections_handles_string_values(
        self, workshop_service, mock_client
    ):
        """Should handle string numeric values from API."""
        mock_client.get.return_value = {
            "response": {
                "total": "1",  # String
                "publishedfiledetails": [
                    {
                        "publishedfileid": "123",
                        "title": "String Collection",
                        "subscriptions": "5000",  # String
                        "favorited": "250",  # String
                        "file_type": "2",  # String
                        "vote_data": {"score": "0.95", "votes_up": "95", "votes_down": "5"},
                        "children": [{"publishedfileid": "1"}],
                        "time_created": "1609459200",
                        "time_updated": "1704067200",
                    }
                ],
            }
        }

        result = await workshop_service.search_workshop_collections(app_id=730)

        assert "String Collection" in result
        assert "5,000" in result  # Formatted with comma


# --- get_workshop_item_details tests ---


class TestGetWorkshopItemDetails:
    """Tests for get_workshop_item_details endpoint."""

    @pytest.mark.asyncio
    async def test_get_details_success(self, workshop_service, mock_client):
        """Should return item details."""
        mock_client.get.return_value = {
            "response": {
                "publishedfiledetails": [
                    {
                        "result": 1,
                        "publishedfileid": "123456",
                        "title": "Awesome Mod",
                        "file_description": "This is a great mod for the game.",
                        "consumer_appid": 730,
                        "creator": "76561198000000001",
                        "creator_name": "ModAuthor",
                        "subscriptions": 10000,
                        "favorited": 5000,
                        "views": 50000,
                        "file_size": 52428800,  # 50 MB
                        "vote_data": {"score": 0.95, "votes_up": 950, "votes_down": 50},
                        "tags": [{"tag": "Gameplay"}, {"tag": "Realism"}],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                        "children": [{"publishedfileid": "111"}, {"publishedfileid": "222"}],
                    }
                ]
            }
        }

        result = await workshop_service.get_workshop_item_details(workshop_id="123456")

        assert "Awesome Mod" in result
        assert "ModAuthor" in result
        assert "10,000" in result  # Subscribers
        assert "95%" in result  # Rating
        assert "50.0 MB" in result
        assert "Dependencies (2)" in result

    @pytest.mark.asyncio
    async def test_get_details_not_found(self, workshop_service, mock_client):
        """Should handle item not found."""
        mock_client.get.return_value = {"response": {"publishedfiledetails": []}}

        result = await workshop_service.get_workshop_item_details(workshop_id="999999")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_details_private_item(self, workshop_service, mock_client):
        """Should handle private/invalid items."""
        mock_client.get.return_value = {
            "response": {
                "publishedfiledetails": [
                    {"result": 9, "publishedfileid": "123456"}  # Result 9 = private/deleted
                ]
            }
        }

        result = await workshop_service.get_workshop_item_details(workshop_id="123456")

        assert "not found or is private" in result.lower()

    @pytest.mark.asyncio
    async def test_get_details_json_format(self, workshop_service, mock_client):
        """Should return JSON when format='json'."""
        mock_client.get.return_value = {
            "response": {
                "publishedfiledetails": [
                    {
                        "result": 1,
                        "publishedfileid": "123",
                        "title": "Test",
                        "file_description": "Description",
                        "consumer_appid": 730,
                        "creator": "76561198000000001",
                        "subscriptions": 100,
                        "file_size": 1024,
                        "vote_data": {"score": 0.9, "votes_up": 90, "votes_down": 10},
                        "tags": [],
                        "time_created": 1609459200,
                        "time_updated": 1704067200,
                    }
                ]
            }
        }

        result = await workshop_service.get_workshop_item_details(
            workshop_id="123", format="json"
        )

        data = json.loads(result)
        assert data["workshop_id"] == "123"
        assert data["title"] == "Test"
        assert data["subscriber_count"] == 100
        assert data["vote_data"]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_get_details_truncates_long_description(self, workshop_service, mock_client):
        """Should truncate very long descriptions."""
        long_desc = "A" * 2000
        mock_client.get.return_value = {
            "response": {
                "publishedfiledetails": [
                    {
                        "result": 1,
                        "publishedfileid": "123",
                        "title": "Test",
                        "file_description": long_desc,
                        "consumer_appid": 730,
                        "creator": "76561198000000001",
                        "subscriptions": 100,
                        "file_size": 1024,
                        "vote_data": {},
                        "tags": [],
                    }
                ]
            }
        }

        result = await workshop_service.get_workshop_item_details(workshop_id="123")

        assert "[Description truncated]" in result
        assert len(result) < len(long_desc) + 500  # Should be much shorter


# --- get_workshop_collection tests ---


class TestGetWorkshopCollection:
    """Tests for get_workshop_collection endpoint."""

    @pytest.mark.asyncio
    async def test_get_collection_success(self, workshop_service, mock_client):
        """Should return collection with items."""
        # First call: get collection details
        # Second call: get child item details
        mock_client.get.side_effect = [
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "999999",
                            "title": "My Mod Collection",
                            "file_description": "A collection of great mods.",
                            "file_type": 2,  # Collection type
                            "consumer_appid": 730,
                            "creator": "76561198000000001",
                            "creator_name": "Collector",
                            "subscriptions": 5000,
                            "children": [
                                {"publishedfileid": "111"},
                                {"publishedfileid": "222"},
                            ],
                        }
                    ]
                }
            },
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "111",
                            "title": "Mod One",
                            "subscriptions": 1000,
                            "file_size": 1024,
                            "vote_data": {"score": 0.9},
                        },
                        {
                            "result": 1,
                            "publishedfileid": "222",
                            "title": "Mod Two",
                            "subscriptions": 2000,
                            "file_size": 2048,
                            "vote_data": {"score": 0.8},
                        },
                    ]
                }
            },
        ]

        result = await workshop_service.get_workshop_collection(collection_id="999999")

        assert "My Mod Collection" in result
        assert "Collector" in result
        assert "Items in collection: 2" in result
        assert "Mod One" in result
        assert "Mod Two" in result

    @pytest.mark.asyncio
    async def test_get_collection_not_found(self, workshop_service, mock_client):
        """Should handle collection not found."""
        mock_client.get.return_value = {"response": {"publishedfiledetails": []}}

        result = await workshop_service.get_workshop_collection(collection_id="999999")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_collection_not_a_collection(self, workshop_service, mock_client):
        """Should reject non-collection items."""
        mock_client.get.return_value = {
            "response": {
                "publishedfiledetails": [
                    {
                        "result": 1,
                        "publishedfileid": "123",
                        "title": "Regular Mod",
                        "file_type": 0,  # Not a collection
                    }
                ]
            }
        }

        result = await workshop_service.get_workshop_collection(collection_id="123")

        assert "not a collection" in result.lower()

    @pytest.mark.asyncio
    async def test_get_collection_json_format(self, workshop_service, mock_client):
        """Should return JSON when format='json'."""
        mock_client.get.side_effect = [
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "999",
                            "title": "Collection",
                            "file_description": "Desc",
                            "file_type": 2,
                            "consumer_appid": 730,
                            "creator": "76561198000000001",
                            "subscriptions": 100,
                            "children": [{"publishedfileid": "111"}],
                        }
                    ]
                }
            },
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "111",
                            "title": "Item",
                            "subscriptions": 50,
                            "file_size": 1024,
                            "vote_data": {"score": 0.9},
                        }
                    ]
                }
            },
        ]

        result = await workshop_service.get_workshop_collection(
            collection_id="999", format="json"
        )

        data = json.loads(result)
        assert data["collection_id"] == "999"
        assert data["name"] == "Collection"
        assert data["item_count"] == 1
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_collection_handles_batch_fetch_failure(
        self, workshop_service, mock_client
    ):
        """Should still return collection info if batch item fetch fails."""
        mock_client.get.side_effect = [
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": 1,
                            "publishedfileid": "999",
                            "title": "Collection",
                            "file_type": 2,
                            "consumer_appid": 730,
                            "creator": "76561198000000001",
                            "subscriptions": 100,
                            "children": [{"publishedfileid": "111"}],
                        }
                    ]
                }
            },
            Exception("Batch fetch failed"),  # Second call fails
        ]

        result = await workshop_service.get_workshop_collection(collection_id="999")

        # Should still return collection info even if item fetch failed
        assert "Collection" in result
        assert "Items in collection: 1" in result


# --- Helper function tests ---


class TestHelperFunctions:
    """Tests for module helper functions."""

    def test_format_file_size(self):
        """Test file size formatting."""
        from steam_mcp.endpoints.steam_workshop import _format_file_size

        assert _format_file_size(500) == "500 B"
        assert _format_file_size(1024) == "1.0 KB"
        assert _format_file_size(1048576) == "1.0 MB"
        assert _format_file_size(1073741824) == "1.0 GB"
        assert _format_file_size(52428800) == "50.0 MB"

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        from steam_mcp.endpoints.steam_workshop import _format_timestamp

        assert _format_timestamp(0) == "Unknown"
        assert "2021-01-01" in _format_timestamp(1609459200)
        assert "UTC" in _format_timestamp(1609459200)

    def test_format_timestamp_negative(self):
        """Test timestamp formatting with negative value."""
        from steam_mcp.endpoints.steam_workshop import _format_timestamp

        assert _format_timestamp(-1) == "Unknown"


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_empty_workshop_id_returns_error(self, workshop_service):
        """Empty workshop_id should return error."""
        result = await workshop_service.get_workshop_item_details(workshop_id="")
        assert "Workshop ID is required" in result

    @pytest.mark.asyncio
    async def test_whitespace_workshop_id_returns_error(self, workshop_service):
        """Whitespace-only workshop_id should return error."""
        result = await workshop_service.get_workshop_item_details(workshop_id="   ")
        assert "Workshop ID is required" in result

    @pytest.mark.asyncio
    async def test_empty_workshop_id_json_format(self, workshop_service):
        """Empty workshop_id should return JSON error when format='json'."""
        result = await workshop_service.get_workshop_item_details(
            workshop_id="", format="json"
        )
        data = json.loads(result)
        assert "error" in data
        assert "Workshop ID is required" in data["error"]

    @pytest.mark.asyncio
    async def test_empty_collection_id_returns_error(self, workshop_service):
        """Empty collection_id should return error."""
        result = await workshop_service.get_workshop_collection(collection_id="")
        assert "Collection ID is required" in result

    @pytest.mark.asyncio
    async def test_whitespace_collection_id_returns_error(self, workshop_service):
        """Whitespace-only collection_id should return error."""
        result = await workshop_service.get_workshop_collection(collection_id="   ")
        assert "Collection ID is required" in result


class TestTagFiltering:
    """Tests for tag filtering edge cases."""

    @pytest.mark.asyncio
    async def test_tags_with_missing_key_filtered(self, workshop_service, mock_client):
        """Tags missing the 'tag' key should be filtered out."""
        mock_client.get.return_value = {
            "response": {
                "total": 1,
                "publishedfiledetails": [
                    {
                        "publishedfileid": "123",
                        "title": "Test",
                        "subscriptions": 100,
                        "file_size": 1024,
                        "vote_data": {"score": 0.9},
                        # Tags with missing 'tag' key
                        "tags": [{"tag": "Valid"}, {"other": "NoTag"}, {"tag": None}],
                    }
                ],
            }
        }

        result = await workshop_service.search_workshop_items(app_id=730, format="json")
        data = json.loads(result)

        # Only "Valid" should be in tags, others should be filtered
        assert data["items"][0]["tags"] == ["Valid"]


class TestStringTypeCoercion:
    """Tests for handling string values from Steam API (real API returns strings for some numeric fields)."""

    @pytest.mark.asyncio
    async def test_search_handles_string_numeric_values(self, workshop_service, mock_client):
        """API may return numeric fields as strings - should not raise TypeError."""
        mock_client.get.return_value = {
            "response": {
                "total": 1,
                "publishedfiledetails": [
                    {
                        "publishedfileid": "123456",
                        "title": "String Values Mod",
                        "subscriptions": "5000",  # String instead of int
                        "favorited": "250",  # String instead of int
                        "file_size": "1048576",  # String instead of int
                        "vote_data": {"score": "0.95"},  # String instead of float
                        "tags": [{"tag": "Maps"}],
                        "time_created": "1609459200",  # String instead of int
                    }
                ],
            }
        }

        # Should not raise "'<' not supported between instances of 'str' and 'int'"
        result = await workshop_service.search_workshop_items(app_id=730)

        assert "String Values Mod" in result
        assert "5,000" in result  # Formatted with comma
        assert "1.0 MB" in result  # File size formatted

    @pytest.mark.asyncio
    async def test_item_details_handles_string_values(self, workshop_service, mock_client):
        """get_workshop_item_details should handle string numeric values."""
        mock_client.get.return_value = {
            "response": {
                "publishedfiledetails": [
                    {
                        "result": "1",  # String instead of int
                        "publishedfileid": "999",
                        "title": "Test Item",
                        "file_description": "A test item",
                        "consumer_appid": "730",
                        "creator": "76561198000000001",
                        "subscriptions": "10000",
                        "favorited": "500",
                        "views": "50000",
                        "file_size": "2097152",
                        "vote_data": {
                            "score": "0.88",
                            "votes_up": "100",
                            "votes_down": "10",
                        },
                        "time_created": "1609459200",
                        "time_updated": "1704067200",
                        "tags": [],
                    }
                ]
            }
        }

        result = await workshop_service.get_workshop_item_details(workshop_id="999")

        assert "Test Item" in result
        assert "10,000" in result  # subscribers formatted
        assert "2.0 MB" in result  # file size
        assert "88%" in result  # rating

    @pytest.mark.asyncio
    async def test_collection_handles_string_values(self, workshop_service, mock_client):
        """get_workshop_collection should handle string numeric values."""
        mock_client.get.side_effect = [
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": "1",
                            "publishedfileid": "888",
                            "title": "Test Collection",
                            "file_description": "Collection desc",
                            "file_type": "2",  # String instead of int
                            "consumer_appid": "730",
                            "creator": "76561198000000001",
                            "subscriptions": "3000",
                            "children": [{"publishedfileid": "111"}],
                        }
                    ]
                }
            },
            {
                "response": {
                    "publishedfiledetails": [
                        {
                            "result": "1",
                            "publishedfileid": "111",
                            "title": "Child Item",
                            "subscriptions": "1500",
                            "file_size": "512000",
                            "vote_data": {"score": "0.75"},
                        }
                    ]
                }
            },
        ]

        result = await workshop_service.get_workshop_collection(collection_id="888")

        assert "Test Collection" in result
        assert "3,000" in result  # collection subscribers
        assert "Child Item" in result
        assert "1,500" in result  # child item subscribers

    def test_safe_int_function(self):
        """Test _safe_int helper function."""
        from steam_mcp.endpoints.steam_workshop import _safe_int

        assert _safe_int("123") == 123
        assert _safe_int(456) == 456
        assert _safe_int(None) == 0
        assert _safe_int("") == 0
        assert _safe_int("invalid") == 0
        assert _safe_int(None, default=99) == 99

    def test_safe_float_function(self):
        """Test _safe_float helper function."""
        from steam_mcp.endpoints.steam_workshop import _safe_float

        assert _safe_float("0.95") == 0.95
        assert _safe_float(0.88) == 0.88
        assert _safe_float(None) == 0.0
        assert _safe_float("") == 0.0
        assert _safe_float("invalid") == 0.0
        assert _safe_float(None, default=1.0) == 1.0

    def test_format_file_size_string_input(self):
        """_format_file_size should handle string input."""
        from steam_mcp.endpoints.steam_workshop import _format_file_size

        assert _format_file_size("1048576") == "1.0 MB"
        assert _format_file_size("") == "0 B"
        assert _format_file_size(None) == "0 B"
        assert _format_file_size("invalid") == "Unknown size"

    def test_format_timestamp_string_input(self):
        """_format_timestamp should handle string input."""
        from steam_mcp.endpoints.steam_workshop import _format_timestamp

        assert "2021-01-01" in _format_timestamp("1609459200")
        assert _format_timestamp("0") == "Unknown"
        assert _format_timestamp("") == "Unknown"
        assert _format_timestamp(None) == "Unknown"
        assert _format_timestamp("invalid") == "Unknown"
