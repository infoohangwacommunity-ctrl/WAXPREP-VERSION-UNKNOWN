"""Lockfile tests for Stage 09."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.supplychain.conftest import lock_entry, write_project
from waxprep.supplychain.lockfile import (
    LockfileError,
    read_lockfile,
    read_requirements,
)


def write_lock(path: Path, blocks: tuple[str, ...], header: str = "version = 1\n") -> Path:
    path.write_text(header + "\n" + "\n".join(blocks), encoding="utf-8")
    return path


def test_reads_repository_lockfile() -> None:
    requirements = read_requirements(Path("pyproject.toml"))
    lock = read_lockfile(Path("uv.lock"), requirements)
    runtime = lock.runtime_closure()

    names = {package.key for package in runtime}
    assert {"fastapi", "uvicorn", "pydantic", "httpx"} <= names
    assert "pytest" not in names  # development-only tool is excluded
    assert all(package.has_hashes for package in runtime)
    assert all(package.source_type == "registry" for package in runtime)
    assert {requirement.group for requirement in requirements} == {"runtime", "dev"}
    assert lock.find("fastapi")
    assert lock.direct("runtime")


def test_runtime_closure_follows_transitive_dependencies(tmp_path: Path) -> None:
    lock_path = write_lock(
        tmp_path / "uv.lock",
        (
            lock_entry("alpha", "1.0.0", dependencies=("beta",)),
            lock_entry("beta", "2.0.0", dependencies=("gamma",)),
            lock_entry("gamma", "3.0.0"),
            lock_entry("devtool", "1.0.0"),
        ),
    )
    requirements = read_requirements(
        write_project(tmp_path / "p", packages=()).joinpath("pyproject.toml")
    )
    lock = read_lockfile(lock_path, requirements)
    assert [package.key for package in lock.runtime_closure()] == ["alpha", "beta", "gamma"]


def test_closure_survives_cycles_and_duplicate_entries(tmp_path: Path) -> None:
    lock_path = write_lock(
        tmp_path / "uv.lock",
        (
            lock_entry("alpha", "1.0.0", dependencies=("beta",)),
            lock_entry("alpha", "9.9.9"),
            lock_entry("beta", "2.0.0", dependencies=("alpha",)),
        ),
    )
    requirements = read_requirements(
        write_project(tmp_path / "p", packages=()).joinpath("pyproject.toml")
    )
    lock = read_lockfile(lock_path, requirements)
    closure = lock.runtime_closure()
    assert [(package.key, package.version) for package in closure] == [
        ("alpha", "1.0.0"),
        ("beta", "2.0.0"),
    ]
    assert len(lock.find("alpha")) == 2
    assert lock.find("missing") == ()


def test_source_types_and_missing_hashes(tmp_path: Path) -> None:
    lock_path = write_lock(
        tmp_path / "uv.lock",
        (
            lock_entry("reg", "1.0", hashed=False),
            lock_entry("gitpkg", "1.0", source='{ git = "https://example.invalid/repo" }'),
            lock_entry("urlpkg", "1.0", source='{ url = "https://example.invalid/pkg.whl" }'),
            lock_entry("pathpkg", "1.0", source='{ path = "../pathpkg" }'),
            lock_entry("editpkg", "1.0", source='{ editable = "../editpkg" }'),
            lock_entry("weird", "1.0", source='{ mystery = "x" }'),
            lock_entry("nosource", "1.0", source=None),
        ),
    )
    requirements = read_requirements(
        write_project(tmp_path / "p", packages=()).joinpath("pyproject.toml")
    )
    lock = read_lockfile(lock_path, requirements)
    types = {package.key: package.source_type for package in lock.packages}
    assert types == {
        "reg": "registry",
        "gitpkg": "vcs",
        "urlpkg": "url",
        "pathpkg": "path",
        "editpkg": "editable",
        "weird": "unknown",
        "nosource": "unknown",
    }
    assert not lock.find("reg")[0].has_hashes
    assert lock.find("reg")[0].purl == "pkg:pypi/reg@1.0"


def test_hashes_are_deduplicated(tmp_path: Path) -> None:
    lock_path = write_lock(
        tmp_path / "uv.lock",
        (
            '[[package]]\nname = "alpha"\nversion = "1.0.0"\n'
            'source = { registry = "https://pypi.org/simple" }\n'
            'sdist = { url = "a", hash = "sha256:same" }\n'
            'wheels = [{ url = "b", hash = "sha256:same" }, { url = "c", hash = "sha256:other" }]\n',
        ),
    )
    requirements = read_requirements(
        write_project(tmp_path / "p", packages=()).joinpath("pyproject.toml")
    )
    lock = read_lockfile(lock_path, requirements)
    assert lock.find("alpha")[0].hashes == ("sha256:same", "sha256:other")


@pytest.mark.parametrize(
    ("header", "blocks", "message"),
    [
        ("version = 2\n", (), "unsupported lockfile version"),
        ("version = 1\npackage = 1\n", (), "'package' must be an array"),
        ("version = 1\n", ('[[package]]\nname = ""\nversion = "1"\n',), "name"),
        ("version = 1\n", ('[[package]]\nname = "a"\nversion = "1"\nsource = 1\n',), "source"),
        (
            "version = 1\n",
            ('[[package]]\nname = "a"\nversion = "1"\ndependencies = 1\n',),
            "expected an array",
        ),
        (
            "version = 1\n",
            ('[[package]]\nname = "a"\nversion = "1"\ndependencies = [{ marker = "x" }]\n',),
            "dependencies",
        ),
        (
            "version = 1\n",
            ('[[package]]\nname = "a"\nversion = "1"\nwheels = [1]\n',),
            "expected a table",
        ),
        (
            "version = 1\n",
            ('[[package]]\nname = "a"\nversion = "1"\nsource = { registry = 1 }\n',),
            "expected a string",
        ),
    ],
)
def test_lockfile_validation(
    tmp_path: Path, header: str, blocks: tuple[str, ...], message: str
) -> None:
    lock_path = write_lock(tmp_path / "uv.lock", blocks, header=header)
    with pytest.raises(LockfileError, match=message):
        read_lockfile(lock_path, ())


def test_missing_lockfile_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(LockfileError, match="missing file"):
        read_lockfile(tmp_path / "uv.lock", ())


def test_requirement_parsing_and_errors(tmp_path: Path) -> None:
    project = write_project(
        tmp_path / "p",
        packages=(),
        dependencies=("alpha", "beta[extra]>=2,<3", "gamma>=1; python_version > '3.13'"),
    )
    requirements = read_requirements(project / "pyproject.toml")
    assert [(item.name, item.specifier) for item in requirements[:3]] == [
        ("alpha", ""),
        ("beta", ">=2,<3"),
        ("gamma", ">=1"),
    ]

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1"\ndependencies = ["!!bad"]\n',
        encoding="utf-8",
    )
    with pytest.raises(LockfileError, match="invalid requirement"):
        read_requirements(broken / "pyproject.toml")


@pytest.mark.parametrize(
    "content",
    [
        '[project]\ndependencies = "alpha"\n',
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = "pytest"\n',
        'project = "x"\n',
        "not toml [",
    ],
)
def test_pyproject_validation(tmp_path: Path, content: str) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(LockfileError):
        read_requirements(path)
