"""Tests for endpoint registry and base endpoint classes."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from steam_mcp.endpoints.base import (
    EndpointRegistry,
    EndpointTool,
    BaseEndpoint,
    EndpointManager,
    endpoint,
    _build_input_schema,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before and after each test."""
    EndpointRegistry.clear()
    yield
    EndpointRegistry.clear()


class TestBuildInputSchema:
    """Tests for _build_input_schema function."""

    def test_builds_schema_with_required_param(self):
        params = {
            "steam_id": {
                "type": "string",
                "description": "Steam ID",
                "required": True,
            }
        }
        schema = _build_input_schema(params)

        assert schema["type"] == "object"
        assert "steam_id" in schema["properties"]
        assert schema["properties"]["steam_id"]["type"] == "string"
        assert "steam_id" in schema["required"]

    def test_builds_schema_with_optional_param(self):
        params = {
            "include_avatar": {
                "type": "boolean",
                "description": "Include avatar",
                "required": False,
                "default": True,
            }
        }
        schema = _build_input_schema(params)

        assert "include_avatar" in schema["properties"]
        assert schema["properties"]["include_avatar"]["default"] is True
        assert "include_avatar" not in schema["required"]

    def test_builds_schema_with_enum(self):
        params = {
            "format": {
                "type": "string",
                "description": "Output format",
                "enum": ["json", "text"],
            }
        }
        schema = _build_input_schema(params)

        assert schema["properties"]["format"]["enum"] == ["json", "text"]


class TestEndpointDecorator:
    """Tests for the @endpoint decorator."""

    def test_decorator_adds_metadata(self):
        @endpoint(
            name="test_tool",
            description="A test tool",
            params={"arg1": {"type": "string", "description": "Arg 1"}},
        )
        async def my_tool(self, arg1: str) -> str:
            return arg1

        assert hasattr(my_tool, "_endpoint_meta")
        assert my_tool._endpoint_meta["name"] == "test_tool"
        assert my_tool._endpoint_meta["description"] == "A test tool"

    def test_decorator_preserves_function(self):
        @endpoint(name="test", description="Test")
        async def my_tool(self) -> str:
            return "result"

        # The function should still be callable
        assert callable(my_tool)
        assert my_tool.__name__ == "my_tool"


class TestEndpointRegistry:
    """Tests for EndpointRegistry class."""

    def test_register_and_get_tool(self):
        tool = EndpointTool(
            name="test_tool",
            description="Test",
            input_schema={"type": "object", "properties": {}},
            handler=AsyncMock(),
            endpoint_class=BaseEndpoint,  # type: ignore
        )

        EndpointRegistry.register_tool(tool)
        retrieved = EndpointRegistry.get_tool("test_tool")

        assert retrieved is not None
        assert retrieved.name == "test_tool"

    def test_get_nonexistent_tool_returns_none(self):
        result = EndpointRegistry.get_tool("nonexistent")
        assert result is None

    def test_get_all_tools(self):
        tool1 = EndpointTool(
            name="tool1",
            description="Tool 1",
            input_schema={},
            handler=AsyncMock(),
            endpoint_class=BaseEndpoint,  # type: ignore
        )
        tool2 = EndpointTool(
            name="tool2",
            description="Tool 2",
            input_schema={},
            handler=AsyncMock(),
            endpoint_class=BaseEndpoint,  # type: ignore
        )

        EndpointRegistry.register_tool(tool1)
        EndpointRegistry.register_tool(tool2)

        all_tools = EndpointRegistry.get_all_tools()
        assert len(all_tools) == 2

    def test_clear_removes_all(self):
        tool = EndpointTool(
            name="test",
            description="Test",
            input_schema={},
            handler=AsyncMock(),
            endpoint_class=BaseEndpoint,  # type: ignore
        )
        EndpointRegistry.register_tool(tool)

        EndpointRegistry.clear()

        assert len(EndpointRegistry.get_all_tools()) == 0


class TestBaseEndpoint:
    """Tests for BaseEndpoint class and metaclass registration."""

    def test_endpoint_class_auto_registers(self):
        # Define a new endpoint class - it should auto-register
        class TestEndpoint(BaseEndpoint):
            @endpoint(name="test_method", description="Test method")
            async def test_method(self) -> str:
                return "test"

        # The tool should be registered
        tool = EndpointRegistry.get_tool("test_method")
        assert tool is not None
        assert tool.name == "test_method"

    def test_endpoint_receives_client(self):
        class TestEndpoint(BaseEndpoint):
            pass

        client = MagicMock()
        ep = TestEndpoint(client)

        assert ep.client is client


class TestEndpointManager:
    """Tests for EndpointManager class."""

    @pytest.mark.asyncio
    async def test_call_tool_routes_correctly(self):
        # Create a test endpoint with a registered tool
        class TestEndpoint(BaseEndpoint):
            @endpoint(name="echo", description="Echo input")
            async def echo(self, message: str) -> str:
                return f"Echo: {message}"

        client = MagicMock()
        manager = EndpointManager(client)

        result = await manager.call_tool("echo", {"message": "hello"})

        assert len(result) == 1
        assert result[0].text == "Echo: hello"

    @pytest.mark.asyncio
    async def test_call_unknown_tool_raises_error(self):
        client = MagicMock()
        manager = EndpointManager(client)

        with pytest.raises(ValueError, match="Unknown tool"):
            await manager.call_tool("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_manager_caches_endpoint_instances(self):
        class TestEndpoint(BaseEndpoint):
            instances_created = 0

            def __init__(self, client):
                super().__init__(client)
                TestEndpoint.instances_created += 1

            @endpoint(name="cached_test", description="Test")
            async def cached_test(self) -> str:
                return "test"

        TestEndpoint.instances_created = 0
        client = MagicMock()
        manager = EndpointManager(client)

        await manager.call_tool("cached_test", {})
        await manager.call_tool("cached_test", {})

        assert TestEndpoint.instances_created == 1
