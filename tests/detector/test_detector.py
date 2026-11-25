# Unit tests for Universal Hardcoding Detector (Stage 08)
#
# These tests verify the detector's ability to identify prohibited
# hardcoded conversational patterns using AST analysis.

from __future__ import annotations

from pathlib import Path

import pytest

from waxprep.detector import (
    Finding,
    Severity,
    UniversalHardcodingDetector,
    is_allowed_module,
    is_protected_module,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def detector(tmp_path: Path) -> UniversalHardcodingDetector:
    """Create a detector instance for testing."""
    return UniversalHardcodingDetector(tmp_path)


@pytest.fixture
def protected_module_file(tmp_path: Path) -> Path:
    """Create a test file in a protected module location."""
    # Create directory structure mimicking protected module
    mod_path = tmp_path / "waxprep" / "messaging"
    mod_path.mkdir(parents=True)
    file_path = mod_path / "test_module.py"
    return file_path


@pytest.fixture
def allowed_module_file(tmp_path: Path) -> Path:
    """Create a test file in an allowed module location."""
    mod_path = tmp_path / "waxprep" / "core"
    mod_path.mkdir(parents=True)
    file_path = mod_path / "test_module.py"
    return file_path


# =============================================================================
# Module boundary tests
# =============================================================================


class TestModuleBoundaries:
    """Tests for module boundary classification."""

    def test_protected_module_messaging(self) -> None:
        """waxprep.messaging should be classified as protected."""
        assert is_protected_module("waxprep/messaging/handler.py")
        assert is_protected_module("waxprep/messaging/__init__.py")
        assert is_protected_module("waxprep/messaging/router.py")

    def test_protected_module_context(self) -> None:
        """waxprep.context should be classified as protected."""
        assert is_protected_module("waxprep/context/profile.py")
        assert is_protected_module("waxprep.context.learner.py")

    def test_protected_module_services(self) -> None:
        """waxprep.services should be classified as protected."""
        assert is_protected_module("waxprep/services/orchestrator.py")
        assert is_protected_module("waxprep.services/composition.py")

    def test_allowed_module_core(self) -> None:
        """waxprep.core should be classified as allowed."""
        assert is_allowed_module("waxprep/core/protocols.py")
        assert is_allowed_module("waxprep.core/pure.py")

    def test_allowed_module_config(self) -> None:
        """waxprep.config should be classified as allowed."""
        assert is_allowed_module("waxprep/config.py")

    def test_allowed_module_adapters(self) -> None:
        """waxprep.adapters should be classified as allowed."""
        assert is_allowed_module("waxprep/adapters/fake_channel.py")
        assert is_allowed_module("waxprep.adapters.channel_adapter.py")

    def test_not_protected(self) -> None:
        """Non-matching paths should not be protected."""
        assert not is_protected_module("waxprep/core/protocols.py")
        assert not is_protected_module("some_other_module.py")

    def test_not_allowed(self) -> None:
        """Protected modules should not be allowed."""
        assert not is_allowed_module("waxprep/messaging/handler.py")


# =============================================================================
# WHD-001: Fixed-string comparison tests
# =============================================================================


class TestWHD001FixedStringComparison:
    """Tests for fixed-string comparison detection (WHD-001)."""

    def test_detects_string_comparison_in_protected_module(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag string comparisons in protected modules."""
        code = """
def handle_message(message: str) -> str:
    if message == "hello":
        return "Hi there!"
    return "Unknown"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert len(findings) >= 1
        assert any(f.rule_id == "WHD-001" for f in findings)

    def test_detects_comparison_with_input_variable(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should recognize input-like variable names."""
        code = """
def process(content: str) -> bool:
    if content == "help":
        return True
    return False
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-001" for f in findings)

    def test_does_not_flag_in_allowed_module(
        self, detector: UniversalHardcodingDetector, allowed_module_file: Path
    ) -> None:
        """String comparisons in allowed modules should not block."""
        code = """
def validate_status(status: str) -> bool:
    if status == "active":
        return True
    return False
"""
        allowed_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(allowed_module_file)

        # Should detect but not block (confidence may be lower)
        whd_findings = [f for f in findings if f.rule_id == "WHD-001"]
        if whd_findings:
            assert not whd_findings[0].blocks_merge

    def test_detects_not_equal_comparison(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag != comparisons too."""
        code = """
def check_input(text: str) -> str:
    if text != "stop":
        return "continue"
    return "halt"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-001" for f in findings)


# =============================================================================
# WHD-002: Membership test tests
# =============================================================================


class TestWHD002MembershipTest:
    """Tests for membership test detection (WHD-002)."""

    def test_detects_list_membership_in_protected_module(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag membership tests against lists."""
        code = """
def classify(message: str) -> str:
    greetings = ["hello", "hi", "hey"]
    if message in greetings:
        return "greeting"
    return "other"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-002" for f in findings)

    def test_detects_set_membership(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag membership tests against sets."""
        code = """
def check_topic(text: str) -> bool:
    topics = {"biology", "anatomy", "chemistry"}
    return text in topics
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-002" for f in findings)

    def test_detects_not_in_membership(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag not-in membership tests."""
        code = """
def filter_message(input_text: str) -> bool:
    blocked_words = ["spam", "ads"]
    if input_text not in blocked_words:
        return True
    return False
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-002" for f in findings)

    def test_does_not_flag_non_string_collections(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Non-string collections should not trigger detection."""
        code = """
def check_numbers(values: list[int]) -> bool:
    valid_values = [1, 2, 3, 4, 5]
    return values in valid_values
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        # Should not detect string vocabulary
        whd_findings = [f for f in findings if f.rule_id == "WHD-002"]
        assert len(whd_findings) == 0


# =============================================================================
# WHD-003: If/elif chain tests
# =============================================================================


class TestWHD003IfElifChain:
    """Tests for if/elif chain detection (WHD-003)."""

    def test_detects_long_if_elif_chain(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag long if/elif chains."""
        code = """
def route_message(message: str) -> str:
    if message == "hello":
        return "greet"
    elif message == "help":
        return "assist"
    elif message == "exam":
        return "exam_flow"
    elif message == "study":
        return "study_mode"
    else:
        return "default"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        chain_findings = [f for f in findings if f.rule_id == "WHD-003"]
        assert chain_findings
        # WHD-003 is documented as review-required, so it must not block.
        assert all(f.severity is Severity.MEDIUM for f in chain_findings)
        assert all(f.blocks_merge is False for f in chain_findings)
        assert all(f.requires_review for f in chain_findings)

    def test_detects_chain_with_mixed_comparisons(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should handle chains with mixed comparison types."""
        code = """
def classify_input(text: str) -> str:
    if text == "greeting":
        return "hello"
    elif text in ["hi", "hey"]:
        return "short_greeting"
    elif text == "question":
        return "answer"
    else:
        return "unknown"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        # Should detect the chain pattern
        assert any(f.rule_id in ("WHD-002", "WHD-003") for f in findings)


# =============================================================================
# WHD-004: Regex matching tests
# =============================================================================


class TestWHD004RegexMatching:
    """Tests for regex pattern detection (WHD-004)."""

    def test_detects_word_boundary_regex(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag regex with word boundaries."""
        # Raw source: the file contains a backslash followed by "b", which is
        # what a real regex word boundary looks like in Python source.
        code = r"""
import re

def check_phrase(text: str) -> bool:
    pattern = r"\bhello\b"
    return bool(re.search(pattern, text))
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        # WHD-004 detects regex with word boundaries in protected modules
        # The pattern \bhello\b has word boundaries, which is suspicious
        assert any(f.rule_id == "WHD-004" for f in findings), (
            "Regex with word boundaries in protected module should be flagged"
        )

    def test_detects_re_match_usage(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag re.match usage with word boundaries."""
        code = r"""
import re

def match_input(message: str) -> bool:
    return bool(re.match(r"\bhelp\b", message))
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        # WHD-004 detects regex with word boundaries in protected modules
        # The pattern \bhelp\b has word boundaries, which is suspicious
        assert any(f.rule_id == "WHD-004" for f in findings), (
            "Regex with word boundaries in protected module should be flagged"
        )

    def test_does_not_flag_simple_validation_regex(
        self, detector: UniversalHardcodingDetector, allowed_module_file: Path
    ) -> None:
        """Legitimate validation regex should not flag in allowed modules."""
        code = r"""
import re

def validate_email(email: str) -> bool:
    pattern = r"[^@]+@[^@]+\.[^@]+"
    return bool(re.match(pattern, email))
"""
        allowed_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(allowed_module_file)

        # Should not detect suspicious patterns
        whd_findings = [f for f in findings if f.rule_id == "WHD-004"]
        assert len(whd_findings) == 0

    def test_detects_word_boundary_in_escaped_string_literal(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """A normal string with escaped backslashes is still a word boundary."""
        code = (
            "import re\n"
            "\n"
            "def check_phrase(text: str) -> bool:\n"
            '    pattern = "\\\\bno\\\\b"\n'
            "    return bool(re.search(pattern, text))\n"
        )
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-004" for f in findings)

    def test_detects_short_word_boundary_literal(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Short word-boundary patterns are detected without the length heuristic."""
        code = r"""
import re

def check_phrase(text: str) -> bool:
    return bool(re.search(r"\bhi\b", text))
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-004" for f in findings)

    def test_does_not_flag_short_validation_regex_in_protected_module(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Short technical validation patterns are not phrase detection."""
        code = r"""
import re

def validate_code(value: str) -> bool:
    return bool(re.fullmatch(r"^\d+$", value))
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert [f for f in findings if f.rule_id == "WHD-004"] == []


# =============================================================================
# WHD-005: Dictionary lookup tests
# =============================================================================


class TestWHD005DictionaryLookup:
    """Tests for dictionary lookup detection (WHD-005)."""

    def test_detects_mapping_variable_with_string_key(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag dictionary lookups with suggestive names."""
        code = """
response_mapping = {
    "hello": "Hi there!",
    "help": "How can I help?",
}

def get_response(message: str) -> str:
    return response_mapping["hello"]
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        whd_findings = [f for f in findings if f.rule_id == "WHD-005"]
        assert len(whd_findings) == 1
        assert whd_findings[0].severity is Severity.MEDIUM
        assert whd_findings[0].blocks_merge is False
        assert whd_findings[0].requires_review is True

    def test_detects_action_mapping(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag action mapping lookups."""
        code = """
action_table = {
    "greeting": greet_user,
    "question": answer_question,
}

def handle(text: str) -> None:
    action = action_table["greeting"]
    action()
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        whd_findings = [f for f in findings if f.rule_id == "WHD-005"]
        assert len(whd_findings) == 1
        assert "action_table" in whd_findings[0].evidence[1]


# =============================================================================
# WHD-007: Literal response tests
# =============================================================================


class TestWHD007LiteralResponse:
    """Tests for literal response detection (WHD-007)."""

    def test_detects_greeting_function(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag functions returning literal greetings."""
        code = """
def get_greeting(name: str) -> str:
    return "Hello, welcome!"

def generate_response() -> str:
    return "How can I help you today?"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-007" for f in findings)

    def test_detects_reply_function(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag reply functions."""
        code = """
def create_reply(user_input: str) -> str:
    return "I understand your question."
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-007" for f in findings)

    def test_detects_speak_function(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag speak/say functions."""
        code = """
def speak(message: str) -> str:
    return "Processing your request..."

def say_hello() -> str:
    return "Hello!"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        assert any(f.rule_id == "WHD-007" for f in findings)


# =============================================================================
# WHD-008: Hardcoded vocabulary tests
# =============================================================================


class TestWHD008HardcodedVocabulary:
    """Tests for hardcoded vocabulary detection (WHD-008)."""

    def test_detects_vocabulary_variable(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag vocabulary variable assignments."""
        code = """
greetings = ["hello", "hi", "hey", "good morning"]

def check_greeting(text: str) -> bool:
    return text in greetings
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        vocabulary_findings = [f for f in findings if f.rule_id == "WHD-008"]
        assert len(vocabulary_findings) == 1
        assert vocabulary_findings[0].blocks_merge is False
        assert vocabulary_findings[0].requires_review is True

    def test_detects_subjects_vocabulary(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag subject-related vocabularies."""
        code = """
subjects = ["biology", "anatomy", "chemistry", "physics"]

def classify_subject(message: str) -> str:
    for subject in subjects:
        if subject in message:
            return subject
    return "unknown"
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        vocabulary_findings = [f for f in findings if f.rule_id == "WHD-008"]
        assert len(vocabulary_findings) == 1
        assert vocabulary_findings[0].blocks_merge is False
        assert vocabulary_findings[0].requires_review is True

    def test_detects_keywords_list(
        self, detector: UniversalHardcodingDetector, protected_module_file: Path
    ) -> None:
        """Detector should flag keyword lists."""
        code = """
keywords = ["exam", "test", "quiz", "study guide"]

def has_keywords(text: str) -> bool:
    return any(kw in text for kw in keywords)
"""
        protected_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(protected_module_file)

        vocabulary_findings = [f for f in findings if f.rule_id == "WHD-008"]
        assert len(vocabulary_findings) == 1
        assert vocabulary_findings[0].blocks_merge is False
        assert vocabulary_findings[0].requires_review is True

    def test_does_not_flag_technical_constants(
        self, detector: UniversalHardcodingDetector, allowed_module_file: Path
    ) -> None:
        """Technical constants should not flag in allowed modules."""
        code = """
# These are technical constants, not conversational vocabulary
SUPPORTED_FORMATS = ["jpg", "png", "gif", "webp"]
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
"""
        allowed_module_file.write_text(code, encoding="utf-8")

        findings = detector.scan_file(allowed_module_file)

        # Should not flag technical constants
        whd_findings = [f for f in findings if f.rule_id == "WHD-008"]
        assert len(whd_findings) == 0


# =============================================================================
# Integration tests
# =============================================================================


class TestIntegration:
    """Integration tests for the detector."""

    def test_scan_directory_returns_all_findings(self, tmp_path: Path) -> None:
        """Scanning a directory should return all findings."""
        # Create test structure
        mod_path = tmp_path / "waxprep" / "messaging"
        mod_path.mkdir(parents=True)

        file_path = mod_path / "test.py"
        file_path.write_text(
            """
def handle(message: str) -> str:
    if message == "hello":
        return "Hi!"
    return "Unknown"
""",
            encoding="utf-8",
        )

        detector = UniversalHardcodingDetector(tmp_path)
        findings = detector.scan_directory(tmp_path)

        assert len(findings) >= 1
        assert any(f.rule_id == "WHD-001" for f in findings)

    def test_report_generation(self, tmp_path: Path) -> None:
        """Detector should generate valid reports."""
        mod_path = tmp_path / "waxprep" / "messaging"
        mod_path.mkdir(parents=True)

        file_path = mod_path / "test.py"
        file_path.write_text(
            """
def process(message: str) -> str:
    if message == "test":
        return "result"
""",
            encoding="utf-8",
        )

        detector = UniversalHardcodingDetector(tmp_path)
        detector.scan_file(file_path)
        report = detector.get_report()

        assert "total_findings" in report
        assert "findings" in report
        assert "rules_triggered" in report
        assert report["total_findings"] >= 1

    def test_has_blocking_findings(self, tmp_path: Path) -> None:
        """Detector should correctly identify blocking findings."""
        mod_path = tmp_path / "waxprep" / "messaging"
        mod_path.mkdir(parents=True)

        file_path = mod_path / "test.py"
        file_path.write_text(
            """
def handle(message: str) -> str:
    if message == "hello":
        return "Hi!"
""",
            encoding="utf-8",
        )

        detector = UniversalHardcodingDetector(tmp_path)
        detector.scan_file(file_path)

        assert detector.has_blocking_findings()

    def test_no_blocking_findings_for_allowed_module(self, tmp_path: Path) -> None:
        """Allowed modules should not have blocking findings."""
        mod_path = tmp_path / "waxprep" / "core"
        mod_path.mkdir(parents=True)

        file_path = mod_path / "test.py"
        file_path.write_text(
            """
def validate_status(status: str) -> bool:
    if status == "active":
        return True
    return False
""",
            encoding="utf-8",
        )

        detector = UniversalHardcodingDetector(tmp_path)
        detector.scan_file(file_path)

        # Should not block
        assert not detector.has_blocking_findings()


# =============================================================================
# Finding serialization tests
# =============================================================================


class TestFindingSerialization:
    """Tests for finding data serialization."""

    def test_finding_to_dict(self) -> None:
        """Finding should serialize correctly to dict."""
        finding = Finding(
            rule_id="WHD-001",
            file_path="test.py",
            line_number=10,
            message="Test finding",
            severity=Severity.HIGH,
            confidence=0.85,
            evidence=["Evidence 1", "Evidence 2"],
            blocks_merge=True,
        )

        result = finding.to_dict()

        assert result["rule_id"] == "WHD-001"
        assert result["file_path"] == "test.py"
        assert result["line_number"] == 10
        assert result["message"] == "Test finding"
        assert result["severity"] == "HIGH"
        assert result["confidence"] == 0.85
        assert result["evidence"] == ["Evidence 1", "Evidence 2"]
        assert result["blocks_merge"] is True
        assert result["is_deterministic"] is True


# =============================================================================
# Data file inspector tests
# =============================================================================


class TestDataFileInspector:
    """Tests for the data file inspector."""

    def test_inspects_json_vocabulary(self, tmp_path: Path) -> None:
        """Inspector should detect JSON vocabulary patterns."""
        data_path = tmp_path / "vocab.json"
        data_path.write_text(
            """
{
    "hello": "greeting_response",
    "hi": "short_greeting",
    "help": "help_response",
    "exam": "exam_flow"
}
""",
            encoding="utf-8",
        )

        from waxprep.detector import DataFileInspector

        inspector = DataFileInspector(tmp_path)
        findings = inspector.inspect_file(data_path)

        # Should detect string-to-string mappings
        assert any(f.rule_id == "WHD-009" for f in findings)

    def test_inspects_yaml_vocabulary(self, tmp_path: Path) -> None:
        """Inspector should detect YAML vocabulary patterns."""
        data_path = tmp_path / "words.yaml"
        data_path.write_text(
            """
words:
  - hello
  - hi
  - help
  - exam
  - study
""",
            encoding="utf-8",
        )

        from waxprep.detector import DataFileInspector

        inspector = DataFileInspector(tmp_path)
        findings = inspector.inspect_file(data_path)

        # Should detect vocabulary list
        assert any(f.rule_id == "WHD-010" for f in findings)


# =============================================================================
# Edge case tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_file(self, detector: UniversalHardcodingDetector, tmp_path: Path) -> None:
        """Empty files should produce no findings."""
        file_path = tmp_path / "empty.py"
        file_path.write_text("", encoding="utf-8")

        findings = detector.scan_file(file_path)

        assert len(findings) == 0

    def test_syntax_error_file(self, detector: UniversalHardcodingDetector, tmp_path: Path) -> None:
        """Files with syntax errors should be skipped gracefully."""
        file_path = tmp_path / "bad_syntax.py"
        file_path.write_text("def broken(:", encoding="utf-8")

        findings = detector.scan_file(file_path)

        assert len(findings) == 0

    def test_non_python_file(self, detector: UniversalHardcodingDetector, tmp_path: Path) -> None:
        """Non-Python files should be skipped."""
        file_path = tmp_path / "readme.txt"
        file_path.write_text("This is not Python", encoding="utf-8")

        findings = detector.scan_file(file_path)

        assert len(findings) == 0

    def test_scans_only_python_files(
        self, detector: UniversalHardcodingDetector, tmp_path: Path
    ) -> None:
        """Directory scan should only process .py files."""
        # Create mixed files
        (tmp_path / "script.py").write_text('if message == "hello": pass', encoding="utf-8")
        (tmp_path / "data.json").write_text('{"key": "value"}', encoding="utf-8")
        (tmp_path / "readme.md").write_text("# README", encoding="utf-8")

        findings = detector.scan_directory(tmp_path)

        # Should only find Python findings
        assert len(findings) >= 1
        assert all(f.rule_id in ("WHD-001",) for f in findings)
