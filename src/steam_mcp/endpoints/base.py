"""Base endpoint class and tool registry for modular endpoint system.

This module provides the foundation for creating modular Steam API endpoint handlers.
Each endpoint module (ISteamUser, IPlayerService, etc.) inherits from BaseEndpoint
and uses the @endpoint decorator to register MCP tools.

Example usage:

    from steam_mcp.endpoints import BaseEndpoint, endpoint

    class ISteamUser(BaseEndpoint):
        '''Steam User API endpoints.'''

        @endpoint(
            name="get_player_summary",
            description="Get Steam player profile information",
            params={
                "steam_id": {
                    "type": "string",
                    "description": "Steam ID in any format (SteamID64, vanity URL, etc.)",
                    "required": True,
                }
            },
        )
        async def get_player_summary(self, steam_id: str) -> str:
            '''Get player summary for a Steam user.'''
            normalized_id = await normalize_steam_id(steam_id, self.client)
            players = await self.client.get_player_summaries([normalized_id])
            if not players:
                return "Player not found"
            return self.format_player(players[0])
"""

import functools
import inspect
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, TypeVar

from mcp.types import Tool, TextContent

from steam_mcp.client import SteamClient
from steam_mcp.utils.steam_id import normalize_steam_id, SteamIDError


logger = logging.getLogger(__name__)

# Type for async endpoint methods
F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, str]])


