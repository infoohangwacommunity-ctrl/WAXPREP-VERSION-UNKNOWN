# Stage 09 — Dependency and Supply-Chain Security

> **Scope:** the external software WaxPrep depends on, and the integrity of the
> process that brings it into the application. It is separate from Stage 08,
> which inspects WaxPrep's own source for prohibited patterns.

Stage 09 is development and release tooling. It is never imported by the
request path, never installs or upgrades a dependency, and adds no runtime
service or database.

## Architecture

The stage follows a hybrid model, using the existing Quality Gate rather than
creating a second one:

| Workflow | Responsibility |
| --- | --- |
| `.github/workflows/quality-gate.yml` | Blocking dependency trust gate on every push and pull request |
| `.github/workflows/dependency-review.yml` | Pull-request review of newly introduced vulnerabilities and licenses |
| `.github/workflows/dependency-security.yml` | Weekly scheduled monitoring, trust report and SBOM artifacts |
| `.github/dependabot.yml` | Proposes version and security updates; never approves or merges them |

The implementation lives in `src/waxprep/supplychain/`:

| Module | Responsibility |
| --- | --- |
| `policy.py` | Exception register, license policy, source policy, dependency inventory |
| `lockfile.py` | `uv.lock` / `pyproject.toml` parsing and runtime dependency closure |
| `audit.py` | Runs pip-audit and parses its JSON report |
| `licenses.py` | License resolution from installed distribution metadata |
| `osv.py` | OSV batch lookup for malicious-package (`MAL-`) advisories |
| `checks.py` | Combines evidence into blocking, review and informational findings |
| `report.py` | Gate summary and Dependency Trust Intelligence report |
| `sbom.py` | CycloneDX 1.5 SBOM for the resolved runtime set |
| `cli.py` | `check`, `trust`, `sbom` commands |

Policies are TOML parsed with the standard library, not YAML, so the gate adds
no dependency of its own.

## The six components

### 09.1 Vulnerability scanning and exception management

pip-audit remains the only blocking vulnerability scanner. The gate runs it
without `--ignore-vuln`; exceptions are applied afterwards from
`security/dependency-policy/vulnerability-exceptions.toml`.

An exception covers one advisory, one package and explicit affected versions.
It cannot cover a different package, an alias-only match for another version,
or a newly resolved version. Expired exceptions block the gate whether or not
the advisory still appears. See
[DEPENDENCY_EXCEPTION_POLICY.md](DEPENDENCY_EXCEPTION_POLICY.md).

### 09.2 Dependency version and source verification

- Every direct runtime dependency must declare a version constraint.
- Every direct runtime dependency must be resolved in `uv.lock`.
- Every direct runtime dependency must have a documented purpose and owner in
  `dependency-inventory.toml`.
- A resolved major version must be listed under `reviewed_majors` in
  `source-policy.toml`; otherwise it is a review finding.
- Runtime packages must resolve from an allowed registry. Git, direct URL,
  path, editable and unknown sources are blocking unless policy explicitly
  allows them (both are disabled).

### 09.3 Lockfile and artifact integrity

`uv.lock` is mandatory and must declare version 1. `uv lock --check` and
`uv sync --frozen` remain in CI and in the documented deployment procedure.
Every registry package in the runtime closure must carry at least one hash
from `uv.lock`; missing hashes block.

The gate reads the lockfile, not the installed environment, for resolution,
source and hash facts.

### 09.4 License compliance

License policy uses SPDX identifiers with three lists: `approved`, `review`
and `prohibited`. Compound expressions pass only when every atom is approved
or explicitly accepted. Licenses are read from installed distribution
metadata (`License-Expression`, then legacy `License`, then trove
classifiers).

A review-required or unknown license blocks the gate until a human records the
acceptance, with an owner, reason and re-review date, in the `[reviewed]`
table of `license-policy.toml`. A warning nobody has to resolve is not enough.
The `allow_licenses` list in `.github/dependency-review-config.yml` must match
the internal `approved` list exactly; the gate fails when they disagree, so a
review-required license cannot be approved silently by the pull-request
workflow.

### 09.5 Suspicious package and provenance checks

- Source restrictions prevent dependency confusion and unexpected origins.
- OSV is queried by exact resolved name and version; any `MAL-` advisory
  blocks.
- An OSV transport or parsing failure is a review finding, never a silent
  pass.
- Provenance is reported as `not-verified`. A clean OSV result is not treated
  as proof of provenance, and this gate does not claim PyPI attestations were
  checked.

