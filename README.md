# Steam MCP Server

A modular [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for integrating Steam API with AI agents like Claude.

## Features

- **14 Tools** across 5 Steam API interfaces
- **"My Profile" Queries**: Set your Steam ID once, use "me" or "my" in queries
- **Modular Architecture**: Easily add new Steam API endpoints
- **Auto-Discovery**: Endpoint modules are automatically registered
- **Rate Limiting**: Built-in rate limiting (10 req/s) to respect Steam API limits
- **Steam ID Normalization**: Accepts any Steam ID format (SteamID64, vanity URL, etc.)
- **Docker Support**: Ready for containerized deployment

## Quick Start

### Prerequisites

- Python 3.12+ (or Docker)
- Steam Web API Key ([Get one here](https://steamcommunity.com/dev/apikey))
- Your SteamID64 (optional, for "my profile" queries - find it at [steamid.io](https://steamid.io))

### Installation

```bash
# Clone the repository
git clone https://github.com/CodeKeanu/steam-mcp.git
cd steam-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Copy environment file and configure
cp .env.example .env
# Edit .env and add your STEAM_API_KEY and optionally STEAM_USER_ID
```

## Claude Desktop Configuration

Add the server to your Claude Desktop configuration:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Option 1: Direct Python (recommended for development)

```json
{
  "mcpServers": {
    "steam": {
      "command": "steam-mcp",
      "env": {
        "STEAM_API_KEY": "your_api_key_here",
        "STEAM_USER_ID": "your_steamid64_here"
      }
    }
  }
}
```

### Option 2: Docker with environment variables

```json
{
  "mcpServers": {
    "steam": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "STEAM_API_KEY=your_api_key_here",
        "-e", "STEAM_USER_ID=your_steamid64_here",
        "steam-mcp"
      ]
    }
  }
}
```

### Option 3: Docker with .env file

First, create a `.env` file with your configuration:

```bash
# .env
STEAM_API_KEY=your_api_key_here
STEAM_USER_ID=your_steamid64_here
```

Then configure Claude Desktop to use it:

```json
{
  "mcpServers": {
    "steam": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/path/to/your/steam-mcp/.env",
        "steam-mcp"
      ]
    }
  }
}
```

> **Note**: Replace `/path/to/your/steam-mcp/.env` with the actual path to your `.env` file.

### Building the Docker Image

Before using Docker options, build the image:

```bash
docker build -t steam-mcp .
```

## Available Tools

### ISteamUser - Player Identity & Profiles

| Tool | Description |
|------|-------------|
| `get_my_steam_id` | Get your configured Steam ID (verifies STEAM_USER_ID setup) |
| `get_player_summary` | Get player profile information |
| `get_player_summaries` | Get profiles for multiple players (batch) |
| `resolve_vanity_url` | Convert vanity URL to SteamID64 |
| `get_friend_list` | Get a player's friend list |
| `get_player_bans` | Check VAC/game ban status |

### IPlayerService - Game Library & Playtime

| Tool | Description |
|------|-------------|
| `get_owned_games` | Get player's game library with playtime |
| `get_recently_played_games` | Games played in the last 2 weeks |
| `get_steam_level` | Get player's Steam level |

### ISteamUserStats - Achievements & Stats

| Tool | Description |
|------|-------------|
| `get_player_achievements` | Get achievement progress for a game |
| `get_game_schema` | Get achievement definitions for a game |
| `get_global_achievement_percentages` | Get rarity percentages (no auth needed) |
| `get_user_stats_for_game` | Get game-specific statistics |

### ISteamNews - Game News

| Tool | Description |
|------|-------------|
| `get_news_for_app` | Get news/patch notes for a game (no auth needed) |

### ISteamApps - App Metadata

| Tool | Description |
|------|-------------|
| `get_app_list` | Search Steam apps by name |
| `check_app_up_to_date` | Check if app version is current |
| `get_app_details` | Get detailed app info (price, genres, etc.) |

## Example Queries

Once configured with `STEAM_USER_ID`, you can ask Claude:

- "What games do I own?"
- "Show my recently played games"
- "What's my Steam level?"
- "Show my achievements for Counter-Strike 2" (app ID: 730)
- "What are the rarest achievements in Elden Ring?" (app ID: 1245620)
- "Get the latest news for Team Fortress 2" (app ID: 440)
- "Search for games with 'Dark Souls' in the name"

## Configuration

| Environment Variable | Required | Description |
|---------------------|----------|-------------|
| `STEAM_API_KEY` | Yes | Your Steam Web API key |
| `STEAM_USER_ID` | No | Your SteamID64 for "my profile" queries |
| `STEAM_RATE_LIMIT` | No | Requests per second (default: 10) |
| `STEAM_TIMEOUT` | No | Request timeout in seconds (default: 30) |
| `STEAM_MAX_RETRIES` | No | Max retry attempts (default: 3) |

## Adding New Endpoints

Create a new file in `src/steam_mcp/endpoints/`:

```python
from steam_mcp.endpoints import BaseEndpoint, endpoint
from steam_mcp.utils import normalize_steam_id

class INewInterface(BaseEndpoint):
    """New Steam API interface."""

    @endpoint(
        name="my_new_tool",
        description="Description of what this tool does",
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

The endpoint is automatically discovered and registered - no other changes needed.

## Steam ID Formats

The server accepts any Steam ID format:

- **SteamID64**: `76561198000000000`
- **SteamID**: `STEAM_0:0:19867136`
- **SteamID3**: `[U:1:39734272]`
- **Vanity URL**: `https://steamcommunity.com/id/username`
- **Profile URL**: `https://steamcommunity.com/profiles/76561198000000000`
- **Vanity name**: `username`

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/

# Format code
ruff format src/
```

## Docker

### Using Pre-built Image (Recommended)

The easiest way to run the server:

```bash
# Pull and run with docker compose
docker compose pull
docker compose up steam-mcp
```

Make sure you have a `.env` file configured (copy from `.env.example`).

### Using with Claude Desktop

```json
{
  "mcpServers": {
    "steam": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/path/to/steam-mcp/.env",
        "ghcr.io/codekeanu/steam-mcp:latest"
      ]
    }
  }
}
```

### Building Locally

```bash
# Build from source
docker compose --profile local build

# Run local build
docker compose --profile local up steam-mcp-local

# Development mode with hot reload
docker compose --profile dev up steam-mcp-dev
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
