# Steam MCP Server

[![CI](https://github.com/CodeKeanu/steam-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CodeKeanu/steam-mcp/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/CodeKeanu/steam-mcp?include_prereleases)](https://github.com/CodeKeanu/steam-mcp/releases)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that lets AI assistants like Claude talk to the Steam API. Ask about your games, achievements, playtime, and more.

## What Can It Do?

Once set up, you can ask Claude things like:
- "What games do I own?"
- "Show my achievements for Counter-Strike 2"
- "What are the rarest achievements in Elden Ring?"
- "How many hours have I played this week?"
- "What's the latest news for Team Fortress 2?"
- "Show my pending trade offers"
- "What's the current price for an AK-47 Redline?"

The server includes 38 tools covering player profiles, game libraries, achievements, stats, reviews, wishlists, news, community guides, trading/market data, family sharing, Steam Workshop, and cloud saves.

---

## Quick Start (Non-Developers)

Just want to get it running? Here's the fastest path using Docker.

### What You'll Need

1. **Docker** - [Get Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. **Steam API Key** - [Grab one here](https://steamcommunity.com/dev/apikey) (it's free)
3. **Your SteamID64** - Find it at [steamid.io](https://steamid.io) by pasting your profile URL

### Setup

1. Create a file called `.env` somewhere you'll remember (like your Documents folder):

```bash
STEAM_API_KEY=your_api_key_here
STEAM_USER_ID=your_steamid64_here
```

2. Add this to your Claude Desktop config:

**Config location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "steam": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/full/path/to/your/.env",
        "ghcr.io/codekeanu/steam-mcp:latest"
      ]
    }
  }
}
```

> **Heads up:** Replace `/full/path/to/your/.env` with the actual path to your `.env` file. On Windows, use forward slashes like `C:/Users/YourName/Documents/.env`.

3. Restart Claude Desktop and you're good to go!

---

## Developer Setup

Want to build from source, contribute, or hack on the code? This section's for you.

### Prerequisites

- Python 3.12+
- Git
- Steam API Key ([get one here](https://steamcommunity.com/dev/apikey))

### Installation

```bash
# Clone it
git clone https://github.com/CodeKeanu/steam-mcp.git
cd steam-mcp

# Set up a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in dev mode
pip install -e ".[dev]"

# Configure your keys
cp .env.example .env
# Edit .env with your STEAM_API_KEY and STEAM_USER_ID
```

### Running Locally

For development, point Claude Desktop directly at your local install:

```json
{
  "mcpServers": {
    "steam": {
      "command": "/path/to/steam-mcp/.venv/bin/steam-mcp",
      "env": {
        "STEAM_API_KEY": "your_api_key_here",
        "STEAM_USER_ID": "your_steamid64_here"
      }
    }
  }
}
```

### Development Commands

```bash
# Run tests
source .venv/bin/activate
pytest

# Run tests with coverage
pytest --cov=src/steam_mcp --cov-report=term-missing
```

### Docker (Local Builds)

```bash
# Build from source
docker compose --profile local build steam-mcp-local

# Run your local build
docker compose --profile local up steam-mcp-local

# Dev mode with volume mount (reflects code changes on restart)
docker compose --profile dev up steam-mcp-dev
```

### Adding New Endpoints

Create a new file in `src/steam_mcp/endpoints/` - it gets auto-discovered:

```python
from steam_mcp.endpoints import BaseEndpoint, endpoint
from steam_mcp.utils import normalize_steam_id

class INewInterface(BaseEndpoint):
    """Your new Steam API interface."""

    @endpoint(
        name="my_new_tool",
        description="What this tool does",
        params={
            "steam_id": {
                "type": "string",
                "description": "Steam ID in any format",
                "required": True,
            },
        },
    )
    async def my_new_tool(self, steam_id: str) -> str:
        normalized_id = await normalize_steam_id(steam_id, self.client)
        result = await self.client.get("INewInterface", "Method", version=1, params={...})
        return "Formatted result"
```

No registration needed - just drop in the file and restart.

### Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/cool-thing`)
3. Make your changes
4. Run tests and linting
5. Push and open a PR

---

## Available Tools (38 total)

### Player Profiles (ISteamUser) - 6 tools

