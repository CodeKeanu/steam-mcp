"""IGameServersService API endpoints.

This module provides MCP tools for querying game server information,
including server lists and detailed server status.

Reference: https://partner.steamgames.com/doc/webapi/IGameServersService
"""

import json
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


class IGameServersService(BaseEndpoint):
    """IGameServersService API endpoints for game server queries."""

    @endpoint(
        name="get_game_servers",
        description=(
            "Get a list of game servers for a specific game. "
            "Returns server name, map, player count, and address."
        ),
        supports_json=True,
        params={
            "app_id": {
                "type": "integer",
                "description": "Game App ID (e.g., 730 for CS2, 440 for TF2)",
                "required": True,
            },
            "filter": {
                "type": "string",
                "description": (
                    "Server filter string. Examples: "
                    "'\\\\gamedir\\\\tf' for TF2 servers, "
                    "'\\\\map\\\\de_dust2' for specific map, "
                    "'\\\\noplayers\\\\1' for empty servers, "
                    "'\\\\full\\\\1' for full servers. "
                    "Combine with '\\\\' separator."
                ),
                "required": False,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of servers to return (default: 25, max: 100)",
                "required": False,
                "default": 25,
                "minimum": 1,
                "maximum": 100,
            },
        },
    )
    async def get_game_servers(
        self,
        app_id: int,
        filter: str | None = None,
        limit: int = 25,
        format: str = "text",
    ) -> str:
        """Get game servers for a specific app."""
        # Build the filter string - always include appid
        filter_parts = [f"\\appid\\{app_id}"]
        if filter:
            filter_parts.append(filter)
        filter_str = "".join(filter_parts)

        result = await self.client.get(
            "IGameServersService",
            "GetServerList",
            version=1,
            params={"filter": filter_str, "limit": limit},
        )

        response = result.get("response", {})
        servers = response.get("servers", [])

        if not servers:
            msg = f"No servers found for App ID {app_id}"
            if filter:
                msg += f" with filter '{filter}'"
            if format == "json":
                return json.dumps({"error": msg, "app_id": app_id, "servers": []})
            return msg

        if format == "json":
            data = {
                "app_id": app_id,
                "server_count": len(servers),
                "servers": [
                    {
                        "name": s.get("name", "Unknown"),
                        "address": s.get("addr", "Unknown"),
                        "map": s.get("map", "Unknown"),
                        "players": s.get("players", 0),
                        "max_players": s.get("max_players", 0),
                        "bots": s.get("bots", 0),
                        "game_type": s.get("gametype", ""),
                        "secure": s.get("secure", False),
                        "dedicated": s.get("dedicated", True),
                        "os": s.get("os", ""),
                        "version": s.get("version", ""),
                    }
                    for s in servers
                ],
            }
            return json.dumps(data, indent=2)

        # Text format
        output = [
            f"Game Servers for App ID {app_id}",
            f"Found {len(servers)} server(s)",
            "",
        ]

        for server in servers:
            name = server.get("name", "Unknown Server")
            addr = server.get("addr", "Unknown")
            map_name = server.get("map", "Unknown")
            players = server.get("players", 0)
            max_players = server.get("max_players", 0)
            bots = server.get("bots", 0)
            secure = "VAC" if server.get("secure") else "No VAC"

            player_info = f"{players}/{max_players}"
            if bots > 0:
                player_info += f" ({bots} bots)"

            output.append(f"  {name}")
            output.append(f"    Address: {addr}")
            output.append(f"    Map: {map_name} | Players: {player_info} | {secure}")
            output.append("")

        return "\n".join(output)

    @endpoint(
        name="query_server_status",
        description=(
            "Get detailed status of a specific game server by address. "
            "Returns server info, current players, and game rules."
        ),
        supports_json=True,
        params={
            "server_address": {
                "type": "string",
                "description": "Server address in IP:port format (e.g., '192.168.1.1:27015')",
                "required": True,
            },
        },
    )
    async def query_server_status(
        self,
        server_address: str,
        format: str = "text",
    ) -> str:
        """Query detailed status of a specific server."""
        # Use the filter to find the specific server
        result = await self.client.get(
            "IGameServersService",
            "GetServerList",
            version=1,
            params={"filter": f"\\addr\\{server_address}", "limit": 1},
        )

        response = result.get("response", {})
        servers = response.get("servers", [])

        if not servers:
            msg = f"Server not found at address: {server_address}"
            if format == "json":
                return json.dumps({"error": msg, "address": server_address})
            return msg

        server = servers[0]

        if format == "json":
            return json.dumps(
                {
                    "address": server.get("addr", server_address),
                    "name": server.get("name", "Unknown"),
                    "app_id": server.get("appid"),
                    "game_dir": server.get("gamedir", ""),
                    "map": server.get("map", "Unknown"),
                    "players": server.get("players", 0),
                    "max_players": server.get("max_players", 0),
                    "bots": server.get("bots", 0),
                    "game_type": server.get("gametype", ""),
                    "secure": server.get("secure", False),
                    "dedicated": server.get("dedicated", True),
                    "os": server.get("os", ""),
                    "version": server.get("version", ""),
                    "product": server.get("product", ""),
                    "region": server.get("region", -1),
                    "steamid": server.get("steamid", ""),
                },
                indent=2,
            )

        # Text format
        name = server.get("name", "Unknown Server")
        addr = server.get("addr", server_address)
        map_name = server.get("map", "Unknown")
        players = server.get("players", 0)
        max_players = server.get("max_players", 0)
        bots = server.get("bots", 0)
        app_id = server.get("appid", "Unknown")
        game_dir = server.get("gamedir", "Unknown")
        version = server.get("version", "Unknown")
        secure = "Yes" if server.get("secure") else "No"
        dedicated = "Dedicated" if server.get("dedicated") else "Listen"
        os_type = server.get("os", "Unknown")
        game_type = server.get("gametype", "None")

        # Map OS codes
        os_names = {"l": "Linux", "w": "Windows", "m": "macOS", "o": "macOS"}
        os_display = os_names.get(os_type.lower(), os_type) if os_type else "Unknown"

        output = [
            f"Server Status: {name}",
            f"",
            f"  Address:     {addr}",
            f"  App ID:      {app_id}",
            f"  Game:        {game_dir}",
            f"  Map:         {map_name}",
            f"  Players:     {players}/{max_players}",
        ]

        if bots > 0:
            output.append(f"  Bots:        {bots}")

        output.extend([
            f"  Version:     {version}",
            f"  Server Type: {dedicated}",
            f"  OS:          {os_display}",
            f"  VAC Secured: {secure}",
        ])

        if game_type:
            output.append(f"  Game Type:   {game_type}")

        return "\n".join(output)