@dataclass
class EndpointTool:
    """Metadata for a registered endpoint tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Coroutine[Any, Any, str]]
    endpoint_class: type["BaseEndpoint"]
    supports_json: bool = False


@dataclass
class EndpointParam:
    """Schema for an endpoint parameter."""

    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    items: dict[str, Any] | None = None  # For array types


class EndpointRegistry:
    """Registry for all endpoint tools across endpoint modules.

    This registry enables auto-discovery of tools from endpoint classes
    and provides a unified interface for the MCP server.

    Note: Uses lazy initialization to avoid class-level mutable state issues.
    """

    _tools: dict[str, EndpointTool] | None = None
    _endpoint_classes: list[type["BaseEndpoint"]] | None = None

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure registry is initialized (lazy initialization)."""
        if cls._tools is None:
            cls._tools = {}
        if cls._endpoint_classes is None:
            cls._endpoint_classes = []

    @classmethod
    def register_tool(cls, tool: EndpointTool) -> None:
        """Register a tool in the global registry."""
        cls._ensure_initialized()
        assert cls._tools is not None  # For type checker
        if tool.name in cls._tools:
            logger.warning(
                f"Tool '{tool.name}' already registered, overwriting"
            )
        cls._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    @classmethod
    def register_endpoint_class(cls, endpoint_class: type["BaseEndpoint"]) -> None:
        """Register an endpoint class for instantiation."""
        cls._ensure_initialized()
        assert cls._endpoint_classes is not None  # For type checker
        if endpoint_class not in cls._endpoint_classes:
            cls._endpoint_classes.append(endpoint_class)
            logger.debug(f"Registered endpoint class: {endpoint_class.__name__}")

    @classmethod
    def get_tool(cls, name: str) -> EndpointTool | None:
        """Get a tool by name."""
        cls._ensure_initialized()
        assert cls._tools is not None  # For type checker
        return cls._tools.get(name)

    @classmethod
    def get_all_tools(cls) -> list[EndpointTool]:
        """Get all registered tools."""
        cls._ensure_initialized()
        assert cls._tools is not None  # For type checker
        return list(cls._tools.values())

    @classmethod
    def get_mcp_tools(cls) -> list[Tool]:
        """Get all tools in MCP Tool format."""
        cls._ensure_initialized()
        assert cls._tools is not None  # For type checker
        return [
            Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
            )
            for tool in cls._tools.values()
        ]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools (useful for testing)."""
        cls._tools = {}
        cls._endpoint_classes = []


def _build_input_schema(
    params: dict[str, dict[str, Any] | EndpointParam]
) -> dict[str, Any]:
    """Build JSON Schema from parameter definitions."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in params.items():
        if isinstance(param, EndpointParam):
            param_dict = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                param_dict["enum"] = param.enum
            if param.default is not None:
                param_dict["default"] = param.default
            if param.minimum is not None:
                param_dict["minimum"] = param.minimum
            if param.maximum is not None:
                param_dict["maximum"] = param.maximum
            if param.items:
                param_dict["items"] = param.items
            if param.required:
                required.append(name)
        else:
            param_dict = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
            }
            if "enum" in param:
                param_dict["enum"] = param["enum"]
            if "default" in param:
                param_dict["default"] = param["default"]
            if "minimum" in param:
                param_dict["minimum"] = param["minimum"]
            if "maximum" in param:
                param_dict["maximum"] = param["maximum"]
            if "items" in param:
                param_dict["items"] = param["items"]
            if param.get("required", True):
                required.append(name)

        properties[name] = param_dict

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def endpoint(
    name: str,
    description: str,
    params: dict[str, dict[str, Any] | EndpointParam] | None = None,
    supports_json: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to register a method as an MCP tool endpoint.

    This decorator marks an async method as an MCP tool and registers it
    with the EndpointRegistry. The method will be called with keyword arguments
    matching the parameter names defined in `params`.

    Args:
        name: Tool name (should be unique across all endpoints)
        description: Human-readable description of what the tool does
        params: Dictionary of parameter definitions. Each parameter can be
                a dict with keys: type, description, required, enum, default
        supports_json: If True, adds a 'format' parameter that allows switching
                       between 'text' (default) and 'json' output formats

    Returns:
        Decorated function

    Example:
        @endpoint(
            name="get_player_summary",
            description="Get Steam player profile",
            supports_json=True,
            params={
                "steam_id": {
                    "type": "string",
                    "description": "Steam ID in any format",
                    "required": True,
                },
                "include_avatar": {
                    "type": "boolean",
                    "description": "Include avatar URL",
                    "default": True,
                    "required": False,
                },
            },
        )
        async def get_player_summary(self, steam_id: str, include_avatar: bool = True, format: str = "text") -> str:
            ...
    """
    params = params or {}

    # If supports_json, auto-add the format parameter
    if supports_json:
        params = dict(params)  # Make a copy to avoid mutating the original
        params["format"] = {
            "type": "string",
            "description": "Output format: 'text' for human-readable output, 'json' for structured JSON",
            "enum": ["text", "json"],
            "default": "text",
            "required": False,
        }

    input_schema = _build_input_schema(params)

    def decorator(func: F) -> F:
        # Store endpoint metadata directly on the function
        # No wrapper needed - the function is called directly by EndpointManager
        func._endpoint_meta = {  # type: ignore[attr-defined]
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "params": params,
            "supports_json": supports_json,
        }
        return func

    return decorator


class BaseEndpointMeta(type):
    """Metaclass that auto-registers endpoint classes and their tools."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Don't register the base class itself
        if name != "BaseEndpoint" and any(
            isinstance(b, BaseEndpointMeta) for b in bases
        ):
            EndpointRegistry.register_endpoint_class(cls)  # type: ignore[arg-type]

            # Register all endpoint methods
            for attr_name, attr_value in namespace.items():
                if hasattr(attr_value, "_endpoint_meta"):
                    meta = attr_value._endpoint_meta
                    tool = EndpointTool(
                        name=meta["name"],
                        description=meta["description"],
                        input_schema=meta["input_schema"],
                        handler=attr_value,
                        endpoint_class=cls,  # type: ignore[arg-type]
                        supports_json=meta.get("supports_json", False),
                    )
                    EndpointRegistry.register_tool(tool)

        return cls


class BaseEndpoint(metaclass=BaseEndpointMeta):
    """
    Base class for Steam API endpoint modules.

    Subclasses represent Steam API interfaces (ISteamUser, IPlayerService, etc.)
    and define MCP tools using the @endpoint decorator.

    Attributes:
        client: SteamClient instance for making API calls

    Example:
        class ISteamUser(BaseEndpoint):
            '''ISteamUser API endpoints.'''

            @endpoint(
                name="get_player_summary",
                description="Get player profile information",
                params={"steam_id": {"type": "string", "description": "Steam ID"}},
            )
            async def get_player_summary(self, steam_id: str) -> str:
                players = await self.client.get_player_summaries([steam_id])
                return json.dumps(players[0], indent=2)
    """

    def __init__(self, client: SteamClient) -> None:
        """
        Initialize endpoint with Steam client.

        Args:
            client: SteamClient instance for API calls
        """
        self.client = client

    async def _resolve_steam_id(self, steam_id: str) -> str:
        """
        Resolve steam_id, handling 'me'/'my' shortcuts.

        This is a shared utility method for all endpoints that work with Steam IDs.
        It handles the common pattern of accepting 'me'/'my' shortcuts and normalizing
        various Steam ID formats.

        Args:
            steam_id: Steam ID in any format, or 'me'/'my' for owner's profile

        Returns:
            Normalized SteamID64, or error message starting with "Error"
        """
        steam_id_lower = steam_id.strip().lower()
        if steam_id_lower in ("me", "my", "myself", "mine"):
            if not self.client.owner_steam_id:
                return (
                    "Error: No owner Steam ID configured. "
                    "Set STEAM_USER_ID environment variable to use 'me'/'my' shortcuts."
                )
            return self.client.owner_steam_id

        try:
            return await normalize_steam_id(steam_id, self.client)
        except SteamIDError as e:
            return f"Error resolving Steam ID: {e}"

    @classmethod
    def get_tools(cls) -> list[Tool]:
        """Get MCP Tool definitions for this endpoint class."""
        tools = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if hasattr(attr, "_endpoint_meta"):
                meta = attr._endpoint_meta
                tools.append(
                    Tool(
                        name=meta["name"],
                        description=meta["description"],
                        inputSchema=meta["input_schema"],
                    )
                )
        return tools


class EndpointManager:
    """
    Manages endpoint instances and routes tool calls.

    This class is the bridge between the MCP server and endpoint modules.
    It instantiates endpoint classes and routes tool calls to the correct handler.
    """

    def __init__(self, client: SteamClient) -> None:
        """
        Initialize endpoint manager.

        Args:
            client: SteamClient instance shared by all endpoints
        """
        self.client = client
        self._instances: dict[type[BaseEndpoint], BaseEndpoint] = {}

    def _get_instance(self, endpoint_class: type[BaseEndpoint]) -> BaseEndpoint:
        """Get or create an instance of an endpoint class."""
        if endpoint_class not in self._instances:
            self._instances[endpoint_class] = endpoint_class(self.client)
        return self._instances[endpoint_class]

    def get_all_tools(self) -> list[Tool]:
        """Get all registered MCP tools."""
        return EndpointRegistry.get_mcp_tools()

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None
    ) -> list[TextContent]:
        """
        Route a tool call to the appropriate endpoint handler.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            List of TextContent with the tool result

        Raises:
            ValueError: If tool is not found
        """
        tool = EndpointRegistry.get_tool(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Get endpoint instance
        instance = self._get_instance(tool.endpoint_class)

        # Call the handler
        try:
            result = await tool.handler(instance, **(arguments or {}))
            return [TextContent(type="text", text=result)]
        except Exception as e:
            logger.exception(f"Error executing tool {name}")
            return [TextContent(type="text", text=f"Error: {e}")]
