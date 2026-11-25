"""pip-audit integration for Stage 09.

pip-audit remains the single blocking vulnerability scanner. This module only
runs it and parses its JSON report; exception decisions are made by the gate
afterwards, scoped to one advisory, one package and explicit versions. The
scanner is never given a blanket advisory-wide ignore.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_TIMEOUT_SECONDS = 300
PIP_AUDIT_COMMAND: tuple[str, ...] = (
    sys.executable,
    "-m",
    "pip_audit",
    "--format",
    "json",
    "--progress-spinner",
    "off",
)


@dataclass(frozen=True)
class Advisory:
    """One vulnerability advisory reported for one resolved package."""

    advisory_id: str
    package: str
    version: str
    aliases: tuple[str, ...] = ()
    fix_versions: tuple[str, ...] = ()
    description: str = ""

    @property
    def identifiers(self) -> tuple[str, ...]:
        """Every identifier that may be used to reference this advisory."""
        return (self.advisory_id, *self.aliases)


@dataclass(frozen=True)
class AuditOutcome:
    """Result of a vulnerability scan."""

    advisories: tuple[Advisory, ...]
    error: str | None = None


def _table(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object")
    return {str(key): item for key, item in value.items()}


def _string_list(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{where}: expected an array of strings")
    return tuple(str(item) for item in value)


def parse_audit_report(payload: object) -> tuple[Advisory, ...]:
    """Parse pip-audit's JSON report into advisories.

    Raises:
        ValueError: when the payload does not have the documented shape.
    """
    document = _table(payload, "audit report")
    dependencies = document.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("audit report: 'dependencies' must be an array")

    advisories: list[Advisory] = []
    for index, item in enumerate(dependencies):
        dependency = _table(item, f"dependencies[{index}]")
        name = dependency.get("name")
        version = dependency.get("version")
        # pip-audit emits entries it could not audit (for example the local
        # project itself) with a skip_reason and no version. They carry no
        # advisory; every other entry must have a name and version.
        if not isinstance(version, str) and isinstance(dependency.get("skip_reason"), str):
            continue
        if not isinstance(name, str) or not isinstance(version, str):
            raise ValueError(f"dependencies[{index}]: name and version are required")
        vulnerabilities = dependency.get("vulns", [])
        if not isinstance(vulnerabilities, list):
            raise ValueError(f"dependencies[{index}].vulns: expected an array")
        for vuln_index, vuln in enumerate(vulnerabilities):
            where = f"dependencies[{index}].vulns[{vuln_index}]"
            table = _table(vuln, where)
            advisory_id = table.get("id")
            if not isinstance(advisory_id, str) or not advisory_id:
                raise ValueError(f"{where}: 'id' is required")
            description = table.get("description", "")
            advisories.append(
                Advisory(
                    advisory_id=advisory_id,
                    package=name,
                    version=version,
                    aliases=_string_list(table.get("aliases"), f"{where}.aliases"),
                    fix_versions=_string_list(table.get("fix_versions"), f"{where}.fix_versions"),
                    description=description if isinstance(description, str) else "",
                )
            )
    return tuple(advisories)


def run_pip_audit(
    command: Sequence[str] | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> AuditOutcome:
    """Run pip-audit and return parsed advisories.

    pip-audit exits 1 when it finds vulnerabilities; that is a successful scan,
    not a tool failure. Anything else is reported as an error so the gate
    cannot mistake "scanner broken" for "no vulnerabilities".
    """
    try:
        completed = subprocess.run(
            list(command or PIP_AUDIT_COMMAND),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return AuditOutcome(advisories=(), error=f"pip-audit could not run: {exc}")

    if completed.returncode not in (0, 1):
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        summary = detail[-1] if detail else "no diagnostic output"
        return AuditOutcome(
            advisories=(),
            error=f"pip-audit exited {completed.returncode}: {summary}",
        )

    try:
        payload = json.loads(completed.stdout or "{}")
        return AuditOutcome(advisories=parse_audit_report(payload))
    except (json.JSONDecodeError, ValueError) as exc:
        return AuditOutcome(advisories=(), error=f"pip-audit report is invalid: {exc}")
