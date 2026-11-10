#!/usr/bin/env python3
"""
WaxPrep Architectural Analysis Script

This script runs all architectural analysis tools:
1. AST-Based Structural Analysis
2. Import Linter
3. Semgrep (if configured)
4. Architectural Fitness Tests

Usage:
    python scripts/analyze_architecture.py [options] <path>

Options:
    --ast-only           Run only AST analysis
    --import-only        Run only import linter
    --all                Run all analyses (default)
    --check              Exit with error code if violations found
    --json               Output results as JSON
    --verbose            Show detailed output
    --help               Show this help message
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def run_ast_analysis(paths: List[Union[str, Path]], **kwargs) -> Dict:
    """Run AST-based structural analysis."""
    try:
        from ast_analyzer.analyzer import analyze_path
        
        logger.info("Running AST analysis...")
        results = []
        
        for path in paths:
            result = analyze_path(path, **kwargs)
            results.append(result)
        
        # Merge results
        merged = {
            'files_scanned': sum(r.get('files_scanned', 0) for r in results),
            'lines_scanned': sum(r.get('lines_scanned', 0) for r in results),
            'total_violations': sum(r.get('total_violations', 0) for r in results),
            'by_severity': {},
            'by_rule': {},
            'violations': [],
        }
        
        for r in results:
            for severity, count in r.get('by_severity', {}).items():
                merged['by_severity'][severity] = merged['by_severity'].get(severity, 0) + count
            for rule_id, count in r.get('by_rule', {}).items():
                merged['by_rule'][rule_id] = merged['by_rule'].get(rule_id, 0) + count
            merged['violations'].extend(r.get('violations', []))
        
        return {'ast_analysis': merged}
        
    except Exception as e:
        logger.error(f"AST analysis failed: {e}")
        return {'ast_analysis': {'error': str(e)}}


def run_import_linter(paths: List[Union[str, Path]], **kwargs) -> Dict:
    """Run import linter."""
    try:
        from lint_imports import ImportLinter
        
        logger.info("Running import linter...")
        linter = ImportLinter()
        
        # Convert paths to strings
        path_strs = [str(p) for p in paths]
        violations = linter.lint_files(path_strs)
        
        return {
            'import_linter': {
                'violations': [
                    {
                        'file': v.file,
                        'line': v.line,
                        'message': v.message,
                        'severity': 'blocking'
                    }
                    for v in violations
                ],
                'total_violations': len(violations),
                'passed': len(violations) == 0
            }
        }
        
    except Exception as e:
        logger.error(f"Import linter failed: {e}")
        return {'import_linter': {'error': str(e)}}


def run_semgrep(paths: List[Union[str, Path]], **kwargs) -> Dict:
    """Run Semgrep analysis."""
    try:
        import subprocess
        
        logger.info("Running Semgrep...")
        
        # Convert paths to strings
        path_strs = [str(p) for p in paths]
        
        # Run semgrep with waxprep rules
        result = subprocess.run(
            ['semgrep', '--config=.semgrep/waxprep_rules.yml'] + path_strs,
            capture_output=True,
            text=True
        )
        
        # Parse output (simplified)
        output_lines = result.stdout.strip().split('\n') if result.stdout else []
        
        violations = []
        for line in output_lines:
            if 'error' in line.lower() or 'warning' in line.lower():
                violations.append({'message': line})
        
        return {
            'semgrep': {
                'violations': violations,
                'total_violations': len(violations),
                'passed': len(violations) == 0,
                'returncode': result.returncode
            }
        }
        
    except Exception as e:
        logger.error(f"Semgrep failed: {e}")
        return {'semgrep': {'error': str(e), 'skipped': True}}


def run_fitness_tests(**kwargs) -> Dict:
    """Run architectural fitness tests."""
    try:
        import subprocess
        
        logger.info("Running architectural fitness tests...")
        
        result = subprocess.run(
            ['pytest', 'tests/architecture/', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS_DIR.parent)
        )
        
        # Parse output
        passed = 'passed' in result.stdout.lower()
        failed = 'failed' in result.stdout.lower()
        
        return {
            'fitness_tests': {
                'passed': passed and not failed,
                'output': result.stdout,
                'returncode': result.returncode
            }
        }
        
    except Exception as e:
        logger.error(f"Fitness tests failed: {e}")
        return {'fitness_tests': {'error': str(e)}}


def merge_results(results: List[Dict]) -> Dict:
    """Merge multiple analysis results into one."""
    merged = {
        'summary': {
            'total_violations': 0,
            'by_tool': {},
            'passed': True
        },
        'details': {}
    }
    
    for result in results:
        for tool, data in result.items():
            merged['details'][tool] = data
            violations = data.get('total_violations', 0)
            merged['summary']['by_tool'][tool] = violations
            merged['summary']['total_violations'] += violations
            
            if violations > 0 or data.get('passed', True) is False:
                merged['summary']['passed'] = False
    
    return merged


def print_results(results: Dict, verbose: bool = False) -> None:
    """Print analysis results."""
    print("=" * 80)
    print("WAXPREP ARCHITECTURAL ANALYSIS REPORT")
    print("=" * 80)
    print()
    
    # Print summary
    summary = results.get('summary', {})
    print("SUMMARY")
    print("-" * 40)
    print(f"Total violations: {summary.get('total_violations', 0)}")
    print(f"Overall status: {'✅ PASS' if summary.get('passed', False) else '❌ FAIL'}")
    print()
    
    # Print by tool
    print("BY TOOL")
    print("-" * 40)
    for tool, count in summary.get('by_tool', {}).items():
        print(f"  {tool}: {count} violations")
    print()
    
    # Print details for each tool
    for tool, data in results.get('details', {}).items():
        print(f"{tool.upper()}")
        print("-" * 40)
        
        if 'error' in data:
            print(f"  ❌ Error: {data['error']}")
        elif 'skipped' in data:
            print(f"  ⏭️  Skipped: {data.get('skipped', '')}")
        elif 'passed' in data:
            print(f"  Status: {'✅ PASS' if data['passed'] else '❌ FAIL'}")
            if 'total_violations' in data:
                print(f"  Violations: {data['total_violations']}")
        
        if verbose and 'violations' in data:
            for v in data['violations']:
                print(f"    - {v.get('message', v)}")
        
        print()
    
    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='WaxPrep Architectural Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('paths', nargs='*', default=['src/waxprep', 'tests'],
                        help='Paths to analyze (default: src/waxprep tests)')
    parser.add_argument('--ast-only', action='store_true',
                        help='Run only AST analysis')
    parser.add_argument('--import-only', action='store_true',
                        help='Run only import linter')
    parser.add_argument('--all', action='store_true', default=True,
                        help='Run all analyses')
    parser.add_argument('--check', action='store_true',
                        help='Exit with error code if violations found')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed output')
    parser.add_argument('--exclude-tests', action='store_true',
                        help='Exclude test files from analysis')
    
    args = parser.parse_args()
    
    # Convert paths to Path objects
    paths = [Path(p) for p in args.paths]
    
    # Determine which analyses to run
    results = []
    
    if args.all or args.ast_only:
        # Configure AST analyzer
        exclude_patterns = ['tests/*', '*/test_*.py', '*_test.py']
        if args.exclude_tests:
            exclude_patterns.append('tests/*')
        
        ast_result = run_ast_analysis(
            paths,
            exclude_patterns=exclude_patterns
        )
        results.append(ast_result)
    
    if args.all or args.import_only:
        import_result = run_import_linter(paths)
        results.append(import_result)
    
    if args.all:
        semgrep_result = run_semgrep(paths)
        results.append(semgrep_result)
        
        fitness_result = run_fitness_tests()
        results.append(fitness_result)
    
    # Merge results
    merged = merge_results(results)
    
    # Output results
    if args.json:
        print(json.dumps(merged, indent=2))
    else:
        print_results(merged, verbose=args.verbose)
    
    # Exit with error if check flag is set and violations found
    if args.check and not merged['summary'].get('passed', False):
        sys.exit(1)


if __name__ == '__main__':
    main()
