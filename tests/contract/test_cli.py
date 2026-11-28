"""Stage 17 — contract schema CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waxprep.contracts.cli import main
from waxprep.contracts.schema import MANIFEST_FILENAME, build_default_registry

pytestmark = pytest.mark.contract


def write_schema(path: Path, **properties: object) -> Path:
    path.write_text(
        json.dumps({
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }),
        encoding="utf-8",
    )
    return path


class TestGenerateAndCheck:
    def test_generate_then_check_is_clean(self, tmp_path: Path, capsys):
        assert main(["generate", "--output", str(tmp_path)]) == 0
        assert "Wrote 3 contract schema files" in capsys.readouterr().out
        assert main(["check", "--schemas", str(tmp_path)]) == 0
        assert "in sync" in capsys.readouterr().out

    def test_check_reports_missing_and_changed(self, tmp_path: Path, capsys):
        registry = build_default_registry()
        registry.write_to(tmp_path)
        (tmp_path / MANIFEST_FILENAME).unlink()
        schema = next(path for path in tmp_path.glob("*.schema.json"))
        schema.write_text("{}\n", encoding="utf-8")

        assert main(["check", "--schemas", str(tmp_path)]) == 1
        output = capsys.readouterr().out
        assert "missing contract schema" in output
        assert "changed contract schema" in output
        assert "generate" in output

    def test_list_prints_identities(self, capsys):
        assert main(["list"]) == 0
        printed = json.loads(capsys.readouterr().out)
        assert "waxprep.operation.result@1.0.0" in printed["contracts"]


class TestCompatibilityCommand:
    def test_compatible_change_returns_zero(self, tmp_path: Path, capsys):
        old = write_schema(tmp_path / "old.json", name={"type": "string"})
        new = write_schema(
            tmp_path / "new.json",
            name={"type": "string"},
            note={"type": "string"},
        )
        # The new property is required in this fixture; make it optional.
        payload = json.loads(new.read_text(encoding="utf-8"))
        payload["required"] = ["name"]
        new.write_text(json.dumps(payload), encoding="utf-8")

        assert main(["compat", "--old", str(old), "--new", str(new)]) == 0
        output = capsys.readouterr().out
        assert "classification: compatible" in output
        assert "add_optional_field" in output

    def test_breaking_change_returns_one(self, tmp_path: Path, capsys):
        old = write_schema(tmp_path / "old.json", name={"type": "string"})
        new = write_schema(tmp_path / "new.json")
        assert main(["compat", "--old", str(old), "--new", str(new)]) == 1
        output = capsys.readouterr().out
        assert "classification: breaking" in output
        assert "recommended bump: major" in output

    def test_missing_arguments_exit(self):
        with pytest.raises(SystemExit):
            main([])


def test_module_entrypoint(monkeypatch, capsys):
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["waxprep-contracts", "list"])
    monkeypatch.delitem(sys.modules, "waxprep.contracts.cli", raising=False)
    with pytest.raises(SystemExit) as raised:
        runpy.run_module("waxprep.contracts.cli", run_name="__main__")
    assert raised.value.code == 0
    assert "waxprep.operation.result@1.0.0" in capsys.readouterr().out
