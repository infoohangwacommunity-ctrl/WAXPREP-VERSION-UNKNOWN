#!/usr/bin/env python3
"""
AI-Assisted Architectural Reviewer for WaxPrep

This module provides AI-powered review of code changes to detect
architectural violations that static analysis might miss.

Part of Layer 3: AI-Assisted Adversarial Review

The reviewer examines:
1. Educational decision-making in code
2. Hardcoded educational knowledge
3. Architectural boundary violations
4. Suspicious patterns

It provides:
- File and location of violation
- Rule violated
- Explanation
- Evidence
- Confidence level
- Suggestion for fix
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging
import hashlib


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class Severity(Enum):
    """Severity levels for architectural violations."""
    BLOCKING = "blocking"
    WARNING = "warning"
    INFORMATIONAL = "informational"


class Confidence(Enum):
    """Confidence levels for AI reviewer findings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ReviewFinding:
    """A single architectural finding from the AI reviewer."""
    file: str
    line: int
    column: int = 0
    rule_id: str = ""
    rule_name: str = ""
    severity: Severity = Severity.WARNING
    confidence: Confidence = Confidence.MEDIUM
    title: str = ""
    description: str = ""
    explanation: str = ""
    evidence: str = ""
    suggestion: str = ""
    category: str = "architectural"
    
    def to_dict(self) -> Dict:
        """Convert finding to dictionary."""
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "title": self.title,
            "description": self.description,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "category": self.category,
        }
    
    def to_json(self) -> str:
        """Convert finding to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class ReviewReport:
    """Complete review report from the AI reviewer."""
    findings: List[ReviewFinding] = field(default_factory=list)
    summary: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
    def add_finding(self, finding: ReviewFinding) -> None:
        """Add a finding to the report."""
        self.findings.append(finding)
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary."""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "metadata": self.metadata,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def get_summary(self) -> Dict:
        """Get summary statistics."""
        by_severity = {}
        by_category = {}
        by_rule = {}
        
        for finding in self.findings:
            # By severity
            severity = finding.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # By category
            category = finding.category
            by_category[category] = by_category.get(category, 0) + 1
            
            # By rule
            rule_id = finding.rule_id
            by_rule[rule_id] = by_rule.get(rule_id, 0) + 1
        
        return {
            "total_findings": len(self.findings),
            "by_severity": by_severity,
            "by_category": by_category,
            "by_rule": by_rule,
            "blocking": len([f for f in self.findings if f.severity == Severity.BLOCKING]),
            "warning": len([f for f in self.findings if f.severity == Severity.WARNING]),
            "informational": len([f for f in self.findings if f.severity == Severity.INFORMATIONAL]),
        }


