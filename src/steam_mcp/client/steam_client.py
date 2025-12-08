"""Steam API Client with rate limiting and error handling.

This client provides a robust interface to the Steam Web API with:
- Rate limiting to avoid hitting API limits
- Automatic retry with exponential backoff
- Consistent error handling across all endpoints
- Response wrapper normalization
"""

import asyncio
import logging
import os
import time
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class SteamAPIError(Exception):
    """Base exception for Steam API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(SteamAPIError):
    """Raised when rate limit is exceeded."""

    pass


class PrivateProfileError(SteamAPIError):
    """Raised when accessing data from a private profile."""

    pass


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_second: float = 10.0):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second (default: 10)
        """
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request can be made within rate limits."""
        async with self._lock:
            now = time.monotonic()
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_request_time = time.monotonic()


class SteamClient:
    """Async client for the Steam Web API."""

    BASE_URL = "https://api.steampowered.com"
    STORE_API_URL = "https://store.steampowered.com/api"

    def __init__(
        self,
        api_key: str | None = None,
        owner_steam_id: str | None = None,
        requests_per_second: float = 10.0,
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        """
        Initialize Steam API client.

        Args:
            api_key: Steam Web API key. If not provided, reads from STEAM_API_KEY env var.
            owner_steam_id: SteamID64 of the API key owner. If not provided, reads from
                           STEAM_USER_ID env var. This enables "get my profile" style queries.
            requests_per_second: Rate limit for API requests.
            max_retries: Maximum number of retry attempts for failed requests.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or os.getenv("STEAM_API_KEY")
        if not self.api_key:
            raise ValueError("STEAM_API_KEY must be provided or set in environment")

        # Owner Steam ID is optional but enables convenient "my profile" queries
        self.owner_steam_id = owner_steam_id or os.getenv("STEAM_USER_ID")

        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limiter = RateLimiter(requests_per_second)

        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "SteamClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _build_url(self, interface: str, method: str, version: int = 1) -> str:
        """Build Steam API URL."""
        return f"{self.BASE_URL}/{interface}/{method}/v{version}/"

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make an HTTP request with rate limiting and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Query parameters
            **kwargs: Additional arguments passed to httpx

        Returns:
            Parsed JSON response

        Raises:
            SteamAPIError: On API errors
        """
        params = params or {}
        params["key"] = self.api_key
        params["format"] = "json"

        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            await self.rate_limiter.acquire()

            try:
                response = await self._client.request(
                    method, url, params=params, **kwargs
                )

                # Check for HTML error responses (Steam sometimes returns HTML on errors)
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    raise SteamAPIError(
                        "Steam API returned HTML error page", response.status_code
                    )

                # Handle HTTP errors
                if response.status_code == 429:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code == 403:
                    raise SteamAPIError(
                        "Access forbidden - check API key permissions",
                        response.status_code,
                    )

                if response.status_code == 401:
                    raise SteamAPIError("Invalid API key", response.status_code)

                response.raise_for_status()

                data = response.json()
                return self._normalize_response(data)

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code >= 500:
                    logger.warning(
                        f"Server error {e.response.status_code} "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
                raise SteamAPIError(str(e), e.response.status_code) from e

            except httpx.HTTPError as e:
                raise SteamAPIError(f"HTTP error: {e}") from e

        raise SteamAPIError(
            f"Request failed after {self.max_retries} attempts: {last_exception}"
        )

    def _normalize_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize Steam API response wrappers.

        Steam API responses have inconsistent wrapper objects:
        - Most use: {"response": {...}}
        - Some use: {"playerstats": {...}}
        - Others use: {"appnews": {...}}

        This method returns the data as-is but logs the structure for debugging.
        """
        if not isinstance(data, dict):
            return {"data": data}
        return data

    async def get(
        self,
        interface: str,
        method: str,
        version: int = 1,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make a GET request to the Steam API.

        Args:
            interface: Steam API interface (e.g., "ISteamUser")
            method: API method (e.g., "GetPlayerSummaries")
            version: API version (default: 1)
            params: Additional query parameters

        Returns:
            API response data
        """
        url = self._build_url(interface, method, version)
        return await self._request("GET", url, params=params)

    async def post(
        self,
        interface: str,
        method: str,
        version: int = 1,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make a POST request to the Steam API.

        Args:
            interface: Steam API interface
            method: API method
            version: API version
            params: Query parameters
            data: POST body data

        Returns:
            API response data
        """
        url = self._build_url(interface, method, version)
        return await self._request("POST", url, params=params, data=data)

    async def get_store_api(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make a request to the Steam Store API (unofficial but stable).

        Args:
            endpoint: Store API endpoint (e.g., "appdetails")
            params: Query parameters

        Returns:
            API response data

        Note:
            These endpoints are not officially documented but are widely used
            and relatively stable.
        """
        url = f"{self.STORE_API_URL}/{endpoint}"
        # Store API doesn't require API key
        params = params or {}
        params.pop("key", None)

        await self.rate_limiter.acquire()

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise SteamAPIError(f"Store API error: {e}") from e

    async def get_raw(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make a GET request to an arbitrary URL (no API key added).

        Args:
            url: Full URL to request
            params: Query parameters

        Returns:
            Parsed JSON response

        Note:
            Used for Steam endpoints that don't require authentication,
            like the reviews endpoint.
        """
        params = params or {}

        await self.rate_limiter.acquire()

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise SteamAPIError(f"Request error: {e}") from e

    # Convenience methods for common operations

    async def resolve_vanity_url(self, vanity_name: str) -> str | None:
        """
        Resolve a Steam vanity URL to SteamID64.

        Args:
            vanity_name: The vanity URL name (e.g., "gabelogannewell")

        Returns:
            SteamID64 string or None if not found
        """
        try:
            result = await self.get(
                "ISteamUser",
                "ResolveVanityURL",
                version=1,
                params={"vanityurl": vanity_name},
            )

            response = result.get("response", {})
            if response.get("success") == 1:
                return response.get("steamid")
            return None

        except SteamAPIError:
            return None

    async def get_player_summaries(
        self, steam_ids: list[str]
    ) -> list[dict[str, Any]]:
        """
        Get player summaries for one or more Steam IDs.

        Args:
            steam_ids: List of SteamID64 strings (max 100)

        Returns:
            List of player summary dictionaries

        Raises:
            SteamAPIError: On API errors
            ValueError: If more than 100 IDs provided
        """
        if len(steam_ids) > 100:
            raise ValueError("Maximum 100 Steam IDs per request")

        result = await self.get(
            "ISteamUser",
            "GetPlayerSummaries",
            version=2,
            params={"steamids": ",".join(steam_ids)},
        )

        return result.get("response", {}).get("players", [])

    def is_profile_public(self, player_summary: dict[str, Any]) -> bool:
        """
        Check if a player's profile is public.

        Args:
            player_summary: Player summary from GetPlayerSummaries

        Returns:
            True if profile is public (communityvisibilitystate == 3)
        """
        return player_summary.get("communityvisibilitystate") == 3
