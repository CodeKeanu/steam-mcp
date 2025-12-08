# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v0.3.1] - 2025-12-08

### Changed
- `get_similar_games` now accepts `app_ids: list[int]` instead of single `app_id: int`
  - Reduces token usage for AI agents querying multiple games
  - Fetches source games in parallel
  - Combines genres from all source games for matching
- Added input deduplication and validation

## [v0.3.0] - 2025-12-08

### Added
- **Game Discovery Tools**
  - `find_unplayed_games_with_friends` - Compare game libraries with multiple friends to find games everyone owns but nobody has played (perfect for co-op discovery)
  - `get_similar_games` - Get game recommendations based on shared genres/tags with a source game

### Changed
- Tool count increased from 14 to 16

## [v0.2.1] - 2025-12-07

### Fixed
- Steam ID handling bugs in endpoint modules
- Resolved edge cases in Steam ID normalization

## [v0.2.0] - 2025-12-06

### Added
- **Owner Steam ID support** (`STEAM_USER_ID` env var)
  - Enables "my profile" queries without specifying Steam ID
  - New `get_my_steam_id` tool to verify configuration
  - "me"/"my" shortcuts in all player-related endpoints

- **IPlayerService endpoints** (`player_service.py`)
  - `get_owned_games` - Player's game library with playtime, sorting options
  - `get_recently_played_games` - Games played in last 2 weeks
  - `get_steam_level` - Player's Steam level with tier classification

- **ISteamUserStats endpoints** (`user_stats.py`)
  - `get_player_achievements` - Achievement progress for a game
  - `get_game_schema` - Achievement definitions and stat schema
  - `get_global_achievement_percentages` - Rarity percentages (no auth required)
  - `get_user_stats_for_game` - Game-specific statistics

- **ISteamNews endpoints** (`steam_news.py`)
  - `get_news_for_app` - Game news, patch notes, announcements (no auth required)

- **ISteamApps/IStoreService endpoints** (`steam_apps.py`)
  - `get_app_list` - Search Steam apps by name
  - `check_app_up_to_date` - Version checking for game servers
  - `get_app_details` - Detailed app info (price, genres, platforms, etc.)

### Changed
- Updated `.env.example` with `STEAM_USER_ID` documentation

## [v0.1.0] - 2025-12-06

### Added
- Core MCP server with automatic endpoint discovery
- Modular endpoint system with `BaseEndpoint` class and `@endpoint` decorator
- `EndpointRegistry` for auto-registration of endpoint modules
- Async Steam API client (`SteamClient`) with:
  - Token bucket rate limiting (10 requests/second)
  - Retry logic with exponential backoff
  - HTML error response handling
  - Proper error codes for private profiles (401/403)
- SteamID normalization utilities supporting:
  - SteamID64 format
  - Legacy STEAM_X:Y:Z format
  - Steam3 [U:1:X] format
  - Vanity URLs and full profile URLs
- ISteamUser example endpoint with 5 tools:
  - `get_player_summary` - Single player profile lookup
  - `get_player_summaries` - Batch player profiles (up to 100)
  - `resolve_vanity_url` - Convert vanity name to SteamID64
  - `get_friend_list` - Get player's friends (handles private profiles)
  - `get_player_bans` - Check VAC/game ban status
- Multi-stage Dockerfile with non-root user for security
- Docker Compose configuration
- Comprehensive README with usage instructions

[Unreleased]: https://github.com/CodeKeanu/steam-mcp/compare/v0.3.1...HEAD
[v0.3.1]: https://github.com/CodeKeanu/steam-mcp/compare/v0.3.0...v0.3.1
[v0.3.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.2.1...v0.3.0
[v0.2.1]: https://github.com/CodeKeanu/steam-mcp/compare/v0.2.0...v0.2.1
[v0.2.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/CodeKeanu/steam-mcp/releases/tag/v0.1.0
