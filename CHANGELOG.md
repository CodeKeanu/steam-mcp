# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Game Server Status** (`game_servers.py`)
  - `get_game_servers` - List game servers for a specific game
    - Filter by map, player count, VAC status
    - Returns server name, address, map, player count, VAC status
  - `query_server_status` - Get detailed status of a specific server
    - Lookup by IP:port address
    - Returns full server info including OS, version, game type

### Changed
- Tool count increased from 36 to 38

## [v0.9.0] - 2025-12-12

### Added
- **Steam Workshop Integration** (`steam_workshop.py`)
  - `search_workshop_items` - Search Workshop mods by game
    - Text search and tag filtering support
    - Sort by popular, trending, recent, or rating
    - Returns subscriber counts, ratings, file sizes
  - `search_workshop_collections` - Search Workshop collections by game
    - Discover popular modpacks and curated item lists
    - Sort by popular, trending, recent, or rating
    - Text search support
    - Returns collection name, item count, subscriber count
  - `get_workshop_item_details` - Get detailed Workshop item information
    - Full description, author info, dependencies
    - Subscriber/favorite counts, vote breakdown
    - Creation and update timestamps
  - `get_workshop_collection` - Get items from a Workshop collection
    - Collection metadata and item list
    - Batch fetches item details
- **Family Sharing Integration** (`family_groups.py`)
  - `get_family_group` - Get family group membership information
    - Returns family members, roles (Adult/Child/Member), and cooldown status
    - Shows available slots in the family group
  - `get_shared_library_apps` - Get games available through family sharing
    - Shows shared games grouped by owner
    - Indicates exclusion reasons (not shareable, already owned, etc.)
    - Optional `include_own` parameter to include owned apps

### Changed
- Tool count increased from 30 to 36

## [v0.8.0] - 2025-12-11

### Added
- **Trading & Market Integration** (`steam_trading.py`)
  - `get_trade_offers` - Get incoming/outgoing trade offers with item details
    - Filter by: active, incoming, outgoing, or historical
    - Shows items to give/receive with descriptions
  - `get_trade_history` - View completed trade history
    - Configurable max trades limit
    - Shows items exchanged and trade partners
  - `get_market_listings` - Check current Steam Community Market prices
    - Lowest price, median price, and 24h volume
    - Supports different currencies (USD, GBP, EUR)
  - `check_market_eligibility` - Check if a user can use the Steam Market
    - Shows restrictions, reasons, and expiration dates

### Changed
- Tool count increased from 26 to 30

## [v0.7.1] - 2025-12-11

### Fixed
- **Wishlist sales detection** (#20) - Steam's `appdetails` API only returns data for the first app when batching; now uses individual requests per app
- **Guide content limitation** (#19) - Added notice that Steam's API only provides summaries; full guide content requires visiting Steam directly

## [v0.7.0] - 2025-12-11

### Added
- **Steam Community Guides Integration** (`steam_guides.py`)
  - `search_game_guides` - Search community guides for any game by App ID
    - Filter by section (walkthrough, reference, achievement)
    - Sort by popularity, recency, or rating
    - Optional search query filter
  - `get_guide_content` - Retrieve guide summary and metadata via official API
- **Wishlist Management & Price Tracking** (`steam_wishlist.py`)
  - `get_wishlist` - Get a user's Steam wishlist with current pricing
  - `check_wishlist_sales` - Find discounted games on wishlist, sorted by discount
  - `compare_prices` - Compare prices across multiple games with review scores
  - Supports public wishlists, parallel API fetching for performance
  - Works with 'me'/'my' Steam ID shortcuts
- **Response Caching** (#17) - TTL-based caching layer for API responses

### Changed
- Tool count increased from 21 to 26

## [v0.6.0] - 2025-12-09

### Added
- `get_current_players` - Get live player count for any game
- `get_global_stats_for_game` - Aggregated global stats across all players

### Changed
- Tool count increased from 19 to 21

## [v0.5.4] - 2025-12-09

### Changed
- Consolidated CI into single workflow with job dependencies (GitHub best practice)
- Workflow chain: Tests → Docker Build → Release
- Replaced separate tests.yml, docker-publish.yml, release.yml with unified ci.yml
- Updated README badge to single CI badge

## [v0.5.3] - 2025-12-09

### Changed
- Chained CI workflows: Tests → Docker Build → Release
- Docker and Release only run if previous workflow passes
- Release only triggers on version tags

## [v0.5.2] - 2025-12-09

### Added
- Automatic GitHub release workflow on version tags
- Extracts release notes from CHANGELOG.md

### Fixed
- Badge URLs now include branch parameter for proper cache busting

## [v0.5.1] - 2025-12-09

### Fixed
- Updated tool count in README (18 → 19)
- Fixed pyproject.toml URLs to point to correct repository (CodeKeanu/steam-mcp)
- Reorganized README tool tables with per-section counts
- Simplified dev commands to only reference pytest (removed mypy/ruff)
- Added venv activation to dev workflow instructions

## [v0.5.0] - 2025-12-08

### Added
- **Aggregate Game Details Tool** (`get_full_game_details`)
  - Comprehensive game information in a single API call
  - Combines: app details, user reviews, current player count, achievement statistics, and recent news
  - Configurable sections: toggle reviews, achievements, or news
  - Adjustable sample sizes for reviews (1-5) and news items (1-5)
  - Parallel API fetching for optimal performance
  - Graceful handling of partial API failures
  - Type-safe dataclasses for internal data structures

### Changed
- Tool count increased from 17 to 18

## [v0.4.0] - 2025-12-08

### Added
- **Game Reviews Tool** (`get_game_reviews`)
  - Fetch user reviews for one or more Steam games
  - Three view modes: `summary` (scores only), `standard` (3 reviews), `detailed` (10 reviews)
  - Steam rating labels (Mostly Positive, Very Positive, etc.)
  - Review statistics: total count, positive/negative breakdown, percentage
  - Filter by review type (all/positive/negative) and language
  - Sample reviews with playtime, helpfulness votes, and recommendation
- `get_raw()` method added to SteamClient for unauthenticated endpoints

### Changed
- Tool count increased from 16 to 17

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

[Unreleased]: https://github.com/CodeKeanu/steam-mcp/compare/v0.9.0...HEAD
[v0.9.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.8.0...v0.9.0
[v0.8.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.7.1...v0.8.0
[v0.7.1]: https://github.com/CodeKeanu/steam-mcp/compare/v0.7.0...v0.7.1
[v0.7.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.6.0...v0.7.0
[v0.6.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.5.4...v0.6.0
[v0.5.4]: https://github.com/CodeKeanu/steam-mcp/compare/v0.5.3...v0.5.4
[v0.5.3]: https://github.com/CodeKeanu/steam-mcp/compare/v0.5.2...v0.5.3
[v0.5.2]: https://github.com/CodeKeanu/steam-mcp/compare/v0.5.1...v0.5.2
[v0.5.1]: https://github.com/CodeKeanu/steam-mcp/compare/v0.5.0...v0.5.1
[v0.5.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.4.0...v0.5.0
[v0.4.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.3.1...v0.4.0
[v0.3.1]: https://github.com/CodeKeanu/steam-mcp/compare/v0.3.0...v0.3.1
[v0.3.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.2.1...v0.3.0
[v0.2.1]: https://github.com/CodeKeanu/steam-mcp/compare/v0.2.0...v0.2.1
[v0.2.0]: https://github.com/CodeKeanu/steam-mcp/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/CodeKeanu/steam-mcp/releases/tag/v0.1.0