### 09.6 Updates, dependency review and SBOM

Dependabot uses the `uv` ecosystem, because WaxPrep resolves dependencies with
uv and commits `uv.lock`; the `pip` ecosystem does not understand that
lockfile. It proposes grouped patch/minor updates and individual major
updates. Every Dependabot pull request runs the full Quality Gate, Dependency
Review, and the supply-chain gate; nothing is auto-approved.

The scheduled workflow regenerates the trust report and a CycloneDX 1.5 SBOM,
uploaded as workflow artifacts keyed by commit SHA. The SBOM preserves the
real dependency graph from `uv.lock`: the root application references only its
direct dependencies, and each component references the packages it declares,
so a transitive dependency is never reported as a direct one. SBOMs are not
committed and no SBOM database is introduced.

## Gate policy

| Condition | Result |
| --- | --- |
| Critical or high known vulnerability | Block |
| Any newly introduced moderate vulnerability | Block |
| Known vulnerability covered by a valid scoped exception | Informational |
| Expired exception | Block |
| Malicious-package (`MAL-`) match | Block |
| Unapproved dependency source | Block |
| Missing `uv.lock` or inconsistent lockfile | Block |
| Missing artifact hash for a registry package | Block |
| Prohibited license | Block |
| Review-required or unknown license without a `[reviewed]` acceptance | Block |
| Review-required license with a recorded `[reviewed]` acceptance | Informational |
| Dependency Review `allow_licenses` disagrees with the internal policy | Block |
| Direct runtime dependency without documented purpose | Block |
| Unreviewed major version | Review |
| Missing provenance | Informational only |

Blocking findings exit 1. Review and informational findings are printed but do
not fail the gate, so a legitimate review item cannot silently become a
release blocker or vice versa.

## Commands

```bash
# Blocking gate (also runs inside make check / just check and CI)
uv run python -m waxprep.supplychain.cli check --format summary
uv run python -m waxprep.supplychain.cli check --format json

# Dependency Trust Intelligence report
uv run python -m waxprep.supplychain.cli trust --output artifacts/dependency-trust.md

# CycloneDX 1.5 SBOM for the runtime closure
uv run python -m waxprep.supplychain.cli sbom --output artifacts/waxprep-sbom.cdx.json

# Sandbox without network: OSV becomes a review finding
uv run python -m waxprep.supplychain.cli check --offline

# Reproducible exception expiry check
uv run python -m waxprep.supplychain.cli check --today 2026-12-31
```

## Deployment expectations

The dependency set approved by CI must be the set production installs:

- install with the committed lockfile and frozen resolution
  (`uv sync --frozen` with the appropriate extras);
- never resolve, upgrade or install an unpinned dependency at deploy time;
- a failed Quality Gate or dependency gate blocks promotion of that release;
- a deployed release is traceable to its Git commit and its lockfile.

Render/Railway build commands must be inspected before changing them; this
stage does not modify deployment configuration.

## Testing

`tests/supplychain/` covers every control with synthetic fixtures and mocked
scanner output:

- scoped exception matching and expiry (including standalone stale entries);
- missing/unpinned/unresolved direct dependencies and undocumented purposes;
- unapproved registries, VCS/URL/path/unknown sources and missing hashes;
- approved, review, prohibited and unknown licenses, including compound SPDX;
- known advisories, scan unavailability, malicious matches and OSV failure;
- lockfile and `pyproject.toml` structural failures;
- SBOM shape, report rendering, JSON output and CLI exit codes.

No malicious package is installed and no test contacts a live scanner.

## Deliberately not implemented

No custom vulnerability database, AI malware classifier, package reputation
engine, second vulnerability scanner, automatic production upgrades, custom
SBOM database, runtime scanner service, custom lockfile format or automatic
approval of Dependabot pull requests.

## Known limitations

- pip-audit reports known advisories; it cannot prove a package is safe.
- License facts come from installed metadata, not from the source distribution,
  and are an engineering policy rather than legal advice.
- Provenance attestations are not verified; the report says so explicitly.
- OSV malicious-package coverage depends on published OpenSSF reports.
- `uv`'s preview malware check is not enabled; OSV is the intelligence source.
- There is no cross-language or operating-system vulnerability scanning.
- The gate evaluates the runtime closure for inventory/SBOM/licensing, but
  pip-audit audits the installed environment, which also includes dev tools.
  Dev-only advisories still block unless a scoped exception exists.
- Exception review dates are calendar dates, not timezone-aware timestamps.
