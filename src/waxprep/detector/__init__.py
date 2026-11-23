# Universal Hardcoding Detection System
#
# Stage 08 — Independent, deterministic source-code detection system
# that identifies prohibited hardcoded conversational behavior.
#
# This detector investigates HOW source code makes decisions about
# student messages, not just what words appear in the code.
"""Universal Hardcoding Detection System — Stage 08."""

from __future__ import annotations

import ast

# Constant is available in Python 3.8+ but was moved in 3.14
# For compatibility, we use the appropriate import
import ast as _ast
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

Constant = _ast.Constant

# =============================================================================
# Severity levels
# =============================================================================


class Severity(StrEnum):
    """Detection severity levels."""

    HIGH = "HIGH"  # Blocking — strong evidence of prohibited behavior
    MEDIUM = "MEDIUM"  # Review required — suspicious but inconclusive
    LOW = "LOW"  # Informational — potential architectural drift


# =============================================================================
# Finding representation
# =============================================================================


@dataclass
class Finding:
    """A single detection finding with evidence and metadata."""

    rule_id: str
    file_path: str
    line_number: int
    message: str
    severity: Severity
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    is_deterministic: bool = True
    blocks_merge: bool = False

    def to_dict(self) -> dict[str, object]:
        """Serialize finding to dictionary."""
        return {
            "rule_id": self.rule_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "message": self.message,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "is_deterministic": self.is_deterministic,
            "blocks_merge": self.blocks_merge,
        }


# =============================================================================
# Architectural boundaries
# =============================================================================

# Protected modules where hardcoded conversational behavior is prohibited
PROTECTED_MODULES: frozenset[str] = frozenset({
    "waxprep.messaging",
    "waxprep.context",
    "waxprep.services",
})

# Allowed modules where fixed values are legitimate
ALLOWED_MODULES: frozenset[str] = frozenset({
    "waxprep.core",
    "waxprep.config",
    "waxprep.id",
    "waxprep.registries",
    "waxprep.adapters",
    "waxprep.middleware",
    "waxprep.main",
})


def is_protected_module(module_path: str) -> bool:
    """Check if a module is in the protected zone."""
    path = module_path.replace("/", ".")
    for protected in PROTECTED_MODULES:
        if path.startswith(protected) or path == protected:
            return True
    return False


def is_allowed_module(module_path: str) -> bool:
    """Check if a module is in the allowed zone."""
    path = module_path.replace("/", ".")
    for allowed in ALLOWED_MODULES:
        if path.startswith(allowed) or path == allowed:
            return True
    return False


# =============================================================================
# Core detector class
# =============================================================================


