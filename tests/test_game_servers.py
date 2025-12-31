"""Tests for IGameServersService endpoint."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from steam_mcp.endpoints.game_servers import IGameServersService


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.owner_steam_id = None
    client.get = AsyncMock()
    return client


@pytest.fixture
def game_servers(mock_client):
    """Create IGameServersService instance with mock client."""
    return IGameServersService(mock_client)


# --- get_game_servers Tests ---


class TestGetGameServers:
    """Tests for get_game_servers endpoint."""

    @pytest.mark.asyncio
    async def test_returns_server_list_text_format(self, game_servers, mock_client):
        """Should return formatted server list in text format."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Test Server",
                        "addr": "192.168.1.1:27015",
                        "map": "de_dust2",
                        "players": 10,
                        "max_players": 24,
                        "bots": 0,
                        "secure": True,
                    }
                ]
            }
        }

        result = await game_servers.get_game_servers(app_id=730)

        assert "Test Server" in result
        assert "192.168.1.1:27015" in result
        assert "de_dust2" in result
        assert "10/24" in result
        assert "VAC" in result

    @pytest.mark.asyncio
    async def test_returns_server_list_json_format(self, game_servers, mock_client):
        """Should return structured server list in JSON format."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Test Server",
                        "addr": "192.168.1.1:27015",
                        "map": "ctf_2fort",
                        "players": 5,
                        "max_players": 32,
                        "bots": 2,
                        "secure": False,
                    }
                ]
            }
        }

        result = await game_servers.get_game_servers(app_id=440, format="json")
        data = json.loads(result)

        assert data["app_id"] == 440
        assert data["server_count"] == 1
        assert len(data["servers"]) == 1
        assert data["servers"][0]["name"] == "Test Server"
        assert data["servers"][0]["bots"] == 2

    @pytest.mark.asyncio
    async def test_no_servers_found_text(self, game_servers, mock_client):
        """Should return appropriate message when no servers found."""
        mock_client.get.return_value = {"response": {}}

        result = await game_servers.get_game_servers(app_id=12345)

        assert "No servers found" in result
        assert "12345" in result

    @pytest.mark.asyncio
    async def test_no_servers_found_json(self, game_servers, mock_client):
        """Should return error JSON when no servers found."""
        mock_client.get.return_value = {"response": {"servers": []}}

        result = await game_servers.get_game_servers(app_id=12345, format="json")
        data = json.loads(result)

        assert "error" in data
        assert data["servers"] == []

    @pytest.mark.asyncio
    async def test_filter_passed_to_api(self, game_servers, mock_client):
        """Should include user filter in API request."""
        mock_client.get.return_value = {"response": {"servers": []}}

        await game_servers.get_game_servers(
            app_id=730, filter="\\map\\de_dust2"
        )

        call_args = mock_client.get.call_args
        assert "\\appid\\730" in call_args.kwargs["params"]["filter"]
        assert "\\map\\de_dust2" in call_args.kwargs["params"]["filter"]

    @pytest.mark.asyncio
    async def test_limit_passed_to_api(self, game_servers, mock_client):
        """Should pass limit parameter to API."""
        mock_client.get.return_value = {"response": {"servers": []}}

        await game_servers.get_game_servers(app_id=730, limit=50)

        call_args = mock_client.get.call_args
        assert call_args.kwargs["params"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_bots_displayed_in_text_output(self, game_servers, mock_client):
        """Should show bot count when bots are present."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Bot Server",
                        "addr": "1.2.3.4:27015",
                        "map": "test",
                        "players": 10,
                        "max_players": 24,
                        "bots": 5,
                        "secure": True,
                    }
                ]
            }
        }

        result = await game_servers.get_game_servers(app_id=730)

        assert "5 bots" in result


# --- query_server_status Tests ---


