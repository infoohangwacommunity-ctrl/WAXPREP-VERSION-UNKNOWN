"""
Detector Verification: AST Analyzer Tests

These tests verify that the AST analyzer correctly detects
architectural violations.

Part of Deliverable 3: Detector Verification
"""

import pytest
from pathlib import Path
import sys
import os

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Import the AST analyzer
try:
    from ast_analyzer.analyzer import ASTAnalyzer, create_analyzer
    from ast_analyzer.rules import (
        HardcodedStringsRule,
        HiddenDictionaryRule,
        HardcodedResponseRule,
        EducationalConditionalRule,
        Severity,
    )
    ANALYZER_AVAILABLE = True
except ImportError as e:
    ANALYZER_AVAILABLE = False
    print(f"AST Analyzer not available: {e}")


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def analyzer():
    """Get an AST analyzer instance."""
    if not ANALYZER_AVAILABLE:
        pytest.skip("AST Analyzer not available")
    return create_analyzer()


class TestHardcodedSubjectsDetection:
    """Test detection of hardcoded subjects."""
    
    def test_detects_hardcoded_subject_list(self, analyzer):
        """Test that hardcoded subject lists are detected."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        fixture_path = FIXTURES_DIR / "hardcoded_subjects.py"
        violations = analyzer.scan_file(fixture_path)
        
        # Should detect violations
        assert len(violations) > 0
        
        # Check for specific rule
        rule_ids = [v.rule_id for v in violations]
        assert "WAXPREP-HARD-006" in rule_ids or "WAXPREP-HARD-001" in rule_ids
    
    def test_detects_subject_dictionary(self, analyzer):
        """Test that subject dictionaries are detected."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        fixture_path = FIXTURES_DIR / "hardcoded_subjects.py"
        violations = analyzer.scan_file(fixture_path)
        
        # Should detect dictionary violations
        assert len(violations) > 0
        
        # Check for dictionary-related violations
        messages = [v.message for v in violations]
        dict_violations = [m for m in messages if "dictionary" in m.lower() or "dict" in m.lower()]
        assert len(dict_violations) > 0


class TestHardcodedStudentLevelsDetection:
    """Test detection of hardcoded student levels."""
    
    def test_detects_hardcoded_levels(self, analyzer):
        """Test that hardcoded student levels are detected."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        fixture_path = FIXTURES_DIR / "hardcoded_student_levels.py"
        violations = analyzer.scan_file(fixture_path)
        
        # Should detect violations
        assert len(violations) > 0
        
        # Check for level-related violations
        messages = [v.message for v in violations]
        level_violations = [m for m in messages if "level" in m.lower() or "beginner" in m.lower()]
        assert len(level_violations) > 0


class TestHardcodedResponsesDetection:
    """Test detection of hardcoded responses."""
    
    def test_detects_hardcoded_responses(self, analyzer):
        """Test that hardcoded responses are detected."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        fixture_path = FIXTURES_DIR / "hardcoded_responses.py"
        violations = analyzer.scan_file(fixture_path)
        
        # Should detect violations
        assert len(violations) > 0
        
        # Check for response-related violations
        rule_ids = [v.rule_id for v in violations]
        assert "WAXPREP-HARD-004" in rule_ids


class TestLegitimateCodeNotFlagged:
    """Test that legitimate code is not flagged."""
    
    def test_legitimate_code_passes(self, analyzer):
        """Test that legitimate code doesn't trigger violations."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        fixture_path = FIXTURES_DIR / "legitimate_code.py"
        violations = analyzer.scan_file(fixture_path)
        
        # Should have NO violations for legitimate code
        # (Note: There might be some false positives initially,
        # but we should aim for zero)
        assert len(violations) == 0, f"Legitimate code flagged with violations: {[v.message for v in violations]}"


class TestAnalyzerSummary:
    """Test analyzer summary functionality."""
    
    def test_summary_structure(self, analyzer):
        """Test that summary has correct structure."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        # Scan a file with violations
        fixture_path = FIXTURES_DIR / "hardcoded_subjects.py"
        violations = analyzer.scan_file(fixture_path)
        analyzer._violations = violations
        
        summary = analyzer.get_summary()
        
        # Check summary structure
        assert "files_scanned" in summary
        assert "lines_scanned" in summary
        assert "total_violations" in summary
        assert "by_severity" in summary
        assert "by_rule" in summary
        assert "violations" in summary
    
    def test_summary_by_severity(self, analyzer):
        """Test that summary correctly counts by severity."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        # Scan a file with violations
        fixture_path = FIXTURES_DIR / "hardcoded_subjects.py"
        violations = analyzer.scan_file(fixture_path)
        analyzer._violations = violations
        
        summary = analyzer.get_summary()
        
        # Check that severity counts add up
        total_by_severity = sum(summary["by_severity"].values())
        assert total_by_severity == summary["total_violations"]


class TestRuleCoverage:
    """Test that all rules are being applied."""
    
    def test_all_rules_available(self, analyzer):
        """Test that all AST rules are available."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        from ast_analyzer.rules import AST_RULES
        
        # Should have multiple rules
        assert len(AST_RULES) >= 4
    
    def test_rule_ids_unique(self, analyzer):
        """Test that all rule IDs are unique."""
        if not ANALYZER_AVAILABLE:
            pytest.skip()
        
        from ast_analyzer.rules import AST_RULES
        
        rule_ids = [rule.rule_id for rule in AST_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
