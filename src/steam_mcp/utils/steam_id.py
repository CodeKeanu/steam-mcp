"""Steam ID normalization utilities.

Steam has multiple ID formats that users might provide:
- SteamID64: 76561198000000000 (API uses this)
- SteamID32: 39734272
- SteamID: STEAM_0:0:19867136
- SteamID3: [U:1:39734272]
- Vanity URL: https://steamcommunity.com/id/username
- Profile URL: https://steamcommunity.com/profiles/76561198000000000

This module normalizes any input format to SteamID64.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from steam_mcp.client import SteamClient


class SteamIDError(Exception):
    """Raised when a Steam ID cannot be parsed or resolved."""

    pass


# Steam ID64 base value (account type = Individual, universe = Public)
STEAMID64_BASE = 76561197960265728

# Regex patterns for Steam ID formats
STEAMID64_PATTERN = re.compile(r"^7656119\d{10}$")
STEAMID_PATTERN = re.compile(r"^STEAM_([0-5]):([01]):(\d+)$", re.IGNORECASE)
STEAMID3_PATTERN = re.compile(r"^\[U:1:(\d+)\]$")
VANITY_URL_PATTERN = re.compile(r"(?:https?://)?steamcommunity\.com/id/([^/]+)/?")
PROFILE_URL_PATTERN = re.compile(r"(?:https?://)?steamcommunity\.com/profiles/(7656119\d{10})/?")

# Note: We intentionally do NOT auto-detect plain numeric strings as SteamID32.
# This is error-prone because small numbers (like app IDs) would be incorrectly
# converted. Users should use explicit formats like [U:1:12345] or STEAM_0:0:6172
# for SteamID32 values.


def steamid32_to_64(steamid32: int) -> str:
    """Convert SteamID32 to SteamID64."""
    return str(STEAMID64_BASE + steamid32)


def steamid_to_64(steam_id: str) -> str:
    """Convert legacy STEAM_X:Y:Z format to SteamID64."""
    match = STEAMID_PATTERN.match(steam_id)
    if not match:
        raise SteamIDError(f"Invalid STEAM_X:Y:Z format: {steam_id}")

    y = int(match.group(2))
    z = int(match.group(3))
    steamid32 = z * 2 + y
    return steamid32_to_64(steamid32)


def steamid3_to_64(steam_id3: str) -> str:
    """Convert [U:1:X] format to SteamID64."""
    match = STEAMID3_PATTERN.match(steam_id3)
    if not match:
        raise SteamIDError(f"Invalid [U:1:X] format: {steam_id3}")

    steamid32 = int(match.group(1))
    return steamid32_to_64(steamid32)


def parse_steam_id(steam_id: str) -> str | None:
    """
    Parse a Steam ID from various formats to SteamID64.

    Returns the SteamID64 string if the input can be parsed locally,
    or None if the input requires an API call (vanity URL).

    Args:
        steam_id: Any Steam ID format

    Returns:
        SteamID64 string or None if API resolution needed

    Raises:
        SteamIDError: If the format is invalid
    """
    steam_id = steam_id.strip()

    # Check for SteamID64 (17-digit number starting with 7656119)
    if STEAMID64_PATTERN.match(steam_id):
        return steam_id

    # Check for profile URL with SteamID64
    profile_match = PROFILE_URL_PATTERN.match(steam_id)
    if profile_match:
        return profile_match.group(1)

    # Check for legacy STEAM_X:Y:Z format
    if STEAMID_PATTERN.match(steam_id):
        return steamid_to_64(steam_id)

    # Check for SteamID3 [U:1:X] format
    if STEAMID3_PATTERN.match(steam_id):
        return steamid3_to_64(steam_id)

    # Check for vanity URL - requires API call
    vanity_match = VANITY_URL_PATTERN.match(steam_id)
    if vanity_match:
        return None  # Signal that API resolution is needed

    # Check if it might be a vanity name (alphanumeric, no special format)
    # Plain numbers are also treated as potential vanity names and will be
    # resolved via API (this is safer than auto-converting to SteamID32)
    if re.match(r"^[a-zA-Z0-9_-]+$", steam_id):
        return None  # Treat as potential vanity URL, needs API resolution

    raise SteamIDError(
        f"Unable to parse Steam ID: '{steam_id}'. "
        "Accepted formats: SteamID64, STEAM_X:Y:Z, [U:1:X], "
        "vanity URL, or profile URL."
    )


def extract_vanity_name(steam_id: str) -> str | None:
    """
    Extract vanity name from input if present.

    Returns the vanity name if the input is a vanity URL or appears to be
    a vanity name, or None if it's a numeric ID format.
    """
    steam_id = steam_id.strip()

    # Check for vanity URL
    vanity_match = VANITY_URL_PATTERN.match(steam_id)
    if vanity_match:
        return vanity_match.group(1)

    # If it's not a recognized numeric format, treat as vanity name
    if not (
        STEAMID64_PATTERN.match(steam_id)
        or PROFILE_URL_PATTERN.match(steam_id)
        or STEAMID_PATTERN.match(steam_id)
        or STEAMID3_PATTERN.match(steam_id)
    ):
        if re.match(r"^[a-zA-Z0-9_-]+$", steam_id):
            return steam_id

    return None


async def normalize_steam_id(steam_id: str, client: "SteamClient") -> str:
    """
    Normalize any Steam ID format to SteamID64.

    This function handles all Steam ID formats including vanity URLs,
    which require an API call to resolve.

    Args:
        steam_id: Any Steam ID format
        client: SteamClient instance for resolving vanity URLs

    Returns:
        SteamID64 string

    Raises:
        SteamIDError: If the ID cannot be parsed or resolved
    """
    # Try local parsing first
    result = parse_steam_id(steam_id)
    if result is not None:
        return result

    # Need to resolve vanity URL
    vanity_name = extract_vanity_name(steam_id)
    if vanity_name:
        resolved = await client.resolve_vanity_url(vanity_name)
        if resolved:
            return resolved
        raise SteamIDError(f"Could not resolve vanity URL: '{vanity_name}'")

    raise SteamIDError(f"Unable to normalize Steam ID: '{steam_id}'")
