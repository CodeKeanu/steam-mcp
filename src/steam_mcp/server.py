#!/usr/bin/env python3
"""Steam MCP Server - Steam API integration via Model Context Protocol.

This is the main entry point for the Steam MCP server. It initializes the
MCP server, loads endpoint modules, and handles tool calls.
"""

import asyncio
import importlib
import logging
import os
import pkgutil
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from steam_mcp.client import SteamClient
from steam_mcp.endpoints.base import EndpointManager, EndpointRegistry


# Configure logging - only to stderr to avoid corrupting MCP protocol
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
server = Server("steam-mcp-server")

# Global instances
steam_client: SteamClient | None = None
endpoint_manager: EndpointManager | None = None


def discover_endpoints() -> None:
    """
    Discover and import all endpoint modules.

    This function imports all modules in the steam_mcp.endpoints package,
    which triggers the metaclass to register their tools.
    """
    import steam_mcp.endpoints as endpoints_package

    package_path = os.path.dirname(endpoints_package.__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_path]):
        if module_name != "base":  # Skip the base module
            try:
                importlib.import_module(f"steam_mcp.endpoints.{module_name}")
                logger.info(f"Loaded endpoint module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load endpoint module {module_name}: {e}")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available Steam API tools."""
    if endpoint_manager is None:
        return []
    return endpoint_manager.get_all_tools()


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool execution requests."""
    if endpoint_manager is None:
        raise RuntimeError("Endpoint manager not initialized")

    if steam_client is None:
        raise RuntimeError("Steam client not initialized")

    try:
        return await endpoint_manager.call_tool(name, arguments)
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        logger.exception(f"Unexpected error executing tool {name}")
        return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def run_server() -> None:
    """Run the MCP server."""
    global steam_client, endpoint_manager

    # Validate API key is present
    api_key = os.getenv("STEAM_API_KEY")
    if not api_key:
        logger.error("STEAM_API_KEY environment variable is required")
        sys.exit(1)

    # Initialize Steam client
    try:
        steam_client = SteamClient(api_key=api_key)
        logger.info("Steam client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Steam client: {e}")
        sys.exit(1)

    # Discover and load endpoint modules
    discover_endpoints()

    # Initialize endpoint manager
    endpoint_manager = EndpointManager(steam_client)

    tool_count = len(endpoint_manager.get_all_tools())
    logger.info(f"Loaded {tool_count} tools from endpoint modules")

    # Run the MCP server
    async with stdio_server() as (read_stream, write_stream):
        try:
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="steam-mcp-server",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        finally:
            if steam_client:
                await steam_client.close()


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
