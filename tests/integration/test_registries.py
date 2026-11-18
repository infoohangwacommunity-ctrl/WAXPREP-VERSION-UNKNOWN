"""
Test Registries - Stage 02
Prove registries work with fake adapters.
"""

import pytest

from waxprep.adapters import FakeChannelAdapter, FakeModelAdapter, FakeTool
from waxprep.registries.base import DuplicateRegistrationError
from waxprep.registries.channel import ChannelRegistry, get_channel_registry
from waxprep.registries.model import ModelRegistry, get_model_registry
from waxprep.registries.tool import ToolRegistry, get_tool_registry


class TestChannelRegistry:
    """Test channel registry with fake adapter."""

    @pytest.mark.integration
    def test_fake_adapter_has_name(self):
        """Prove fake adapter has required name attribute."""
        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "name")
        assert adapter.name == "fake"

    @pytest.mark.integration
    def test_fake_adapter_has_handle_message(self):
        """Prove fake adapter has required handle_message method."""
        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "handle_message")
        assert callable(adapter.handle_message)

    @pytest.mark.integration
    def test_channel_registry_register(self):
        """Prove channel registry can register adapter."""
        registry = ChannelRegistry()
        adapter = FakeChannelAdapter()
        registry.register("test", adapter)
        assert registry.is_registered("test")

    @pytest.mark.integration
    def test_channel_registry_get(self):
        """Prove channel registry can retrieve adapter."""
        registry = ChannelRegistry()
        adapter = FakeChannelAdapter()
        registry.register("test", adapter)
        retrieved = registry.get("test")
        assert retrieved is adapter

    @pytest.mark.integration
    def test_channel_registry_list_all(self):
        """Prove channel registry can list all adapters."""
        registry = ChannelRegistry()
        registry.register("test1", FakeChannelAdapter())
        registry.register("test2", FakeChannelAdapter())
        assert "test1" in registry.list_all()
        assert "test2" in registry.list_all()

    @pytest.mark.integration
    def test_channel_registry_get_missing_key(self):
        """Prove channel registry raises KeyError for unregistered name."""
        registry = ChannelRegistry()
        with pytest.raises(KeyError, match="No item registered with name"):
            registry.get("nonexistent")

    @pytest.mark.integration
    def test_channel_registry_rejects_adapter_without_name(self):
        """Prove channel registry rejects adapters without a 'name' attribute."""
        registry = ChannelRegistry()

        class NoNameAdapter:
            async def handle_message(self, message: dict) -> dict:
                return message

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            registry.register("no_name", NoNameAdapter())

    @pytest.mark.integration
    def test_default_channel_registry_has_fake(self):
        """Prove default channel registry can be populated with fake adapter."""
        registry = get_channel_registry()
        registry.register_defaults()
        assert registry.is_registered("fake")

    @pytest.mark.integration
    def test_channel_registry_rejects_duplicate(self):
        """Prove channel registry rejects duplicate registrations."""
        registry = ChannelRegistry()
        adapter = FakeChannelAdapter()
        registry.register("test", adapter)
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            registry.register("test", adapter)

    @pytest.mark.integration
    def test_channel_registry_rejects_non_callable_handle_message(self):
        """Prove channel registry rejects adapters without callable handle_message."""
        registry = ChannelRegistry()

        class BadAdapter:
            name = "bad"

            async def handle_message(self, message: dict) -> dict:
                return message

        # This should pass - handle_message is callable
        registry.register("good", BadAdapter())

        class WorseAdapter:
            name = "worse"
            handle_message = "not callable"  # type: ignore

        with pytest.raises(ValueError, match="callable"):
            registry.register("worse", WorseAdapter())


class TestModelRegistry:
    """Test model registry with fake adapter."""

    @pytest.mark.integration
    def test_fake_adapter_has_name(self):
        """Prove fake adapter has required name attribute."""
        adapter = FakeModelAdapter()
        assert hasattr(adapter, "name")
        assert adapter.name == "fake"

    @pytest.mark.integration
    def test_fake_adapter_has_generate(self):
        """Prove fake adapter has required generate method."""
        adapter = FakeModelAdapter()
        assert hasattr(adapter, "generate")
        assert callable(adapter.generate)

    @pytest.mark.integration
    def test_model_registry_register(self):
        """Prove model registry can register adapter."""
        registry = ModelRegistry()
        adapter = FakeModelAdapter()
        registry.register("test", adapter)
        assert registry.is_registered("test")

    @pytest.mark.integration
    def test_default_model_registry_has_fake(self):
        """Prove default model registry can be populated with fake adapter."""
        registry = get_model_registry()
        registry.register_defaults()
        assert registry.is_registered("fake")

    @pytest.mark.integration
    def test_model_registry_rejects_duplicate(self):
        """Prove model registry rejects duplicate registrations."""
        registry = ModelRegistry()
        adapter = FakeModelAdapter()
        registry.register("test", adapter)
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            registry.register("test", adapter)

    @pytest.mark.integration
    def test_model_registry_rejects_adapter_without_name(self):
        """Prove model registry rejects adapters without a 'name' attribute."""
        registry = ModelRegistry()

        class NoNameAdapter:
            async def generate(self, prompt: str) -> str:
                return prompt

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            registry.register("no_name", NoNameAdapter())

    @pytest.mark.integration
    def test_model_registry_get_missing_key(self):
        """Prove model registry raises KeyError for unregistered name."""
        registry = ModelRegistry()
        with pytest.raises(KeyError, match="No item registered with name"):
            registry.get("nonexistent")

    @pytest.mark.integration
    def test_model_registry_rejects_non_callable_generate(self):
        """Prove model registry rejects adapters without callable generate."""
        registry = ModelRegistry()

        class BadAdapter:
            name = "bad"

            async def generate(self, prompt: str) -> str:
                return prompt

        # This should pass - generate is callable
        registry.register("good", BadAdapter())

        class WorseAdapter:
            name = "worse"
            generate = "not callable"  # type: ignore

        with pytest.raises(ValueError, match="callable"):
            registry.register("worse", WorseAdapter())

    @pytest.mark.integration
    def test_fake_model_adapter_generate_returns_canned_response(self):
        """Prove fake model adapter returns a canned response."""
        import asyncio

        adapter = FakeModelAdapter()
        response = asyncio.run(adapter.generate("test prompt"))
        assert isinstance(response, str)
        assert "test prompt" in response
        assert response.startswith("[FAKE]") or response.startswith("Fake response")


