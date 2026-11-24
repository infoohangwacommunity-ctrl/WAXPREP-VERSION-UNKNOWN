# Tests for CLI entry point and quality gate integration (Stage 08)
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from waxprep.detector.cli import main as cli_main
from waxprep.detector.quality_gate import check_hardcoding
from waxprep.detector.quality_gate import main as qg_main
import runpy

# =============================================================================
# CLI tests
# =============================================================================


def test_cli_default_args(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CLI with args runs detection and returns int."""
    monkeypatch.setattr(sys, "argv", ["detector-cli", str(tmp_path), "--format", "text"])
    result = cli_main()
    assert isinstance(result, int)


def test_cli_json_format(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """CLI with json format prints valid JSON."""
    test_file = tmp_path / "dummy.py"
    test_file.write_text("x = 1\n")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sys, "argv", ["detector-cli", str(tmp_path), "--format", "json"])
    try:
        cli_main()
    finally:
        monkeypatch.undo()
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert "total_findings" in parsed


# =============================================================================
# Quality gate integration tests
# =============================================================================


def test_check_hardcoding_returns_result(tmp_path: Path) -> None:
    """check_hardcoding returns a CheckResult with expected keys."""
    result = check_hardcoding(tmp_path)
    assert "passed" in result
    assert "blocked" in result
    assert "total_findings" in result
    assert "blocking_findings" in result
    assert "high_severity" in result
    assert "medium_severity" in result
    assert "low_severity" in result
    assert "findings" in result
    assert "summary" in result


def test_check_hardcoding_passed_for_empty_dir(tmp_path: Path) -> None:
    """Empty directory yields passed=True, blocked=False."""
    result = check_hardcoding(tmp_path)
    assert result["passed"] is True
    assert result["blocked"] is False
    assert result["total_findings"] == 0


def test_check_hardcoding_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """check_hardcoding with json format prints valid JSON."""
    check_hardcoding(tmp_path, output_format="json")
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["passed"] is True


def test_check_hardcoding_json_output_file(tmp_path: Path) -> None:
    """check_hardcoding writes JSON report when json_output_path is given."""
    out_file = tmp_path / "report.json"
    check_hardcoding(tmp_path, output_format="json", json_output_path=out_file)
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["passed"] is True


def test_check_hardcoding_summary_format(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """check_hardcoding with summary format prints human-readable summary."""
    check_hardcoding(tmp_path, output_format="summary")
    captured = capsys.readouterr()
    assert "Universal Hardcoding Detection:" in captured.out


def test_check_hardcoding_unknown_format_falls_back_to_summary(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Unknown format falls back to summary output."""
    check_hardcoding(tmp_path, output_format="unknown")
    captured = capsys.readouterr()
    assert "Universal Hardcoding Detection:" in captured.out


def test_qg_main_cli_parser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quality gate CLI parses args and returns appropriate exit code."""
    monkeypatch.setattr(sys, "argv", ["qg", str(tmp_path), "--format", "json"])
    exit_code = qg_main()
    assert exit_code == 0


def test_qg_main_continue_on_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--continue-on-warning returns 0 for non-blocking findings."""
    monkeypatch.setattr(sys, "argv", ["qg", str(tmp_path), "--continue-on-warning"])
    exit_code = qg_main()
    assert exit_code == 0


def test_cli_name_main_block(tmp_path: Path) -> None:
    """CLI __main__ block covers line 19 of cli.py."""
    test_file = tmp_path / "dummy.py"
    test_file.write_text("x = 1\n")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.argv = ['cli', '{tmp_path}', '--format', 'text']; "
            f"from waxprep.detector.cli import main; sys.exit(main())",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_qg_name_main_block(tmp_path: Path) -> None:
    """Quality gate __main__ block covers line 179 of quality_gate.py."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.argv = ['qg', '{tmp_path}', '--format', 'json']; "
            f"from waxprep.detector.quality_gate import main; sys.exit(main())",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_name_main_direct_script(tmp_path: Path) -> None:
    """Direct script execution covers cli.py __main__ block."""
    test_file = tmp_path / "dummy.py"
    test_file.write_text("x = 1\n")
    result = subprocess.run(
        [sys.executable, "src/waxprep/detector/cli.py", str(tmp_path), "--format", "text"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result.returncode == 0


def test_cli_main_block_sys_exit(tmp_path: Path) -> None:
    """Test that __main__ block executes sys.exit(main()) correctly.

    This test verifies line 35 of cli.py: sys.exit(main())
    By running the script directly and checking the exit code,
    we ensure the __main__ block is exercised end-to-end.
    """
    test_file = tmp_path / "dummy.py"
    test_file.write_text("x = 1\n")

    # Run as a module (triggers __main__ block with sys.exit)
    result = subprocess.run(
        [sys.executable, "-m", "waxprep.detector.cli", str(tmp_path), "--format", "text"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    # Exit code 0 means no blocking findings (expected for clean test file)
    assert result.returncode == 0
    # Verify output - detector may report "No hardcoded patterns" for clean files
    # The key is that the __main__ block executed and sys.exit was called
    assert result.returncode == 0  # Confirms sys.exit(main()) worked


def test_qg_name_main_direct_script(tmp_path: Path) -> None:
    """Direct script execution covers quality_gate.py __main__ block."""
    result = subprocess.run(
        [
            sys.executable,
            "src/waxprep/detector/quality_gate.py",
            str(tmp_path),
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert result.returncode == 0


def test_cli_main_function_coverage(tmp_path: Path) -> None:
    """Test main() function directly to ensure coverage of CLI logic.

    This test covers the main() function and its interaction with
    run_detection, ensuring the CLI argument parsing and execution
    path is covered.
    """
    test_file = tmp_path / "dummy.py"
    test_file.write_text("x = 1\n")

    # Import and call main directly (simulates __main__ block behavior)
    from waxprep.detector.cli import main

    # Set up sys.argv as the CLI would see it
    old_argv = sys.argv
    try:
        sys.argv = ["cli", str(tmp_path), "--format", "text"]
        exit_code = main()
        assert exit_code == 0  # No blocking findings for clean file
    finally:
        sys.argv = old_argv


def test_cli_main_block_execution(tmp_path: Path) -> None:
    """Test __main__ block execution to cover line 33 of cli.py.

    This test uses runpy to execute cli.py as a module in-process,
    which ensures the __main__ block (if __name__ == "__main__":
    sys.exit(main())) is executed and counted by coverage.
    """
    test_file = tmp_path / "dummy.py"
    test_file.write_text("x = 1\n")

    # Use runpy to execute the module in-process (coverage counts this)
    old_argv = sys.argv
    try:
        sys.argv = ["cli", str(tmp_path), "--format", "text"]
        # runpy.run_path executes the file with __name__ == "__main__"
        # This triggers the __main__ block and sys.exit()
        try:
            runpy.run_path(
                str(
                    Path(__file__).resolve().parent.parent.parent
                    / "src"
                    / "waxprep"
                    / "detector"
                    / "cli.py"
                ),
                run_name="__main__",
            )
        except SystemExit as e:
            # sys.exit() raises SystemExit, which is expected
            assert e.code == 0, f"Expected exit code 0, got {e.code}"
    finally:
        sys.argv = old_argv
