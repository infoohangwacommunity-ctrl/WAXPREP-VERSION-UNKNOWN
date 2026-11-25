# Dependency Vulnerability Exception Policy

## Principle

An exception is a tracked, temporary acceptance of one known vulnerability for
one package version. It is not a blanket permission to ignore an advisory.
The scanner is never given `--ignore-vuln`; the gate evaluates each reported
advisory against the register.

## Register

The register is
`security/dependency-policy/vulnerability-exceptions.toml`. Every entry has:

| Field | Purpose |
| --- | --- |
| `advisory` | GHSA or OSV identifier being accepted |
| `package` | Exact affected package name |
| `versions` | Explicit affected versions (not a range expression) |
| `reason` | Why the vulnerability cannot be remediated now |
| `risk` | Exposure assessment, including runtime vs development-only |
| `owner` | Accountable owner |
| `introduced` | Date the exception was accepted |
| `review_by` | Date the exception expires |
| `remediation_evidence` | What was attempted and what would unblock the fix |

An exception matches only when the advisory identifier, canonical package name
and resolved version all match. An exception for `wcmatch 8.5.2` cannot cover
`wcmatch 8.6.0`, another package that shares the advisory, or an advisory
alias for an unaffected version.

## Expiry

An exception is valid through its `review_by` date and expired the day after.
An expired exception blocks the gate even if the advisory no longer appears, so
stale entries cannot accumulate. The evaluation date can be overridden with
`--today YYYY-MM-DD` for reproducibility.

## Adding an exception

1. Confirm the vulnerability is reported by pip-audit for the resolved version.
2. Try remediation first: upgrade, pin a fixed version, or remove the
   dependency.
3. If remediation is blocked, add an entry with a specific reason, an honest
   risk assessment, an owner, and a review date no more than 90 days out.
4. Record the remediation evidence: what was attempted and what upstream change
   would allow removal.
5. Run `uv run python -m waxprep.supplychain.cli check` and confirm the finding
   becomes informational.
6. Mention the exception in the pull request so reviewers see it.

## Removing an exception

Remove the entry when the fixed version is installable, the dependency is gone,
or the advisory is withdrawn. Do not extend a review date without a fresh risk
assessment and new remediation evidence. The gate will fail on expiry, which is
the intended reminder.

## Current exceptions

| Advisory | Package | Versions | Owner | Review by |
| --- | --- | --- | --- | --- |
| GHSA-53pm-wgxf-c6qf | wcmatch | 8.5.2 | WaxPrep Engineering Team | 2026-12-22 |

Reason: Semgrep constrains `wcmatch` to `< 9`, so the fixed release cannot be
installed while the blocking Semgrep scan is kept. `wcmatch` is a
development-only transitive dependency and is not part of the production
runtime closure.

## What is not accepted

- Advisory-wide ignores.
- Exceptions without a package and explicit versions.
- Permanent exceptions with no review date.
- Exceptions that silently cover a newly introduced dependency.
- Extending a review date without remediation evidence.
