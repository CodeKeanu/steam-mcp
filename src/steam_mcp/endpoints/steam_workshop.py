"""Steam Workshop API endpoints.

This module provides MCP tools for the IPublishedFileService Steam API interface,
which handles Steam Workshop content discovery, search, and details.

Reference: https://partner.steamgames.com/doc/webapi/IPublishedFileService
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


logger = logging.getLogger(__name__)


# Query type mappings for sorting
QUERY_TYPES = {
    "popular": 0,  # RankedByVote
    "trend": 1,  # RankedByTrend
    "recent": 2,  # RankedByPublicationDate
    "rating": 3,  # RankedByVoteScore (same as popular but different algorithm)
}


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int, handling strings from API."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float, handling strings from API."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _format_file_size(size_bytes: int | str | None) -> str:
    """Format file size in human readable form."""
    try:
        size_bytes = int(size_bytes) if size_bytes else 0
    except (ValueError, TypeError):
        return "Unknown size"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _format_timestamp(ts: int | str | None) -> str:
    """Format Unix timestamp as readable date (UTC)."""
    try:
        ts = int(ts) if ts else 0
    except (ValueError, TypeError):
        return "Unknown"
    if ts <= 0:
        return "Unknown"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, OSError):
        return "Unknown"


class IPublishedFileService(BaseEndpoint):
    """Steam Workshop (IPublishedFileService) API endpoints."""

    @endpoint(
        name="search_workshop_items",
        description=(
            "Search Steam Workshop for mods and community content by game. "
            "Returns items with title, author, subscriber count, and rating. "
            "Note: Workshop availability varies by game."
        ),
        supports_json=True,
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game to search Workshop for",
                "required": True,
            },
            "search_query": {
                "type": "string",
                "description": "Text search filter (optional)",
                "required": False,
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by Workshop tags (e.g., 'Maps', 'Weapons', 'Characters')",
                "required": False,
            },
            "sort_by": {
                "type": "string",
                "description": "Sort order: 'popular' (most voted), 'trend' (trending), 'recent' (newest), 'rating' (highest rated)",
                "required": False,
                "default": "popular",
                "enum": ["popular", "trend", "recent", "rating"],
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 20, max: 50)",
                "required": False,
                "default": 20,
                "minimum": 1,
                "maximum": 50,
            },
        },
    )
    async def search_workshop_items(
        self,
        app_id: int,
        search_query: str = "",
        tags: list[str] | None = None,
        sort_by: str = "popular",
        max_results: int = 20,
        format: str = "text",
    ) -> str:
        """Search Steam Workshop for items."""
        # Build query parameters
        query_type = QUERY_TYPES.get(sort_by, 0)

        params: dict[str, Any] = {
            "appid": app_id,
            "query_type": query_type,
            "numperpage": min(max_results, 50),
            "return_metadata": True,
            "return_tags": True,
            "return_vote_data": True,
        }

        if search_query:
            params["search_text"] = search_query

        if tags:
            # Steam API expects tags as separate requiredtags[n] params
            for i, tag in enumerate(tags):
                params[f"requiredtags[{i}]"] = tag

        try:
            result = await self.client.get(
                "IPublishedFileService",
                "QueryFiles",
                version=1,
                params=params,
            )
        except Exception as e:
            error_msg = f"Error searching Workshop: {e}"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        response = result.get("response", {})
        items = response.get("publishedfiledetails", [])
        total = response.get("total", len(items))

        if not items:
            msg = f"No Workshop items found for app {app_id}."
            if search_query:
                msg += f" Search query: '{search_query}'"
            if tags:
                msg += f" Tags: {', '.join(tags)}"
            msg += "\n\nThis game may not have Workshop support, or no items match your filters."
            if format == "json":
                return json.dumps({"error": msg})
            return msg

        if format == "json":
            data = {
                "app_id": app_id,
                "total_results": total,
                "returned": len(items),
                "sort_by": sort_by,
                "items": [
                    {
                        "workshop_id": item.get("publishedfileid"),
                        "title": item.get("title", "Untitled"),
                        "description": (item.get("short_description") or item.get("file_description", ""))[:500],
                        "author_steam_id": item.get("creator"),
                        "preview_url": item.get("preview_url"),
                        "subscriber_count": item.get("subscriptions", 0),
                        "favorited_count": item.get("favorited", 0),
                        "views": item.get("views", 0),
                        "vote_data": {
                            "score": item.get("vote_data", {}).get("score", 0),
                            "votes_up": item.get("vote_data", {}).get("votes_up", 0),
                            "votes_down": item.get("vote_data", {}).get("votes_down", 0),
                        },
                        "file_size_bytes": item.get("file_size", 0),
                        "tags": [t.get("tag") for t in item.get("tags", []) if t.get("tag")],
                        "time_created": item.get("time_created"),
                        "time_updated": item.get("time_updated"),
                    }
                    for item in items
                ],
            }
            return json.dumps(data, indent=2)

        # Text format
        output = [
            f"Steam Workshop Results for App {app_id}",
            f"Total: {total} items | Showing: {len(items)} | Sort: {sort_by}",
        ]

        if search_query:
            output.append(f"Search: '{search_query}'")
        if tags:
            output.append(f"Tags: {', '.join(tags)}")
        output.append("")

        for item in items:
            workshop_id = item.get("publishedfileid", "?")
            title = item.get("title", "Untitled")
            subs = _safe_int(item.get("subscriptions"))
            favorites = _safe_int(item.get("favorited"))
            file_size = item.get("file_size", 0)

            # Vote data
            vote_data = item.get("vote_data", {})
            score = _safe_float(vote_data.get("score"))
            rating_pct = f"{score * 100:.0f}%" if score else "N/A"

            # Tags
            item_tags = [t.get("tag") for t in item.get("tags", []) if t.get("tag")]
            tags_str = ", ".join(item_tags[:3]) if item_tags else "No tags"
            if len(item_tags) > 3:
                tags_str += f" (+{len(item_tags) - 3})"

            output.append(
                f"[{workshop_id}] {title}\n"
                f"    Subscribers: {subs:,} | Favorites: {favorites:,} | Rating: {rating_pct}\n"
                f"    Size: {_format_file_size(file_size)} | Tags: {tags_str}"
            )
            output.append("")

        return "\n".join(output)

    @endpoint(
        name="get_workshop_item_details",
        description=(
            "Get detailed information about a specific Steam Workshop item. "
            "Returns full description, author info, dependencies, changelog, and more."
        ),
        supports_json=True,
        params={
            "workshop_id": {
                "type": "string",
                "description": "The Workshop item ID (publishedfileid)",
                "required": True,
            },
        },
    )
    async def get_workshop_item_details(
        self,
        workshop_id: str,
        format: str = "text",
    ) -> str:
        """Get detailed information about a Workshop item."""
        # Validate input
        if not workshop_id or not workshop_id.strip():
            error_msg = "Workshop ID is required"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        workshop_id = workshop_id.strip()

        try:
            result = await self.client.get(
                "IPublishedFileService",
                "GetDetails",
                version=1,
                params={
                    "publishedfileids[0]": workshop_id,
                    "includetags": True,
                    "includeadditionalpreviews": True,
                    "includechildren": True,  # Dependencies
                    "includevotes": True,
                    "short_description": False,  # Get full description
                },
            )
        except Exception as e:
            error_msg = f"Error fetching Workshop item details: {e}"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        response = result.get("response", {})
        items = response.get("publishedfiledetails", [])

        if not items:
            error_msg = f"Workshop item {workshop_id} not found."
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        item = items[0]

        # Check for error result (item not found or private)
        if _safe_int(item.get("result")) != 1:
            error_msg = f"Workshop item {workshop_id} not found or is private."
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        if format == "json":
            data = {
                "workshop_id": item.get("publishedfileid"),
                "title": item.get("title", "Untitled"),
                "description": item.get("file_description", ""),
                "app_id": item.get("consumer_appid"),
                "creator_app_id": item.get("creator_appid"),
                "author": {
                    "steam_id": item.get("creator"),
                    "name": item.get("creator_name"),
                },
                "file_url": item.get("file_url"),
                "preview_url": item.get("preview_url"),
                "file_size_bytes": item.get("file_size", 0),
                "subscriber_count": item.get("subscriptions", 0),
                "favorited_count": item.get("favorited", 0),
                "lifetime_subscriptions": item.get("lifetime_subscriptions", 0),
                "lifetime_favorited": item.get("lifetime_favorited", 0),
                "views": item.get("views", 0),
                "vote_data": {
                    "score": item.get("vote_data", {}).get("score", 0),
                    "votes_up": item.get("vote_data", {}).get("votes_up", 0),
                    "votes_down": item.get("vote_data", {}).get("votes_down", 0),
                },
                "tags": [t.get("tag") for t in item.get("tags", [])],
                "time_created": item.get("time_created"),
                "time_updated": item.get("time_updated"),
                "visibility": item.get("visibility"),
                "banned": item.get("banned", False),
                "language": item.get("language"),
                "dependencies": item.get("children", []),
            }
            return json.dumps(data, indent=2)

        # Text format
        title = item.get("title", "Untitled")
        description = item.get("file_description", "No description")
        app_id = item.get("consumer_appid", "Unknown")
        author_name = item.get("creator_name", item.get("creator", "Unknown"))

        subs = _safe_int(item.get("subscriptions"))
        favorites = _safe_int(item.get("favorited"))
        views = _safe_int(item.get("views"))
        file_size = item.get("file_size", 0)

        vote_data = item.get("vote_data", {})
        score = _safe_float(vote_data.get("score"))
        votes_up = _safe_int(vote_data.get("votes_up"))
        votes_down = _safe_int(vote_data.get("votes_down"))
        rating_pct = f"{score * 100:.0f}%" if score else "N/A"

        time_created = item.get("time_created", 0)
        time_updated = item.get("time_updated", 0)

        item_tags = [t.get("tag") for t in item.get("tags", [])]
        dependencies = item.get("children", [])

        output = [
            f"Workshop Item: {title}",
            f"ID: {workshop_id} | App: {app_id}",
            f"Author: {author_name}",
            "",
            f"Subscribers: {subs:,} | Favorites: {favorites:,} | Views: {views:,}",
            f"Rating: {rating_pct} ({votes_up:,} up / {votes_down:,} down)",
            f"File Size: {_format_file_size(file_size)}",
            "",
            f"Created: {_format_timestamp(time_created)}",
            f"Updated: {_format_timestamp(time_updated)}",
        ]

        if item_tags:
            output.append(f"Tags: {', '.join(item_tags)}")

        if dependencies:
            output.append(f"\nDependencies ({len(dependencies)}):")
            for dep in dependencies[:10]:
                dep_id = dep.get("publishedfileid", "Unknown")
                output.append(f"  - {dep_id}")
            if len(dependencies) > 10:
                output.append(f"  ... and {len(dependencies) - 10} more")

        # Truncate description if too long
        if len(description) > 1000:
            description = description[:1000] + "...\n[Description truncated]"

        output.append(f"\nDescription:\n{description}")

        return "\n".join(output)

    @endpoint(
        name="search_workshop_collections",
        description=(
            "Search Steam Workshop for collections (curated item lists) by game. "
            "Returns collections with name, subscriber count, and item count. "
            "Use this to discover popular modpacks or curated content lists."
        ),
        supports_json=True,
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game to search collections for",
                "required": True,
            },
            "search_query": {
                "type": "string",
                "description": "Text search filter (optional)",
                "required": False,
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by Workshop tags (e.g., 'Maps', 'Weapons', 'Characters')",
                "required": False,
            },
            "sort_by": {
                "type": "string",
                "description": "Sort order: 'popular' (most voted), 'trend' (trending), 'recent' (newest), 'rating' (highest rated)",
                "required": False,
                "default": "popular",
                "enum": ["popular", "trend", "recent", "rating"],
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 50)",
                "required": False,
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
    )
    async def search_workshop_collections(
        self,
        app_id: int,
        search_query: str = "",
        tags: list[str] | None = None,
        sort_by: str = "popular",
        max_results: int = 10,
        format: str = "text",
    ) -> str:
        """Search Steam Workshop for collections."""
        query_type = QUERY_TYPES.get(sort_by, 0)

        params: dict[str, Any] = {
            "appid": app_id,
            "query_type": query_type,
            "filetype": 1,  # Collections (1=Collections, 2=Art, 0=Items)
            "numperpage": min(max_results, 50),
            "return_metadata": True,
            "return_tags": True,
            "return_vote_data": True,
            "return_children": True,  # Get item count in collections
        }

        if search_query:
            params["search_text"] = search_query

        if tags:
            for i, tag in enumerate(tags):
                params[f"requiredtags[{i}]"] = tag

        try:
            result = await self.client.get(
                "IPublishedFileService",
                "QueryFiles",
                version=1,
                params=params,
            )
        except Exception as e:
            error_msg = f"Error searching Workshop collections: {e}"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        response = result.get("response", {})
        collections = response.get("publishedfiledetails", [])
        total = _safe_int(response.get("total", len(collections)))

        if not collections:
            msg = f"No Workshop collections found for app {app_id}."
            if search_query:
                msg += f" Search query: '{search_query}'"
            if tags:
                msg += f" Tags: {', '.join(tags)}"
            msg += "\n\nThis game may not have Workshop collections, or no collections match your filters."
            if format == "json":
                return json.dumps({"error": msg})
            return msg

        if format == "json":
            data = {
                "app_id": app_id,
                "total_results": total,
                "returned": len(collections),
                "sort_by": sort_by,
                "collections": [
                    {
                        "collection_id": coll.get("publishedfileid"),
                        "name": coll.get("title", "Untitled"),
                        "description": (coll.get("short_description") or coll.get("file_description", ""))[:300],
                        "author_steam_id": coll.get("creator"),
                        "author_name": coll.get("creator_name"),
                        "preview_url": coll.get("preview_url"),
                        "subscriber_count": _safe_int(coll.get("subscriptions")),
                        "favorited_count": _safe_int(coll.get("favorited")),
                        "item_count": len(coll.get("children", [])),
                        "vote_data": {
                            "score": _safe_float(coll.get("vote_data", {}).get("score")),
                            "votes_up": _safe_int(coll.get("vote_data", {}).get("votes_up")),
                            "votes_down": _safe_int(coll.get("vote_data", {}).get("votes_down")),
                        },
                        "time_created": _safe_int(coll.get("time_created")),
                        "time_updated": _safe_int(coll.get("time_updated")),
                    }
                    for coll in collections
                ],
            }
            return json.dumps(data, indent=2)

        # Text format
        output = [
            f"Steam Workshop Collections for App {app_id}",
            f"Total: {total} collections | Showing: {len(collections)} | Sort: {sort_by}",
        ]

        if search_query:
            output.append(f"Search: '{search_query}'")
        if tags:
            output.append(f"Tags: {', '.join(tags)}")
        output.append("")

        for coll in collections:
            coll_id = coll.get("publishedfileid", "?")
            name = coll.get("title", "Untitled")
            author = coll.get("creator_name", "Unknown")
            subs = _safe_int(coll.get("subscriptions"))
            item_count = len(coll.get("children", []))

            vote_data = coll.get("vote_data", {})
            score = _safe_float(vote_data.get("score"))
            rating_pct = f"{score * 100:.0f}%" if score else "N/A"

            desc = (coll.get("short_description") or coll.get("file_description", ""))[:100]
            if len(desc) == 100:
                desc += "..."

            output.append(
                f"[{coll_id}] {name}\n"
                f"    By: {author} | Items: {item_count} | Subscribers: {subs:,} | Rating: {rating_pct}"
            )
            if desc:
                output.append(f"    {desc}")
            output.append("")

        return "\n".join(output)

    @endpoint(
        name="get_workshop_collection",
        description=(
            "Get items from a Steam Workshop collection. "
            "Returns collection name, description, and list of contained items. "
            "Use 'search_workshop_collections' first to find collection IDs. "
            "Note: Item details are fetched for up to 50 items."
        ),
        supports_json=True,
        params={
            "collection_id": {
                "type": "string",
                "description": "The Workshop collection ID (use search_workshop_collections to find IDs)",
                "required": True,
            },
        },
    )
    async def get_workshop_collection(
        self,
        collection_id: str,
        format: str = "text",
    ) -> str:
        """Get items from a Workshop collection."""
        # Validate input
        if not collection_id or not collection_id.strip():
            error_msg = "Collection ID is required"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        collection_id = collection_id.strip()

        # First, get the collection details
        try:
            collection_result = await self.client.get(
                "IPublishedFileService",
                "GetDetails",
                version=1,
                params={
                    "publishedfileids[0]": collection_id,
                    "includetags": True,
                    "includechildren": True,  # This gives us collection items
                },
            )
        except Exception as e:
            error_msg = f"Error fetching collection: {e}"
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        response = collection_result.get("response", {})
        items = response.get("publishedfiledetails", [])

        if not items:
            error_msg = f"Collection {collection_id} not found."
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        collection = items[0]

        # Check if this is actually a collection (file_type 2 = collection)
        file_type = _safe_int(collection.get("file_type"))
        if file_type != 2:
            error_msg = f"Item {collection_id} is not a collection (file_type={file_type})."
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        # Check result status
        if _safe_int(collection.get("result")) != 1:
            error_msg = f"Collection {collection_id} not found or is private."
            if format == "json":
                return json.dumps({"error": error_msg})
            return error_msg

        collection_name = collection.get("title", "Untitled Collection")
        collection_desc = collection.get("file_description", "")
        children = collection.get("children", [])

        # Get details for all child items (up to 50)
        child_ids = [c.get("publishedfileid") for c in children[:50] if c.get("publishedfileid")]

        child_items = []
        if child_ids:
            try:
                # Build params for batch request
                params: dict[str, Any] = {
                    "includetags": True,
                    "includevotes": True,
                }
                for i, cid in enumerate(child_ids):
                    params[f"publishedfileids[{i}]"] = cid

                child_result = await self.client.get(
                    "IPublishedFileService",
                    "GetDetails",
                    version=1,
                    params=params,
                )
                child_items = child_result.get("response", {}).get("publishedfiledetails", [])
            except Exception as e:
                # If batch fetch fails, continue with just collection info
                logger.warning(f"Failed to fetch collection child items: {e}")

        if format == "json":
            data = {
                "collection_id": collection_id,
                "name": collection_name,
                "description": collection_desc,
                "app_id": collection.get("consumer_appid"),
                "author": {
                    "steam_id": collection.get("creator"),
                    "name": collection.get("creator_name"),
                },
                "subscriber_count": collection.get("subscriptions", 0),
                "item_count": len(children),
                "items": [
                    {
                        "workshop_id": item.get("publishedfileid"),
                        "title": item.get("title", "Untitled"),
                        "subscriber_count": _safe_int(item.get("subscriptions")),
                        "vote_score": _safe_float(item.get("vote_data", {}).get("score")),
                        "file_size_bytes": _safe_int(item.get("file_size")),
                    }
                    for item in child_items
                    if _safe_int(item.get("result")) == 1  # Only include successful results
                ],
            }
            if len(children) > 50:
                data["truncated"] = True
                data["total_items"] = len(children)
            return json.dumps(data, indent=2)

        # Text format
        collection_subs = _safe_int(collection.get("subscriptions"))
        output = [
            f"Workshop Collection: {collection_name}",
            f"ID: {collection_id} | App: {collection.get('consumer_appid', 'Unknown')}",
            f"Author: {collection.get('creator_name', collection.get('creator', 'Unknown'))}",
            f"Subscribers: {collection_subs:,}",
            f"Items in collection: {len(children)}",
        ]

        if collection_desc:
            desc_preview = collection_desc[:300]
            if len(collection_desc) > 300:
                desc_preview += "..."
            output.append(f"\nDescription: {desc_preview}")

        output.append(f"\nCollection Items ({len(child_items)} loaded):")
        output.append("")

        for item in child_items:
            if _safe_int(item.get("result")) != 1:
                continue

            item_id = item.get("publishedfileid", "?")
            item_title = item.get("title", "Untitled")
            item_subs = _safe_int(item.get("subscriptions"))
            item_size = item.get("file_size", 0)

            output.append(
                f"  [{item_id}] {item_title}\n"
                f"      Subscribers: {item_subs:,} | Size: {_format_file_size(item_size)}"
            )

        if len(children) > 50:
            output.append(f"\n  ... and {len(children) - 50} more items")

        return "\n".join(output)
