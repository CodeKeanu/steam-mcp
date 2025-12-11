"""Steam Community Guides endpoints.

This module provides MCP tools for searching and retrieving Steam Community guides
for games. These guides include walkthroughs, achievement guides, build guides,
and strategy guides created by the community.

Guide content is retrieved via the IPublishedFileService/GetDetails API.
Guide search uses HTML parsing as there's no official search API.
"""

import re
from html import unescape
from typing import Any

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


class ISteamGuides(BaseEndpoint):
    """Steam Community Guides endpoints for walkthroughs and game guides."""

    COMMUNITY_URL = "https://steamcommunity.com"

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text, preserving basic structure."""
        if not html:
            return ""

        text = html

        # Convert headers to markdown-style
        text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.IGNORECASE | re.DOTALL)

        # Convert line breaks and paragraphs
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)

        # Convert lists
        text = re.sub(r"<li[^>]*>", "  - ", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</?[uo]l[^>]*>", "\n", text, flags=re.IGNORECASE)

        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        text = unescape(text)

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n"))

        return text.strip()

    def _extract_guide_id(self, url_or_id: str) -> str | None:
        """Extract guide ID from URL or return as-is if already an ID."""
        # If it's already a numeric ID
        if url_or_id.isdigit():
            return url_or_id

        # Extract from URL pattern: ?id=XXXXX or /filedetails/?id=XXXXX
        match = re.search(r"[?&]id=(\d+)", url_or_id)
        if match:
            return match.group(1)

        return None

    @endpoint(
        name="search_game_guides",
        description=(
            "Search Steam Community guides for a specific game. "
            "Returns guides with titles, authors, ratings, and view counts. "
            "Useful for finding walkthroughs, achievement guides, and strategy guides."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game to search guides for",
                "required": True,
            },
            "search_query": {
                "type": "string",
                "description": "Optional search term to filter guides (e.g., 'achievement', 'walkthrough')",
                "required": False,
            },
            "section": {
                "type": "string",
                "enum": ["all", "walkthrough", "reference", "achievement"],
                "description": "Guide section to search (default: all)",
                "required": False,
                "default": "all",
            },
            "sort_by": {
                "type": "string",
                "enum": ["popular", "recent", "rating"],
                "description": "Sort order for results (default: popular)",
                "required": False,
                "default": "popular",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of guides to return (default: 10, max: 25)",
                "required": False,
                "default": 10,
                "minimum": 1,
                "maximum": 25,
            },
        },
    )
    async def search_game_guides(
        self,
        app_id: int,
        search_query: str | None = None,
        section: str = "all",
        sort_by: str = "popular",
        max_results: int = 10,
    ) -> str:
        """Search Steam Community guides for a game."""
        # Clamp max_results
        max_results = max(1, min(max_results, 25))

        # Map section to Steam's section IDs
        section_map = {
            "all": "",
            "walkthrough": "1",
            "reference": "2",
            "achievement": "8",
        }
        section_id = section_map.get(section, "")

        # Map sort_by to Steam's parameters
        sort_map = {
            "popular": "totaluniquesubscribers",
            "recent": "mostrecent",
            "rating": "favorited",
        }
        sort_param = sort_map.get(sort_by, "totaluniquesubscribers")

        # Build URL
        url = f"{self.COMMUNITY_URL}/app/{app_id}/guides/"
        params: dict[str, Any] = {
            "browsefilter": sort_param,
            "p": "1",  # Page 1
        }
        if section_id:
            params["section"] = section_id
        if search_query:
            params["searchText"] = search_query

        try:
            response = await self.client._client.get(url, params=params)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            return f"Error fetching guides for App ID {app_id}: {e}"

        # Check if no guides found
        if "No guides have been written yet" in html or "No guides were found" in html:
            return f"No guides found for App ID {app_id}."

        # Parse guide entries from HTML
        # Pattern matches workshop item cards
        guides: list[dict[str, Any]] = []

        # Match guide items - each guide is in a workshopItemCollection div
        guide_pattern = re.compile(
            r'<div[^>]*class="[^"]*workshopItem[^"]*"[^>]*>.*?'
            r'href="[^"]*filedetails/\?id=(\d+)"[^>]*>.*?'  # Guide ID
            r'<div class="workshopItemTitle[^"]*">([^<]+)</div>.*?'  # Title
            r'(?:<div class="workshopItemAuthorName[^"]*">[^<]*<a[^>]*>([^<]+)</a>)?.*?'  # Author (optional)
            r'(?:<div class="workshopItemRating[^"]*"[^>]*>.*?rating_(\d+))?.*?'  # Rating (optional)
            r'</div>',
            re.IGNORECASE | re.DOTALL
        )

        # Alternative simpler pattern if the first doesn't match
        simple_pattern = re.compile(
            r'filedetails/\?id=(\d+)"[^>]*>.*?'
            r'workshopItemTitle[^"]*">([^<]+)<',
            re.IGNORECASE | re.DOTALL
        )

        matches = guide_pattern.findall(html)
        if not matches:
            matches = simple_pattern.findall(html)
            # Pad matches to have consistent format
            matches = [(m[0], m[1], "", "") for m in matches]

        for match in matches[:max_results]:
            guide_id = match[0]
            title = unescape(match[1].strip())
            author = unescape(match[2].strip()) if len(match) > 2 and match[2] else "Unknown"
            rating_val = match[3] if len(match) > 3 and match[3] else "0"

            # Try to extract additional stats from the HTML
            stats_pattern = re.compile(
                rf'id={guide_id}.*?'
                r'numRatings[^>]*>(\d+).*?'
                r'numComments[^>]*>(\d+)',
                re.IGNORECASE | re.DOTALL
            )
            stats_match = stats_pattern.search(html)
            num_ratings = stats_match.group(1) if stats_match else "0"
            num_comments = stats_match.group(2) if stats_match else "0"

            guides.append({
                "id": guide_id,
                "title": title,
                "author": author,
                "rating": rating_val,
                "ratings_count": num_ratings,
                "comments": num_comments,
            })

        if not guides:
            # Try a more permissive extraction
            # Look for any file details links with guide content
            fallback_pattern = re.compile(
                r'sharedfiles/filedetails/\?id=(\d+)[^>]*>.*?<div[^>]*>([^<]{10,100})</div>',
                re.IGNORECASE | re.DOTALL
            )
            fallback_matches = fallback_pattern.findall(html)
            for match in fallback_matches[:max_results]:
                guide_id, title = match
                title = unescape(title.strip())
                if title and not title.startswith("<"):
                    guides.append({
                        "id": guide_id,
                        "title": title,
                        "author": "Unknown",
                        "rating": "0",
                        "ratings_count": "0",
                        "comments": "0",
                    })

        if not guides:
            return f"No guides found for App ID {app_id}. The game may not have any community guides."

        # Format output
        output: list[str] = []
        search_desc = f" matching '{search_query}'" if search_query else ""
        section_desc = f" in {section}" if section != "all" else ""
        output.append(f"Guides for App ID {app_id}{search_desc}{section_desc}:")
        output.append(f"Found {len(guides)} guide(s) (sorted by {sort_by})")
        output.append("")

        for i, guide in enumerate(guides, 1):
            output.append(f"[{i}] {guide['title']}")
            output.append(f"    ID: {guide['id']}")
            output.append(f"    Author: {guide['author']}")
            if guide["rating"] != "0":
                stars = int(guide["rating"]) if guide["rating"].isdigit() else 0
                output.append(f"    Rating: {'*' * stars} ({guide['ratings_count']} ratings)")
            output.append(f"    URL: {self.COMMUNITY_URL}/sharedfiles/filedetails/?id={guide['id']}")
            output.append("")

        return "\n".join(output).strip()

    @endpoint(
        name="get_guide_content",
        description=(
            "Get the full content of a specific Steam Community guide. "
            "Returns the guide title, author, content (formatted as text), and metadata. "
            "Use search_game_guides first to find guide IDs."
        ),
        params={
            "guide_id": {
                "type": "string",
                "description": "Guide ID or full URL (from search_game_guides results)",
                "required": True,
            },
        },
    )
    async def get_guide_content(
        self,
        guide_id: str,
    ) -> str:
        """Get the full content of a Steam Community guide via official API."""
        # Extract ID if URL provided
        extracted_id = self._extract_guide_id(guide_id)
        if not extracted_id:
            return f"Invalid guide ID or URL: {guide_id}"

        # Use IPublishedFileService/GetDetails API
        try:
            result = await self.client.get(
                "IPublishedFileService",
                "GetDetails",
                version=1,
                params={
                    "publishedfileids[0]": extracted_id,
                    "includevotes": "true",
                    "includetags": "true",
                    "strip_description_bbcode": "true",
                },
            )
        except Exception as e:
            return f"Error fetching guide {extracted_id}: {e}"

        response = result.get("response", {})
        files = response.get("publishedfiledetails", [])

        if not files:
            return f"Guide {extracted_id} not found."

        file_data = files[0]

        # Check result code
        result_code = file_data.get("result", 0)
        if result_code != 1:
            if result_code == 9:
                return f"Guide {extracted_id} has been removed or is unavailable."
            return f"Guide {extracted_id} is not accessible (error code: {result_code})."

        # Extract metadata
        title = file_data.get("title", "Unknown Title")
        creator_id = file_data.get("creator", "Unknown")
        app_id = file_data.get("consumer_appid", "Unknown")
        description = file_data.get("file_description", "")
        time_created = file_data.get("time_created", 0)
        time_updated = file_data.get("time_updated", 0)
        views = file_data.get("views", 0)
        subscriptions = file_data.get("subscriptions", 0)
        favorited = file_data.get("favorited", 0)
        lifetime_subscriptions = file_data.get("lifetime_subscriptions", 0)

        # Vote data
        vote_data = file_data.get("vote_data", {})
        votes_up = vote_data.get("votes_up", 0)
        votes_down = vote_data.get("votes_down", 0)

        # Tags
        tags = file_data.get("tags", [])
        tag_names = [t.get("display_name", t.get("tag", "")) for t in tags]

        # Content is already plain text (BBCode stripped by API)
        content = description

        # Format dates
        from datetime import datetime
        created_str = datetime.fromtimestamp(time_created).strftime("%b %d, %Y") if time_created else "Unknown"
        updated_str = datetime.fromtimestamp(time_updated).strftime("%b %d, %Y") if time_updated else "Unknown"

        # Format output
        output: list[str] = []
        output.append("=" * 60)
        output.append(title)
        output.append("=" * 60)
        output.append("")
        output.append(f"Guide ID: {extracted_id}")
        output.append(f"App ID: {app_id}")
        output.append(f"Creator ID: {creator_id}")
        output.append(f"Created: {created_str}")
        output.append(f"Updated: {updated_str}")
        output.append(f"Views: {views:,}")
        output.append(f"Subscribers: {subscriptions:,} (lifetime: {lifetime_subscriptions:,})")
        output.append(f"Favorites: {favorited:,}")
        output.append(f"Votes: +{votes_up:,} / -{votes_down:,}")
        if tag_names:
            output.append(f"Tags: {', '.join(tag_names)}")
        output.append(f"URL: {self.COMMUNITY_URL}/sharedfiles/filedetails/?id={extracted_id}")
        output.append("")
        output.append("-" * 40)
        output.append("CONTENT")
        output.append("-" * 40)
        output.append("")

        if content:
            output.append(content)
        else:
            output.append("(No text content - this guide may consist primarily of images)")

        output.append("")
        output.append("-" * 40)
        output.append("Note: Steam's API only provides a summary, full guide content requires visiting the URL above.")

        return "\n".join(output).strip()