| Tool | What it does |
|------|--------------|
| `get_my_steam_id` | Verify your Steam ID is configured correctly |
| `get_player_summary` | Get profile info (name, avatar, status) |
| `get_player_summaries` | Batch lookup for multiple players |
| `resolve_vanity_url` | Convert a vanity URL to SteamID64 |
| `get_friend_list` | Get someone's friend list |
| `get_player_bans` | Check VAC/game ban status |

### Game Library (IPlayerService) - 4 tools

| Tool | What it does |
|------|--------------|
| `get_owned_games` | Your game library with playtime stats |
| `get_recently_played_games` | What you've played in the last 2 weeks |
| `get_steam_level` | Your Steam level |
| `find_unplayed_games_with_friends` | Find games you all own but none have played |

### Achievements & Stats (ISteamUserStats) - 6 tools

| Tool | What it does |
|------|--------------|
| `get_player_achievements` | Your achievement progress for a game |
| `get_game_schema` | All achievements available in a game |
| `get_global_achievement_percentages` | How rare each achievement is |
| `get_user_stats_for_game` | Detailed game stats (kills, deaths, etc.) |
| `get_current_players` | How many players are online right now |
| `get_global_stats_for_game` | Aggregated stats across all players |

### Game Info (ISteamApps) - 6 tools

| Tool | What it does |
|------|--------------|
| `get_app_list` | Search for games by name |
| `get_app_details` | Game details (price, description, etc.) |
| `get_full_game_details` | Comprehensive game info (details, reviews, players, achievements, news) in one call |
| `get_similar_games` | Find games similar to ones you like |
| `get_game_reviews` | User reviews with Steam ratings and sample text |
| `check_app_up_to_date` | Check if a game version is current |

### Game News (ISteamNews) - 1 tool

| Tool | What it does |
|------|--------------|
| `get_news_for_app` | Latest news and patch notes |

### Wishlist & Pricing (ISteamWishlist) - 3 tools

| Tool | What it does |
|------|--------------|
| `get_wishlist` | Get a user's wishlist with current pricing |
| `check_wishlist_sales` | Find discounted games on your wishlist |
| `compare_prices` | Compare prices across multiple games |

### Community Guides (ISteamGuides) - 2 tools

| Tool | What it does |
|------|--------------|
| `search_game_guides` | Search Steam Community guides for a game |
| `get_guide_content` | Get guide summary and metadata (full content requires visiting Steam) |

### Trading & Market (IEconService) - 4 tools

| Tool | What it does |
|------|--------------|
| `get_trade_offers` | Get incoming/outgoing trade offers with item details |
| `get_trade_history` | View completed trade history |
| `get_market_listings` | Check current market prices for items |
| `check_market_eligibility` | Check if a user can use the Steam Market |

### Family Sharing (IFamilyGroupsService) - 2 tools

| Tool | What it does |
|------|--------------|
| `get_family_group` | Get family group membership, members, and roles |
| `get_shared_library_apps` | Get games available through family sharing |

### Steam Workshop (IPublishedFileService) - 4 tools

| Tool | What it does |
|------|--------------|
| `search_workshop_items` | Search Workshop mods by game, with text/tag filters and sorting |
| `search_workshop_collections` | Search Workshop collections (curated item lists) by game with sorting |
| `get_workshop_item_details` | Get full details on a Workshop item (description, subscribers, dependencies) |
| `get_workshop_collection` | Get items from a Workshop collection |

### Cloud Saves (ISteamRemoteStorage) - 2 tools

| Tool | What it does |
|------|--------------|
| `list_cloud_files` | List cloud save files for a game (names, sizes, timestamps) |
| `get_cloud_quota` | Get cloud storage usage and limits |

---

## Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `STEAM_API_KEY` | Yes | Your Steam Web API key |
| `STEAM_USER_ID` | No | Your SteamID64 for "my profile" queries |
| `STEAM_RATE_LIMIT` | No | Requests per second (default: 10) |
| `STEAM_TIMEOUT` | No | Request timeout in seconds (default: 30) |
| `STEAM_MAX_RETRIES` | No | Max retry attempts (default: 3) |

## Steam ID Formats

The server understands all these formats:

- `76561198000000000` (SteamID64)
- `STEAM_0:0:19867136` (SteamID)
- `[U:1:39734272]` (SteamID3)
- `https://steamcommunity.com/id/username` (Vanity URL)
- `https://steamcommunity.com/profiles/76561198000000000` (Profile URL)
- `username` (Just the vanity name)

---

## License

MIT - do whatever you want with it.
