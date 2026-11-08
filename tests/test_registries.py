"""
Test Registries - Stage 02
Prove registries work with fake adapters.
"""

from waxprep.registries.channel import ChannelRegistry, FakeChannelAdapter, get_channel_registry
from waxprep.registries.model import FakeModelAdapter, ModelRegistry, get_model_registry
from waxprep.registries.tool import FakeTool, ToolRegistry, get_tool_registry


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
        """Prove default channel registry has fake adapter."""
        registry = get_channel_registry()
        assert registry.is_registered("fake")


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
        """Prove default model registry has fake adapter."""
        registry = get_model_registry()
        assert registry.is_registered("fake")


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
        """Prove default tool registry has fake tool."""
        registry = get_tool_registry()
        assert registry.is_registered("fake_tool")
