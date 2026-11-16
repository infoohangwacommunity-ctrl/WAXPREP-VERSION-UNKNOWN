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

    def test_fake_adapter_has_name(self):
        """Prove fake adapter has required name attribute."""
        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "name")
        assert adapter.name == "fake"

    def test_fake_adapter_has_handle_message(self):
        """Prove fake adapter has required handle_message method."""
        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "handle_message")
        assert callable(adapter.handle_message)

    def test_channel_registry_register(self):
        """Prove channel registry can register adapter."""
        registry = ChannelRegistry()
        adapter = FakeChannelAdapter()
        registry.register("test", adapter)
        assert registry.is_registered("test")

    def test_channel_registry_get(self):
        """Prove channel registry can retrieve adapter."""
        registry = ChannelRegistry()
        adapter = FakeChannelAdapter()
        registry.register("test", adapter)
        retrieved = registry.get("test")
        assert retrieved is adapter

    def test_channel_registry_list_all(self):
        """Prove channel registry can list all adapters."""
        registry = ChannelRegistry()
        registry.register("test1", FakeChannelAdapter())
        registry.register("test2", FakeChannelAdapter())
        assert "test1" in registry.list_all()
        assert "test2" in registry.list_all()

    def test_default_channel_registry_has_fake(self):
        """Prove default channel registry can be populated with fake adapter."""
        registry = get_channel_registry()
        registry.register_defaults()
        assert registry.is_registered("fake")

    def test_channel_registry_rejects_duplicate(self):
        """Prove channel registry rejects duplicate registrations."""
        registry = ChannelRegistry()
        adapter = FakeChannelAdapter()
        registry.register("test", adapter)
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            registry.register("test", adapter)

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

    def test_fake_adapter_has_name(self):
        """Prove fake adapter has required name attribute."""
        adapter = FakeModelAdapter()
        assert hasattr(adapter, "name")
        assert adapter.name == "fake"

    def test_fake_adapter_has_generate(self):
        """Prove fake adapter has required generate method."""
        adapter = FakeModelAdapter()
        assert hasattr(adapter, "generate")
        assert callable(adapter.generate)

    def test_model_registry_register(self):
        """Prove model registry can register adapter."""
        registry = ModelRegistry()
        adapter = FakeModelAdapter()
        registry.register("test", adapter)
        assert registry.is_registered("test")

    def test_default_model_registry_has_fake(self):
        """Prove default model registry can be populated with fake adapter."""
        registry = get_model_registry()
        registry.register_defaults()
        assert registry.is_registered("fake")

    def test_model_registry_rejects_duplicate(self):
        """Prove model registry rejects duplicate registrations."""
        registry = ModelRegistry()
        adapter = FakeModelAdapter()
        registry.register("test", adapter)
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            registry.register("test", adapter)

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


class TestToolRegistry:
    """Test tool registry with fake tool."""

    def test_fake_tool_has_name(self):
        """Prove fake tool has required name attribute."""
        tool = FakeTool()
        assert hasattr(tool, "name")
        assert tool.name == "fake_tool"

    def test_fake_tool_has_execute(self):
        """Prove fake tool has required execute method."""
        tool = FakeTool()
        assert hasattr(tool, "execute")
        assert callable(tool.execute)

    def test_tool_registry_register(self):
        """Prove tool registry can register tool."""
        registry = ToolRegistry()
        tool = FakeTool()
        registry.register("test", tool)
        assert registry.is_registered("test")

    def test_default_tool_registry_has_fake(self):
        """Prove default tool registry can be populated with fake tool."""
        registry = get_tool_registry()
        registry.register_defaults()
        assert registry.is_registered("fake_tool")

    def test_tool_registry_rejects_duplicate(self):
        """Prove tool registry rejects duplicate registrations."""
        registry = ToolRegistry()
        tool = FakeTool()
        registry.register("test", tool)
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            registry.register("test", tool)

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
