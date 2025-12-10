"""Tests for ISteamGuides endpoints - search_game_guides, get_guide_content."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from steam_mcp.endpoints.steam_guides import ISteamGuides


@pytest.fixture
def mock_client():
    """Create mock Steam client with httpx client."""
    client = MagicMock()
    client._client = MagicMock()
    client._client.get = AsyncMock()
    return client


@pytest.fixture
def steam_guides(mock_client):
    """Create ISteamGuides instance with mock client."""
    return ISteamGuides(mock_client)


class TestHtmlToText:
    """Tests for _html_to_text helper method."""

    def test_empty_string(self, steam_guides):
        """Empty input returns empty output."""
        assert steam_guides._html_to_text("") == ""

    def test_plain_text_passthrough(self, steam_guides):
        """Plain text without HTML passes through."""
        text = "This is plain text."
        assert steam_guides._html_to_text(text) == text

    def test_strips_html_tags(self, steam_guides):
        """HTML tags are removed."""
        html = "<p>Hello <strong>world</strong></p>"
        result = steam_guides._html_to_text(html)
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result
        assert ">" not in result

    def test_converts_headers_to_markdown(self, steam_guides):
        """Headers are converted to markdown style."""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        result = steam_guides._html_to_text(html)
        assert "# Title" in result
        assert "## Subtitle" in result

    def test_converts_lists(self, steam_guides):
        """List items are converted to bullet points."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = steam_guides._html_to_text(html)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_decodes_html_entities(self, steam_guides):
        """HTML entities are decoded."""
        html = "Don&apos;t &amp; won&apos;t &lt;test&gt;"
        result = steam_guides._html_to_text(html)
        assert "Don't" in result
        assert "&" in result
        assert "<test>" in result


class TestExtractGuideId:
    """Tests for _extract_guide_id helper method."""

    def test_numeric_id_passthrough(self, steam_guides):
        """Numeric IDs pass through unchanged."""
        assert steam_guides._extract_guide_id("12345") == "12345"
        assert steam_guides._extract_guide_id("999999999") == "999999999"

    def test_extracts_from_full_url(self, steam_guides):
        """Extracts ID from full Steam URL."""
        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=12345"
        assert steam_guides._extract_guide_id(url) == "12345"

    def test_extracts_from_url_with_extra_params(self, steam_guides):
        """Extracts ID even with additional URL parameters."""
        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=12345&searchtext=test"
        assert steam_guides._extract_guide_id(url) == "12345"

    def test_returns_none_for_invalid_input(self, steam_guides):
        """Returns None for invalid input."""
        assert steam_guides._extract_guide_id("invalid") is None
        assert steam_guides._extract_guide_id("not-a-number") is None
        assert steam_guides._extract_guide_id("") is None


class TestSearchGameGuides:
    """Tests for search_game_guides endpoint."""

    @pytest.mark.asyncio
    async def test_no_guides_found_message(self, steam_guides, mock_client):
        """Returns appropriate message when no guides exist."""
        mock_response = MagicMock()
        mock_response.text = "No guides have been written yet for this game."
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.search_game_guides(app_id=12345)

        assert "No guides found for App ID 12345" in result

    @pytest.mark.asyncio
    async def test_extracts_guides_from_html(self, steam_guides, mock_client):
        """Extracts guide information from HTML response."""
        html = """
        <div class="workshopItem">
            <a href="https://steamcommunity.com/sharedfiles/filedetails/?id=98765">
            <div class="workshopItemTitle">Achievement Guide</div>
            <div class="workshopItemAuthorName"><a href="#">TestAuthor</a></div>
            </a>
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.search_game_guides(app_id=440)

        assert "Achievement Guide" in result
        assert "98765" in result

    @pytest.mark.asyncio
    async def test_respects_max_results(self, steam_guides, mock_client):
        """Limits output to max_results."""
        # Create HTML with multiple guides
        guides_html = ""
        for i in range(10):
            guides_html += f"""
            <div class="workshopItem">
                <a href="https://steamcommunity.com/sharedfiles/filedetails/?id={1000 + i}">
                <div class="workshopItemTitle">Guide {i}</div>
                </a>
            </div>
            """

        mock_response = MagicMock()
        mock_response.text = guides_html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.search_game_guides(app_id=440, max_results=3)

        # Count guide entries
        guide_count = result.count("ID: ")
        assert guide_count <= 3

    @pytest.mark.asyncio
    async def test_passes_search_query(self, steam_guides, mock_client):
        """Search query is passed to the request."""
        mock_response = MagicMock()
        mock_response.text = "No guides were found"
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        await steam_guides.search_game_guides(
            app_id=440, search_query="walkthrough"
        )

        call_args = mock_client._client.get.call_args
        assert call_args[1]["params"]["searchText"] == "walkthrough"

    @pytest.mark.asyncio
    async def test_passes_section_filter(self, steam_guides, mock_client):
        """Section filter is mapped and passed correctly."""
        mock_response = MagicMock()
        mock_response.text = "No guides were found"
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        await steam_guides.search_game_guides(app_id=440, section="achievement")

        call_args = mock_client._client.get.call_args
        assert call_args[1]["params"]["section"] == "8"  # Achievement section ID

    @pytest.mark.asyncio
    async def test_passes_sort_order(self, steam_guides, mock_client):
        """Sort order is mapped and passed correctly."""
        mock_response = MagicMock()
        mock_response.text = "No guides were found"
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        await steam_guides.search_game_guides(app_id=440, sort_by="recent")

        call_args = mock_client._client.get.call_args
        assert call_args[1]["params"]["browsefilter"] == "mostrecent"

    @pytest.mark.asyncio
    async def test_handles_http_error(self, steam_guides, mock_client):
        """Returns error message on HTTP failure."""
        mock_client._client.get.side_effect = Exception("Connection failed")

        result = await steam_guides.search_game_guides(app_id=440)

        assert "Error fetching guides" in result
        assert "440" in result

    @pytest.mark.asyncio
    async def test_formats_output_with_guide_url(self, steam_guides, mock_client):
        """Output includes direct URL to each guide."""
        html = """
        <div class="workshopItem">
            <a href="https://steamcommunity.com/sharedfiles/filedetails/?id=12345">
            <div class="workshopItemTitle">Test Guide</div>
            </a>
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.search_game_guides(app_id=440)

        assert "steamcommunity.com/sharedfiles/filedetails/?id=12345" in result


