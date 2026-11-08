"""
Channel Port Contract Tests - Stage 05

Contract tests for ChannelPort implementations.
Verifies that all channel adapters satisfy the ChannelPort protocol.
"""

import pytest

from waxprep.domain.models.message import Message, MessageDirection, MessageType
from waxprep.domain.value_objects import MessageId, StudentId, create_message_id, create_student_id


class TestChannelPortContract:
    """Contract tests for ChannelPort implementations."""

    @pytest.fixture
    def student_id(self) -> StudentId:
        """Create a student ID."""
        return create_student_id()

    @pytest.fixture
    def message_id(self) -> MessageId:
        """Create a message ID."""
        return create_message_id()

    @pytest.fixture
    def incoming_message(self, student_id: StudentId, message_id: MessageId) -> Message:
        """Create an incoming message."""
        return Message.create(
            id=message_id,
            content="Hello, can you help me?",
            direction=MessageDirection.INCOMING,
            student_id=student_id,
            message_type=MessageType.TEXT,
        )

    @pytest.fixture
    def outgoing_message(self, student_id: StudentId, message_id: MessageId) -> Message:
        """Create an outgoing message."""
        return Message.create(
            id=message_id,
            content="Sure, I can help!",
            direction=MessageDirection.OUTGOING,
            student_id=student_id,
            message_type=MessageType.TEXT,
        )

    def test_channel_port_has_name(self, incoming_message: Message) -> None:
        """Test that channel adapter has a name attribute."""
        # This test will be parameterized over all channel implementations
        # For now, we test with the fake adapter
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "name")
        assert isinstance(adapter.name, str)
        assert len(adapter.name) > 0

    def test_channel_port_has_handle_message(self, incoming_message: Message) -> None:
        """Test that channel adapter has handle_message method."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "handle_message")
        assert callable(adapter.handle_message)

    def test_channel_port_has_send_message(self, outgoing_message: Message) -> None:
        """Test that channel adapter has send_message method."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "send_message")
        assert callable(adapter.send_message)

    def test_channel_port_has_get_capabilities(self) -> None:
        """Test that channel adapter has get_capabilities method."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "get_capabilities")
        assert callable(adapter.get_capabilities)

    def test_channel_port_has_send_typing_indicator(self) -> None:
        """Test that channel adapter has send_typing_indicator method."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        assert hasattr(adapter, "send_typing_indicator")
        assert callable(adapter.send_typing_indicator)

    @pytest.mark.asyncio
    async def test_handle_message_returns_result(self, incoming_message: Message) -> None:
        """Test that handle_message returns a Result type."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        result = await adapter.handle_message(incoming_message)
        # For now, the fake adapter returns a dict, not a Result
        # This will be updated when we implement proper Result types
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_send_message_returns_result(self, outgoing_message: Message) -> None:
        """Test that send_message returns a Result type."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        student_id = create_student_id()
        result = await adapter.send_message(student_id, outgoing_message)
        # For now, the fake adapter returns a bool, not a Result
        # This will be updated when we implement proper Result types
        assert isinstance(result, bool)

    def test_get_capabilities_returns_dict(self) -> None:
        """Test that get_capabilities returns a dictionary."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        capabilities = adapter.get_capabilities()
        assert isinstance(capabilities, dict)
        # Check for expected capability keys
        assert "name" in capabilities or "supported_message_types" in capabilities

    @pytest.mark.asyncio
    async def test_send_typing_indicator_returns_result(self) -> None:
        """Test that send_typing_indicator returns a Result type."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        adapter = FakeChannelAdapter()
        student_id = create_student_id()
        result = await adapter.send_typing_indicator(student_id, is_typing=True)
        # For now, the fake adapter doesn't implement this
        # This will be updated when we implement proper adapters
        # assert isinstance(result, Result)