class TestToolRegistry:
    """Test tool registry with fake tool."""

    @pytest.mark.integration
    def test_fake_tool_has_name(self):
        """Prove fake tool has required name attribute."""
        tool = FakeTool()
        assert hasattr(tool, "name")
        assert tool.name == "fake_tool"

    @pytest.mark.integration
    def test_fake_tool_has_execute(self):
        """Prove fake tool has required execute method."""
        tool = FakeTool()
        assert hasattr(tool, "execute")
        assert callable(tool.execute)

    @pytest.mark.integration
    def test_tool_registry_register(self):
        """Prove tool registry can register tool."""
        registry = ToolRegistry()
        tool = FakeTool()
        registry.register("test", tool)
        assert registry.is_registered("test")

    @pytest.mark.integration
    def test_default_tool_registry_has_fake(self):
        """Prove default tool registry can be populated with fake tool."""
        registry = get_tool_registry()
        registry.register_defaults()
        assert registry.is_registered("fake_tool")

    @pytest.mark.integration
    def test_tool_registry_rejects_duplicate(self):
        """Prove tool registry rejects duplicate registrations."""
        registry = ToolRegistry()
        tool = FakeTool()
        registry.register("test", tool)
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            registry.register("test", tool)

    @pytest.mark.integration
    def test_tool_registry_rejects_tool_without_name(self):
        """Prove tool registry rejects tools without a 'name' attribute."""
        registry = ToolRegistry()

        class NoNameTool:
            async def execute(self, **kwargs):
                pass

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            registry.register("no_name", NoNameTool())

    @pytest.mark.integration
    def test_tool_registry_get_missing_key(self):
        """Prove tool registry raises KeyError for unregistered name."""
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="No item registered with name"):
            registry.get("nonexistent")

    @pytest.mark.integration
    def test_tool_registry_rejects_non_callable_execute(self):
        """Prove tool registry rejects tools without callable execute."""
        registry = ToolRegistry()

        class BadTool:
            name = "bad"

            async def execute(self, **kwargs):
                pass

        # This should pass - execute is callable
        registry.register("good", BadTool())

        class WorseTool:
            name = "worse"
            execute = "not callable"  # type: ignore

        with pytest.raises(ValueError, match="callable"):
            registry.register("worse", WorseTool())


class TestFakeChannelHandleMessageViaRegistry:
    """Prove fake channel handle_message body executes via registry."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_message_via_registry(self):
        """Retrieve fake channel from registry and call handle_message."""
        registry = get_channel_registry()
        registry.register_defaults()
        adapter = registry.get("fake")
        message = {"id": "msg-123", "content": "hello"}
        result = await adapter.handle_message(message)
        assert result["status"] == "fake_processed"
        assert result["message_id"] == "msg-123"
        assert result["channel"] == "fake"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_message_default_id(self):
        """handle_message uses 'unknown' when message has no id."""
        registry = get_channel_registry()
        registry.register_defaults()
        adapter = registry.get("fake")
        result = await adapter.handle_message({"content": "no-id"})
        assert result["message_id"] == "unknown"
        assert result["channel"] == "fake"


class TestFakeToolExecuteViaRegistry:
    """Prove fake tool execute body executes via registry."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_via_registry(self):
        """Retrieve fake tool from registry and call execute."""
        registry = get_tool_registry()
        registry.register_defaults()
        tool = registry.get("fake_tool")
        result = await tool.execute(arg1="val1", arg2=42)
        assert result["status"] == "fake_executed"
        assert result["tool"] == "fake_tool"
        assert result["input"] == {"arg1": "val1", "arg2": 42}

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_empty_kwargs(self):
        """execute works with no kwargs."""
        registry = get_tool_registry()
        registry.register_defaults()
        tool = registry.get("fake_tool")
        result = await tool.execute()
        assert result["status"] == "fake_executed"
        assert result["tool"] == "fake_tool"
        assert result["input"] == {}


class TestFakeModelGenerateViaRegistry:
    """Prove fake model generate body executes via registry."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_via_registry(self):
        """Retrieve fake model from registry and call generate."""
        registry = get_model_registry()
        registry.register_defaults()
        adapter = registry.get("fake")
        result = await adapter.generate("Hello world")
        assert result.startswith("Fake response to: Hello world...")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_generate_long_prompt_truncated(self):
        """generate truncates prompt at 50 chars in output."""
        registry = get_model_registry()
        registry.register_defaults()
        adapter = registry.get("fake")
        long_prompt = "A" * 100
        result = await adapter.generate(long_prompt)
        assert result == "Fake response to: " + "A" * 50 + "..."
