"""Synthetic Stage 09 projects.

Fixtures never install or contact a malicious package. They build a harmless
lockfile, pyproject and policy set whose shapes exercise the gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REGISTRY = '{ registry = "https://pypi.org/simple" }'


def lock_entry(
    name: str,
    version: str,
    *,
    source: str | None = REGISTRY,
    dependencies: tuple[str, ...] = (),
    hashed: bool = True,
) -> str:
    """Build one synthetic ``uv.lock`` package block."""
    lines = [f"name = {name!r}", f"version = {version!r}"]
    if source is not None:
        lines.append(f"source = {source}")
    if dependencies:
        deps = ", ".join(f"{{ name = {dependency!r} }}" for dependency in dependencies)
        lines.append(f"dependencies = [{deps}]")
    if hashed:
        lines.append(
            f'sdist = {{ url = "https://files.pythonhosted.org/{name}.tar.gz", '
            f'hash = "sha256:{name}" }}'
        )
        lines.append(
            f'wheels = [{{ url = "https://files.pythonhosted.org/{name}.whl", '
            f'hash = "sha256:{name}" }}]'
        )
    return "\n".join(["[[package]]", *lines]) + "\n"


def write_project(
    root: Path,
    *,
    packages: tuple[str, ...],
    dependencies: tuple[str, ...] = ("alpha>=1.0",),
    dev: tuple[str, ...] = ("pytest>=9.2.0",),
    exceptions: str = "exceptions = []\n",
    approved: tuple[str, ...] = ("MIT",),
    review: tuple[str, ...] = (),
    prohibited: tuple[str, ...] = ("GPL-3.0-only",),
    reviewed_majors: str = "[reviewed_majors]\nalpha = [1]\n",
    purpose: str = '[purpose]\nalpha = "test dependency"\n',
    owner: str = '[owner]\nalpha = "team"\n',
) -> Path:
    """Write a complete synthetic project and return its root."""
    root.mkdir(parents=True, exist_ok=True)
    deps = ",\n".join(f'    "{item}"' for item in dependencies)
    dev_deps = ",\n".join(f'    "{item}"' for item in dev)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "synthetic"\n'
        'version = "0.1.0"\n'
        "dependencies = [\n"
        f"{deps}\n"
        "]\n"
        "[project.optional-dependencies]\n"
        "dev = [\n"
        f"{dev_deps}\n"
        "]\n",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text("version = 1\n\n" + "\n".join(packages), encoding="utf-8")

    policy = root / "security" / "dependency-policy"
    policy.mkdir(parents=True, exist_ok=True)
    (policy / "vulnerability-exceptions.toml").write_text(exceptions, encoding="utf-8")
    (policy / "license-policy.toml").write_text(
        "approved = [" + ", ".join(repr(item) for item in approved) + "]\n"
        "review = [" + ", ".join(repr(item) for item in review) + "]\n"
        "prohibited = [" + ", ".join(repr(item) for item in prohibited) + "]\n",
        encoding="utf-8",
    )
    (policy / "source-policy.toml").write_text(
        'allowed_registries = ["https://pypi.org/simple"]\n'
        "allow_vcs = false\n"
        "allow_url = false\n" + reviewed_majors,
        encoding="utf-8",
    )
    (policy / "dependency-inventory.toml").write_text(purpose + owner, encoding="utf-8")
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal valid project: alpha (direct) -> beta (transitive)."""
    return write_project(
        tmp_path / "project",
        packages=(
            lock_entry("alpha", "1.2.3", dependencies=("beta",)),
            lock_entry("beta", "2.0.0"),
            lock_entry("tool", "1.0.0"),
        ),
    )
