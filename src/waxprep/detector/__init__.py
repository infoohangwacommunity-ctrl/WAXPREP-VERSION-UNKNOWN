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
import json
import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

Constant = ast.Constant

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

    @property
    def requires_review(self) -> bool:
        """True when this is review evidence rather than a merge blocker.

        Detection, review and merge-blocking are three separate concepts. A
        finding can exist and require a human decision without blocking a
        merge. Only findings with ``blocks_merge`` set stop the gate.
        """
        return self.severity is Severity.MEDIUM and not self.blocks_merge

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
            "requires_review": self.requires_review,
        }


@dataclass(frozen=True)
class ScanProblem:
    """A file that could not be inspected.

    Kept separate from findings so that "no findings" is never confused with
    "not successfully inspected".
    """

    file_path: str
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize scan problem to dictionary."""
        return {"file_path": self.file_path, "reason": self.reason, "detail": self.detail}


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


# Directories that are never scanned: VCS metadata, virtual environments,
# dependency trees, caches and build output.
SKIPPED_DIRECTORY_NAMES: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "site-packages",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".hypothesis",
    "dist",
    "build",
})


def is_skipped_path(path: Path) -> bool:
    """Return True when a path is inside a directory that must not be scanned."""
    return any(part in SKIPPED_DIRECTORY_NAMES for part in path.parts)


# =============================================================================
# Input-identification heuristic
# =============================================================================

# Whole identifier tokens that indicate a value may be student-supplied input.
# Matching is token-based (snake_case / camelCase aware), never substring-based:
# "context" must not match "text", and "metadata" must not match "data".
INPUT_NAME_TOKENS: frozenset[str] = frozenset({
    "message",
    "messages",
    "msg",
    "text",
    "content",
    "input",
    "query",
    "prompt",
    "body",
    "data",
    "payload",
    "utterance",
})

# Function names whose result is treated as inbound student input.
INPUT_FUNCTION_NAMES: frozenset[str] = frozenset({
    "get_message",
    "get_text",
    "get_content",
    "get_input",
    "fetch_message",
    "read_message",
    "receive_message",
})

# `receive`/`read` as whole tokens: receive_message() matches, reader() does not.
INPUT_FUNCTION_TOKENS: frozenset[str] = frozenset({"receive", "received", "read"})


def identifier_tokens(name: str) -> set[str]:
    """Split an identifier into lowercase word tokens.

    Handles snake_case and camelCase. Returns whole tokens only, so callers
    compare tokens instead of substrings.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {token for token in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if token}


def looks_like_student_input(node: ast.expr) -> bool:
    """Heuristic: does this expression look like student-supplied input?

    Variable names alone are not proof of student input. This helper is
    deliberately conservative: it matches whole name tokens and a small set of
    inbound-input function names. Attributes, internal context objects,
    metadata and configuration values are not treated as input.
    """
    if isinstance(node, ast.Name):
        return bool(identifier_tokens(node.id) & INPUT_NAME_TOKENS)

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function_name = node.func.id.lower()
        if function_name in INPUT_FUNCTION_NAMES:
            return True
        return bool(identifier_tokens(function_name) & INPUT_FUNCTION_TOKENS)

    return False


def has_word_boundary(pattern: str) -> bool:
    """Return True when a regex pattern contains a word-boundary escape.

    A raw literal such as ``r"\\bword\\b"`` contains a backslash followed by
    the letter ``b``. It does not contain the backspace character, which only
    appears when a non-raw string uses that escape. The previous implementation
    checked for the backspace character and therefore missed every normal
    regex word boundary.
    """
    return r"\b" in pattern


