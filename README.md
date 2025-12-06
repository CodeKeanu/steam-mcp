# Steam MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that lets AI assistants like Claude talk to the Steam API. Ask about your games, achievements, playtime, and more.

## What Can It Do?

Once set up, you can ask Claude things like:
- "What games do I own?"
- "Show my achievements for Counter-Strike 2"
- "What are the rarest achievements in Elden Ring?"
- "How many hours have I played this week?"
- "What's the latest news for Team Fortress 2?"

The server includes 14 tools covering player profiles, game libraries, achievements, stats, and news.

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
pytest

# Type checking
mypy src/

# Lint
ruff check src/

# Format
ruff format src/
```

### Docker (Local Builds)

```bash
# Build from source
docker compose --profile local build

# Run your local build
docker compose --profile local up steam-mcp-local

# Dev mode with hot reload
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

## Available Tools

### Player Profiles (ISteamUser)

| Tool | What it does |
|------|--------------|
| `get_my_steam_id` | Verify your Steam ID is configured correctly |
| `get_player_summary` | Get profile info (name, avatar, status) |
| `get_player_summaries` | Batch lookup for multiple players |
| `resolve_vanity_url` | Convert a vanity URL to SteamID64 |
| `get_friend_list` | Get someone's friend list |
| `get_player_bans` | Check VAC/game ban status |

### Game Library (IPlayerService)

| Tool | What it does |
|------|--------------|
| `get_owned_games` | Your game library with playtime stats |
| `get_recently_played_games` | What you've played in the last 2 weeks |
| `get_steam_level` | Your Steam level |

### Achievements & Stats (ISteamUserStats)

| Tool | What it does |
|------|--------------|
| `get_player_achievements` | Your achievement progress for a game |
| `get_game_schema` | All achievements available in a game |
| `get_global_achievement_percentages` | How rare each achievement is |
| `get_user_stats_for_game` | Detailed game stats (kills, deaths, etc.) |

### Game Info (ISteamApps & ISteamNews)

| Tool | What it does |
|------|--------------|
| `get_app_list` | Search for games by name |
| `get_app_details` | Game details (price, description, etc.) |
| `check_app_up_to_date` | Check if a game version is current |
| `get_news_for_app` | Latest news and patch notes |

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
