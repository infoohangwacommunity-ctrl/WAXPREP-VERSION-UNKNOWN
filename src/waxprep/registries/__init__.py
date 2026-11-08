"""
Registry System - Stage 02
Empty registries with fake adapters to prove architecture works.
NO real adapters. NO channel implementations. NO model implementations.
"""

from waxprep.registries.base import BaseRegistry
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry

__all__ = ["BaseRegistry", "ChannelRegistry", "ModelRegistry", "ToolRegistry"]