# WHD-003: a fixed decision tree needs at least three branches, at least two
# of which route on string literals. The same thresholds apply to if/elif
# chains and to match/case statements, so both spellings of the same routing
# table are treated alike.
MIN_DECISION_BRANCHES = 3
MIN_STRING_BRANCHES = 2


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
        self.problems: list[ScanProblem] = []
        self._visited_files: set[str] = set()

    def scan_file(self, file_path: Path) -> list[Finding]:
        """Scan a single Python file for prohibited patterns.

        Files that cannot be read or parsed are recorded in ``problems``; they
        are never silently reported as clean.
        """
        if not file_path.suffix == ".py":
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.problems.append(ScanProblem(str(file_path), "unreadable", str(exc)))
            return []
        except UnicodeDecodeError as exc:
            self.problems.append(ScanProblem(str(file_path), "invalid-encoding", str(exc)))
            return []

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            self.problems.append(ScanProblem(str(file_path), "syntax-error", exc.msg or ""))
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
            # Skip caches, virtual environments and build output
            if is_skipped_path(py_file):
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

        # Blocking status comes from the enforcement property, never from
        # severity alone: severity and merge-blocking are separate concepts.
        blocking = [f for f in self.findings if f.blocks_merge]
        review = [f for f in self.findings if f.requires_review]

        return {
            "total_findings": len(self.findings),
            "high_risk": len(high_risk),
            "medium_risk": len(medium_risk),
            "low_risk": len(low_risk),
            "blocking_findings": len(blocking),
            "review_findings": len(review),
            "findings": [f.to_dict() for f in self.findings],
            "rules_triggered": sorted({f.rule_id for f in self.findings}),
            "scan_complete": not self.problems,
            "scan_problems": [p.to_dict() for p in self.problems],
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
                                if looks_like_student_input(left):
                                    self.Comparisons.append((left, comparator))

                self.generic_visit(node)

        visitor = ComparisonVisitor()
        visitor.visit(tree)

        for left, constant in visitor.Comparisons:
            line_no = left.lineno if hasattr(left, "lineno") else constant.lineno

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
                        if looks_like_student_input(node.left):
                            comp = node.comparators[0]
                            # Check if right side is a literal collection
                            if isinstance(comp, (ast.List, ast.Set, ast.Tuple)):
                                if self._collection_contains_strings(comp):
                                    self.memberships.append((node.left, comp))
                            # Check if right side is a name that was assigned a string collection
                            elif isinstance(comp, ast.Name) and comp.id in string_collections:
                                self.memberships.append((node.left, comp))

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
        WHD-003: Detect if/elif chains and match/case statements that create
        fixed decision trees based on string comparisons in protected modules.
        """
        findings: list[Finding] = []
        source.splitlines()

        class IfChainVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.chains: list[tuple[ast.If | ast.Match, int, str]] = []

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

                if (
                    chain_length >= MIN_DECISION_BRANCHES
                    and string_comparisons >= MIN_STRING_BRANCHES
                ):
                    self.chains.append((node, chain_length, "if/elif chain"))

                self.generic_visit(node)

            def visit_Match(self, node: ast.Match) -> None:
                """Treat match/case on string literals as a fixed decision tree.

                A match statement is the structural equivalent of an if/elif
                chain: each string-literal case pattern routes on a fixed
                value. Match patterns are not ``Compare`` nodes, so without
                this rule such routing was invisible to WHD-003.
                """
                branch_count = len(node.cases)
                string_patterns = sum(
                    1 for case in node.cases if self._pattern_is_string_literal(case.pattern)
                )

                if branch_count >= MIN_DECISION_BRANCHES and string_patterns >= MIN_STRING_BRANCHES:
                    self.chains.append((node, branch_count, "match/case statement"))

                self.generic_visit(node)

            def _pattern_is_string_literal(self, pattern: ast.pattern) -> bool:
                """Return True when a case pattern routes on string literal(s)."""
                if isinstance(pattern, ast.MatchValue):
                    value = pattern.value
                    return isinstance(value, Constant) and isinstance(value.value, str)
                if isinstance(pattern, ast.MatchOr):
                    return any(self._pattern_is_string_literal(p) for p in pattern.patterns)
                return False

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

        for node, chain_length, structure in visitor.chains:
            finding = Finding(
                rule_id="WHD-003",
                file_path=str(file_path),
                line_number=node.lineno,
                message=(
                    f"Fixed decision tree ({structure} with {chain_length} branches) "
                    f"in protected module"
                ),
                severity=Severity.MEDIUM,
                confidence=0.70,
                evidence=[
                    f"{structure.capitalize()} with {chain_length} branches at line {node.lineno}",
                    "Multiple string comparisons detected",
                    f"Module: {module_path}",
                    f"Protected module: {is_protected_module(module_path)}",
                ],
                # WHD-003 is documented as review-required: a long if/elif chain
                # or a match/case routing table is evidence for a human, not
                # proof of prohibited behavior.
                blocks_merge=False,
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
                            # Word boundaries are a backslash followed by "b" in the
                            # pattern, not the backspace character.
                            has_regex_syntax = len(val) > 5 and ("(" in val or "[" in val)
                            if has_word_boundary(val) or has_regex_syntax:
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
                has_word_boundary(pattern)  # explicit \b word-boundary escapes
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
                # Only reads are lookups: `mapping["x"] = value` is a write.
                if isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name):
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
                # WHD-005 is documented as review-required, not blocking.
                blocks_merge=False,
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

            def _calculate_nesting_depth(self, node: ast.If, current: int = 1) -> int:
                """Calculate maximum nesting depth of if statements.

                The outermost if counts as level 1, so three nested if
                statements are reported as three levels of nesting.
                """
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
                    # WHD-007 is documented as review-required, not blocking.
                    blocks_merge=False,
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
                    # WHD-008 is documented as review-required, not blocking.
                    blocks_merge=False,
                )
                findings.append(finding)

        return findings


# =============================================================================
# Data/configuration file inspector
# =============================================================================

# WHD-010 describes a vocabulary list as five or more terms in one collection.
# Several unrelated one-item arrays are configuration, not a vocabulary.
MIN_VOCABULARY_TERMS = 5


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
        self.problems: list[ScanProblem] = []

    def inspect_file(self, file_path: Path) -> list[Finding]:
        """Inspect a data/configuration file.

        Unreadable files are recorded in ``problems`` rather than silently
        reported as clean.
        """
        findings: list[Finding] = []

        suffix = file_path.suffix.lower()
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.problems.append(ScanProblem(str(file_path), "unreadable", str(exc)))
            return []
        except UnicodeDecodeError as exc:
            self.problems.append(ScanProblem(str(file_path), "invalid-encoding", str(exc)))
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
            if data_file.is_file() and not is_skipped_path(data_file):
                suffix = data_file.suffix.lower()
                if suffix in {".json", ".yaml", ".yml", ".toml", ".csv", ".md"}:
                    self.inspect_file(data_file)

        return self.findings

    def _inspect_json(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect JSON content for vocabulary/mapping patterns."""
        findings: list[Finding] = []

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            self.problems.append(ScanProblem(str(file_path), "invalid-json", str(exc)))
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
            if all(isinstance(item, str) for item in data) and len(data) >= MIN_VOCABULARY_TERMS:
                # Check if these look like vocabulary
                sample = data[:5]
                if self._looks_like_vocabulary(sample):
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
        """Inspect YAML content for vocabulary patterns.

        Line-based parsing is intentionally conservative: only a contiguous run
        of list items at one indentation level counts as a list, and only
        key/value pairs at one indentation level count as a mapping. Nested
        structures are not merged into a single "vocabulary".
        """
        findings: list[Finding] = []

        list_runs: list[list[str]] = []
        current_run: list[str] = []
        current_indent: int | None = None
        mapping_pairs: dict[int, list[tuple[str, str]]] = {}

        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip())

            if stripped.startswith("- "):
                item = stripped[2:].strip().strip('"').strip("'")
                if not item or item.startswith(("{", "[")):
                    continue
                if current_indent is None or indent != current_indent:
                    if current_run:
                        list_runs.append(current_run)
                    current_run = []
                    current_indent = indent
                current_run.append(item)
                continue

            if current_run:
                list_runs.append(current_run)
                current_run = []
                current_indent = None

            key, separator, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if separator and key and value and not value.startswith(("{", "[")):
                mapping_pairs.setdefault(indent, []).append((key, value))

        if current_run:
            list_runs.append(current_run)

        vocabulary_run = max(list_runs, key=len, default=[])
        if len(vocabulary_run) >= MIN_VOCABULARY_TERMS:
            finding = Finding(
                rule_id="WHD-010",
                file_path=str(file_path),
                line_number=1,
                message=(f"YAML file contains vocabulary list ({len(vocabulary_run)} terms)"),
                severity=Severity.LOW,
                confidence=0.50,
                evidence=[
                    f"File: {file_path.name}",
                    f"Sample terms: {vocabulary_run[:5]}",
                ],
                blocks_merge=False,
            )
            findings.append(finding)

        largest_mapping = max((len(pairs) for pairs in mapping_pairs.values()), default=0)
        if largest_mapping >= 3:
            finding = Finding(
                rule_id="WHD-009",
                file_path=str(file_path),
                line_number=1,
                message=(f"YAML contains {largest_mapping} string-to-string mappings"),
                severity=Severity.MEDIUM,
                confidence=0.60,
                evidence=[
                    f"File: {file_path.name}",
                    "Mappings share one indentation level",
                ],
                blocks_merge=False,
            )
            findings.append(finding)

        return findings

    def _inspect_toml(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect TOML content for vocabulary lists (WHD-010).

        Uses a real TOML parser. WHD-010 describes one vocabulary list of five
        or more terms; several unrelated short arrays are ordinary
        configuration and are not reported.
        """
        findings: list[Finding] = []

        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            self.problems.append(ScanProblem(str(file_path), "invalid-toml", str(exc)))
            return findings

        for location, terms in self._find_string_arrays(data, [], MIN_VOCABULARY_TERMS):
            findings.append(
                Finding(
                    rule_id="WHD-010",
                    file_path=str(file_path),
                    line_number=1,
                    message=(f"TOML contains vocabulary list ({len(terms)} terms)"),
                    severity=Severity.LOW,
                    confidence=0.45,
                    evidence=[
                        f"File: {file_path.name}",
                        f"Path in TOML: {location}",
                        f"Sample terms: {terms[:5]}",
                    ],
                    blocks_merge=False,
                )
            )

        return findings

    def _find_string_arrays(
        self,
        data: object,
        path: list[str],
        minimum_terms: int,
    ) -> list[tuple[str, list[str]]]:
        """Recursively collect string-only arrays with at least ``minimum_terms``."""
        found: list[tuple[str, list[str]]] = []

        if isinstance(data, dict):
            for key, value in data.items():
                found.extend(self._find_string_arrays(value, [*path, str(key)], minimum_terms))
        elif isinstance(data, list):
            terms = [item for item in data if isinstance(item, str)]
            if len(terms) == len(data) and len(terms) >= minimum_terms:
                if self._looks_like_vocabulary(terms):
                    found.append(("/".join(path), terms))
            for item in data:
                if isinstance(item, (dict, list)):
                    found.extend(self._find_string_arrays(item, path, minimum_terms))

        return found

    def _looks_like_vocabulary(self, terms: list[str]) -> bool:
        """Conservative check: does a string list look like vocabulary terms?

        Natural-language vocabulary is lowercase alphabetic words. Lists of
        code identifiers (``register_defaults``, ``FakeChannelAdapter``) are
        configuration, not vocabulary, even when they are alphabetic.
        """
        sample = terms[:5]
        simple_words = sum(
            1 for term in sample if len(term) > 3 and term.isalpha() and term.islower()
        )
        return simple_words >= 3

    def _inspect_csv(self, content: str, file_path: Path) -> list[Finding]:
        """Inspect CSV content for vocabulary patterns."""
        findings: list[Finding] = []

        import csv
        from io import StringIO

        try:
            reader = csv.reader(StringIO(content))
            rows = list(reader)
        except csv.Error as exc:
            self.problems.append(ScanProblem(str(file_path), "invalid-csv", str(exc)))
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


# Explicit default scope for project-wide enforcement. Python sources,
# documentation and project data files are scanned. Tests and archived
# documents are excluded from the default scope so that test fixtures and
# historical examples do not create misleading findings; callers that want a
# different scope pass explicit targets.
DEFAULT_SCAN_TARGETS: tuple[str, ...] = (
    "src",
    "docs",
    "README.md",
    "tests/README.md",
    "pyproject.toml",
)

ScanTargets = str | Path | Sequence[str | Path] | None


@dataclass
class AnalysisResult:
    """Findings and scan problems for one explicit set of scan targets."""

    targets: list[str]
    findings: list[Finding]
    problems: list[ScanProblem]

    @property
    def blocking_findings(self) -> list[Finding]:
        """Findings that must stop a merge."""
        return [f for f in self.findings if f.blocks_merge]

    @property
    def complete(self) -> bool:
        """True only when every targeted file was successfully inspected."""
        return not self.problems


def _normalize_targets(targets: ScanTargets, root_path: str | Path) -> list[Path]:
    """Resolve scan targets against the project root."""
    requested: list[str | Path]
    if targets is None:
        requested = [root_path]
    elif isinstance(targets, (str, Path)):
        requested = [targets]
    else:
        requested = list(targets)

    root = Path(root_path)
    resolved: list[Path] = []
    for target in requested:
        path = Path(target)
        if path.is_absolute():
            resolved.append(path)
            continue
        if path == root or root in path.parents:
            resolved.append(path)
        else:
            resolved.append(root / path)
    return resolved


def analyze(targets: ScanTargets = None, root_path: str | Path = ".") -> AnalysisResult:
    """Analyse explicit scan targets with a single enforcement policy.

    A directory target is scanned recursively for Python sources and data
    files. A file target is scanned according to its suffix. Nothing outside
    the named targets is inspected: scope is explicit, never accidental.
    """
    detector = UniversalHardcodingDetector(root_path)
    inspector = DataFileInspector(root_path)
    paths = _normalize_targets(targets, root_path)

    findings: list[Finding] = []

    for path in paths:
        if path.is_dir():
            findings.extend(detector.scan_directory(path))
            findings.extend(inspector.inspect_directory(path))
        elif path.suffix == ".py":
            findings.extend(detector.scan_file(path))
        elif path.exists():
            findings.extend(inspector.inspect_file(path))
        else:
            detector.problems.append(ScanProblem(str(path), "missing-target"))

    return AnalysisResult(
        targets=[str(path) for path in paths],
        findings=findings,
        problems=[*detector.problems, *inspector.problems],
    )


def _print_scan_problems(problems: list[ScanProblem]) -> None:
    """Report files that were not successfully inspected."""
    if not problems:
        return

    print(f"\nSCAN INCOMPLETE: {len(problems)} file(s) could not be inspected")
    print(f"{'=' * 50}")
    for problem in problems:
        detail = f": {problem.detail}" if problem.detail else ""
        print(f"  ! {problem.file_path} ({problem.reason}){detail}")


def run_detection(
    root_path: str | Path = ".",
    output_format: str = "text",
    targets: ScanTargets = None,
) -> int:
    """
    Run the Universal Hardcoding Detector and output results.

    Args:
        root_path: Project root used to resolve relative targets and modules
        output_format: Output format (text, json, summary)
        targets: Explicit files/directories to scan. ``None`` scans root_path.

    Returns:
        Exit code: 0 when the scan is complete and nothing blocks the merge,
        1 when a blocking finding exists or a targeted file could not be
        inspected.
    """
    result = analyze(targets, root_path)
    blocking = result.blocking_findings
    review = [f for f in result.findings if f.requires_review]
    python_count = sum(1 for f in result.findings if f.file_path.endswith(".py"))

    if output_format == "json":
        report = {
            "targets": result.targets,
            "total_findings": len(result.findings),
            "python_findings": python_count,
            "data_findings": len(result.findings) - python_count,
            "blocking_findings": len(blocking),
            "review_findings": len(review),
            "scan_complete": result.complete,
            "scan_problems": [problem.to_dict() for problem in result.problems],
            "findings": [f.to_dict() for f in result.findings],
        }
        print(json.dumps(report, indent=2))
    elif output_format == "summary":
        high = sum(1 for f in result.findings if f.severity == Severity.HIGH)
        medium = sum(1 for f in result.findings if f.severity == Severity.MEDIUM)
        low = sum(1 for f in result.findings if f.severity == Severity.LOW)

        print("Universal Hardcoding Detection Report")
        print(f"{'=' * 50}")
        print(f"Scanned targets: {', '.join(result.targets)}")
        print(f"Total findings: {len(result.findings)}")
        print(f"  HIGH (blocking): {high}")
        print(f"  MEDIUM (review): {medium}")
        print(f"  LOW (info): {low}")
        print(f"Blocking findings: {len(blocking)}")
        print(f"Review findings: {len(review)}")
        _print_scan_problems(result.problems)

        if blocking:
            print("\nBLOCKING FINDINGS DETECTED")
            print(f"{'=' * 50}")
            for f in blocking:
                print(f"\n[{f.rule_id}] {f.file_path}:{f.line_number}")
                print(f"  {f.message}")
                print(f"  Confidence: {f.confidence:.0%}")
                for ev in f.evidence:
                    print(f"  - {ev}")
    else:  # text format
        if result.findings:
            print("Universal Hardcoding Detection Report")
            print(f"{'=' * 50}")
            for f in sorted(result.findings, key=lambda x: (x.severity.value, x.file_path)):
                print(f"\n[{f.rule_id}] {f.file_path}:{f.line_number}")
                print(f"  Severity: {f.severity.value}")
                print(f"  {f.message}")
                print(f"  Confidence: {f.confidence:.0%}")
                for ev in f.evidence:
                    print(f"  - {ev}")
        else:
            print("No hardcoded conversational patterns detected.")
        _print_scan_problems(result.problems)

    return 0 if result.complete and not blocking else 1


# Entry point is in cli.py
