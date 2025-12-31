"""Tests for ISteamNews endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from steam_mcp.endpoints.steam_news import ISteamNews


@pytest.fixture
def mock_client():
    """Create mock Steam client."""
    client = MagicMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def steam_news(mock_client):
    """Create ISteamNews instance with mock client."""
    return ISteamNews(mock_client)


class TestGetNewsForApp:
    """Tests for get_news_for_app endpoint."""

    @pytest.mark.asyncio
    async def test_returns_news_items(self, steam_news, mock_client):
        """Should return formatted news items."""
        mock_client.get.return_value = {
            "appnews": {
                "newsitems": [
                    {
                        "title": "Big Update",
                        "author": "Developer",
                        "url": "https://example.com/news",
                        "contents": "Exciting news about the update!",
                        "date": 1702000000,
                        "feedlabel": "Steam Blog",
                        "is_external_url": False,
                    }
                ]
            }
        }

        result = await steam_news.get_news_for_app(app_id=440)

        assert "News for App ID 440" in result
        assert "Big Update" in result
        assert "Developer" in result
        assert "Steam Blog" in result
        assert "Exciting news" in result
        assert "https://example.com/news" in result

    @pytest.mark.asyncio
    async def test_no_news_found(self, steam_news, mock_client):
        """Should return message when no news found."""
        mock_client.get.return_value = {"appnews": {"newsitems": []}}

        result = await steam_news.get_news_for_app(app_id=12345)

        assert "No news found" in result
        assert "12345" in result

    @pytest.mark.asyncio
    async def test_multiple_news_items(self, steam_news, mock_client):
        """Should return multiple news items."""
        mock_client.get.return_value = {
            "appnews": {
                "newsitems": [
                    {
                        "title": "First News",
                        "author": "Author1",
                        "url": "url1",
                        "contents": "Content 1",
                        "date": 1702000000,
                    },
                    {
                        "title": "Second News",
                        "author": "Author2",
                        "url": "url2",
                        "contents": "Content 2",
                        "date": 1701000000,
                    },
                ]
            }
        }

        result = await steam_news.get_news_for_app(app_id=440, count=5)

        assert "2 article(s)" in result
        assert "First News" in result
        assert "Second News" in result

    @pytest.mark.asyncio
    async def test_count_clamped_to_max(self, steam_news, mock_client):
        """Should clamp count to maximum of 20."""
        mock_client.get.return_value = {"appnews": {"newsitems": []}}

        await steam_news.get_news_for_app(app_id=440, count=50)

        # Verify the count passed to API is clamped
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["count"] == 20

    @pytest.mark.asyncio
    async def test_count_clamped_to_min(self, steam_news, mock_client):
        """Should clamp count to minimum of 1."""
        mock_client.get.return_value = {"appnews": {"newsitems": []}}

        await steam_news.get_news_for_app(app_id=440, count=0)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["count"] == 1

    @pytest.mark.asyncio
    async def test_external_url_marked(self, steam_news, mock_client):
        """Should mark external URLs."""
        mock_client.get.return_value = {
            "appnews": {
                "newsitems": [
                    {
                        "title": "External News",
                        "author": "Author",
                        "url": "https://external.com/news",
                        "contents": "Content",
                        "date": 1702000000,
                        "is_external_url": True,
                    }
                ]
            }
        }

        result = await steam_news.get_news_for_app(app_id=440)

        assert "[External]" in result

    @pytest.mark.asyncio
    async def test_handles_missing_date(self, steam_news, mock_client):
        """Should handle missing date gracefully."""
        mock_client.get.return_value = {
            "appnews": {
                "newsitems": [
                    {
                        "title": "No Date News",
                        "author": "Author",
                        "url": "url",
                        "contents": "Content",
                        "date": 0,
                    }
                ]
            }
        }

        result = await steam_news.get_news_for_app(app_id=440)

        assert "Unknown date" in result

    @pytest.mark.asyncio
    async def test_max_length_passed_to_api(self, steam_news, mock_client):
        """Should pass max_length parameter to API."""
        mock_client.get.return_value = {"appnews": {"newsitems": []}}

        await steam_news.get_news_for_app(app_id=440, max_length=500)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["maxlength"] == 500

    @pytest.mark.asyncio
    async def test_zero_max_length_for_full_content(self, steam_news, mock_client):
        """Should pass 0 for full content when max_length is 0."""
        mock_client.get.return_value = {"appnews": {"newsitems": []}}

        await steam_news.get_news_for_app(app_id=440, max_length=0)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["maxlength"] == 0


class TestCleanHtml:
    """Tests for _clean_html helper method."""

    @pytest.fixture
    def steam_news_instance(self, mock_client):
        """Create ISteamNews instance for testing."""
        return ISteamNews(mock_client)

    def test_removes_html_tags(self, steam_news_instance):
        """Should remove HTML tags."""
        text = "<p>Hello <b>World</b></p>"
        result = steam_news_instance._clean_html(text)

        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_decodes_html_entities(self, steam_news_instance):
        """Should decode common HTML entities."""
        text = "Hello &amp; World &lt;test&gt; &quot;quoted&quot;"
        result = steam_news_instance._clean_html(text)

        assert "&" in result
        assert "<test>" in result
        assert '"quoted"' in result

    def test_normalizes_whitespace(self, steam_news_instance):
        """Should normalize multiple whitespaces."""
        text = "Hello    World\n\nTest"
        result = steam_news_instance._clean_html(text)

        assert "  " not in result
        assert result == "Hello World Test"

    def test_handles_empty_string(self, steam_news_instance):
        """Should handle empty string."""
        result = steam_news_instance._clean_html("")

        assert result == ""

    def test_handles_none_like_empty(self, steam_news_instance):
        """Should handle None-like empty values."""
        result = steam_news_instance._clean_html(None)

        assert result == ""

    def test_replaces_nbsp(self, steam_news_instance):
        """Should replace &nbsp; with space."""
        text = "Hello&nbsp;World"
        result = steam_news_instance._clean_html(text)

        assert result == "Hello World"


class TestContentTruncation:
    """Tests for content truncation in output."""

    @pytest.mark.asyncio
    async def test_long_content_truncated(self, steam_news, mock_client):
        """Should truncate content longer than MAX_CONTENT_LENGTH."""
        long_content = "A" * 600  # Longer than MAX_CONTENT_LENGTH (500)
        mock_client.get.return_value = {
            "appnews": {
                "newsitems": [
                    {
                        "title": "Long Content",
                        "author": "Author",
                        "url": "url",
                        "contents": long_content,
                        "date": 1702000000,
                    }
                ]
            }
        }

        result = await steam_news.get_news_for_app(app_id=440)

        # Content should be truncated and have ellipsis
        assert "..." in result
        # Should not contain all 600 As
        assert "A" * 600 not in result

    @pytest.mark.asyncio
    async def test_short_content_not_truncated(self, steam_news, mock_client):
        """Should not truncate content shorter than MAX_CONTENT_LENGTH."""
        short_content = "Short content"
        mock_client.get.return_value = {
            "appnews": {
                "newsitems": [
                    {
                        "title": "Short Content",
                        "author": "Author",
                        "url": "url",
                        "contents": short_content,
                        "date": 1702000000,
                    }
                ]
            }
        }

        result = await steam_news.get_news_for_app(app_id=440)

        assert "Short content" in result
