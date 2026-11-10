"""
AST Analyzer for WaxPrep Architectural Enforcement

This module provides AST-based structural analysis to detect hardcoded
educational patterns in Python code without executing it.

Part of Layer 1: AST-Based Structural Analysis
"""

from .analyzer import ASTAnalyzer
from .rules import (
    HardcodedStringsRule,
    HiddenDictionaryRule,
    HardcodedResponseRule,
    EducationalConditionalRule,
)

__all__ = [
    "ASTAnalyzer",
    "HardcodedStringsRule",
    "HiddenDictionaryRule",
    "HardcodedResponseRule",
    "EducationalConditionalRule",
]
