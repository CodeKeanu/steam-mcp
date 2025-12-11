"""TTL-based async cache for Steam API responses.

A simple in-memory cache with configurable TTLs per endpoint type.
"""

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CacheCategory(Enum):
    """Cache categories with associated TTLs (in seconds)."""

    # Static data - rarely changes
    APP_DETAILS = 3600  # 1 hour
    GLOBAL_ACHIEVEMENTS = 3600  # 1 hour
    GAME_SCHEMA = 3600  # 1 hour

    # Semi-dynamic data
    PLAYER_SUMMARY = 300  # 5 minutes
    PLAYER_GAMES = 300  # 5 minutes

    # Dynamic data
    CURRENT_PLAYERS = 60  # 1 minute
    NEWS = 300  # 5 minutes

    # Default for unspecified endpoints
    DEFAULT = 300  # 5 minutes


@dataclass
class CacheEntry:
    """A cached response with expiration time."""

    value: Any
    expires_at: float


class TTLCache:
    """Async-safe TTL cache for API responses."""

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Initialize the cache.

        Args:
            default_ttl: Default TTL in seconds for entries without explicit TTL.
            max_size: Maximum number of entries before cleanup triggers.
        """
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(endpoint: str, params: dict[str, Any] | None = None) -> str:
        """
        Generate a cache key from endpoint and parameters.

        Args:
            endpoint: API endpoint identifier.
            params: Query parameters.

        Returns:
            SHA256 hash of endpoint + sorted params.
        """
        key_data = {"endpoint": endpoint, "params": params or {}}
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> tuple[bool, Any]:
        """
        Get a cached value if it exists and hasn't expired.

        Args:
            endpoint: API endpoint identifier.
            params: Query parameters.

        Returns:
            Tuple of (hit, value). hit is True if cache hit, value is the cached data.
        """
        key = self._make_key(endpoint, params)

        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return False, None

            if time.monotonic() > entry.expires_at:
                # Entry expired, remove it
                del self._cache[key]
                self._misses += 1
                return False, None

            self._hits += 1
            return True, entry.value

    async def set(
        self,
        endpoint: str,
        params: dict[str, Any] | None,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Store a value in the cache.

        Args:
            endpoint: API endpoint identifier.
            params: Query parameters.
            value: Data to cache.
            ttl: Time-to-live in seconds. Uses default_ttl if not specified.
        """
        key = self._make_key(endpoint, params)
        ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + ttl

        async with self._lock:
            # Cleanup if we're at capacity
            if len(self._cache) >= self._max_size:
                await self._cleanup_expired()

            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    async def invalidate(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> bool:
        """
        Remove a specific entry from the cache.

        Args:
            endpoint: API endpoint identifier.
            params: Query parameters.

        Returns:
            True if entry was removed, False if not found.
        """
        key = self._make_key(endpoint, params)

        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries removed.
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def _cleanup_expired(self) -> int:
        """
        Remove all expired entries (called internally, lock must be held).

        Returns:
            Number of entries removed.
        """
        now = time.monotonic()
        expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (
                round(self._hits / (self._hits + self._misses) * 100, 1)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
        }


def cached(
    category: CacheCategory | None = None,
    ttl: int | None = None,
    key_func: Callable[..., str] | None = None,
) -> Callable:
    """
    Decorator for caching async method results.

    Args:
        category: CacheCategory to use for TTL. Ignored if ttl is provided.
        ttl: Explicit TTL in seconds. Overrides category TTL.
        key_func: Optional function to generate cache key from args.

    Returns:
        Decorator function.

    Usage:
        @cached(category=CacheCategory.APP_DETAILS)
        async def get_app_details(self, app_id: int) -> dict:
            ...

        @cached(ttl=60)
        async def get_current_players(self, app_id: int) -> int:
            ...
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Check for bypass_cache parameter
            bypass_cache = kwargs.pop("bypass_cache", False)

            # Get or create cache instance
            cache = getattr(self, "_cache", None)
            if cache is None or bypass_cache:
                return await func(self, *args, **kwargs)

            # Generate cache key
            if key_func:
                endpoint = key_func(*args, **kwargs)
            else:
                endpoint = f"{func.__module__}.{func.__qualname__}"
                params = {"args": args, "kwargs": kwargs}
                endpoint = f"{endpoint}:{json.dumps(params, sort_keys=True, default=str)}"

            # Determine TTL
            effective_ttl = ttl
            if effective_ttl is None and category is not None:
                effective_ttl = category.value
            if effective_ttl is None:
                effective_ttl = CacheCategory.DEFAULT.value

            # Try cache
            hit, cached_value = await cache.get(endpoint, None)
            if hit:
                return cached_value

            # Call function and cache result
            result = await func(self, *args, **kwargs)
            await cache.set(endpoint, None, result, effective_ttl)
            return result

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
