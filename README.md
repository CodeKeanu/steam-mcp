# Steam MCP Server

A modular [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for integrating Steam API with AI agents like Claude.

## Features

- **Modular Architecture**: Easily add new Steam API endpoints by creating endpoint modules
- **Auto-Discovery**: Endpoint modules are automatically discovered and registered
- **Rate Limiting**: Built-in rate limiting to respect Steam API limits
- **Steam ID Normalization**: Accepts any Steam ID format (SteamID64, vanity URL, etc.)
- **Error Handling**: Robust error handling with retry logic
- **Docker Support**: Ready for containerized deployment

## Quick Start

### Prerequisites

- Python 3.12+
- Steam Web API Key ([Get one here](https://steamcommunity.com/dev/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/steam-mcp.git
cd steam-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Copy environment file and add your API key
cp .env.example .env
# Edit .env and add your STEAM_API_KEY
```

### Configuration

Add the server to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "steam": {
      "command": "steam-mcp",
      "env": {
        "STEAM_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "steam": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "STEAM_API_KEY=your_key", "steam-mcp"]
    }
  }
}
```

## Available Tools

### ISteamUser

| Tool | Description |
|------|-------------|
| `get_player_summary` | Get player profile information |
| `get_player_summaries` | Get profiles for multiple players |
| `resolve_vanity_url` | Convert vanity URL to SteamID64 |
| `get_friend_list` | Get a player's friend list |
| `get_player_bans` | Check VAC/game ban status |

## Adding New Endpoints

The framework is designed to make adding new endpoints simple. Create a new file in `src/steam_mcp/endpoints/`:

```python
# src/steam_mcp/endpoints/player_service.py
"""IPlayerService API endpoints."""

from steam_mcp.endpoints import BaseEndpoint, endpoint
from steam_mcp.utils import normalize_steam_id


class IPlayerService(BaseEndpoint):
    """IPlayerService API endpoints for game library data."""

    @endpoint(
        name="get_owned_games",
        description="Get a player's owned games and playtime",
        params={
            "steam_id": {
                "type": "string",
                "description": "Steam ID in any format",
                "required": True,
            },
            "include_free_games": {
                "type": "boolean",
                "description": "Include free-to-play games",
                "default": False,
                "required": False,
            },
        },
    )
    async def get_owned_games(
        self, steam_id: str, include_free_games: bool = False
    ) -> str:
        normalized_id = await normalize_steam_id(steam_id, self.client)

        result = await self.client.get(
            "IPlayerService",
            "GetOwnedGames",
            version=1,
            params={
                "steamid": normalized_id,
                "include_appinfo": True,
                "include_played_free_games": include_free_games,
            },
        )

        games = result.get("response", {}).get("games", [])
        # Format and return result...
        return f"Found {len(games)} games"
```

That's it! The endpoint is automatically discovered and registered.

## Architecture

```
steam-mcp/
├── src/steam_mcp/
│   ├── __init__.py
│   ├── server.py              # MCP server entry point
│   ├── client/
│   │   ├── __init__.py
│   │   └── steam_client.py    # HTTP client with rate limiting
│   ├── endpoints/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseEndpoint and @endpoint decorator
│   │   └── steam_user.py      # ISteamUser endpoints (example)
│   └── utils/
│       ├── __init__.py
│       └── steam_id.py        # Steam ID normalization
├── tests/
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

### Key Components

- **BaseEndpoint**: Abstract base class for endpoint modules
- **@endpoint decorator**: Registers methods as MCP tools
- **EndpointRegistry**: Auto-discovers and manages all tools
- **SteamClient**: HTTP client with rate limiting and error handling
- **normalize_steam_id**: Handles all Steam ID formats

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

```bash
# Build image
docker build -t steam-mcp .

# Run with docker-compose
docker-compose up steam-mcp

# Run development mode with hot reload
docker-compose --profile dev up steam-mcp-dev
```

## Steam ID Formats

The server accepts any Steam ID format:

- **SteamID64**: `76561198000000000`
- **SteamID32**: `39734272`
- **SteamID**: `STEAM_0:0:19867136`
- **SteamID3**: `[U:1:39734272]`
- **Vanity URL**: `https://steamcommunity.com/id/username`
- **Profile URL**: `https://steamcommunity.com/profiles/76561198000000000`
- **Vanity name**: `username`

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
