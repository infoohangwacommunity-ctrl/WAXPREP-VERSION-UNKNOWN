#!/usr/bin/env python3
"""
Quality Gate Test Script - Stage 07

Tests the quality gate locally to ensure it catches violations.
This implements the "gate must be observed to fail" principle.

Usage:
    python scripts/test_quality_gate.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_import_linter() -> tuple[str, bool]:
    """Test that import linter catches violations."""
    print("Testing import linter...")
    
    # Create a temporary file with a violation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
from fastapi import FastAPI
from waxprep.domain.models.result import Result

# This should be caught by the import linter
from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.domain.models.result import Result
""")
        temp_file = Path(f.name)
    
    try:
        # Run the linter
        exit_code, stdout, stderr = run_command(
            [sys.executable, "scripts/lint_imports.py", "--check"],
            cwd=Path(__file__).parent.parent,
        )
        
        if exit_code != 0:
            return "Import linter correctly detected violations", True
        else:
            return "Import linter failed to detect violations", False
    finally:
        temp_file.unlink()


def test_ruff() -> tuple[str, bool]:
    """Test that Ruff catches violations."""
    print("Testing Ruff...")
    
    # Create a temporary file with a violation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
# This should be caught by Ruff
import os
import sys  # unused

def foo():
    pass  # missing docstring
""")
        temp_file = Path(f.name)
    
    try:
        exit_code, stdout, stderr = run_command(
            ["ruff", "check", str(temp_file)],
        )
        
        if exit_code != 0:
            return "Ruff correctly detected violations", True
        else:
            return "Ruff failed to detect violations", False
    finally:
        temp_file.unlink()


def test_pyright() -> tuple[str, bool]:
    """Test that Pyright catches type violations."""
    print("Testing Pyright...")
    
    # Create a temporary file with a type violation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
# This should be caught by Pyright
def foo(x: int) -> str:
    return x  # type error
""")
        temp_file = Path(f.name)
    
    try:
        exit_code, stdout, stderr = run_command(
            ["pyright", str(temp_file)],
        )
        
        if exit_code != 0:
            return "Pyright correctly detected type violations", True
        else:
            return "Pyright failed to detect type violations", False
    finally:
        temp_file.unlink()


def test_bandit() -> tuple[str, bool]:
    """Test that Bandit catches security violations."""
    print("Testing Bandit...")
    
    # Create a temporary file with a security violation
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
import os

# This should be caught by Bandit
password = "hardcoded_password"
api_key = "sk-1234567890abcdef"
""")
        temp_file = Path(f.name)
    
    try:
        exit_code, stdout, stderr = run_command(
            ["bandit", "-r", str(temp_file.parent), "-f", "json"],
        )
        
        # Bandit returns 0 if no issues, 1 if issues found
        if exit_code != 0:
            return "Bandit correctly detected security violations", True
        else:
            return "Bandit failed to detect security violations", False
    finally:
        temp_file.unlink()


def test_tests() -> tuple[str, bool]:
    """Test that tests run and can fail."""
    print("Testing test suite...")
    
    exit_code, stdout, stderr = run_command(
        ["pytest", "tests/", "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
    )
    
    # Tests should pass (exit code 0)
    if exit_code == 0:
        return "All tests passed", True
    else:
        return f"Tests failed with exit code {exit_code}", False


def main() -> int:
    """Run all quality gate tests."""
    print("=" * 60)
    print("Quality Gate Test Suite - Stage 07")
    print("Testing that the gate can be observed to fail")
    print("=" * 60)
    print()
    
    tests = [
        ("Import Linter", test_import_linter),
        ("Ruff", test_ruff),
        ("Pyright", test_pyright),
        ("Bandit", test_bandit),
        ("Test Suite", test_tests),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            message, passed = test_func()
            results.append((name, passed, message))
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status}: {name} - {message}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"❌ ERROR: {name} - {e}")
        print()
    
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for name, result, message in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print()
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All quality gate tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} quality gate tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
