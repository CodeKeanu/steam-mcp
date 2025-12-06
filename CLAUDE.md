# Steam MCP Server - Project Context

## Project Overview

This is a **Model Context Protocol (MCP) server** for the Steam API, allowing AI agents (like Claude) to interact with Steam's Web API through standardized MCP tools.

## Current Status: Stage 1 Complete (Framework)

The modular framework is complete and ready for endpoint implementation in Stage 2.

### What's Been Built

1. **Core MCP Server** (`src/steam_mcp/server.py`)
   - Entry point for the MCP server
   - Auto-discovers endpoint modules at startup
   - Handles tool listing and routing

2. **Modular Endpoint System** (`src/steam_mcp/endpoints/`)
   - `base.py`: BaseEndpoint class, @endpoint decorator, EndpointRegistry
   - Adding new endpoints is copy-paste simple - just create a new file

3. **Steam API Client** (`src/steam_mcp/client/steam_client.py`)
   - Async HTTP client with rate limiting (token bucket, 10 req/s)
   - Retry logic with exponential backoff
   - Error handling for Steam API quirks (HTML errors, 401/403/429)

4. **Steam ID Utilities** (`src/steam_mcp/utils/steam_id.py`)
   - Normalizes any Steam ID format to SteamID64
   - Supports: SteamID64, STEAM_X:Y:Z, [U:1:X], vanity URLs, profile URLs

5. **Example Endpoint** (`src/steam_mcp/endpoints/steam_user.py`)
   - ISteamUser interface implementation
   - Tools: get_player_summary, get_player_summaries, resolve_vanity_url, get_friend_list, get_player_bans

### Project Structure

```
steam-mcp/
├── src/steam_mcp/
│   ├── server.py           # MCP server entry point
│   ├── client/
│   │   └── steam_client.py # HTTP client with rate limiting
│   ├── endpoints/
│   │   ├── base.py         # BaseEndpoint + @endpoint decorator
│   │   └── steam_user.py   # ISteamUser endpoints (example)
│   └── utils/
│       └── steam_id.py     # Steam ID normalization
├── tests/                  # Unit tests
├── pyproject.toml          # Python 3.12+, dependencies
├── Dockerfile              # Multi-stage production build
├── docker-compose.yml      # Container orchestration
└── README.md               # User documentation
```

## How to Add New Endpoints (Stage 2)

Create a new file in `src/steam_mcp/endpoints/` following this pattern:

```python
from steam_mcp.endpoints import BaseEndpoint, endpoint
from steam_mcp.utils import normalize_steam_id

class IPlayerService(BaseEndpoint):
    """IPlayerService API endpoints."""

    @endpoint(
        name="get_owned_games",
        description="Get a player's owned games",
        params={
            "steam_id": {
                "type": "string",
                "description": "Steam ID in any format",
                "required": True,
            },
        },
    )
    async def get_owned_games(self, steam_id: str) -> str:
        normalized = await normalize_steam_id(steam_id, self.client)
        result = await self.client.get(
            "IPlayerService", "GetOwnedGames", version=1,
            params={"steamid": normalized, "include_appinfo": True}
        )
        # Format and return result
        return f"Found {len(result.get('response', {}).get('games', []))} games"
```

The endpoint is automatically discovered and registered - no other changes needed.

## Key Steam API Interfaces to Implement (Stage 2)

Priority order based on common usage:

1. **IPlayerService** - Owned games, playtime, badges, Steam level
2. **ISteamUserStats** - Achievements, game stats, leaderboards
3. **ISteamApps** - App/game metadata, version info
4. **ISteamNews** - Game news feeds
5. **ISteamEconomy** - In-game economy, item prices (if needed)

## Technical Decisions Made

1. **Python 3.12+** - Latest features, best performance
2. **No automatic SteamID32 detection** - Too error-prone with small numbers
3. **Lazy initialization for EndpointRegistry** - Avoids mutable class-level state
4. **401 errors = private profile** - Specific handling for GetFriendList
5. **Rate limiting at 10 req/s** - Conservative default for Steam API

## Configuration

Required environment variable:
- `STEAM_API_KEY` - Get from https://steamcommunity.com/dev/apikey

## Running the Server

```bash
# Development
pip install -e .
STEAM_API_KEY=xxx steam-mcp

# Docker
docker-compose up steam-mcp
```

## Agent Configuration

Two specialized agents are available in `.claude/agents/`:
- `steam-api-expert.md` - Steam API knowledge and best practices
- `principal-python-ml-engineer.md` - Python/MCP code quality

Use these agents for Steam API questions and code reviews.