class AIArchitecturalReviewer:
    """
    AI-Assisted Architectural Reviewer.
    
    Analyzes code changes to detect architectural violations
    that static analysis might miss.
    """
    
    # Architectural rules definition
    ARCHITECTURAL_RULES = {
        "WAXPREP-ARCH-001": {
            "name": "domain_purity",
            "description": "Domain layer must contain only pure business logic",
            "category": "architecture",
            "severity": Severity.BLOCKING,
            "patterns": [
                r"from waxprep\.(application|adapters|infrastructure)",
                r"import (fastapi|uvicorn|httpx|pydantic)",
            ],
            "suggestion": "Move external dependencies out of domain layer"
        },
        "WAXPREP-ARCH-002": {
            "name": "application_boundaries",
            "description": "Application layer must not contain concrete implementations",
            "category": "architecture",
            "severity": Severity.BLOCKING,
            "patterns": [
                r"FakeChannelAdapter\(\)",
                r"FakeModelAdapter\(\)",
                r"FakeTool\(\)",
            ],
            "suggestion": "Use dependency injection, not direct instantiation"
        },
        "WAXPREP-HARD-001": {
            "name": "no_hardcoded_subjects",
            "description": "No hardcoded educational subject classifications",
            "category": "hardcoding",
            "severity": Severity.BLOCKING,
            "keywords": [
                "anatomy", "biology", "chemistry", "physics", "mathematics",
                "science", "history", "geography", "literature", "art",
            ],
            "suggestion": "Use AI model for subject classification"
        },
        "WAXPREP-HARD-002": {
            "name": "no_hardcoded_student_levels",
            "description": "No hardcoded student categories or levels",
            "category": "hardcoding",
            "severity": Severity.BLOCKING,
            "keywords": [
                "beginner", "intermediate", "advanced",
                "ss1", "ss2", "ss3", "jss1", "jss2", "jss3",
                "primary", "secondary", "undergraduate", "postgraduate",
            ],
            "suggestion": "Use AI model for level assessment"
        },
        "WAXPREP-HARD-003": {
            "name": "no_hardcoded_teaching_methods",
            "description": "No hardcoded teaching methodologies",
            "category": "hardcoding",
            "severity": Severity.BLOCKING,
            "keywords": [
                "explanation", "lecture", "tutorial", "quiz", "test",
                "exam", "assignment", "homework", "exercise",
            ],
            "suggestion": "Use AI model for pedagogical decisions"
        },
        "WAXPREP-HARD-004": {
            "name": "no_hardcoded_responses",
            "description": "No hardcoded educational responses",
            "category": "hardcoding",
            "severity": Severity.BLOCKING,
            "patterns": [
                r'return \"[A-Z][a-z]+ to WaxPrep',
                r'return \"Anatomy is',
                r'return \"Biology is',
                r'return \"Welcome to WaxPrep',
            ],
            "suggestion": "Use AI model to generate response dynamically"
        },
        "WAXPREP-HARD-005": {
            "name": "no_educational_conditionals",
            "description": "No conditional branching on educational strings",
            "category": "hardcoding",
            "severity": Severity.BLOCKING,
            "patterns": [
                r'if \"anatomy\" in',
                r'if \"biology\" in',
                r'if \"chemistry\" in',
                r'if .* == \"anatomy\"',
                r'if .* == \"biology\"',
                r'elif .* == \"chemistry\"',
            ],
            "suggestion": "Use AI model for intent detection"
        },
        "WAXPREP-HARD-006": {
            "name": "no_hidden_educational_dictionaries",
            "description": "No dictionaries containing educational knowledge",
            "category": "hardcoding",
            "severity": Severity.BLOCKING,
            "patterns": [
                r'SUBJECTS\s*=',
                r'TOPICS\s*=',
                r'LEVELS\s*=',
                r'subject_codes\s*=',
            ],
            "suggestion": "Remove educational data from dictionary or use AI model"
        },
    }
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 model: str = "default",
                 confidence_threshold: float = 0.85):
        """
        Initialize the AI reviewer.
        
        Args:
            config_path: Path to configuration file
            model: AI model to use
            confidence_threshold: Minimum confidence for findings
        """
        self.config_path = config_path or ".waxprep/ai_reviewer_config.yaml"
        self.model = model
        self.confidence_threshold = confidence_threshold
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from file."""
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    # Update settings from config
                    if config:
                        self.model = config.get('model', self.model)
                        self.confidence_threshold = config.get(
                            'confidence_threshold', self.confidence_threshold
                        )
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
    
    def review_file(self, file_path: Union[str, Path], content: Optional[str] = None) -> List[ReviewFinding]:
        """
        Review a single file for architectural violations.
        
        Args:
            file_path: Path to the file
            content: File content (if not provided, will be read from file)
            
        Returns:
            List of findings
        """
        file_path = Path(file_path)
        
        if content is None:
            if not file_path.exists():
                return []
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return []
        
        findings = []
        lines = content.splitlines()
        
        # Review each rule
        for rule_id, rule_config in self.ARCHITECTURAL_RULES.items():
            rule_findings = self._check_rule(file_path, content, lines, rule_id, rule_config)
            findings.extend(rule_findings)
        
        return findings
    
    def _check_rule(self, 
                    file_path: Path,
                    content: str,
                    lines: List[str],
                    rule_id: str,
                    rule_config: Dict) -> List[ReviewFinding]:
        """
        Check a single rule against file content.
        
        Args:
            file_path: Path to the file
            content: File content
            lines: File lines
            rule_id: Rule ID
            rule_config: Rule configuration
            
        Returns:
            List of findings for this rule
        """
        findings = []
        
        # Get rule parameters
        name = rule_config.get('name', '')
        description = rule_config.get('description', '')
        category = rule_config.get('category', 'architectural')
        severity = rule_config.get('severity', Severity.WARNING)
        patterns = rule_config.get('patterns', [])
        keywords = rule_config.get('keywords', [])
        suggestion = rule_config.get('suggestion', '')
        
        # Check patterns
        for i, line in enumerate(lines, start=1):
            line_lower = line.lower()
            
            # Check regex patterns
            for pattern in patterns:
                if re.search(pattern, line_lower, re.IGNORECASE):
                    finding = ReviewFinding(
                        file=str(file_path),
                        line=i,
                        rule_id=rule_id,
                        rule_name=name,
                        severity=severity,
                        confidence=Confidence.HIGH,
                        title=f"{rule_id}: {description}",
                        description=description,
                        explanation=f"Pattern '{pattern}' detected in line {i}",
                        evidence=line.strip(),
                        suggestion=suggestion,
                        category=category,
                    )
                    findings.append(finding)
                    break  # Only one finding per line per rule
            
            # Check keywords
            for keyword in keywords:
                if keyword.lower() in line_lower:
                    # Calculate confidence based on context
                    confidence = self._calculate_confidence(line, keyword)
                    if self._get_confidence_value(confidence) >= self.confidence_threshold:
                        finding = ReviewFinding(
                            file=str(file_path),
                            line=i,
                            rule_id=rule_id,
                            rule_name=name,
                            severity=severity,
                            confidence=confidence,
                            title=f"{rule_id}: {description}",
                            description=description,
                            explanation=f"Keyword '{keyword}' detected in line {i}",
                            evidence=line.strip(),
                            suggestion=suggestion,
                            category=category,
                        )
                        findings.append(finding)
                        break  # Only one finding per line per rule
        
        return findings
    
    def _calculate_confidence(self, line: str, keyword: str) -> Confidence:
        """
        Calculate confidence level based on context.
        
        Args:
            line: The line containing the keyword
            keyword: The keyword that was matched
            
        Returns:
            Confidence level
        """
        line_lower = line.lower()
        keyword_lower = keyword.lower()
        
        # High confidence: keyword appears in educational context
        educational_context = [
            'subject', 'topic', 'course', 'lesson', 'chapter',
            'student', 'level', 'grade', 'class', 'teaching',
            'learning', 'educational', 'curriculum', 'syllabus'
        ]
        
        if any(ctx in line_lower for ctx in educational_context):
            return Confidence.HIGH
        
        # Medium confidence: keyword appears in assignment or comparison
        assignment_patterns = ['=', '==', '!=', 'in', 'not in']
        if any(pattern in line for pattern in assignment_patterns):
            return Confidence.MEDIUM
        
        # Low confidence: keyword appears in comment or docstring
        if line.strip().startswith(('#', '"""', "'''")):
            return Confidence.LOW
        
        return Confidence.MEDIUM
    
    def _get_confidence_value(self, confidence: Confidence) -> float:
        """Convert Confidence enum to float value."""
        return {
            Confidence.HIGH: 0.95,
            Confidence.MEDIUM: 0.75,
            Confidence.LOW: 0.50,
        }.get(confidence, 0.0)
    
    def review_directory(self, directory: Union[str, Path]) -> List[ReviewFinding]:
        """
        Review all Python files in a directory.
        
        Args:
            directory: Path to the directory
            
        Returns:
            List of all findings
        """
        directory = Path(directory)
        findings = []
        
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return findings
        
        # Find all Python files (excluding tests)
        py_files = [
            f for f in directory.rglob('*.py')
            if not any(exclude in str(f) for exclude in ['/tests/', '/test_', '_test.py'])
        ]
        
        logger.info(f"Reviewing {len(py_files)} Python files...")
        
        for py_file in py_files:
            file_findings = self.review_file(py_file)
            findings.extend(file_findings)
            
            if file_findings:
                logger.info(f"  {py_file}: {len(file_findings)} findings")
        
        return findings
    
    def review_paths(self, paths: List[Union[str, Path]]) -> List[ReviewFinding]:
        """
        Review multiple paths (files or directories).
        
        Args:
            paths: List of paths to review
            
        Returns:
            List of all findings
        """
        all_findings = []
        
        for path in paths:
            path = Path(path)
            if path.is_file():
                all_findings.extend(self.review_file(path))
            elif path.is_dir():
                all_findings.extend(self.review_directory(path))
        
        return all_findings
    
    def generate_report(self, findings: List[ReviewFinding]) -> ReviewReport:
        """
        Generate a complete review report.
        
        Args:
            findings: List of findings
            
        Returns:
            ReviewReport object
        """
        report = ReviewReport()
        report.findings = findings
        report.summary = report.get_summary()
        report.metadata = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "confidence_threshold": self.confidence_threshold,
            "rules_checked": len(self.ARCHITECTURAL_RULES),
        }
        
        return report
    
    def review_and_report(self, paths: List[Union[str, Path]]) -> ReviewReport:
        """
        Review paths and generate a complete report.
        
        Args:
            paths: List of paths to review
            
        Returns:
            ReviewReport object
        """
        findings = self.review_paths(paths)
        return self.generate_report(findings)


