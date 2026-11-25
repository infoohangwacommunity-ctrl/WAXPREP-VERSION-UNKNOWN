# Branch and edge-case tests for the Universal Hardcoding Detector (Stage 08)
#
# Every test asserts an observable outcome. A test that only checks
# `isinstance(findings, list)` proves nothing about detector behaviour.

from __future__ import annotations

import ast
import csv as csv_module
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from waxprep.detector import (
    DEFAULT_SCAN_TARGETS,
    AnalysisResult,
    DataFileInspector,
    Finding,
    ScanProblem,
    Severity,
    UniversalHardcodingDetector,
    analyze,
    has_word_boundary,
    identifier_tokens,
    looks_like_student_input,
    run_detection,
)


def rule_ids(findings: Sequence[Finding]) -> list[str]:
    """Return the rule IDs of a finding list in order."""
    return [finding.rule_id for finding in findings]


def protected_file(tmp_path: Path, name: str = "module.py") -> Path:
    """Create a Python file inside a protected module and return its path."""
    module_dir = tmp_path / "waxprep" / "messaging"
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir / name


# =============================================================================
# Data file inspector: YAML
# =============================================================================


class TestDataFileInspectorYaml:
    """Cover DataFileInspector._inspect_yaml behaviour."""

    def test_yaml_vocabulary_list(self, tmp_path: Path) -> None:
        """YAML with a single >=5-term list triggers WHD-010."""
        yaml_file = tmp_path / "vocab.yml"
        yaml_file.write_text(
            'words:\n  - "hello"\n  - "goodbye"\n  - "yes"\n  - "no"\n  - "maybe"\n'
        )
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        vocabulary = [f for f in findings if f.rule_id == "WHD-010"]
        assert len(vocabulary) == 1
        assert "5 terms" in vocabulary[0].message
        assert vocabulary[0].blocks_merge is False

    def test_yaml_string_mappings(self, tmp_path: Path) -> None:
        """YAML with >=3 key:value string pairs triggers WHD-009."""
        yaml_file = tmp_path / "mappings.yml"
        yaml_file.write_text('hello: "greeting"\ngoodbye: "farewell"\nyes: "affirmative"\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        mappings = [f for f in findings if f.rule_id == "WHD-009"]
        assert len(mappings) == 1
        assert "3 string-to-string mappings" in mappings[0].message

    def test_yaml_empty_file(self, tmp_path: Path) -> None:
        """Empty YAML produces no findings."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.write_text("")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []

    def test_yaml_nested_list_items_are_not_a_flat_vocabulary(self, tmp_path: Path) -> None:
        """Inline nested lists are not counted as a flat vocabulary run."""
        yaml_file = tmp_path / "nested_list.yml"
        yaml_file.write_text('matrix:\n  - ["hello", "world"]\n  - ["yes", "no"]\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert [f for f in findings if f.rule_id == "WHD-010"] == []

    def test_yaml_indented_sublist_breaks_run(self, tmp_path: Path) -> None:
        """Items at a different indentation level are separate lists."""
        yaml_file = tmp_path / "sublist.yml"
        yaml_file.write_text("words:\n  - hello\n    - goodbye\n")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert [f for f in findings if f.rule_id == "WHD-010"] == []


# =============================================================================
# Data file inspector: TOML
# =============================================================================


class TestDataFileInspectorToml:
    """Cover DataFileInspector._inspect_toml behaviour."""

    def test_toml_vocabulary_array(self, tmp_path: Path) -> None:
        """One array with five terms triggers WHD-010."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('words = ["hello", "goodbye", "greeting", "farewell", "maybe"]\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        vocabulary = [f for f in findings if f.rule_id == "WHD-010"]
        assert len(vocabulary) == 1
        assert "5 terms" in vocabulary[0].message

    def test_toml_unrelated_short_arrays_are_configuration(self, tmp_path: Path) -> None:
        """Three one-item arrays are configuration, not a vocabulary list."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_text('words = ["hello"]\nphrases = ["goodbye"]\nterms = ["yes"]\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []

    def test_toml_nested_array_is_found(self, tmp_path: Path) -> None:
        """Vocabulary arrays nested in TOML tables are inspected."""
        toml_file = tmp_path / "nested.toml"
        toml_file.write_text(
            '[tool.words]\nterms = ["hello", "goodbye", "greeting", "farewell", "maybe"]\n'
        )
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        vocabulary = [f for f in findings if f.rule_id == "WHD-010"]
        assert len(vocabulary) == 1
        assert "tool/words/terms" in vocabulary[0].evidence[1]

    def test_toml_non_alphabetic_terms_are_not_vocabulary(self, tmp_path: Path) -> None:
        """Five single-character entries are not vocabulary terms."""
        toml_file = tmp_path / "flags.toml"
        toml_file.write_text('flags = ["a", "b", "c", "d", "e"]\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert [f for f in findings if f.rule_id == "WHD-010"] == []

    def test_toml_identifier_list_is_configuration(self, tmp_path: Path) -> None:
        """A list of code identifiers is configuration, not vocabulary."""
        toml_file = tmp_path / "tool.toml"
        toml_file.write_text(
            'ignore_names = ["register_defaults", "FakeChannelAdapter", '
            '"get_app", "liveness", "readiness"]\n'
        )
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []

    def test_toml_nested_arrays_are_walked(self, tmp_path: Path) -> None:
        """Arrays nested inside arrays are inspected recursively."""
        toml_file = tmp_path / "nested.toml"
        toml_file.write_text('matrix = [["a"], ["b"]]\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []

    def test_toml_invalid_syntax_is_reported(self, tmp_path: Path) -> None:
        """Invalid TOML is reported as a scan problem, not as clean."""
        toml_file = tmp_path / "broken.toml"
        toml_file.write_text("words = [\n")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []
        assert [problem.reason for problem in inspector.problems] == ["invalid-toml"]


# =============================================================================
# Data file inspector: CSV
# =============================================================================


class TestDataFileInspectorCsv:
    """Cover DataFileInspector._inspect_csv behaviour."""

    def test_csv_vocabulary_row(self, tmp_path: Path) -> None:
        """A row of >=5 text cells triggers WHD-010."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("hello,goodbye,yes,maybe,perhaps\n")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        vocabulary = [f for f in findings if f.rule_id == "WHD-010"]
        assert len(vocabulary) == 1

    def test_csv_short_row_is_not_vocabulary(self, tmp_path: Path) -> None:
        """A short or malformed row is not a vocabulary list."""
        csv_file = tmp_path / "short.csv"
        csv_file.write_text('hello,"unclosed quote\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []

    def test_csv_parse_error_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A csv.Error is recorded as a scan problem."""

        class RaisingReader:
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise csv_module.Error("simulated csv error")

        monkeypatch.setattr(csv_module, "reader", RaisingReader)
        inspector = DataFileInspector(str(tmp_path))
        result = inspector._inspect_csv("hello,goodbye\n", tmp_path / "test.csv")

        assert result == []
        assert [problem.reason for problem in inspector.problems] == ["invalid-csv"]


# =============================================================================
# Data file inspector: Markdown
# =============================================================================


class TestDataFileInspectorMarkdown:
    """Cover DataFileInspector._inspect_markdown behaviour."""

    def test_markdown_response_template(self, tmp_path: Path) -> None:
        """Markdown with a response template pattern triggers WHD-011."""
        md_file = tmp_path / "docs.md"
        md_file.write_text('If the student says "hello", respond with "greeting"\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        templates = [f for f in findings if f.rule_id == "WHD-011"]
        assert len(templates) == 1
        assert templates[0].blocks_merge is False

    def test_markdown_without_templates_is_clean(self, tmp_path: Path) -> None:
        """Ordinary prose does not produce WHD-011."""
        md_file = tmp_path / "plain.md"
        md_file.write_text("# Architecture\n\nThe messaging layer routes messages.\n")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []


# =============================================================================
# Incomplete scans are visible
# =============================================================================


class TestScanProblems:
    """Files that cannot be inspected must never look like clean scans."""

    def test_syntax_error_is_reported(self, tmp_path: Path) -> None:
        """Invalid Python is recorded as a scan problem."""
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def foo(\n")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(bad_file)

        assert findings == []
        assert [problem.reason for problem in detector.problems] == ["syntax-error"]

    def test_unreadable_file_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OSError while reading is recorded as a scan problem."""
        unreadable = tmp_path / "unreadable.py"
        unreadable.write_text("x = 1\n")

        def raise_os_error(self: Path, *args: object, **kwargs: object) -> str:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "read_text", raise_os_error)
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(unreadable)

        assert findings == []
        assert [problem.reason for problem in detector.problems] == ["unreadable"]

    def test_invalid_utf8_is_reported(self, tmp_path: Path) -> None:
        """Invalid UTF-8 is recorded as a scan problem."""
        binary_file = tmp_path / "binary.py"
        binary_file.write_bytes(b"\xff\xfe\x00\x00")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(binary_file)

        assert findings == []
        assert [problem.reason for problem in detector.problems] == ["invalid-encoding"]

    def test_data_file_unreadable_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OSError while reading a data file is recorded."""

        def raise_os_error(self: Path, *args: object, **kwargs: object) -> str:
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "read_text", raise_os_error)
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_file(tmp_path / "data.json")

        assert findings == []
        assert [problem.reason for problem in inspector.problems] == ["unreadable"]

    def test_data_file_invalid_utf8_is_reported(self, tmp_path: Path) -> None:
        """Invalid UTF-8 in a data file is recorded."""
        binary = tmp_path / "binary.yml"
        binary.write_bytes(b"\xff\xfe\x00\x00")
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_file(binary)

        assert findings == []
        assert [problem.reason for problem in inspector.problems] == ["invalid-encoding"]

    def test_invalid_json_is_reported(self, tmp_path: Path) -> None:
        """Invalid JSON is recorded as a scan problem."""
        json_file = tmp_path / "bad.json"
        json_file.write_text("{invalid json")
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_directory(str(tmp_path))

        assert findings == []
        assert [problem.reason for problem in inspector.problems] == ["invalid-json"]

    def test_missing_target_is_reported(self, tmp_path: Path) -> None:
        """A named target that does not exist is reported, not ignored."""
        result = analyze(["does-not-exist"], root_path=tmp_path)

        assert result.findings == []
        assert [problem.reason for problem in result.problems] == ["missing-target"]
        assert result.complete is False


# =============================================================================
# Directory scanning exclusions
# =============================================================================


class TestDirectoryScanning:
    """Generated and test files are excluded from directory scans."""

    def test_skips_cache_and_vcs_directories(self, tmp_path: Path) -> None:
        """Files under __pycache__ are not scanned."""
        clean = protected_file(tmp_path, "clean.py")
        clean.write_text("x = 1\n")
        cache_dir = tmp_path / "waxprep" / "messaging" / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "cached.py").write_text(
            "def handle(message):\n    if message == 'hello':\n        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_directory(str(tmp_path))

        assert findings == []
        assert detector.problems == []

    def test_skips_test_prefixed_files(self, tmp_path: Path) -> None:
        """Files named test_*.py are excluded, other files are scanned."""
        violation = "def handle(message):\n    if message == 'hello':\n        return 'greeting'\n"
        protected_file(tmp_path, "check.py").write_text(violation)
        protected_file(tmp_path, "test_check.py").write_text(violation)
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_directory(str(tmp_path))

        assert len(findings) == 1
        assert findings[0].file_path.endswith("check.py")


# =============================================================================
# AST rule branches
# =============================================================================


class TestDetectorNestedConditions:
    """Cover _detect_nested_conditions (WHD-006)."""

    def test_deeply_nested_if(self, tmp_path: Path) -> None:
        """Three levels of nesting produce a WHD-006 informational finding."""
        test_file = tmp_path / "nested.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if message == 'a':\n"
            "        if message == 'b':\n"
            "            if message == 'c':\n"
            "                return 'x'\n"
            "    return 'default'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        nested = [f for f in findings if f.rule_id == "WHD-006"]
        assert len(nested) == 1
        assert nested[0].severity is Severity.LOW
        assert nested[0].blocks_merge is False


class TestDetectorLiteralResponses:
    """Cover _detect_literal_responses (WHD-007)."""

    def test_function_returns_string_in_non_protected(self, tmp_path: Path) -> None:
        """Response functions outside protected modules are not flagged."""
        test_file = tmp_path / "helper.py"
        test_file.write_text("def get_greeting():\n    return 'hello'\n")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-007" not in rule_ids(findings)

    def test_protected_module_flags_list_and_tuple_returns(self, tmp_path: Path) -> None:
        """String lists and tuples returned from protected modules are flagged."""
        test_file = protected_file(tmp_path, "responses.py")
        test_file.write_text(
            "def get_responses():\n    return ['hello', 'world']\n\n"
            "def create_reply():\n    return ('hello',)\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        replies = [f for f in findings if f.rule_id == "WHD-007"]
        assert len(replies) == 2
        assert all(f.blocks_merge is False for f in replies)
        assert all(f.requires_review for f in replies)


class TestDetectorVocabularyDetection:
    """Cover _detect_hardcoded_vocabularies (WHD-008)."""

    def test_string_set_assignment(self, tmp_path: Path) -> None:
        """A set of strings in a protected module triggers WHD-008."""
        test_file = protected_file(tmp_path, "vocab.py")
        test_file.write_text("WORDS = {'hello', 'goodbye', 'yes'}\n")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-008" in rule_ids(findings)

    def test_nested_collection_vocabulary(self, tmp_path: Path) -> None:
        """Nested collections are flattened before counting terms."""
        test_file = protected_file(tmp_path, "nested_vocab.py")
        test_file.write_text("WORDS = [['hello'], ['world']]\n")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        vocabulary = [f for f in findings if f.rule_id == "WHD-008"]
        assert len(vocabulary) == 1
        assert "2 terms" in vocabulary[0].message

    def test_non_protected_module_not_flagged(self, tmp_path: Path) -> None:
        """Vocabulary outside protected modules is not flagged."""
        test_file = tmp_path / "vocab.py"
        test_file.write_text("WORDS = ['hello', 'world']\n")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-008" not in rule_ids(findings)


class TestDetectorDictLookup:
    """Cover _detect_dictionary_lookups (WHD-005)."""

    def test_dict_subscript_with_string_key(self, tmp_path: Path) -> None:
        """A string-keyed lookup on a mapping-named dict is a review finding."""
        test_file = tmp_path / "reader.py"
        test_file.write_text("responses = {'hello': 'greeting'}\nx = responses['hello']\n")
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        lookups = [f for f in findings if f.rule_id == "WHD-005"]
        assert len(lookups) == 1
        assert lookups[0].severity is Severity.MEDIUM
        assert lookups[0].blocks_merge is False

    def test_subscript_assignment_is_not_a_lookup(self, tmp_path: Path) -> None:
        """Writing `response['key'] = value` is not a word-to-action lookup."""
        test_file = tmp_path / "writer.py"
        test_file.write_text(
            "def build_response(content):\n"
            "    response = {'content': content}\n"
            "    response['metadata'] = None\n"
            "    return response\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-005" not in rule_ids(findings)


class TestDetectorMembership:
    """Cover _detect_membership_tests (WHD-002)."""

    def test_in_list_literal(self, tmp_path: Path) -> None:
        """`message in ['hello', 'hi']` is detected."""
        test_file = tmp_path / "check.py"
        test_file.write_text(
            "def process(message):\n    if message in ['hello', 'hi']:\n        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-002" in rule_ids(findings)

    def test_nested_collection_membership(self, tmp_path: Path) -> None:
        """Nested string collections are still inspected."""
        test_file = tmp_path / "nested_membership.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if message in [['hello'], ['world']]:\n"
            "        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-002" in rule_ids(findings)

    def test_non_string_collection_not_flagged(self, tmp_path: Path) -> None:
        """Numeric collections are not vocabularies."""
        test_file = tmp_path / "int_membership.py"
        test_file.write_text(
            "def handle(message):\n    if message in [1, 2, 3]:\n        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-002" not in rule_ids(findings)


class TestDetectorFixedStringComparison:
    """Cover _detect_fixed_string_comparisons (WHD-001)."""

    def test_comparison_with_constant(self, tmp_path: Path) -> None:
        """`message == 'hello'` is a HIGH finding."""
        test_file = tmp_path / "compare.py"
        test_file.write_text(
            "def check(message):\n    if message == 'hello':\n        return True\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        comparisons = [f for f in findings if f.rule_id == "WHD-001"]
        assert len(comparisons) == 1
        assert comparisons[0].severity is Severity.HIGH

    def test_attribute_access_is_not_input(self, tmp_path: Path) -> None:
        """`self.message` is object state, not inbound student input."""
        test_file = tmp_path / "attr_compare.py"
        test_file.write_text(
            "class Bot:\n"
            "    def handle(self):\n"
            "        if self.message == 'hello':\n"
            "            return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-001" not in rule_ids(findings)

    def test_call_to_input_reader_is_input(self, tmp_path: Path) -> None:
        """`get_message()` returns inbound input."""
        test_file = tmp_path / "input_func.py"
        test_file.write_text(
            "def handle():\n    if get_message() == 'hello':\n        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-001" in rule_ids(findings)

    def test_call_to_processor_is_not_input(self, tmp_path: Path) -> None:
        """`process_message()` returns a processed value, not raw input."""
        test_file = tmp_path / "process_func.py"
        test_file.write_text(
            "def handle():\n    if process_message() == 'hello':\n        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-001" not in rule_ids(findings)


# =============================================================================
# Data file inspector: JSON and nested structures
# =============================================================================


class TestDataFileInspectorStructure:
    """Cover JSON/YAML recursion branches."""

    def test_json_few_mappings_not_flagged(self, tmp_path: Path) -> None:
        """Two string mappings are not a behavioral engine."""
        json_file = tmp_path / "few_keys.json"
        json_file.write_text('{"hello": "greeting", "world": "planet"}')
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_directory(str(tmp_path))

        assert [f for f in findings if f.rule_id == "WHD-009"] == []

    def test_json_vocabulary_list(self, tmp_path: Path) -> None:
        """A JSON array of five terms triggers WHD-010."""
        json_file = tmp_path / "data.json"
        json_file.write_text('["hello", "world", "greeting", "farewell", "yes"]')
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_directory(str(tmp_path))

        assert "WHD-010" in rule_ids(findings)

    def test_json_nested_list_recursive(self, tmp_path: Path) -> None:
        """Nested dicts and lists are inspected recursively."""
        json_file = tmp_path / "nested.json"
        json_file.write_text(
            json.dumps({
                "greetings": ["hello", "world"],
                "nested_list": [["a", "b"], {"c": "d"}],
            })
        )
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_file(json_file)

        assert findings == []

    def test_yaml_list_of_lists(self, tmp_path: Path) -> None:
        """Nested YAML lists do not form a flat vocabulary run."""
        yaml_file = tmp_path / "nested.yml"
        yaml_file.write_text('matrix:\n  - ["hello", "world"]\n  - ["yes", "no"]\n')
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_file(yaml_file)

        assert findings == []

    def test_yaml_nested_dict_in_list(self, tmp_path: Path) -> None:
        """Nested list-of-mapping entries are not counted as vocabulary."""
        yaml_file = tmp_path / "nested.yml"
        yaml_file.write_text(
            "items:\n"
            '  - name: "hello"\n'
            '    response: "greeting"\n'
            '  - name: "goodbye"\n'
            '    response: "farewell"\n'
        )
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_file(yaml_file)

        assert findings == []

    def test_yaml_vocabulary_and_mappings(self, tmp_path: Path) -> None:
        """A YAML file can report both a vocabulary list and a mapping."""
        yaml_file = tmp_path / "complex.yml"
        yaml_file.write_text(
            "words:\n"
            '  - "hello"\n'
            '  - "world"\n'
            '  - "greeting"\n'
            '  - "farewell"\n'
            '  - "yes"\n'
            'hello: "greeting"\n'
            'world: "planet"\n'
            'yes: "affirmative"\n'
        )
        inspector = DataFileInspector(str(tmp_path))

        findings = inspector.inspect_file(yaml_file)

        assert rule_ids(findings) == ["WHD-010", "WHD-009"]


# =============================================================================
# Explicit scope and report consistency
# =============================================================================


class TestTargetNormalization:
    """Scan targets are resolved explicitly, never project-wide by accident."""

    def test_default_scope_is_explicit(self) -> None:
        """The default scope names Python sources and project docs."""
        assert "src" in DEFAULT_SCAN_TARGETS
        assert "docs" in DEFAULT_SCAN_TARGETS
        assert "README.md" in DEFAULT_SCAN_TARGETS

    def test_root_target_is_scanned(self, tmp_path: Path) -> None:
        """A directory target scans its Python files."""
        (tmp_path / "ok.py").write_text("x = 1\n")

        result = analyze(str(tmp_path))

        assert result.targets == [str(tmp_path)]
        assert result.complete is True

    def test_relative_target_is_resolved_against_root(self, tmp_path: Path) -> None:
        """Relative targets are joined to the project root."""
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "ok.py").write_text("x = 1\n")

        result = analyze(["pkg"], root_path=tmp_path)

        assert result.targets == [str(package)]

    def test_target_equal_to_root_is_not_nested(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A target naming the root itself must not become root/root."""
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "ok.py").write_text("x = 1\n")
        monkeypatch.chdir(tmp_path)

        result = analyze(["pkg"], root_path="pkg")

        assert result.targets == ["pkg"]
        assert result.complete is True

    def test_target_under_relative_root_is_not_nested(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A relative target already under a relative root is kept as-is."""
        package = tmp_path / "pkg"
        subpackage = package / "sub"
        subpackage.mkdir(parents=True)
        (subpackage / "ok.py").write_text("x = 1\n")
        monkeypatch.chdir(tmp_path)

        result = analyze(["pkg/sub"], root_path="pkg")

        assert result.targets == ["pkg/sub"]
        assert result.complete is True

    def test_single_string_target(self, tmp_path: Path) -> None:
        """A single string target is accepted, not treated as characters."""
        (tmp_path / "ok.py").write_text("x = 1\n")

        result = analyze(str(tmp_path))

        assert result.complete is True

    def test_python_file_target_is_scanned(self, tmp_path: Path) -> None:
        """A .py file target is scanned as Python source."""
        file_path = tmp_path / "ok.py"
        file_path.write_text("x = 1\n")

        result = analyze([str(file_path)], root_path=tmp_path)

        assert result.targets == [str(file_path)]
        assert result.complete is True

    def test_data_file_target_is_inspected(self, tmp_path: Path) -> None:
        """A data file target is inspected by the data-file inspector."""
        file_path = tmp_path / "data.json"
        file_path.write_text('["hello", "world", "greeting", "farewell", "yes"]')

        result = analyze([str(file_path)], root_path=tmp_path)

        assert "WHD-010" in rule_ids(result.findings)


class TestAnalysisResult:
    """Cover AnalysisResult properties."""

    def test_blocking_and_complete(self) -> None:
        """Blocking findings and completeness are derived, not duplicated."""
        blocker = Finding(
            rule_id="WHD-001",
            file_path="a.py",
            line_number=1,
            message="blocker",
            severity=Severity.HIGH,
            confidence=0.9,
            blocks_merge=True,
        )
        result = AnalysisResult(targets=["a.py"], findings=[blocker], problems=[])

        assert result.blocking_findings == [blocker]
        assert result.complete is True

        incomplete = AnalysisResult(
            targets=["a.py"],
            findings=[blocker],
            problems=[ScanProblem("b.py", "unreadable", "denied")],
        )
        assert incomplete.complete is False
        assert incomplete.problems[0].to_dict() == {
            "file_path": "b.py",
            "reason": "unreadable",
            "detail": "denied",
        }


class TestRequiresReview:
    """Detection, review and blocking are separate concepts."""

    def test_medium_review_finding(self) -> None:
        """A non-blocking MEDIUM finding requires review."""
        finding = Finding(
            rule_id="WHD-003",
            file_path="a.py",
            line_number=1,
            message="review",
            severity=Severity.MEDIUM,
            confidence=0.7,
        )
        assert finding.requires_review is True

    def test_high_blocking_finding(self) -> None:
        """A blocking HIGH finding does not merely require review."""
        finding = Finding(
            rule_id="WHD-001",
            file_path="a.py",
            line_number=1,
            message="blocker",
            severity=Severity.HIGH,
            confidence=0.9,
            blocks_merge=True,
        )
        assert finding.requires_review is False

    def test_low_finding(self) -> None:
        """LOW findings are informational."""
        finding = Finding(
            rule_id="WHD-006",
            file_path="a.py",
            line_number=1,
            message="info",
            severity=Severity.LOW,
            confidence=0.5,
        )
        assert finding.requires_review is False


class TestReportConsistency:
    """Report counts and merge decisions use the same blocking property."""

    def test_medium_findings_do_not_block_and_are_counted_as_review(self, tmp_path: Path) -> None:
        """A WHD-005 finding is review evidence, not a merge blocker."""
        test_file = protected_file(tmp_path, "lookup.py")
        test_file.write_text(
            "response_mapping = {'hello': 'hi'}\n\n"
            "def get_response() -> str:\n"
            "    return response_mapping['hello']\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        detector.scan_file(test_file)

        report = detector.get_report()

        assert report["total_findings"] == 1
        assert report["blocking_findings"] == 0
        assert report["review_findings"] == 1
        assert report["scan_complete"] is True
        assert detector.has_blocking_findings() is False

    def test_high_findings_block_and_are_counted(self, tmp_path: Path) -> None:
        """A WHD-001 finding in a protected module blocks and is counted."""
        test_file = protected_file(tmp_path, "compare.py")
        test_file.write_text(
            "def handle(message: str) -> str:\n    if message == 'hello':\n        return 'hi'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        detector.scan_file(test_file)

        report = detector.get_report()

        assert report["blocking_findings"] == 1
        assert report["review_findings"] == 0
        assert detector.has_blocking_findings() is True

    def test_scan_problems_appear_in_report(self, tmp_path: Path) -> None:
        """Incomplete scans are visible in the report."""
        (tmp_path / "broken.py").write_text("def foo(\n")
        detector = UniversalHardcodingDetector(str(tmp_path))
        detector.scan_directory(str(tmp_path))

        report = detector.get_report()

        assert report["scan_complete"] is False
        problems = report["scan_problems"]
        assert isinstance(problems, list)
        assert problems[0]["reason"] == "syntax-error"


# =============================================================================
# Heuristics
# =============================================================================


class TestInputHeuristic:
    """Name matching is token-based, not substring-based."""

    @pytest.mark.parametrize(
        "name",
        ["message", "student_message", "input_text", "rawMessage", "payload", "msg"],
    )
    def test_input_like_names(self, name: str) -> None:
        """Whole input tokens are recognised."""
        assert looks_like_student_input(ast.Name(id=name))

    @pytest.mark.parametrize("name", ["context", "metadata", "status", "options"])
    def test_non_input_names(self, name: str) -> None:
        """`context` is not `text`; `metadata` is not `data`."""
        assert looks_like_student_input(ast.Name(id=name)) is False

    def test_camel_case_is_split(self) -> None:
        """camelCase boundaries are token boundaries."""
        assert identifier_tokens("rawMessage") == {"raw", "message"}

    def test_context_and_metadata_are_not_student_input(self, tmp_path: Path) -> None:
        """`context` is not `text` and `metadata` is not `data` at detection time."""
        test_file = protected_file(tmp_path, "context_compare.py")
        test_file.write_text(
            "def check_context(context, metadata):\n"
            "    if context == 'ready':\n"
            "        return True\n"
            "    if metadata == 'complete':\n"
            "        return True\n"
            "    return False\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))

        findings = detector.scan_file(test_file)

        assert "WHD-001" not in rule_ids(findings)

    def test_word_boundary_detection(self) -> None:
        """`\\b` in a pattern is a backslash and a letter, not a backspace."""
        assert has_word_boundary(r"\bhello\b") is True
        assert has_word_boundary(r"^\d+$") is False


# =============================================================================
# run_detection output and exit codes
# =============================================================================


class TestRunDetectionFunction:
    """Cover run_detection() output formats and exit codes."""

    def test_run_detection_json_format(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output reports scope, counts and completeness."""
        (tmp_path / "dummy.py").write_text("x = 1\n")

        result = run_detection(str(tmp_path), "json")
        report = json.loads(capsys.readouterr().out)

        assert result == 0
        assert report["total_findings"] == 0
        assert report["blocking_findings"] == 0
        assert report["scan_complete"] is True
        assert report["targets"] == [str(tmp_path)]

    def test_run_detection_summary_format(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Summary output names the scanned targets."""
        (tmp_path / "dummy.py").write_text("x = 1\n")

        result = run_detection(str(tmp_path), "summary")
        output = capsys.readouterr().out

        assert result == 0
        assert "Universal Hardcoding Detection Report" in output
        assert "Scanned targets:" in output
        assert "Blocking findings: 0" in output

    def test_run_detection_text_format_empty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Text output reports a clean scan explicitly."""
        (tmp_path / "clean.py").write_text("x = 1\n")

        result = run_detection(str(tmp_path), "text")
        output = capsys.readouterr().out

        assert result == 0
        assert "No hardcoded conversational patterns detected" in output

    def test_run_detection_summary_blocking_branch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Summary output lists blocking findings and exits 1."""
        (tmp_path / "blocker.py").write_text(
            "def handle(message):\n    if message == 'hello':\n        return 'greeting'\n"
        )
        import waxprep.detector as detector_module

        original = detector_module.is_protected_module
        detector_module.is_protected_module = lambda path: True
        try:
            result = run_detection(str(tmp_path), "summary")
        finally:
            detector_module.is_protected_module = original
        output = capsys.readouterr().out

        assert result == 1
        assert "BLOCKING FINDINGS DETECTED" in output

    def test_run_detection_text_format_with_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Text output lists findings with severity and evidence."""
        (tmp_path / "found.py").write_text(
            "def handle(message):\n    if message == 'hello':\n        return 'greeting'\n"
        )

        result = run_detection(str(tmp_path), "text")
        output = capsys.readouterr().out

        assert result == 0
        assert "[WHD-001]" in output
        assert "Severity: HIGH" in output

    def test_run_detection_reports_incomplete_scan(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A scan that could not inspect a file exits 1 and says so."""
        (tmp_path / "broken.py").write_text("def foo(\n")

        result = run_detection(str(tmp_path), "text")
        output = capsys.readouterr().out

        assert result == 1
        assert "SCAN INCOMPLETE" in output
        assert "syntax-error" in output

    def test_run_detection_respects_explicit_targets(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Only the named targets are scanned."""
        (tmp_path / "ignored.py").write_text(
            "def handle(message):\n    if message == 'hello':\n        return 'greeting'\n"
        )
        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / "ok.py").write_text("x = 1\n")

        result = run_detection(str(tmp_path), "json", targets=[str(clean_dir)])
        report = json.loads(capsys.readouterr().out)

        assert result == 0
        assert report["total_findings"] == 0
        assert report["targets"] == [str(clean_dir)]
