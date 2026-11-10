"""
AST Analyzer - Main Analyzer Class

Scans Python source code using AST to detect architectural violations.
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Optional, Union
import logging

from .rules import (
    BaseASTRule,
    Violation,
    Severity,
    AST_RULES,
    get_rule_by_id,
    get_all_rules,
)


# Configure logging
logger = logging.getLogger(__name__)


class ASTAnalyzer:
    """
    Main class for AST-based architectural analysis.
    
    Scans Python files and detects violations of WaxPrep's architectural rules.
    """
    
    def __init__(self, 
                 rules: Optional[List[BaseASTRule]] = None,
                 include_patterns: Optional[List[str]] = None,
                 exclude_patterns: Optional[List[str]] = None):
        """
        Initialize the analyzer.
        
        Args:
            rules: List of AST rules to apply. If None, uses all default rules.
            include_patterns: File patterns to include (e.g., ["*.py"])
            exclude_patterns: File patterns to exclude (e.g., ["tests/*", "*_test.py"])
        """
        self.rules = rules or AST_RULES
        self.include_patterns = include_patterns or ["*.py"]
        self.exclude_patterns = exclude_patterns or ["tests/*", "*_test.py", "*/test_*.py"]
        self._violations: List[Violation] = []
        self._files_scanned: int = 0
        self._lines_scanned: int = 0
        
    def scan_file(self, file_path: Union[str, Path]) -> List[Violation]:
        """
        Scan a single Python file for violations.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            List of violations found
        """
        file_path = Path(file_path)
        
        # Check if file should be scanned
        if not self._should_scan_file(file_path):
            logger.debug(f"Skipping {file_path} (excluded by pattern)")
            return []
        
        # Check if file exists
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return []
        
        # Check if file is Python
        if not file_path.name.endswith('.py'):
            logger.debug(f"Skipping {file_path} (not a Python file)")
            return []
        
        logger.info(f"Scanning {file_path}")
        self._files_scanned += 1
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content, filename=str(file_path))
            self._lines_scanned += len(content.splitlines())
            
            # Apply all rules
            violations = []
            for rule in self.rules:
                rule_violations = rule.get_violations(tree, str(file_path))
                violations.extend(rule_violations)
            
            return violations
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error scanning {file_path}: {e}")
            return []
    
    def scan_directory(self, directory: Union[str, Path]) -> List[Violation]:
        """
        Scan all Python files in a directory.
        
        Args:
            directory: Path to the directory to scan
            
        Returns:
            List of all violations found
        """
        directory = Path(directory)
        violations = []
        
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return []
        
        # Find all Python files
        py_files = list(directory.rglob('*.py'))
        logger.info(f"Found {len(py_files)} Python files in {directory}")
        
        # Scan each file
        for py_file in py_files:
            file_violations = self.scan_file(py_file)
            violations.extend(file_violations)
        
        return violations
    
    def scan_paths(self, paths: List[Union[str, Path]]) -> List[Violation]:
        """
        Scan multiple files or directories.
        
        Args:
            paths: List of file or directory paths
            
        Returns:
            List of all violations found
        """
        all_violations = []
        
        for path in paths:
            path = Path(path)
            if path.is_file():
                all_violations.extend(self.scan_file(path))
            elif path.is_dir():
                all_violations.extend(self.scan_directory(path))
        
        return all_violations
    
    def _should_scan_file(self, file_path: Path) -> bool:
        """
        Check if a file should be scanned based on include/exclude patterns.
        """
        file_str = str(file_path)
        
        # Check include patterns
        for pattern in self.include_patterns:
            if file_str.endswith(pattern.replace('*', '')):
                # Check exclude patterns
                for exclude_pattern in self.exclude_patterns:
                    if exclude_pattern in file_str or file_str.endswith(exclude_pattern.replace('*', '')):
                        return False
                return True
        
        return False
    
    def get_violations(self) -> List[Violation]:
        """Get all violations found during the last scan."""
        return self._violations
    
    def get_summary(self) -> Dict:
        """
        Get a summary of the analysis.
        
        Returns:
            Dictionary with analysis statistics
        """
        violations = self._violations
        
        # Count by severity
        by_severity = {}
        for severity in Severity:
            by_severity[severity.value] = len([v for v in violations if v.severity == severity])
        
        # Count by rule
        by_rule = {}
        for violation in violations:
            rule_id = violation.rule_id
            by_rule[rule_id] = by_rule.get(rule_id, 0) + 1
        
        return {
            "files_scanned": self._files_scanned,
            "lines_scanned": self._lines_scanned,
            "total_violations": len(violations),
            "by_severity": by_severity,
            "by_rule": by_rule,
            "violations": [v.to_dict() for v in violations],
        }
    
    def print_summary(self) -> None:
        """Print a human-readable summary of the analysis."""
        summary = self.get_summary()
        
        print("=" * 80)
        print("AST ANALYSIS SUMMARY")
        print("=" * 80)
        print(f"Files scanned: {summary['files_scanned']}")
        print(f"Lines scanned: {summary['lines_scanned']}")
        print(f"Total violations: {summary['total_violations']}")
        print()
        
        print("By Severity:")
        for severity, count in summary['by_severity'].items():
            print(f"  {severity.upper()}: {count}")
        print()
        
        if summary['by_rule']:
            print("By Rule:")
            for rule_id, count in summary['by_rule'].items():
                print(f"  {rule_id}: {count}")
            print()
        
        if summary['violations']:
            print("Violations:")
            for v in summary['violations']:
                print(f"  [{v['severity'].upper()}] {v['rule_id']} at {v['file']}:{v['line']}")
                print(f"    {v['message']}")
                print(f"    Evidence: {v['evidence'][:100]}...")
                print()
        
        print("=" * 80)
    
    def reset(self) -> None:
        """Reset the analyzer state."""
        self._violations = []
        self._files_scanned = 0
        self._lines_scanned = 0


def create_analyzer(**kwargs) -> ASTAnalyzer:
    """
    Factory function to create an AST analyzer with default settings.
    
    Args:
        **kwargs: Arguments to pass to ASTAnalyzer constructor
        
    Returns:
        Configured ASTAnalyzer instance
    """
    return ASTAnalyzer(**kwargs)


def analyze_path(path: Union[str, Path], **kwargs) -> Dict:
    """
    Convenience function to analyze a path and return the summary.
    
    Args:
        path: Path to analyze
        **kwargs: Arguments to pass to ASTAnalyzer constructor
        
    Returns:
        Analysis summary dictionary
    """
    analyzer = create_analyzer(**kwargs)
    violations = analyzer.scan_paths([path])
    analyzer._violations = violations
    return analyzer.get_summary()


if __name__ == "__main__":
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python analyzer.py <path1> [path2 ...]")
        print("  Scan Python files or directories for architectural violations")
        sys.exit(1)
    
    # Get paths from command line
    paths = sys.argv[1:]
    
    # Create analyzer
    analyzer = create_analyzer()
    
    # Scan paths
    violations = analyzer.scan_paths(paths)
    analyzer._violations = violations
    
    # Print summary
    analyzer.print_summary()
    
    # Exit with error if violations found
    if violations:
        sys.exit(1)
