# Property-Based Tests for Universal Hardcoding Detector (Stage 08)
#
# These tests use Hypothesis to verify detector behavior across
# a wide range of generated inputs and code patterns.

from __future__ import annotations

import string
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, strategies as st

from waxprep.detector import (
    Finding,
    Severity,
    UniversalHardcodingDetector,
    is_allowed_module,
    is_protected_module,
)


# =============================================================================
# Custom strategies for code generation
# =============================================================================


@st.composite
def input_variable_name(draw) -> str:
    """Generate variable names that resemble student input."""
    prefixes = ["message", "text", "content", "input", "data", "body", "query"]
    suffixes = ["", "_str", "_text", "_msg", "_content", "_data"]

    prefix = draw(st.sampled_from(prefixes))
    suffix = draw(st.sampled_from(suffixes))

    return f"{prefix}{suffix}"


@st.composite
def string_literal(draw) -> str:
    """Generate random string literals."""
    length = draw(st.integers(min_value=1, max_value=20))
    chars = draw(st.lists(
        st.sampled_from(string.ascii_letters + string.digits + " "),
        min_size=length,
        max_size=length,
    ))
    return "".join(chars)


@st.composite
def vocabulary_list(draw, min_size=2, max_size=10) -> list[str]:
    """Generate a list of vocabulary strings."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))

    words = []
    for _ in range(size):
        word_length = draw(st.integers(min_value=2, max_value=15))
        word = draw(st.lists(
            st.sampled_from(string.ascii_lowercase),
            min_size=word_length,
            max_size=word_length,
        ))
        words.append("".join(word))

    return words


# =============================================================================
# Property tests for module boundaries
# =============================================================================


class TestModuleBoundaryProperties:
    """Property-based tests for module boundary classification."""

    def test_protected_module_prefixes(self) -> None:
        """Paths starting with protected prefixes should be detected."""
        protected_patterns = [
            "waxprep/messaging/handler.py",
            "waxprep/context/profile.py",
            "waxprep/services/orchestrator.py",
        ]

        for pattern in protected_patterns:
            assert is_protected_module(pattern), \
                f"Expected {pattern} to be protected"

    def test_allowed_module_prefixes(self) -> None:
        """Paths starting with allowed prefixes should be detected."""
        allowed_patterns = [
            "waxprep/core/protocols.py",
            "waxprep/config.py",
            "waxprep/adapters/fake.py",
        ]

        for pattern in allowed_patterns:
            assert is_allowed_module(pattern), \
                f"Expected {pattern} to be allowed"

    def test_mutually_exclusive_boundaries(self) -> None:
        """A module cannot be both protected and allowed."""
        test_cases = [
            ("waxprep/messaging/handler.py", True, False),
            ("waxprep/core/protocols.py", False, True),
            ("external/module.py", False, False),
        ]

        for path, expected_protected, expected_allowed in test_cases:
            protected = is_protected_module(path)
            allowed = is_allowed_module(path)

            # Protected and allowed should be mutually exclusive
            assert protected != allowed or not (protected and allowed), \
                f"Module {path} cannot be both protected and allowed"


# =============================================================================
# Property tests for detection consistency
# =============================================================================


class TestDetectionConsistency:
    """Property tests for detector consistency."""

    @given(st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5))
    def test_same_code_same_result(self, vocabulary: list[str]) -> None:
        """Same code should produce same findings on multiple runs."""
        with TemporaryDirectory() as tmp_dir:
            detector1 = UniversalHardcodingDetector(tmp_dir)
            detector2 = UniversalHardcodingDetector(tmp_dir)

            # Create identical code
            code = f'''
vocabulary = {vocabulary}

def check(text: str) -> bool:
    return text in vocabulary
'''

            # Write to file
            file_path = Path(tmp_dir) / "test.py"
            file_path.write_text(code, encoding="utf-8")

            # Run detector twice
            findings1 = detector1.scan_file(file_path)
            findings2 = detector2.scan_file(file_path)

            # Results should be identical
            assert len(findings1) == len(findings2), \
                "Detector should be deterministic"

            for f1, f2 in zip(findings1, findings2):
                assert f1.rule_id == f2.rule_id
                assert f1.line_number == f2.line_number
                assert f1.message == f2.message

    @given(st.integers(min_value=1, max_value=100))
    def test_scan_non_python_directory(self, num_files: int) -> None:
        """Scanning non-Python directories should return no Python findings."""
        with TemporaryDirectory() as tmp_dir:
            detector = UniversalHardcodingDetector(tmp_dir)

            # Create non-Python files
            for i in range(num_files):
                (Path(tmp_dir) / f"file_{i}.txt").write_text(
                    f"Content {i}", encoding="utf-8"
                )

            findings = detector.scan_directory(tmp_dir)

            # No Python files means no findings
            assert len(findings) == 0, \
                "Non-Python files should not produce Python findings"

    def test_syntax_error_handling(self) -> None:
        """Files with syntax errors should not crash detector."""
        with TemporaryDirectory() as tmp_dir:
            detector = UniversalHardcodingDetector(tmp_dir)

            file_path = Path(tmp_dir) / "bad.py"
            file_path.write_text("def broken(:", encoding="utf-8")

            # Should not raise exception
            findings = detector.scan_file(file_path)

            assert isinstance(findings, list)
            assert len(findings) == 0


# =============================================================================
# Property tests for finding properties
# =============================================================================


class TestFindingProperties:
    """Property tests for finding data integrity."""

    @given(
        st.text(min_size=1, max_size=20),
        st.text(min_size=1, max_size=50),
        st.integers(min_value=1, max_value=1000),
        st.text(min_size=1, max_size=100),
        st.floats(min_value=0.0, max_value=1.0),
    )
    def test_finding_serialization_roundtrip(
        self,
        rule_id: str,
        file_path: str,
        line_number: int,
        message: str,
        confidence: float,
    ) -> None:
        """Finding serialization should be reversible."""
        finding = Finding(
            rule_id=rule_id,
            file_path=file_path,
            line_number=line_number,
            message=message,
            severity=Severity.MEDIUM,
            confidence=confidence,
            evidence=["evidence1", "evidence2"],
        )

        serialized = finding.to_dict()
        deserialized = Finding(
            rule_id=serialized["rule_id"],
            file_path=serialized["file_path"],
            line_number=serialized["line_number"],
            message=serialized["message"],
            severity=Severity(serialized["severity"]),
            confidence=serialized["confidence"],
            evidence=serialized["evidence"],
            is_deterministic=serialized["is_deterministic"],
            blocks_merge=serialized["blocks_merge"],
        )

        assert deserialized.rule_id == finding.rule_id
        assert deserialized.file_path == finding.file_path
        assert deserialized.line_number == finding.line_number
        assert deserialized.message == finding.message
        assert deserialized.confidence == finding.confidence
        assert deserialized.evidence == finding.evidence


# =============================================================================
# Property tests for vocabulary detection
# =============================================================================


class TestVocabularyDetectionProperties:
    """Property tests for vocabulary detection patterns."""

    @given(vocabulary_list(min_size=2, max_size=8))
    def test_vocabulary_trigger_detection(self, vocabulary: list[str]) -> None:
        """Vocabularies with multiple terms should be detectable."""
        with TemporaryDirectory() as tmp_dir:
            # Create protected module structure
            mod_path = Path(tmp_dir) / "waxprep" / "messaging"
            mod_path.mkdir(parents=True)

            file_path = mod_path / "vocab_test.py"
            code = f'''
VocabTerms = {vocabulary}

def check(text: str) -> bool:
    return text in VocabTerms
'''
            file_path.write_text(code, encoding="utf-8")

            detector = UniversalHardcodingDetector(tmp_dir)
            findings = detector.scan_file(file_path)

            # Should detect the vocabulary pattern
            whd_findings = [f for f in findings if f.rule_id in ("WHD-002", "WHD-008")]
            assert len(whd_findings) >= 1, \
                f"Vocabulary {vocabulary} should trigger detection"

    @given(st.lists(st.text(min_size=3, max_size=15), min_size=3, max_size=6))
    def test_string_collection_detection(self, strings: list[str]) -> None:
        """Collections of strings should be detectable."""
        # Filter to ensure they look like vocabulary
        vocab_strings = [s for s in strings if s[0].isalpha()]
        if len(vocab_strings) < 2:
            pytest.skip("Not enough alphabetic strings for vocabulary test")

        with TemporaryDirectory() as tmp_dir:
            mod_path = Path(tmp_dir) / "waxprep" / "context"
            mod_path.mkdir(parents=True)

            file_path = mod_path / "collection_test.py"
            code = f'''
terms = {vocab_strings}

def classify(input_text: str) -> str:
    if input_text in terms:
        return "matched"
    return "not_matched"
'''
            file_path.write_text(code, encoding="utf-8")

            detector = UniversalHardcodingDetector(tmp_dir)
            findings = detector.scan_file(file_path)

            # Should detect membership test
            assert any(f.rule_id == "WHD-002" for f in findings), \
                f"Membership test with {vocab_strings} should be detected"


# =============================================================================
# Property tests for protected module enforcement
# =============================================================================


class TestProtectedModuleEnforcement:
    """Property tests for protected module blocking behavior."""

    @given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=3))
    def test_protected_modules_block(self, vocabulary: list[str]) -> None:
        """Findings in protected modules should block when severity is HIGH."""
        with TemporaryDirectory() as tmp_dir:
            mod_path = Path(tmp_dir) / "waxprep" / "messaging"
            mod_path.mkdir(parents=True)

            file_path = mod_path / "blocked_test.py"
            code = f'''
Terms = {vocabulary}

def handle(message: str) -> str:
    if message in Terms:
        return "response"
    return "other"
'''
            file_path.write_text(code, encoding="utf-8")

            detector = UniversalHardcodingDetector(tmp_dir)
            findings = detector.scan_file(file_path)

            # At least one finding should block in protected module
            blocking = [f for f in findings if f.blocks_merge]
            assert len(blocking) >= 1, \
                "Protected module findings should block"

    @given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=3))
    def test_allowed_modules_do_not_block(
        self, vocabulary: list[str]
    ) -> None:
        """Findings in allowed modules should not block."""
        with TemporaryDirectory() as tmp_dir:
            mod_path = Path(tmp_dir) / "waxprep" / "core"
            mod_path.mkdir(parents=True)

            file_path = mod_path / "allowed_test.py"
            code = f'''
TechnicalTerms = {vocabulary}

def validate(code: str) -> bool:
    return code in TechnicalTerms
'''
            file_path.write_text(code, encoding="utf-8")

            detector = UniversalHardcodingDetector(tmp_dir)
            findings = detector.scan_file(file_path)

            # Findings in allowed modules should not block
            blocking = [f for f in findings if f.blocks_merge]
            assert len(blocking) == 0, \
                "Allowed module findings should not block"


# =============================================================================
# Integration property tests
# =============================================================================


class TestIntegrationProperties:
    """Property-based integration tests."""

    def test_full_project_scan_deterministic(self) -> None:
        """Full project scan should produce deterministic results."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create test project structure
            src_path = Path(tmp_dir) / "src" / "waxprep" / "messaging"
            src_path.mkdir(parents=True)

            (src_path / "test.py").write_text(
                '''
def handle(message: str) -> str:
    if message == "hello":
        return "Hi!"
    elif message == "help":
        return "Help!"
    return "Unknown"
''',
                encoding="utf-8",
            )

            detector1 = UniversalHardcodingDetector(tmp_dir)
            detector2 = UniversalHardcodingDetector(tmp_dir)

            findings1 = detector1.scan_project()
            findings2 = detector2.scan_project()

            # Results should be identical
            assert len(findings1) == len(findings2)
            for f1, f2 in zip(findings1, findings2):
                assert f1.to_dict() == f2.to_dict()

    def test_quality_gate_check_returns_correct_status(self) -> None:
        """Quality gate check should return correct pass/blocked status."""
        from waxprep.detector.quality_gate import check_hardcoding
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            mod_path = Path(tmp_dir) / "waxprep" / "messaging"
            mod_path.mkdir(parents=True)

            (mod_path / "test.py").write_text(
                '''
def handle(message: str) -> str:
    if message == "hello":
        return "Hi!"
    return "Unknown"
''',
                encoding="utf-8",
            )

            result = check_hardcoding(tmp_dir)

            assert result["blocked"] is True
            assert result["blocking_findings"] >= 1
            assert result["high_severity"] >= 1


# =============================================================================
# Runner for property tests
# =============================================================================


def test_run_all_property_tests() -> None:
    """This is a marker test to run all property tests via pytest."""
    pass  # Actual tests are marked with @given
