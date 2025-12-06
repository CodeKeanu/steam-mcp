"""Tests for Steam ID normalization utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from steam_mcp.utils.steam_id import (
    parse_steam_id,
    steamid_to_64,
    steamid3_to_64,
    steamid32_to_64,
    extract_vanity_name,
    normalize_steam_id,
    SteamIDError,
    STEAMID64_BASE,
)


class TestSteamID32To64:
    """Tests for SteamID32 to SteamID64 conversion."""

    def test_converts_valid_steamid32(self):
        # Gabe Newell's account (roughly)
        result = steamid32_to_64(39734272)
        assert result == str(STEAMID64_BASE + 39734272)
        assert result == "76561198000000000"

    def test_converts_zero(self):
        result = steamid32_to_64(0)
        assert result == str(STEAMID64_BASE)

    def test_converts_large_steamid32(self):
        result = steamid32_to_64(1000000000)
        assert result == str(STEAMID64_BASE + 1000000000)


class TestSteamIDTo64:
    """Tests for legacy STEAM_X:Y:Z format conversion."""

    def test_converts_valid_steamid(self):
        # STEAM_0:0:19867136 -> [U:1:39734272]
        result = steamid_to_64("STEAM_0:0:19867136")
        assert result == steamid32_to_64(39734272)

    def test_converts_with_y_equals_1(self):
        # STEAM_0:1:19867136 -> account = 19867136 * 2 + 1 = 39734273
        result = steamid_to_64("STEAM_0:1:19867136")
        assert result == steamid32_to_64(39734273)

    def test_case_insensitive(self):
        result1 = steamid_to_64("STEAM_0:0:19867136")
        result2 = steamid_to_64("steam_0:0:19867136")
        assert result1 == result2

    def test_invalid_format_raises_error(self):
        with pytest.raises(SteamIDError):
            steamid_to_64("STEAM_invalid")


class TestSteamID3To64:
    """Tests for [U:1:X] format conversion."""

    def test_converts_valid_steamid3(self):
        result = steamid3_to_64("[U:1:39734272]")
        assert result == steamid32_to_64(39734272)

    def test_invalid_format_raises_error(self):
        with pytest.raises(SteamIDError):
            steamid3_to_64("[U:2:39734272]")  # Wrong universe

    def test_missing_brackets_raises_error(self):
        with pytest.raises(SteamIDError):
            steamid3_to_64("U:1:39734272")


class TestParseSteamID:
    """Tests for parse_steam_id function."""

    def test_parses_steamid64(self):
        result = parse_steam_id("76561198000000000")
        assert result == "76561198000000000"

    def test_parses_steamid64_with_whitespace(self):
        result = parse_steam_id("  76561198000000000  ")
        assert result == "76561198000000000"

    def test_parses_profile_url(self):
        result = parse_steam_id("https://steamcommunity.com/profiles/76561198000000000")
        assert result == "76561198000000000"

    def test_parses_profile_url_with_trailing_slash(self):
        result = parse_steam_id("https://steamcommunity.com/profiles/76561198000000000/")
        assert result == "76561198000000000"

    def test_parses_legacy_steamid(self):
        result = parse_steam_id("STEAM_0:0:19867136")
        assert result == steamid32_to_64(39734272)

    def test_parses_steamid3(self):
        result = parse_steam_id("[U:1:39734272]")
        assert result == steamid32_to_64(39734272)

    def test_returns_none_for_vanity_url(self):
        result = parse_steam_id("https://steamcommunity.com/id/gabelogannewell")
        assert result is None  # Needs API resolution

    def test_returns_none_for_plain_vanity_name(self):
        result = parse_steam_id("gabelogannewell")
        assert result is None  # Needs API resolution

    def test_returns_none_for_numeric_string(self):
        # Plain numbers are now treated as potential vanity names
        result = parse_steam_id("12345")
        assert result is None  # Will be resolved via API

    def test_rejects_invalid_format(self):
        with pytest.raises(SteamIDError):
            parse_steam_id("not@valid#id!")


class TestExtractVanityName:
    """Tests for extract_vanity_name function."""

    def test_extracts_from_vanity_url(self):
        result = extract_vanity_name("https://steamcommunity.com/id/gabelogannewell")
        assert result == "gabelogannewell"

    def test_extracts_from_vanity_url_with_trailing_slash(self):
        result = extract_vanity_name("https://steamcommunity.com/id/gabelogannewell/")
        assert result == "gabelogannewell"

    def test_returns_plain_name(self):
        result = extract_vanity_name("gabelogannewell")
        assert result == "gabelogannewell"

    def test_returns_none_for_steamid64(self):
        result = extract_vanity_name("76561198000000000")
        assert result is None

    def test_returns_none_for_profile_url(self):
        result = extract_vanity_name("https://steamcommunity.com/profiles/76561198000000000")
        assert result is None

    def test_returns_none_for_legacy_steamid(self):
        result = extract_vanity_name("STEAM_0:0:19867136")
        assert result is None


class TestNormalizeSteamID:
    """Tests for normalize_steam_id async function."""

    @pytest.mark.asyncio
    async def test_normalizes_steamid64_without_api_call(self):
        client = MagicMock()
        result = await normalize_steam_id("76561198000000000", client)
        assert result == "76561198000000000"
        client.resolve_vanity_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_normalizes_legacy_steamid_without_api_call(self):
        client = MagicMock()
        result = await normalize_steam_id("STEAM_0:0:19867136", client)
        assert result == steamid32_to_64(39734272)
        client.resolve_vanity_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolves_vanity_url_via_api(self):
        client = AsyncMock()
        client.resolve_vanity_url.return_value = "76561198000000000"

        result = await normalize_steam_id("gabelogannewell", client)

        assert result == "76561198000000000"
        client.resolve_vanity_url.assert_called_once_with("gabelogannewell")

    @pytest.mark.asyncio
    async def test_raises_error_when_vanity_url_not_found(self):
        client = AsyncMock()
        client.resolve_vanity_url.return_value = None

        with pytest.raises(SteamIDError, match="Could not resolve vanity URL"):
            await normalize_steam_id("nonexistentuser12345", client)
