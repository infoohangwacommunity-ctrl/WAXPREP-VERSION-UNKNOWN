"""
Ports Package - Stage 03

Contains all port interfaces for Hexagonal Architecture.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.

Ports define the contracts that adapters must implement.
"""

from waxprep.application.ports.channel import ChannelPort
from waxprep.application.ports.model import ModelPort
from waxprep.application.ports.tool import ToolPort

__all__ = [
    "ChannelPort",
    "ModelPort",
    "ToolPort",
]