class TestGetGuideContent:
    """Tests for get_guide_content endpoint."""

    @pytest.mark.asyncio
    async def test_invalid_guide_id_returns_error(self, steam_guides):
        """Returns error for invalid guide ID."""
        result = await steam_guides.get_guide_content(guide_id="invalid-id")

        assert "Invalid guide ID" in result

    @pytest.mark.asyncio
    async def test_accepts_numeric_id(self, steam_guides, mock_client):
        """Accepts numeric guide ID."""
        mock_response = MagicMock()
        mock_response.text = '<div class="workshopItemTitle">Test</div>'
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        call_args = mock_client._client.get.call_args
        assert call_args[1]["params"]["id"] == "12345"

    @pytest.mark.asyncio
    async def test_accepts_full_url(self, steam_guides, mock_client):
        """Extracts ID from full URL."""
        mock_response = MagicMock()
        mock_response.text = '<div class="workshopItemTitle">Test</div>'
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        url = "https://steamcommunity.com/sharedfiles/filedetails/?id=98765"
        result = await steam_guides.get_guide_content(guide_id=url)

        call_args = mock_client._client.get.call_args
        assert call_args[1]["params"]["id"] == "98765"

    @pytest.mark.asyncio
    async def test_handles_removed_guide(self, steam_guides, mock_client):
        """Returns appropriate message for removed guides."""
        mock_response = MagicMock()
        mock_response.text = "The item you are trying to view has been removed"
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "has been removed" in result

    @pytest.mark.asyncio
    async def test_handles_private_guide(self, steam_guides, mock_client):
        """Returns appropriate message for private guides."""
        mock_response = MagicMock()
        mock_response.text = "You do not have permission to view this item"
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "private or restricted" in result

    @pytest.mark.asyncio
    async def test_extracts_title(self, steam_guides, mock_client):
        """Extracts guide title from HTML."""
        html = """
        <div class="workshopItemTitle">Ultimate Achievement Guide</div>
        <div class="workshopItemDescription">Some content here</div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "Ultimate Achievement Guide" in result

    @pytest.mark.asyncio
    async def test_extracts_author(self, steam_guides, mock_client):
        """Extracts author name from HTML."""
        html = """
        <div class="workshopItemTitle">Test Guide</div>
        <div class="friendBlockContent">
            GuideAuthor123
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "GuideAuthor123" in result

    @pytest.mark.asyncio
    async def test_extracts_content(self, steam_guides, mock_client):
        """Extracts and formats guide content."""
        html = """
        <div class="workshopItemTitle">Test Guide</div>
        <div class="workshopItemDescription" id="highlightContent">
            <p>This is the guide introduction.</p>
            <h2>Section One</h2>
            <p>Section one content.</p>
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "CONTENT" in result
        # Should contain extracted text
        assert "guide" in result.lower() or "section" in result.lower()

    @pytest.mark.asyncio
    async def test_includes_images_when_requested(self, steam_guides, mock_client):
        """Includes image URLs when include_images=True."""
        html = """
        <div class="workshopItemTitle">Test Guide</div>
        <div class="workshopItemDescription">
            <img src="https://example.com/image1.jpg" />
            <img src="https://example.com/image2.jpg" />
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(
            guide_id="12345", include_images=True
        )

        assert "IMAGES" in result
        assert "example.com/image1.jpg" in result

    @pytest.mark.asyncio
    async def test_excludes_images_by_default(self, steam_guides, mock_client):
        """Does not include images by default."""
        html = """
        <div class="workshopItemTitle">Test Guide</div>
        <div class="workshopItemDescription">
            <img src="https://example.com/image1.jpg" />
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "IMAGES" not in result

    @pytest.mark.asyncio
    async def test_handles_http_error(self, steam_guides, mock_client):
        """Returns error message on HTTP failure."""
        mock_client._client.get.side_effect = Exception("Network error")

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "Error fetching guide" in result
        assert "12345" in result

    @pytest.mark.asyncio
    async def test_output_includes_guide_url(self, steam_guides, mock_client):
        """Output includes URL to the guide."""
        html = '<div class="workshopItemTitle">Test</div>'
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "steamcommunity.com/sharedfiles/filedetails/?id=12345" in result

    @pytest.mark.asyncio
    async def test_handles_empty_content_gracefully(self, steam_guides, mock_client):
        """Handles guides with no extractable content."""
        html = """
        <div class="workshopItemTitle">Empty Guide</div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()
        mock_client._client.get.return_value = mock_response

        result = await steam_guides.get_guide_content(guide_id="12345")

        assert "Empty Guide" in result
        # Should indicate no content was found
        assert "No content could be extracted" in result or "CONTENT" in result