def create_reviewer(**kwargs) -> AIArchitecturalReviewer:
    """
    Factory function to create an AI reviewer.
    
    Args:
        **kwargs: Arguments to pass to AIArchitecturalReviewer constructor
        
    Returns:
        AIArchitecturalReviewer instance
    """
    return AIArchitecturalReviewer(**kwargs)


def review_paths(paths: List[Union[str, Path]], **kwargs) -> ReviewReport:
    """
    Convenience function to review paths and get a report.
    
    Args:
        paths: List of paths to review
        **kwargs: Arguments to pass to AIArchitecturalReviewer constructor
        
    Returns:
        ReviewReport object
    """
    reviewer = create_reviewer(**kwargs)
    return reviewer.review_and_report(paths)


if __name__ == "__main__":
    import sys
    import yaml
    
    if len(sys.argv) < 2:
        print("Usage: python ai_architectural_reviewer.py <path1> [path2 ...]")
        print("  Review Python files or directories for architectural violations")
        print()
        print("Options:")
        print("  --json          Output results as JSON")
        print("  --verbose       Show detailed output")
        print("  --config PATH   Use custom config file")
        print("  --check         Exit with error code if findings found")
        sys.exit(1)
    
    # Parse arguments
    paths = []
    json_output = False
    verbose = False
    config_path = None
    check = False
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--json':
            json_output = True
        elif arg == '--verbose' or arg == '-v':
            verbose = True
        elif arg == '--check':
            check = True
        elif arg == '--config':
            i += 1
            config_path = sys.argv[i]
        else:
            paths.append(arg)
        i += 1
    
    if not paths:
        paths = ['src/waxprep', 'scripts']
    
    # Create reviewer
    reviewer = create_reviewer(config_path=config_path)
    
    # Review paths
    report = reviewer.review_and_report(paths)
    
    # Output results
    if json_output:
        print(report.to_json())
    else:
        # Print summary
        print("=" * 80)
        print("AI ARCHITECTURAL REVIEW REPORT")
        print("=" * 80)
        print()
        print("SUMMARY")
        print("-" * 40)
        summary = report.summary
        print(f"Total findings: {summary['total_findings']}")
        print(f"Blocking: {summary['blocking']}")
        print(f"Warning: {summary['warning']}")
        print(f"Informational: {summary['informational']}")
        print(f"Model: {report.metadata.get('model', 'default')}")
        print(f"Timestamp: {report.metadata.get('timestamp', '')}")
        print()
        
        # Print findings
        if report.findings:
            print("FINDINGS")
            print("-" * 40)
            for finding in report.findings:
                severity_icon = {
                    Severity.BLOCKING: '❌',
                    Severity.WARNING: '⚠️',
                    Severity.INFORMATIONAL: 'ℹ️'
                }.get(finding.severity, '•')
                
                print(f"{severity_icon} [{finding.severity.value.upper()}] {finding.file}:{finding.line}")
                print(f"   Rule: {finding.rule_id} - {finding.rule_name}")
                print(f"   Title: {finding.title}")
                print(f"   Confidence: {finding.confidence.value}")
                if verbose:
                    print(f"   Evidence: {finding.evidence}")
                    print(f"   Suggestion: {finding.suggestion}")
                print()
        else:
            print("✅ No architectural violations detected!")
        
        print("=" * 80)
    
    # Exit with error if check flag is set and findings found
    if check and report.summary['total_findings'] > 0:
        sys.exit(1)
