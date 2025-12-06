"""ISteamNews API endpoints.

This module provides MCP tools for the ISteamNews Steam API interface,
which handles game news feeds and announcements.

Reference: https://partner.steamgames.com/doc/webapi/ISteamNews

Note: This API does not require an API key.
"""

import re
from datetime import datetime

from steam_mcp.endpoints.base import BaseEndpoint, endpoint


# Maximum content length before truncation
MAX_CONTENT_LENGTH = 500


class ISteamNews(BaseEndpoint):
    """ISteamNews API endpoints for game news and announcements."""

    @endpoint(
        name="get_news_for_app",
        description=(
            "Get news articles and announcements for a specific game. "
            "Returns patch notes, updates, community announcements, etc. "
            "No API key required for this endpoint."
        ),
        params={
            "app_id": {
                "type": "integer",
                "description": "Steam App ID of the game (e.g., 440 for TF2, 730 for CS2)",
                "required": True,
            },
            "count": {
                "type": "integer",
                "description": "Number of news items to retrieve (default: 5, max: 20)",
                "required": False,
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum length of content excerpt (0 = full content)",
                "required": False,
                "default": 300,
                "minimum": 0,
            },
        },
    )
    async def get_news_for_app(
        self,
        app_id: int,
        count: int = 5,
        max_length: int = 300,
    ) -> str:
        """Get news for a specific game."""
        # Clamp count to reasonable range
        count = max(1, min(count, 20))

        result = await self.client.get(
            "ISteamNews",
            "GetNewsForApp",
            version=2,
            params={
                "appid": app_id,
                "count": count,
                "maxlength": max_length if max_length > 0 else 0,
            },
        )

        appnews = result.get("appnews", {})
        news_items = appnews.get("newsitems", [])

        if not news_items:
            return f"No news found for App ID {app_id}."

        output = [
            f"News for App ID {app_id}",
            f"Showing {len(news_items)} article(s)",
            "",
        ]

        for item in news_items:
            title = item.get("title", "Untitled")
            author = item.get("author", "Unknown")
            url = item.get("url", "")
            contents = item.get("contents", "")
            date_ts = item.get("date", 0)
            feed_label = item.get("feedlabel", "")
            is_external = item.get("is_external_url", False)

            # Format date
            if date_ts:
                date_str = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d %H:%M")
            else:
                date_str = "Unknown date"

            # Clean up content (remove HTML tags, normalize whitespace)
            clean_content = self._clean_html(contents)

            # Truncate if needed
            if len(clean_content) > MAX_CONTENT_LENGTH:
                clean_content = clean_content[:MAX_CONTENT_LENGTH].rsplit(" ", 1)[0] + "..."

            output.append(f"📰 {title}")
            output.append(f"   By: {author} | {date_str}")
            if feed_label:
                output.append(f"   Source: {feed_label}")
            if clean_content:
                output.append(f"   {clean_content}")
            if url:
                external_tag = " [External]" if is_external else ""
                output.append(f"   Link: {url}{external_tag}")
            output.append("")

        return "\n".join(output)

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and normalize whitespace."""
        if not text:
            return ""

        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", text)

        # Decode common HTML entities
        clean = clean.replace("&nbsp;", " ")
        clean = clean.replace("&amp;", "&")
        clean = clean.replace("&lt;", "<")
        clean = clean.replace("&gt;", ">")
        clean = clean.replace("&quot;", '"')
        clean = clean.replace("&#39;", "'")

        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        return clean
