"""Steam API endpoint modules.

Each endpoint module represents a Steam API interface (ISteamUser, IPlayerService, etc.)
and exposes MCP tools for interacting with that interface.
"""

from .base import BaseEndpoint, endpoint, EndpointRegistry

__all__ = ["BaseEndpoint", "endpoint", "EndpointRegistry"]
