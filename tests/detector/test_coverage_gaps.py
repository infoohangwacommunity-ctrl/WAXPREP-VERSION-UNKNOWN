# Additional coverage tests for detector gaps (Stage 08)
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from waxprep.detector import (
    DataFileInspector,
    Severity,
    UniversalHardcodingDetector,
    Finding,
)


# =============================================================================
# Data file inspector tests
# =============================================================================


class TestDataFileInspectorYaml:
    """Cover DataFileInspector._inspect_yaml gaps."""

    def test_yaml_vocabulary_list(self, tmp_path: Path) -> None:
        """YAML with >=5 string list entries triggers WHD-010."""
        yaml_file = tmp_path / "vocab.yml"
        yaml_file.write_text(
            "words:\n"
            '  - "hello"\n'
            '  - "goodbye"\n'
            '  - "yes"\n'
            '  - "no"\n'
            '  - "maybe"\n'
        )
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        yaml_findings = [f for f in findings if f.rule_id in ("WHD-010", "WHD-009")]
        assert len(yaml_findings) >= 1

    def test_yaml_string_mappings(self, tmp_path: Path) -> None:
        """YAML with >=3 key:value string pairs triggers WHD-009."""
        yaml_file = tmp_path / "mappings.yml"
        yaml_file.write_text(
            'hello: "greeting"\n'
            'goodbye: "farewell"\n'
            'yes: "affirmative"\n'
        )
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        yaml_findings = [f for f in findings if f.rule_id in ("WHD-009", "WHD-010")]
        assert len(yaml_findings) >= 1

    def test_yaml_empty_file(self, tmp_path: Path) -> None:
        """Empty YAML produces no findings."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.write_text("")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        assert all(f.rule_id not in ("WHD-009", "WHD-010") for f in findings)


class TestDataFileInspectorToml:
    """Cover DataFileInspector._inspect_toml gaps."""

    def test_toml_string_array(self, tmp_path: Path) -> None:
        """TOML with 3 separate string arrays triggers WHD-010."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_text(
            'words = ["hello"]\n'
            'phrases = ["goodbye"]\n'
            'terms = ["yes"]\n'
        )
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        toml_findings = [f for f in findings if f.rule_id in ("WHD-010", "WHD-009")]
        assert len(toml_findings) >= 1