class TestQueryServerStatus:
    """Tests for query_server_status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_server_status_text(self, game_servers, mock_client):
        """Should return detailed server status in text format."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "My Game Server",
                        "addr": "192.168.1.1:27015",
                        "appid": 730,
                        "gamedir": "csgo",
                        "map": "de_inferno",
                        "players": 18,
                        "max_players": 24,
                        "bots": 0,
                        "version": "1.38.2.3",
                        "secure": True,
                        "dedicated": True,
                        "os": "l",
                        "gametype": "competitive",
                    }
                ]
            }
        }

        result = await game_servers.query_server_status(
            server_address="192.168.1.1:27015"
        )

        assert "My Game Server" in result
        assert "192.168.1.1:27015" in result
        assert "730" in result
        assert "de_inferno" in result
        assert "18/24" in result
        assert "Linux" in result
        assert "Yes" in result  # VAC secured

    @pytest.mark.asyncio
    async def test_returns_server_status_json(self, game_servers, mock_client):
        """Should return structured server status in JSON format."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Test Server",
                        "addr": "10.0.0.1:27015",
                        "appid": 440,
                        "gamedir": "tf",
                        "map": "cp_dustbowl",
                        "players": 24,
                        "max_players": 32,
                        "bots": 8,
                        "version": "7.0.0",
                        "secure": True,
                        "dedicated": True,
                        "os": "w",
                        "gametype": "payload",
                    }
                ]
            }
        }

        result = await game_servers.query_server_status(
            server_address="10.0.0.1:27015", format="json"
        )
        data = json.loads(result)

        assert data["address"] == "10.0.0.1:27015"
        assert data["name"] == "Test Server"
        assert data["app_id"] == 440
        assert data["map"] == "cp_dustbowl"
        assert data["players"] == 24
        assert data["bots"] == 8
        assert data["secure"] is True

    @pytest.mark.asyncio
    async def test_server_not_found_text(self, game_servers, mock_client):
        """Should return error message when server not found."""
        mock_client.get.return_value = {"response": {}}

        result = await game_servers.query_server_status(
            server_address="1.1.1.1:27015"
        )

        assert "not found" in result.lower()
        assert "1.1.1.1:27015" in result

    @pytest.mark.asyncio
    async def test_server_not_found_json(self, game_servers, mock_client):
        """Should return error JSON when server not found."""
        mock_client.get.return_value = {"response": {"servers": []}}

        result = await game_servers.query_server_status(
            server_address="1.1.1.1:27015", format="json"
        )
        data = json.loads(result)

        assert "error" in data
        assert data["address"] == "1.1.1.1:27015"

    @pytest.mark.asyncio
    async def test_address_filter_sent_to_api(self, game_servers, mock_client):
        """Should filter by server address in API request."""
        mock_client.get.return_value = {"response": {"servers": []}}

        await game_servers.query_server_status(server_address="5.5.5.5:27015")

        call_args = mock_client.get.call_args
        assert "\\addr\\5.5.5.5:27015" in call_args.kwargs["params"]["filter"]

    @pytest.mark.asyncio
    async def test_os_mapping_windows(self, game_servers, mock_client):
        """Should map 'w' OS code to Windows."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Win Server",
                        "addr": "1.2.3.4:27015",
                        "os": "w",
                        "map": "test",
                        "players": 0,
                        "max_players": 10,
                    }
                ]
            }
        }

        result = await game_servers.query_server_status(
            server_address="1.2.3.4:27015"
        )

        assert "Windows" in result

    @pytest.mark.asyncio
    async def test_os_mapping_macos(self, game_servers, mock_client):
        """Should map 'm' and 'o' OS codes to macOS."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Mac Server",
                        "addr": "1.2.3.4:27015",
                        "os": "m",
                        "map": "test",
                        "players": 0,
                        "max_players": 10,
                    }
                ]
            }
        }

        result = await game_servers.query_server_status(
            server_address="1.2.3.4:27015"
        )

        assert "macOS" in result

    @pytest.mark.asyncio
    async def test_bots_shown_when_present(self, game_servers, mock_client):
        """Should display bot count when bots are present."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "Bot Server",
                        "addr": "1.2.3.4:27015",
                        "map": "test",
                        "players": 16,
                        "max_players": 24,
                        "bots": 4,
                    }
                ]
            }
        }

        result = await game_servers.query_server_status(
            server_address="1.2.3.4:27015"
        )

        assert "Bots:" in result
        assert "4" in result

    @pytest.mark.asyncio
    async def test_bots_hidden_when_zero(self, game_servers, mock_client):
        """Should not display bot line when no bots."""
        mock_client.get.return_value = {
            "response": {
                "servers": [
                    {
                        "name": "No Bot Server",
                        "addr": "1.2.3.4:27015",
                        "map": "test",
                        "players": 16,
                        "max_players": 24,
                        "bots": 0,
                    }
                ]
            }
        }

        result = await game_servers.query_server_status(
            server_address="1.2.3.4:27015"
        )

        assert "Bots:" not in result
