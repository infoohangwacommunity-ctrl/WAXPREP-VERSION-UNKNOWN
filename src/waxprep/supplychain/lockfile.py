"""Lockfile and requirement reading for Stage 09.

``uv.lock`` is the record of the exact dependency set the team resolved and
approved. The supply-chain gate reads it directly rather than trusting the
installed environment: an environment can drift, the lockfile is what CI and
deployments must install.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from waxprep.supplychain.names import canonical_name, requirement_name, requirement_specifier
from waxprep.supplychain.tomlio import TomlError, as_table, load_table

RUNTIME_GROUP = "runtime"
DEVELOPMENT_GROUP = "dev"


class LockfileError(ValueError):
    """``uv.lock`` or ``pyproject.toml`` is missing or structurally invalid."""


@dataclass(frozen=True)
class LockedPackage:
    """One resolved package entry from ``uv.lock``."""

    name: str
    version: str
    source_type: str
    source_url: str
    dependencies: tuple[str, ...]
    hashes: tuple[str, ...]

    @property
    def key(self) -> str:
        """Canonical package name."""
        return canonical_name(self.name)

    @property
    def purl(self) -> str:
        """Package URL used by the SBOM and reports."""
        return f"pkg:pypi/{self.key}@{self.version}"

    @property
    def has_hashes(self) -> bool:
        """True when the lockfile records at least one artifact hash."""
        return bool(self.hashes)


@dataclass(frozen=True)
class Requirement:
    """A direct requirement declared in ``pyproject.toml``."""

    name: str
    specifier: str
    group: str

    @property
    def key(self) -> str:
        """Canonical package name."""
        return canonical_name(self.name)


@dataclass(frozen=True)
class Lockfile:
    """Parsed lockfile plus the direct requirements it must satisfy."""

    path: Path
    packages: tuple[LockedPackage, ...]
    requirements: tuple[Requirement, ...]

    def find(self, name: str) -> tuple[LockedPackage, ...]:
        """Return every lock entry for a package name."""
        key = canonical_name(name)
        return tuple(package for package in self.packages if package.key == key)

    def direct(self, group: str) -> tuple[Requirement, ...]:
        """Return direct requirements in one dependency group."""
        return tuple(requirement for requirement in self.requirements if requirement.group == group)

    def runtime_closure(self) -> tuple[LockedPackage, ...]:
        """Return the transitive closure of runtime requirements, sorted by name.

        Development-only tools are deliberately excluded: they are not part of
        the production SBOM or the deployed dependency set.
        """
        resolved: dict[str, LockedPackage] = {}
        pending = [requirement.key for requirement in self.direct(RUNTIME_GROUP)]
        while pending:
            key = pending.pop()
            if key in resolved:
                continue
            entries = self.find(key)
            if not entries:
                continue
            package = entries[0]
            resolved[key] = package
            pending.extend(canonical_name(name) for name in package.dependencies)
        return tuple(resolved[key] for key in sorted(resolved))


def _table(value: object, where: str) -> dict[str, object]:
    try:
        return as_table(value, where)
    except TomlError as exc:
        raise LockfileError(str(exc)) from exc


def _required_str(table: dict[str, object], key: str, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LockfileError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def _source(raw: object, where: str) -> tuple[str, str]:
    if raw is None:
        return "unknown", ""
    table = _table(raw, f"{where}.source")
    for source_key, source_type in (
        ("registry", "registry"),
        ("git", "vcs"),
        ("url", "url"),
        ("path", "path"),
        ("editable", "editable"),
    ):
        if source_key in table:
            value = table[source_key]
            if not isinstance(value, str):
                raise LockfileError(f"{where}.source.{source_key}: expected a string")
            return source_type, value
    return "unknown", ""


def _hashes(table: dict[str, object], where: str) -> tuple[str, ...]:
    hashes: list[str] = []
    sdist = table.get("sdist")
    if isinstance(sdist, dict):
        sdist_table = _table(sdist, f"{where}.sdist")
        value = sdist_table.get("hash")
        if isinstance(value, str) and value:
            hashes.append(value)
    wheels = table.get("wheels")
    if isinstance(wheels, list):
        for index, wheel in enumerate(wheels):
            wheel_table = _table(wheel, f"{where}.wheels[{index}]")
            value = wheel_table.get("hash")
            if isinstance(value, str) and value:
                hashes.append(value)
    return tuple(dict.fromkeys(hashes))


def _dependencies(raw: object, where: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise LockfileError(f"{where}.dependencies: expected an array")
    names: list[str] = []
    for index, item in enumerate(raw):
        table = _table(item, f"{where}.dependencies[{index}]")
        names.append(_required_str(table, "name", f"{where}.dependencies[{index}]"))
    return tuple(names)


def _package(value: object, where: str) -> LockedPackage:
    table = _table(value, where)
    source_type, source_url = _source(table.get("source"), where)
    return LockedPackage(
        name=_required_str(table, "name", where),
        version=_required_str(table, "version", where),
        source_type=source_type,
        source_url=source_url,
        dependencies=_dependencies(table.get("dependencies"), where),
        hashes=_hashes(table, where),
    )


def _requirement(text: str, group: str) -> Requirement:
    try:
        return Requirement(
            name=requirement_name(text),
            specifier=requirement_specifier(text),
            group=group,
        )
    except ValueError as exc:
        raise LockfileError(f"invalid requirement {text!r}: {exc}") from exc


def read_requirements(pyproject_path: Path) -> tuple[Requirement, ...]:
    """Read runtime and development requirements from ``pyproject.toml``."""
    try:
        data = load_table(pyproject_path)
    except TomlError as exc:
        raise LockfileError(str(exc)) from exc
    project = _table(data.get("project"), f"{pyproject_path}.project")
    runtime = project.get("dependencies", [])
    if not isinstance(runtime, list) or not all(isinstance(item, str) for item in runtime):
        raise LockfileError(f"{pyproject_path}.project.dependencies: expected an array of strings")
    optional = _table(
        project.get("optional-dependencies", {}),
        f"{pyproject_path}.project.optional-dependencies",
    )
    dev = optional.get("dev", [])
    if not isinstance(dev, list) or not all(isinstance(item, str) for item in dev):
        raise LockfileError(
            f"{pyproject_path}.project.optional-dependencies.dev: expected an array of strings"
        )
    requirements = [_requirement(text, RUNTIME_GROUP) for text in runtime]
    requirements.extend(_requirement(text, DEVELOPMENT_GROUP) for text in dev)
    return tuple(requirements)


def read_lockfile(lock_path: Path, requirements: tuple[Requirement, ...]) -> Lockfile:
    """Read and validate a ``uv.lock`` file."""
    try:
        data = load_table(lock_path)
    except TomlError as exc:
        raise LockfileError(str(exc)) from exc
    if data.get("version") != 1:
        raise LockfileError(f"{lock_path}: unsupported lockfile version")
    raw_packages = data.get("package")
    if not isinstance(raw_packages, list):
        raise LockfileError(f"{lock_path}: 'package' must be an array of tables")
    packages = tuple(
        _package(item, f"{lock_path}: package #{index + 1}")
        for index, item in enumerate(raw_packages)
    )
    return Lockfile(path=lock_path, packages=packages, requirements=requirements)