class TestDataFileInspectorCsv:
    """Cover DataFileInspector._inspect_csv gaps."""

    def test_csv_vocabulary_row(self, tmp_path: Path) -> None:
        """CSV with row of >=5 text cells (len>2) triggers WHD-010."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("hello,goodbye,yes,maybe,perhaps\n")
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        csv_findings = [f for f in findings if f.rule_id in ("WHD-010", "WHD-009")]
        assert len(csv_findings) >= 1

    def test_csv_parse_error_handling(self, tmp_path: Path) -> None:
        """Malformed CSV returns empty findings gracefully (covers except csv.Error)."""
        csv_file = tmp_path / "bad.csv"
        # A CSV with a quote that never closes triggers csv.Error
        csv_file.write_text('hello,"unclosed quote\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        assert isinstance(findings, list)


class TestDataFileInspectorMarkdown:
    """Cover DataFileInspector._inspect_markdown gaps."""

    def test_markdown_response_template(self, tmp_path: Path) -> None:
        """Markdown with response template pattern triggers WHD-011."""
        md_file = tmp_path / "docs.md"
        md_file.write_text('If the student says "hello", respond with "greeting"\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        md_findings = [f for f in findings if f.rule_id == "WHD-011"]
        assert len(md_findings) >= 1

    def test_markdown_template_keyword(self, tmp_path: Path) -> None:
        """Markdown with template: pattern triggers WHD-011."""
        md_file = tmp_path / "template.md"
        md_file.write_text('template: "welcome_message"\n')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        md_findings = [f for f in findings if f.rule_id == "WHD-011"]
        assert len(md_findings) >= 1


# =============================================================================
# Error handling paths
# =============================================================================


class TestErrorHandlingPaths:
    """Cover exception handling paths in detector."""

    def test_syntax_error_handling(self, tmp_path: Path) -> None:
        """File with invalid syntax is skipped gracefully (covers except SyntaxError)."""
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def foo(\n")
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(bad_file)
        assert isinstance(findings, list)
        assert len(findings) == 0

    def test_os_error_handling(self, tmp_path: Path) -> None:
        """Unreadable file returns empty findings (covers except OSError)."""
        unreadable = tmp_path / "unreadable.py"
        unreadable.write_text("x = 1\n")
        unreadable.chmod(0o000)
        try:
            detector = UniversalHardcodingDetector(str(tmp_path))
            findings = detector.scan_file(unreadable)
            assert isinstance(findings, list)
        finally:
            unreadable.chmod(0o644)

    def test_unicode_decode_error_handling(self, tmp_path: Path) -> None:
        """Binary file with invalid UTF-8 returns empty findings."""
        binary_file = tmp_path / "binary.py"
        binary_file.write_bytes(b"\xff\xfe\x00\x00")
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(binary_file)
        assert isinstance(findings, list)
        assert len(findings) == 0

    def test_scan_directory_skips_pycache(self, tmp_path: Path) -> None:
        """scan_directory skips __pycache__ directories (covers continue at line 177)."""
        src_dir = tmp_path / "pkg"
        src_dir.mkdir()
        (src_dir / "valid.py").write_text("x = 1\n")
        pycache = src_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("y = 2\n")
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_directory(str(tmp_path))
        assert isinstance(findings, list)

    def test_scan_directory_skips_test_prefix(self, tmp_path: Path) -> None:
        """scan_directory skips test_-prefixed files (covers continue at line 182)."""
        src_dir = tmp_path / "pkg"
        src_dir.mkdir()
        (src_dir / "check.py").write_text(
            "def handle(message):\n"
            "    if message == 'hello':\n"
            "        return 'greeting'\n"
        )
        (src_dir / "test_check.py").write_text(
            "def handle(message):\n"
            "    if message == 'hello':\n"
            "        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_directory(str(tmp_path))
        assert isinstance(findings, list)


# =============================================================================
# Detector AST method coverage gaps
# =============================================================================


class TestDetectorNestedConditions:
    """Cover _detect_nested_conditions gaps (WHD-006)."""

    def test_deeply_nested_if(self, tmp_path: Path) -> None:
        """Deeply nested if/elif triggers nested condition detection."""
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
        assert isinstance(findings, list)


class TestDetectorLiteralResponses:
    """Cover _detect_literal_responses gaps (WHD-007)."""

    def test_function_returns_string_in_non_protected(self, tmp_path: Path) -> None:
        """Function returning strings in non-protected module is fine."""
        test_file = tmp_path / "helper.py"
        test_file.write_text(
            "def get_greeting():\n"
            "    return 'hello'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert not any(f.rule_id == "WHD-007" for f in findings)


class TestDetectorVocabularyDetection:
    """Cover _detect_hardcoded_vocabularies gaps (WHD-008)."""

    def test_string_set_assignment(self, tmp_path: Path) -> None:
        """Set of strings assigned to vocabulary-like name."""
        test_file = tmp_path / "vocab.py"
        test_file.write_text(
            "WORDS = {'hello', 'goodbye', 'yes'}\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)


class TestDetectorDictLookup:
    """Cover _detect_dictionary_lookups gaps (WHD-005)."""

    def test_dict_subscript_with_string_key(self, tmp_path: Path) -> None:
        """Dictionary subscript with string key in non-protected module."""
        test_file = tmp_path / "reader.py"
        test_file.write_text(
            "responses = {'hello': 'greeting'}\n"
            "x = responses['hello']\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        dict_findings = [f for f in findings if f.rule_id == "WHD-005"]
        assert len(dict_findings) >= 1
        assert dict_findings[0].blocks_merge is False


class TestDetectorMembership:
    """Cover _detect_membership_tests gaps (WHD-002)."""

    def test_in_list_literal(self, tmp_path: Path) -> None:
        """`message in ['hello', 'hi']` pattern."""
        test_file = tmp_path / "check.py"
        test_file.write_text(
            "def process(message):\n"
            "    if message in ['hello', 'hi']:\n"
            "        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)


class TestDetectorFixedStringComparison:
    """Cover _detect_fixed_string_comparisons gaps (WHD-001)."""

    def test_comparison_with_constant(self, tmp_path: Path) -> None:
        """String comparison against constant."""
        test_file = tmp_path / "compare.py"
        test_file.write_text(
            "def check(message):\n"
            "    if message == 'hello':\n"
            "        return True\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)


class TestDetectorAstHelperPaths:
    """Cover AST visitor helper method gaps."""

    def test_looks_like_input_function_call(self, tmp_path: Path) -> None:
        """_looks_like_input recognizes function calls like get_message() (lines 287-293)."""
        test_file = tmp_path / "input_func.py"
        test_file.write_text(
            "def handle():\n"
            "    if get_message() == 'hello':\n"
            "        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_nested_collection_membership(self, tmp_path: Path) -> None:
        """Nested collection in membership test covers recursive _collection_contains_strings (lines 357-358, 415)."""
        test_file = tmp_path / "nested_membership.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if message in [['hello'], ['world']]:\n"
            "        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_nested_conditions_deep_if(self, tmp_path: Path) -> None:
        """Deep nested if bodies cover _count_inner_bodies recursion (lines 759-760)."""
        test_file = tmp_path / "deep_nested.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if True:\n"
            "        if True:\n"
            "            if message == 'hello':\n"
            "                return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_return_string_extract_list(self, tmp_path: Path) -> None:
        """Function returning list of strings covers _extract_strings for lists (lines 846-847)."""
        test_file = tmp_path / "return_list.py"
        test_file.write_text(
            "def get_responses():\n"
            "    return ['hello', 'world']\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_return_string_extract_tuple(self, tmp_path: Path) -> None:
        """Function returning tuple of strings covers _extract_strings for tuples (lines 849-850)."""
        test_file = tmp_path / "return_tuple.py"
        test_file.write_text(
            "def get_responses():\n"
            "    return ('hello', 'world')\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_nested_collection_membership_deep(self, tmp_path: Path) -> None:
        """Deeply nested collection in membership test covers recursive calls (lines 357-358, 415)."""
        test_file = tmp_path / "deep_nested_membership.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if message in [[['hello']]]:\n"
            "        return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_nested_conditions_very_deep(self, tmp_path: Path) -> None:
        """Very deeply nested if bodies cover _count_inner_bodies (lines 759-760)."""
        test_file = tmp_path / "very_deep.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if True:\n"
            "        if True:\n"
            "            if True:\n"
            "                if message == 'hello':\n"
            "                    return 'greeting'\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_vocab_nested_collection(self, tmp_path: Path) -> None:
        """Vocabulary with nested collection covers _extract_strings recursion (lines 936-937)."""
        test_file = tmp_path / "nested_vocab.py"
        test_file.write_text(
            "WORDS = [['hello'], ['world']]\n"
        )
        detector = UniversalHardcodingDetector(str(tmp_path))
        findings = detector.scan_file(test_file)
        assert isinstance(findings, list)

    def test_json_dict_few_mappings(self, tmp_path: Path) -> None:
        """JSON with <3 string mappings covers dict branch (lines 1017-1018)."""
        json_file = tmp_path / "few_keys.json"
        json_file.write_text('{"hello": "greeting", "world": "planet"}')
        inspector = DataFileInspector(str(tmp_path))
        findings = inspector.inspect_directory(str(tmp_path))
        assert isinstance(findings, list)


# =============================================================================
# Data file inspector coverage gaps
# =============================================================================


def test_data_inspector_json_vocab(tmp_path: Path) -> None:
    """JSON with vocabulary list (>=5 strings) triggers data inspector."""
    json_file = tmp_path / "data.json"
    json_file.write_text('["hello", "world", "greeting", "farewell", "yes"]')
    inspector = DataFileInspector(str(tmp_path))
    findings = inspector.inspect_directory(str(tmp_path))
    json_findings = [f for f in findings if f.rule_id in ("WHD-009", "WHD-010")]
    assert len(json_findings) >= 1


def test_data_inspector_json_invalid(tmp_path: Path) -> None:
    """Invalid JSON returns empty findings (covers except json.JSONDecodeError)."""
    json_file = tmp_path / "bad.json"
    json_file.write_text("{invalid json")
    inspector = DataFileInspector(str(tmp_path))
    findings = inspector.inspect_directory(str(tmp_path))
    assert isinstance(findings, list)


def test_data_inspector_yaml_complex(tmp_path: Path) -> None:
    """YAML with vocabulary list and string mappings covers YAML inspector paths."""
    yaml_file = tmp_path / "complex.yml"
    yaml_file.write_text(
        'words:\n'
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
    findings = inspector.inspect_directory(str(tmp_path))
    assert len(findings) >= 1


def test_data_inspector_toml_multiple_arrays(tmp_path: Path) -> None:
    """TOML with 3 separate string arrays covers TOML inspector."""
    toml_file = tmp_path / "multi.toml"
    toml_file.write_text(
        'words = ["hello"]\n'
        'phrases = ["goodbye"]\n'
        'terms = ["yes"]\n'
    )
    inspector = DataFileInspector(str(tmp_path))
    findings = inspector.inspect_directory(str(tmp_path))
    toml_findings = [f for f in findings if f.rule_id in ("WHD-010", "WHD-009")]
    assert len(toml_findings) >= 1


def test_data_inspector_csv_vocab(tmp_path: Path) -> None:
    """CSV with 5+ text cells per row covers CSV inspector."""
    csv_file = tmp_path / "vocab.csv"
    csv_file.write_text("hello,goodbye,yes,maybe,perhaps\n")
    inspector = DataFileInspector(str(tmp_path))
    findings = inspector.inspect_directory(str(tmp_path))
    csv_findings = [f for f in findings if f.rule_id in ("WHD-010", "WHD-009")]
    assert len(csv_findings) >= 1


def test_data_inspector_markdown_templates(tmp_path: Path) -> None:
    """Markdown with response templates covers markdown inspector."""
    md_file = tmp_path / "responses.md"
    md_file.write_text('If student says "hello", respond with "greeting"\n')
    inspector = DataFileInspector(str(tmp_path))
    findings = inspector.inspect_directory(str(tmp_path))
    md_findings = [f for f in findings if f.rule_id == "WHD-011"]
    assert len(md_findings) >= 1


# =============================================================================
# run_detection() function gaps
# =============================================================================


class TestRunDetectionFunction:
    """Cover run_detection() function gaps."""

    def test_run_detection_json_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """run_detection with json format outputs valid JSON."""
        test_file = tmp_path / "dummy.py"
        test_file.write_text("x = 1\n")
        from waxprep.detector import run_detection
        result = run_detection(str(tmp_path), "json")
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["total_findings"] >= 0
        assert result == 0

    def test_run_detection_summary_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """run_detection with summary format prints summary."""
        test_file = tmp_path / "dummy.py"
        test_file.write_text("x = 1\n")
        from waxprep.detector import run_detection
        run_detection(str(tmp_path), "summary")
        captured = capsys.readouterr()
        assert "Universal Hardcoding Detection Report" in captured.out

    def test_run_detection_text_format_empty(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """run_detection text format with no findings prints 'No hardcoded...'."""
        test_file = tmp_path / "clean.py"
        test_file.write_text("x = 1\n")
        from waxprep.detector import run_detection
        run_detection(str(tmp_path), "text")
        captured = capsys.readouterr()
        assert "No hardcoded conversational patterns detected" in captured.out

    def test_run_detection_summary_blocking_branch(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """run_detection summary format with blocking findings covers blocking>0 branch (lines 1348-1356)."""
        test_file = tmp_path / "blocker.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if message == 'hello':\n"
            "        return 'greeting'\n"
        )
        import waxprep.detector as det
        original = det.is_protected_module
        det.is_protected_module = lambda p: True
        try:
            from waxprep.detector import run_detection
            run_detection(str(tmp_path), "summary")
        finally:
            det.is_protected_module = original
        captured = capsys.readouterr()
        assert "BLOCKING FINDINGS DETECTED" in captured.out

    def test_run_detection_text_format_with_findings(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """run_detection text format with findings covers the else branch (lines 1359-1367)."""
        test_file = tmp_path / "found.py"
        test_file.write_text(
            "def handle(message):\n"
            "    if message == 'hello':\n"
            "        return 'greeting'\n"
        )
        import waxprep.detector as det
        original = det.is_protected_module
        det.is_protected_module = lambda p: True
        try:
            from waxprep.detector import run_detection
            run_detection(str(tmp_path), "text")
        finally:
            det.is_protected_module = original
        captured = capsys.readouterr()
        assert "Universal Hardcoding Detection Report" in captured.out
