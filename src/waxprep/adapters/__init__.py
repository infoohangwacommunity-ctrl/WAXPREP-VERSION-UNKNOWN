"""
Adapters - Stage 02
FAKE adapters only to prove registry architecture works.
NO real implementations. NO WhatsApp. NO Telegram. NO AI providers.
"""

from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.adapters.fake_model import FakeModelAdapter
from waxprep.adapters.fake_tool import FakeTool

__all__ = ["FakeChannelAdapter", "FakeModelAdapter", "FakeTool"]
