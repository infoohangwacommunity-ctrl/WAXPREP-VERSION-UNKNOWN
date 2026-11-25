"""Dependency and supply-chain security — Stage 09.

Purpose:
    Assess the external software WaxPrep depends on: known vulnerabilities,
    resolved versions, lockfile integrity, dependency sources, licenses,
    malicious-package intelligence, provenance evidence and the runtime SBOM.

Boundary rules:
- Development/deployment tooling only: never imported by the request path.
- Reads ``uv.lock``, ``pyproject.toml`` and ``security/dependency-policy/``.
- Uses pip-audit for vulnerability intelligence, OSV for malicious-package
  reports and the installed distribution metadata for licenses.
- Adds no dependency of its own: policy files and lockfile are TOML.

This package does not install, upgrade, deploy or modify dependencies.
"""

from waxprep.supplychain.checks import Assessment, DependencyRecord, Finding, Severity, assess

__all__ = ["Assessment", "DependencyRecord", "Finding", "Severity", "assess"]