class UniversalHardcodingDetector:
    """
    Deterministic source-code detector for prohibited hardcoded
    conversational behavior.

    This detector uses Python AST analysis to identify:
    - Fixed-string comparisons against input
    - Keyword-based branching
    - Hidden dictionaries and vocabularies
    - Fixed response selection
    - Subject/intent classification using predefined text mappings
    - Hardcoded conversation flows
    - Word-to-action mappings
    """

    def __init__(self, root_path: str | Path = "."):
        self.root_path = Path(root_path)
        self.findings: list[Finding] = []
        self._visited_files: set[str] = set()

    def scan_file(self, file_path: Path) -> list[Finding]:
        """Scan a single Python file for prohibited patterns."""
        if not file_path.suffix == ".py":
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return []

        findings: list[Finding] = []
        module_path = self._get_module_path(file_path)

        # Run all detection rules
        findings.extend(self._detect_fixed_string_comparisons(tree, source, file_path, module_path))
        findings.extend(self._detect_membership_tests(tree, source, file_path, module_path))
        findings.extend(self._detect_if_elif_chains(tree, source, file_path, module_path))
        findings.extend(self._detect_regex_matching(tree, source, file_path, module_path))
        findings.extend(self._detect_dictionary_lookups(tree, source, file_path, module_path))
        findings.extend(self._detect_nested_conditions(tree, source, file_path, module_path))
        findings.extend(self._detect_literal_responses(tree, source, file_path, module_path))
        findings.extend(self._detect_hardcoded_vocabularies(tree, source, file_path, module_path))

        self.findings.extend(findings)
        return findings

    def scan_directory(self, directory: str | Path = ".") -> list[Finding]:
        """Scan all Python files in a directory."""
        self.findings = []
        self._visited_files = set()

        root = Path(directory)
        for py_file in root.rglob("*.py"):
            # Skip test files and cached bytecode
            if "__pycache__" in str(py_file):
                continue
            # Skip files with test_ prefix in their stem (filename without extension)
            # but not files that just happen to contain "test" in the path
            if py_file.stem.startswith("test_"):
                # Test files may contain intentional patterns for testing
                continue

            self.scan_file(py_file)

        return self.findings

    def scan_project(self) -> list[Finding]:
        """Scan the entire project from the configured root."""
        return self.scan_directory(self.root_path)

    def get_report(self) -> dict[str, object]:
        """Generate a structured detection report."""
        high_risk = [f for f in self.findings if f.severity == Severity.HIGH]
        medium_risk = [f for f in self.findings if f.severity == Severity.MEDIUM]
        low_risk = [f for f in self.findings if f.severity == Severity.LOW]

        blocking = [f for f in high_risk if f.blocks_merge]

        return {
            "total_findings": len(self.findings),
            "high_risk": len(high_risk),
            "medium_risk": len(medium_risk),
            "low_risk": len(low_risk),
            "blocking_findings": len(blocking),
            "findings": [f.to_dict() for f in self.findings],
            "rules_triggered": sorted({f.rule_id for f in self.findings}),
        }

    def has_blocking_findings(self) -> bool:
        """Check if there are any findings that block merge."""
        return any(f.blocks_merge for f in self.findings)

    def _get_module_path(self, file_path: Path) -> str:
        """Convert file path to module path."""
        try:
            rel_path = file_path.relative_to(self.root_path)
            module = str(rel_path).replace("/", ".").replace(".py", "")
            if module.startswith("src."):
                module = module[4:]
            return module
        except ValueError:
            return str(file_path)

    # =========================================================================
    # Detection Rules
    # =========================================================================

    def _detect_fixed_string_comparisons(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-001: Detect student-input-dependent comparisons against
        fixed literal values in protected modules.
        """
        findings: list[Finding] = []
        lines = source.splitlines()

        class ComparisonVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.Comparisons: list[tuple[ast.expr, ast.Constant]] = []

            def visit_Compare(self, node: ast.Compare) -> None:
                # Look for comparisons where left side might be input
                # and comparator is == or != with a string constant
                if len(node.ops) == 1:
                    op = node.ops[0]
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        for comparator in node.comparators:
                            if isinstance(comparator, Constant) and isinstance(
                                comparator.value, str
                            ):
                                # Check if left side looks like input
                                left = node.left
                                if self._looks_like_input(left):
                                    self.Comparisons.append((left, comparator))

                self.generic_visit(node)

            def _looks_like_input(self, node: ast.expr) -> bool:
                """Heuristic: does this expression look like student input?"""
                # Direct variable names that suggest input
                if isinstance(node, ast.Name):
                    name = node.id.lower()
                    input_indicators = {
                        "message",
                        "text",
                        "content",
                        "input",
                        "student_message",
                        "user_message",
                        "query",
                        "prompt",
                        "body",
                        "data",
                        "payload",
                    }
                    return name in input_indicators or any(
                        indicator in name for indicator in input_indicators
                    )

                # Function calls that might return input
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id.lower()
                        return any(
                            indicator in func_name
                            for indicator in ["get_message", "receive", "read"]
                        )

                return False

        visitor = ComparisonVisitor()
        visitor.visit(tree)

        for left, constant in visitor.Comparisons:
            line_no = left.lineno if hasattr(left, "lineno") else constant.lineno
            lines[line_no - 1].strip() if line_no else ""

            finding = Finding(
                rule_id="WHD-001",
                file_path=str(file_path),
                line_number=line_no,
                message=(
                    "Student-input-dependent comparison against fixed literal in protected module"
                ),
                severity=Severity.HIGH,
                confidence=0.85,
                evidence=[
                    f"Comparison found at line {line_no}",
                    f"Fixed literal: {constant.value!r}",
                    f"Module: {module_path}",
                    f"Protected module: {is_protected_module(module_path)}",
                ],
                blocks_merge=is_protected_module(module_path),
            )
            findings.append(finding)

        return findings

    def _detect_membership_tests(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-002: Detect membership tests (in/not in) against
        fixed vocabularies in protected modules.
        """
        findings: list[Finding] = []
        source.splitlines()

        # First pass: collect all string list/set/tuple assignments
        string_collections: dict[str, ast.List | ast.Set | ast.Tuple] = {}

        class CollectionCollector(ast.NodeVisitor):
            def visit_Assign(self, node: ast.Assign) -> None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, (ast.List, ast.Set, ast.Tuple)):
                            if self._collection_contains_strings(node.value):
                                string_collections[target.id] = node.value
                self.generic_visit(node)

            def _collection_contains_strings(self, node: ast.List | ast.Set | ast.Tuple) -> bool:
                """Check if collection contains string literals."""
                for elt in node.elts:
                    if isinstance(elt, Constant) and isinstance(elt.value, str):
                        return True
                    if isinstance(elt, (ast.List, ast.Set, ast.Tuple)):
                        if self._collection_contains_strings(elt):
                            return True
                return False

        CollectionCollector().visit(tree)

        class MembershipVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.memberships: list[
                    tuple[ast.expr, ast.List | ast.Set | ast.Tuple | ast.Name]
                ] = []

            def visit_Compare(self, node: ast.Compare) -> None:
                for op in node.ops:
                    if isinstance(op, (ast.In, ast.NotIn)):
                        # Check if left side looks like input
                        if self._looks_like_input(node.left):
                            comp = node.comparators[0]
                            # Check if right side is a literal collection
                            if isinstance(comp, (ast.List, ast.Set, ast.Tuple)):
                                if self._collection_contains_strings(comp):
                                    self.memberships.append((node.left, comp))
                            # Check if right side is a name that was assigned a string collection
                            elif isinstance(comp, ast.Name) and comp.id in string_collections:
                                self.memberships.append((node.left, comp))

                self.generic_visit(node)

            def _looks_like_input(self, node: ast.expr) -> bool:
                """Check if node represents student input."""
                if isinstance(node, ast.Name):
                    name = node.id.lower()
                    input_indicators = {
                        "message",
                        "text",
                        "content",
                        "input",
                        "student_message",
                        "user_message",
                        "query",
                        "prompt",
                        "body",
                        "data",
                        "payload",
                    }
                    return name in input_indicators or any(
                        indicator in name for indicator in input_indicators
                    )
                return False

            def _collection_contains_strings(self, node: ast.List | ast.Set | ast.Tuple) -> bool:
                """Check if collection contains string literals."""
                for elt in node.elts:
                    if isinstance(elt, Constant) and isinstance(elt.value, str):
                        return True
                    if isinstance(elt, (ast.List, ast.Set, ast.Tuple)):
                        if self._collection_contains_strings(elt):
                            return True
                return False

        visitor = MembershipVisitor()
        visitor.visit(tree)

        for left, collection in visitor.memberships:
            line_no = left.lineno if hasattr(left, "lineno") else 0

            # Extract the strings in the collection
            strings = []
            if isinstance(collection, (ast.List, ast.Set, ast.Tuple)):
                # Literal collection
                for elt in collection.elts:
                    if isinstance(elt, Constant) and isinstance(elt.value, str):
                        strings.append(elt.value)
                if hasattr(collection, "lineno"):
                    line_no = collection.lineno
            elif isinstance(collection, ast.Name):
                # Named variable - get strings from our earlier collection
                if collection.id in string_collections:
                    coll = string_collections[collection.id]
                    for elt in coll.elts:
                        if isinstance(elt, Constant) and isinstance(elt.value, str):
                            strings.append(elt.value)
                    if hasattr(coll, "lineno"):
                        line_no = coll.lineno

            finding = Finding(
                rule_id="WHD-002",
                file_path=str(file_path),
                line_number=line_no if line_no else 1,
                message=("Membership test against fixed vocabulary in protected module"),
                severity=Severity.HIGH,
                confidence=0.80,
                evidence=[
                    f"Membership test at line {line_no if line_no else 1}",
                    f"Collection contains {len(strings)} string(s)",
                    f"Sample values: {strings[:5]}",
                    f"Module: {module_path}",
                    f"Protected module: {is_protected_module(module_path)}",
                ],
                blocks_merge=is_protected_module(module_path),
            )
            findings.append(finding)

        return findings

    def _detect_if_elif_chains(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-003: Detect if/elif chains that create fixed decision trees
        based on string comparisons in protected modules.
        """
        findings: list[Finding] = []
        source.splitlines()

        class IfChainVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.chains: list[tuple[ast.If, int]] = []

            def visit_If(self, node: ast.If) -> None:
                # Count string comparisons in this if and its elifs
                chain_length = 1
                string_comparisons = self._count_string_comparisons(node.test)

                # Walk through elif chain
                current = node
                while hasattr(current, "orelse") and current.orelse:
                    next_if = current.orelse[0]
                    if isinstance(next_if, ast.If):
                        chain_length += 1
                        string_comparisons += self._count_string_comparisons(next_if.test)
                        current = next_if
                    else:
                        break

                # Flag chains with 3+ string comparisons
                if chain_length >= 3 and string_comparisons >= 2:
                    self.chains.append((node, chain_length))

                self.generic_visit(node)

            def _count_string_comparisons(self, test: ast.expr) -> int:
                """Count string literal comparisons in a test expression."""

                class StringCompareCounter(ast.NodeVisitor):
                    def __init__(self) -> None:
                        self.count = 0

                    def visit_Compare(self, node: ast.Compare) -> None:
                        for op in node.ops:
                            if isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                                for comp in node.comparators:
                                    if isinstance(comp, Constant) and isinstance(comp.value, str):
                                        self.count += 1
                        self.generic_visit(node)

                counter = StringCompareCounter()
                counter.visit(test)
                return counter.count

        visitor = IfChainVisitor()
        visitor.visit(tree)

        for if_node, chain_length in visitor.chains:
            finding = Finding(
                rule_id="WHD-003",
                file_path=str(file_path),
                line_number=if_node.lineno,
                message=(
                    f"Fixed decision tree (if/elif chain with {chain_length} branches) "
                    f"in protected module"
                ),
                severity=Severity.MEDIUM,
                confidence=0.70,
                evidence=[
                    f"If/elif chain with {chain_length} branches at line {if_node.lineno}",
                    "Multiple string comparisons detected",
                    f"Module: {module_path}",
                    f"Protected module: {is_protected_module(module_path)}",
                ],
                blocks_merge=is_protected_module(module_path),
            )
            findings.append(finding)

        return findings

    def _detect_regex_matching(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-004: Detect regex-based pattern matching that could be
        used for hidden phrase detection in protected modules.
        """
        findings: list[Finding] = []
        source.splitlines()

        # First pass: collect regex pattern assignments
        regex_patterns: dict[str, str] = {}

        class PatternCollector(ast.NodeVisitor):
            def visit_Assign(self, node: ast.Assign) -> None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, Constant) and isinstance(node.value.value, str):
                            # Check if this looks like a regex pattern
                            val = node.value.value
                            # Check for word boundary patterns (\b in raw string becomes \x08)
                            # or patterns containing regex-like syntax
                            has_word_boundary = "\x08" in val  # backspace char from \b in raw string
                            has_regex_syntax = len(val) > 5 and ("(" in val or "[" in val)
                            if has_word_boundary or has_regex_syntax:
                                regex_patterns[target.id] = val
                self.generic_visit(node)

        PatternCollector().visit(tree)

        class RegexVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.regex_usages: list[
                    tuple[ast.Call, str, bool]
                ] = []  # (call, pattern, is_variable)

            def visit_Call(self, node: ast.Call) -> None:
                # Look for re.match, re.search, re.findall, re.fullmatch
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("match", "search", "findall", "fullmatch", "finditer"):
                        if isinstance(node.func.value, ast.Name):
                            if node.func.value.id == "re":
                                # Extract the pattern - could be literal or variable
                                pattern = None

                                if node.args and isinstance(node.args[0], Constant):
                                    pattern = node.args[0].value
                                    if isinstance(pattern, str):
                                        self.regex_usages.append((node, pattern, False))
                                elif node.args and isinstance(node.args[0], ast.Name):
                                    # Could be a variable holding a pattern
                                    var_name = node.args[0].id
                                    if var_name in regex_patterns:
                                        pattern = regex_patterns[var_name]
                                        self.regex_usages.append((node, pattern, True))

                self.generic_visit(node)

        visitor = RegexVisitor()
        visitor.visit(tree)

        for call_node, pattern, is_variable in visitor.regex_usages:
            # Check if pattern looks like it could match conversational content
            # Flag patterns with word boundaries or longer patterns only
            # Do NOT use keyword matching - this creates vocabulary dependency
            is_suspicious = (
                "\x08" in pattern  # word boundaries (backspace char from \b in raw string)
                or len(pattern) > 10  # longer patterns
            )

            if is_suspicious and is_protected_module(module_path):
                finding = Finding(
                    rule_id="WHD-004",
                    file_path=str(file_path),
                    line_number=call_node.lineno,
                    message=("Regex pattern matching that may detect phrases in protected module"),
                    severity=Severity.MEDIUM,
                    confidence=0.65,
                    evidence=[
                        f"Regex pattern at line {call_node.lineno}",
                        f"Pattern: {pattern!r}",
                        f"Pattern source: {'variable' if is_variable else 'literal'}",
                        f"Module: {module_path}",
                        f"Protected module: {is_protected_module(module_path)}",
                    ],
                    blocks_merge=False,  # Requires human review
                )
                findings.append(finding)

        return findings

    def _detect_dictionary_lookups(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-005: Detect dictionary lookups where keys are strings
        and values may represent actions/responses in protected modules.
        """
        findings: list[Finding] = []
        source.splitlines()

        class DictLookupVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.lookups: list[tuple[ast.Subscript, ast.Name]] = []

            def visit_Subscript(self, node: ast.Subscript) -> None:
                # Check if this is a dictionary subscript with string key
                if isinstance(node.value, ast.Name):
                    # Could be a variable name suggesting a mapping
                    name = node.value.id.lower()
                    if any(
                        indicator in name
                        for indicator in [
                            "mapping",
                            "response",
                            "action",
                            "template",
                            "reply",
                            "message_map",
                            "vocab",
                            "phrase_map",
                        ]
                    ):
                        if isinstance(node.slice, Constant) and isinstance(node.slice.value, str):
                            # Try to find the dictionary definition
                            # This is a simplified check; full data-flow would be needed
                            self.lookups.append((node, node.value))

                self.generic_visit(node)

        visitor = DictLookupVisitor()
        visitor.visit(tree)

        for subscript_node, dict_name in visitor.lookups:
            dict_var_name = dict_name.id if hasattr(dict_name, "id") else "unknown"
            finding = Finding(
                rule_id="WHD-005",
                file_path=str(file_path),
                line_number=subscript_node.lineno,
                message=(
                    "String-keyed dictionary lookup that may represent "
                    "word-to-action mapping in protected module"
                ),
                severity=Severity.MEDIUM,
                confidence=0.60,
                evidence=[
                    f"Dictionary lookup at line {subscript_node.lineno}",
                    f"Dictionary variable: {dict_var_name}",
                    "Key type: string literal",
                    f"Module: {module_path}",
                    f"Protected module: {is_protected_module(module_path)}",
                ],
                blocks_merge=is_protected_module(module_path),
            )
            findings.append(finding)

        return findings

    def _detect_nested_conditions(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-006: Detect deeply nested conditional structures that
        may represent hidden routing logic in protected modules.
        """
        findings: list[Finding] = []

        class NestingVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.nested_structures: list[tuple[int, int, int]] = []  # (line, depth, bodies)

            def visit_If(self, node: ast.If) -> None:
                depth = self._calculate_nesting_depth(node)
                if depth >= 3:  # 3+ levels of nesting
                    body_count = self._count_inner_bodies(node)
                    self.nested_structures.append((node.lineno, depth, body_count))

                self.generic_visit(node)

            def _calculate_nesting_depth(self, node: ast.If, current: int = 0) -> int:
                """Calculate maximum nesting depth of if statements."""
                max_depth = current
                if hasattr(node, "body"):
                    for stmt in node.body:
                        if isinstance(stmt, ast.If):
                            depth = self._calculate_nesting_depth(stmt, current + 1)
                            max_depth = max(max_depth, depth)
                if hasattr(node, "orelse") and node.orelse:
                    for stmt in node.orelse:
                        if isinstance(stmt, ast.If):
                            depth = self._calculate_nesting_depth(stmt, current + 1)
                            max_depth = max(max_depth, depth)
                return max_depth

            def _count_inner_bodies(self, node: ast.If) -> int:
                """Count inner if statements."""
                count = 0
                for stmt in node.body:
                    if isinstance(stmt, ast.If):
                        count += 1
                        count += self._count_inner_bodies(stmt)
                return count

        visitor = NestingVisitor()
        visitor.visit(tree)

        for line_no, depth, body_count in visitor.nested_structures:
            finding = Finding(
                rule_id="WHD-006",
                file_path=str(file_path),
                line_number=line_no,
                message=(
                    f"Deeply nested conditional structure ({depth} levels, "
                    f"{body_count} inner branches) in protected module"
                ),
                severity=Severity.LOW,
                confidence=0.50,
                evidence=[
                    f"Nesting depth: {depth} levels at line {line_no}",
                    f"Inner branches: {body_count}",
                    f"Module: {module_path}",
                    f"Protected module: {is_protected_module(module_path)}",
                    "This may indicate hidden routing logic",
                ],
                blocks_merge=False,
            )
            findings.append(finding)

        return findings

    def _detect_literal_responses(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-007: Detect functions that return literal string responses
        which may represent predetermined conversational output.
        """
        findings: list[Finding] = []
        source.splitlines()

        class ResponseVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.response_functions: list[tuple[ast.FunctionDef, list[str]]] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                # Look for functions with names suggesting responses
                response_indicators = [
                    "response",
                    "reply",
                    "greeting",
                    "answer",
                    "message",
                    "output",
                    "say",
                    "speak",
                ]

                func_name = node.name.lower()
                if any(indicator in func_name for indicator in response_indicators):
                    # Collect string literals in return statements
                    strings = self._collect_return_strings(node)
                    if strings:
                        self.response_functions.append((node, strings))

                self.generic_visit(node)

            def _collect_return_strings(self, node: ast.FunctionDef) -> list[str]:
                """Collect string literals from return statements."""

                class ReturnStringCollector(ast.NodeVisitor):
                    def __init__(self) -> None:
                        self.strings: list[str] = []

                    def visit_Return(self, node: ast.Return) -> None:
                        if node.value:
                            self._extract_strings(node.value)
                        self.generic_visit(node)

                    def _extract_strings(self, node: ast.expr) -> None:
                        if isinstance(node, Constant) and isinstance(node.value, str):
                            self.strings.append(node.value)
                        elif isinstance(node, ast.List):
                            for elt in node.elts:
                                self._extract_strings(elt)
                        elif isinstance(node, ast.Tuple):
                            for elt in node.elts:
                                self._extract_strings(elt)

                collector = ReturnStringCollector()
                collector.visit(node)
                return collector.strings

        visitor = ResponseVisitor()
        visitor.visit(tree)

        for func_node, strings in visitor.response_functions:
            if is_protected_module(module_path):
                finding = Finding(
                    rule_id="WHD-007",
                    file_path=str(file_path),
                    line_number=func_node.lineno,
                    message=(
                        "Function returns predetermined string response(s) in protected module"
                    ),
                    severity=Severity.MEDIUM,
                    confidence=0.65,
                    evidence=[
                        f"Function: {func_node.name} at line {func_node.lineno}",
                        f"Returns {len(strings)} string literal(s)",
                        f"Sample: {strings[:3]}",
                        f"Module: {module_path}",
                        f"Protected module: {is_protected_module(module_path)}",
                    ],
                    blocks_merge=is_protected_module(module_path),
                )
                findings.append(finding)

        return findings

    def _detect_hardcoded_vocabularies(
        self,
        tree: ast.AST,
        source: str,
        file_path: Path,
        module_path: str,
    ) -> list[Finding]:
        """
        WHD-008: Detect hardcoded vocabularies (lists/sets of strings)
        that may be used for classification or decision-making.
        """
        findings: list[Finding] = []
        source.splitlines()

        class VocabularyVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.vocabularies: list[tuple[ast.AST, list[str], str]] = []

            def visit_Assign(self, node: ast.Assign) -> None:
                # Look for assignments of lists/sets of strings
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id.lower()
                        # Check variable name for vocabulary indicators
                        vocab_indicators = [
                            "words",
                            "phrases",
                            "vocabulary",
                            "terms",
                            "keywords",
                            "topics",
                            "subjects",
                            "greetings",
                            "responses",
                            "replies",
                            "messages",
                            "inputs",
                        ]

                        if any(indicator in name for indicator in vocab_indicators):
                            if isinstance(node.value, (ast.List, ast.Set, ast.Tuple)):
                                strings = self._extract_strings(node.value)
                                if strings and len(strings) >= 2:
                                    self.vocabularies.append((node.value, strings, name))

                self.generic_visit(node)

            def _extract_strings(self, node: ast.List | ast.Set | ast.Tuple) -> list[str]:
                """Extract string literals from a collection."""
                strings = []
                for elt in node.elts:
                    if isinstance(elt, Constant) and isinstance(elt.value, str):
                        strings.append(elt.value)
                    elif isinstance(elt, (ast.List, ast.Set, ast.Tuple)):
                        strings.extend(self._extract_strings(elt))
                return strings

        visitor = VocabularyVisitor()
        visitor.visit(tree)

        for node, strings, var_name in visitor.vocabularies:
            if is_protected_module(module_path):
                # Vocabulary detected based on variable name and collection structure
                # NOT based on specific words - this avoids vocabulary dependency
                node_lineno = node.lineno if hasattr(node, "lineno") else 1

                finding = Finding(
                    rule_id="WHD-008",
                    file_path=str(file_path),
                    line_number=node_lineno,
                    message=(f"Hardcoded vocabulary ({len(strings)} terms) in protected module"),
                    severity=Severity.MEDIUM,
                    confidence=0.60,
                    evidence=[
                        f"Vocabulary variable: {var_name} at line {node_lineno}",
                        f"Contains {len(strings)} terms",
                        f"Sample: {strings[:5]}",
                        f"Module: {module_path}",
                        f"Protected module: {is_protected_module(module_path)}",
                    ],
                    blocks_merge=is_protected_module(module_path),
                )
                findings.append(finding)

        return findings


# =============================================================================
# Data/configuration file inspector
# =============================================================================


class DataFileInspector:
    """
    Inspects data and configuration files for hidden behavioral content.

    Checks JSON, YAML, TOML, CSV, and other data files for:
    - Vocabulary collections
    - Word-to-action mappings
    - Response templates
    - Classification data
    """

    def __init__(self, root_path: str | Path = "."):
        self.root_path = Path(root_path)
        self.findings: list[Finding] = []

    def inspect_file(self, file_path: Path) -> list[Finding]:
        """Inspect a data/configuration file."""
        findings: list[Finding] = []

        suffix = file_path.suffix.lower()
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        if suffix == ".json":
            findings.extend(self._inspect_json(content, file_path))
        elif suffix == ".yaml" or suffix == ".yml":
            findings.extend(self._inspect_yaml(content, file_path))
        elif suffix == ".toml":
            findings.extend(self._inspect_toml(content, file_path))
        elif suffix == ".csv":
            findings.extend(self._inspect_csv(content, file_path))
        elif suffix == ".md":
            findings.extend(self._inspect_markdown(content, file_path))

        self.findings.extend(findings)
        return findings

    def inspect_directory(self, directory: str | Path = ".") -> list[Finding]:
        """Inspect all data files in a directory."""
        self.findings = []
        root = Path(directory)

        for data_file in root.rglob("*"):
            if data_file.is_file():
                suffix = data_file.suffix.lower()
                if suffix in {".json", ".yaml", ".yml", ".toml", ".csv", ".md"}:
                    if "__pycache__" not in str(data_file):
                        self.inspect_file(data_file)

        return self.findings

    def _inspect_json(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect JSON content for vocabulary/mapping patterns."""
        findings: list[Finding] = []

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []

        # Recursively search for vocabulary patterns
        self._search_for_vocabulary(data, [], findings, file_path)

        return findings

    def _search_for_vocabulary(
        self,
        data: object,
        path: list[str],
        findings: list[Finding],
        file_path: Path,
    ) -> None:
        """Recursively search JSON data for vocabulary patterns."""
        if isinstance(data, dict):
            # Check for mapping patterns (key -> value where both are strings)
            string_keys = [k for k, v in data.items() if isinstance(k, str) and isinstance(v, str)]

            if len(string_keys) >= 3:
                # This could be a word-to-action mapping
                finding = Finding(
                    rule_id="WHD-009",
                    file_path=str(file_path),
                    line_number=1,
                    message=(
                        f"JSON contains {len(string_keys)} string-to-string mappings "
                        f"that may represent word-to-action relationships"
                    ),
                    severity=Severity.MEDIUM,
                    confidence=0.60,
                    evidence=[
                        f"File: {file_path.name}",
                        f"Path in JSON: {'/'.join(path)}",
                        f"Sample mappings: {list(data.items())[:3]}",
                        "May function as hidden behavioral engine",
                    ],
                    blocks_merge=False,
                )
                findings.append(finding)

            # Recurse into nested structures
            for key, value in data.items():
                self._search_for_vocabulary(value, [*path, str(key)], findings, file_path)

        elif isinstance(data, list):
            # Check for lists of strings (vocabulary)
            if all(isinstance(item, str) for item in data) and len(data) >= 5:
                # Check if these look like vocabulary
                sample = data[:5]
                is_vocabulary = any(len(word) > 3 and word.isalpha() for word in sample)

                if is_vocabulary:
                    finding = Finding(
                        rule_id="WHD-010",
                        file_path=str(file_path),
                        line_number=1,
                        message=(f"JSON contains vocabulary list ({len(data)} terms)"),
                        severity=Severity.LOW,
                        confidence=0.50,
                        evidence=[
                            f"File: {file_path.name}",
                            f"Path in JSON: {'/'.join(path)}",
                            f"Sample terms: {sample}",
                        ],
                        blocks_merge=False,
                    )
                    findings.append(finding)

            # Recurse into list items
            for item in data:
                if isinstance(item, (dict, list)):
                    self._search_for_vocabulary(item, path, findings, file_path)

    def _inspect_yaml(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect YAML content for vocabulary patterns."""
        # Simple YAML inspection without full parsing
        findings: list[Finding] = []

        lines = content.splitlines()
        string_pairs = []
        string_list = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("- "):
                item = stripped[2:].strip().strip('"').strip("'")
                if item and not item.startswith("{") and not item.startswith("["):
                    string_list.append(item)
            elif ":" in stripped and not stripped.startswith("-"):
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().strip('"').strip("'")
                    if key and value and not value.startswith("{") and not value.startswith("["):
                        string_pairs.append((key, value))

        # Check for vocabulary list
        if len(string_list) >= 5:
            finding = Finding(
                rule_id="WHD-010",
                file_path=str(file_path),
                line_number=1,
                message=(f"YAML file contains vocabulary list ({len(string_list)} terms)"),
                severity=Severity.LOW,
                confidence=0.50,
                evidence=[
                    f"File: {file_path.name}",
                    f"Sample terms: {string_list[:5]}",
                ],
                blocks_merge=False,
            )
            findings.append(finding)

        # Check for string-to-string mappings
        if len(string_pairs) >= 3:
            finding = Finding(
                rule_id="WHD-009",
                file_path=str(file_path),
                line_number=1,
                message=(f"YAML contains {len(string_pairs)} string-to-string mappings"),
                severity=Severity.MEDIUM,
                confidence=0.60,
                evidence=[
                    f"File: {file_path.name}",
                    f"Sample mappings: {string_pairs[:3]}",
                ],
                blocks_merge=False,
            )
            findings.append(finding)

        return findings

    def _inspect_toml(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect TOML content for vocabulary patterns."""
        # Simple TOML inspection looking for arrays of strings
        findings: list[Finding] = []

        import re

        # Look for arrays of strings
        array_pattern = re.compile(r'\["\s*([^"]+)\s*"(?:\s*,\s*"[^"]+"\s*)*\]')
        matches = array_pattern.findall(content)

        if len(matches) >= 3:
            finding = Finding(
                rule_id="WHD-010",
                file_path=str(file_path),
                line_number=1,
                message=("TOML contains string array that may be vocabulary"),
                severity=Severity.LOW,
                confidence=0.45,
                evidence=[
                    f"File: {file_path.name}",
                    f"Found {len(matches)} string arrays",
                ],
                blocks_merge=False,
            )
            findings.append(finding)

        return findings

    def _inspect_csv(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect CSV content for vocabulary patterns."""
        findings: list[Finding] = []

        import csv
        from io import StringIO

        try:
            reader = csv.reader(StringIO(content))
            rows = list(reader)
        except csv.Error:
            return []

        # Check for vocabulary-like columns
        for row in rows:
            string_cells = [cell for cell in row if isinstance(cell, str) and len(cell) > 2]
            if len(string_cells) >= 5:
                finding = Finding(
                    rule_id="WHD-010",
                    file_path=str(file_path),
                    line_number=1,
                    message=(
                        f"CSV row contains {len(string_cells)} text values "
                        f"that may represent vocabulary"
                    ),
                    severity=Severity.LOW,
                    confidence=0.40,
                    evidence=[
                        f"File: {file_path.name}",
                        f"Sample: {string_cells[:5]}",
                    ],
                    blocks_merge=False,
                )
                findings.append(finding)
                break  # Only report once per file

        return findings

    def _inspect_markdown(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect Markdown for response templates or fixed content."""
        findings: list[Finding] = []

        # Look for response template patterns in markdown
        # e.g., "If student says X, respond with Y"
        import re

        patterns = [
            r'(?:if|when|when\s+a|when\s+the)\s+[a-z]+\s+(?:says?|mentions?|asks?|uses?)\s+["\']([^"\']+)["\']',
            r'respond(?:s|ing)?\s+with\s+["\']([^"\']+)["\']',
            r'template["\s:]+["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                finding = Finding(
                    rule_id="WHD-011",
                    file_path=str(file_path),
                    line_number=1,
                    message=(f"Markdown contains {len(matches)} potential response template(s)"),
                    severity=Severity.LOW,
                    confidence=0.40,
                    evidence=[
                        f"File: {file_path.name}",
                        f"Sample matches: {matches[:3]}",
                        "May contain predetermined response structures",
                    ],
                    blocks_merge=False,
                )
                findings.append(finding)
                break

        return findings


# =============================================================================
# Main entry point
# =============================================================================


def run_detection(
    root_path: str | Path = ".",
    output_format: str = "text",
) -> int:
    """
    Run the Universal Hardcoding Detector and output results.

    Args:
        root_path: Path to scan
        output_format: Output format (text, json, summary)

    Returns:
        Exit code: 0 if no blocking findings, 1 if blocking findings exist
    """
    detector = UniversalHardcodingDetector(root_path)
    data_inspector = DataFileInspector(root_path)

    # Run Python code detection
    python_findings = detector.scan_project()

    # Run data file inspection
    data_findings = data_inspector.inspect_directory(root_path)

    all_findings = python_findings + data_findings

    if output_format == "json":
        report = {
            "total_findings": len(all_findings),
            "python_findings": len(python_findings),
            "data_findings": len(data_findings),
            "findings": [f.to_dict() for f in all_findings],
        }
        print(json.dumps(report, indent=2))
    elif output_format == "summary":
        high = sum(1 for f in all_findings if f.severity == Severity.HIGH)
        medium = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
        low = sum(1 for f in all_findings if f.severity == Severity.LOW)
        blocking = sum(1 for f in all_findings if f.blocks_merge)

        print("Universal Hardcoding Detection Report")
        print(f"{'=' * 50}")
        print(f"Total findings: {len(all_findings)}")
        print(f"  HIGH (blocking): {high}")
        print(f"  MEDIUM (review): {medium}")
        print(f"  LOW (info): {low}")
        print(f"Blocking findings: {blocking}")

        if blocking > 0:
            print("\nBLOCKING FINDINGS DETECTED")
            print(f"{'=' * 50}")
            for f in all_findings:
                if f.blocks_merge:
                    print(f"\n[{f.rule_id}] {f.file_path}:{f.line_number}")
                    print(f"  {f.message}")
                    print(f"  Confidence: {f.confidence:.0%}")
                    for ev in f.evidence:
                        print(f"  - {ev}")
    else:  # text format
        if all_findings:
            print("Universal Hardcoding Detection Report")
            print(f"{'=' * 50}")
            for f in sorted(all_findings, key=lambda x: (x.severity.value, x.file_path)):
                print(f"\n[{f.rule_id}] {f.file_path}:{f.line_number}")
                print(f"  Severity: {f.severity.value}")
                print(f"  {f.message}")
                print(f"  Confidence: {f.confidence:.0%}")
                for ev in f.evidence:
                    print(f"  - {ev}")
        else:
            print("No hardcoded conversational patterns detected.")

    return 1 if any(f.blocks_merge for f in all_findings) else 0


# Entry point is in cli.py
