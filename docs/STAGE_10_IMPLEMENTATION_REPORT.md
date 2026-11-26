# Stage 10 — Implementation Report

Scope: turn the existing Stages 05–09 quality systems into an independently
verifiable acceptance system, without redesigning Stage 09, weakening any
threshold, or adding a runtime subsystem.

Baseline commit: `6be6f6ba954ed8f4c0556a34816d999b30575556` (Stage 09 corrections).
This report describes the change applied on top of that baseline.

> The post-implementation review pass is recorded separately in
> `docs/STAGE_10_CORRECTION_REPORT.md`. Where the two disagree, the correction
> report and the current tests are authoritative.

## 1. What changed

| File | Change |
| --- | --- |
| `src/waxprep/ci/acceptance.py` | Pure acceptance engine: `Status`, `CheckClass`, `JobRecord`, `AcceptanceDecision`, `evaluate_acceptance`, `is_full_commit`, declared `REQUIRED_JOBS` / `ADVISORY_JOBS` / `TEST_CATEGORIES` |
| `src/waxprep/ci/evidence.py` | Evidence records (build/write/read/load) and content validation of the coverage XML and CycloneDX SBOM |
| `src/waxprep/ci/report.py` | JSON decision and Markdown summary |
| `src/waxprep/ci/workflows.py` | Workflow audit: YAML validity, least-privilege permissions, SHA pinning, required triggers/jobs, test-matrix reconciliation, evidence recording |
| `src/waxprep/ci/cli.py` | `record`, `accept`, `audit` subcommands |
| `src/waxprep/ci/__init__.py` | Public API; development-time only |
| `.github/workflows/quality-gate.yml` | Now the CI acceptance workflow: `workflow_dispatch`, PR-only cancellation, `ci-audit`, per-job evidence, `supply-chain-evidence`, `ci-acceptance` replacing the previous aggregate |
| `.github/workflows/dependency-review.yml`, `.github/workflows/dependency-security.yml` | Remaining mutable action tags pinned to full commit SHAs |
| `tests/regression/test_ci_*.py` | 86 adversarial tests for acceptance, evidence, CLI/reporting and workflow audit |
| `pyproject.toml` | Description updated; `pyyaml` declared explicitly for the workflow audit (already present via `uvicorn[standard]`) |
| `Makefile`, `justfile` | `ci-audit` target, included in `check` |
| `README.md`, `docs/CONTRIBUTING.md`, `docs/PR_REVIEW_CHECKLIST.md` | Reconciled with the implemented pipeline |
| `docs/STAGE_10_CI_SPECIFICATION.md`, `docs/CI_OPERATIONS.md`, `docs/CI_ACCEPTANCE_POLICY.md`, `docs/CI_SECURITY.md` | New authoritative Stage 10 documentation |
| `.gitignore` | Generated CI evidence and coverage XML excluded |

The previous `gate-aggregate` job was replaced, not supplemented: two decision
makers would be an ambiguity about which one defines acceptance.

## 2. Architectural decisions

1. **The acceptance engine is a pure Python function, not workflow YAML.** Rules
   that only exist in expressions cannot be tested against skipped, cancelled or
   missing results. `evaluate_acceptance` takes records and a commit and returns
   a decision, so every failure mode is covered by regression tests.
2. **Evidence is per job and bound to one commit.** Each job writes
   `ci-evidence/<job>.json` under `if: always()`, so a failed job still produces
   evidence of its failure. Acceptance requires exactly one record per required
   job, classified `blocking`, naming `github.sha`, with status `success`.
3. **Reports are validated by content, not existence.** The coverage XML must
   parse, have a `coverage` root and meet `line-rate` 1.0; the SBOM must declare
   CycloneDX and give every component a `purl`.
4. **Advisory outcomes are recorded honestly.** `pyright` and `vulture` use
   `continue-on-error: true` on the tool step and record that step's *outcome*,
   replacing `|| true`. The job stays green; the failure is visible in evidence
   and in the acceptance report as a warning.
5. **The pipeline audits its own definition.** `ci-audit` fails on a mutable
   action reference, absent `permissions`, a missing trigger/job, a test matrix
   that drifts from `TEST_CATEGORIES`, or a required job that stops recording
   evidence. This makes silent degradation of the gate a CI failure.
6. **`regression` became a matrix category** because the acceptance tests live
   in `tests/regression/`. `tests/detector/` and `tests/supplychain/` continue to
   run in the full-suite coverage job; that is documented instead of being
   presented as separate independent jobs.
7. **No new inspector and no duplicated inspector.** The workflow runs the
   existing systems; `supply-chain-evidence` only *generates* the SBOM and trust
   report required as evidence and runs no additional gate decision.

## 3. Adversarial scenarios proven by tests

`tests/regression/test_ci_acceptance.py`, `test_ci_evidence.py`,
`test_ci_cli.py` and `test_ci_workflows.py` (86 tests):

| Scenario | Expected | Result |
| --- | --- | --- |
| All required jobs success, advisories success | Accepted | Covered |
| Required job `failure` / `cancelled` / `skipped` | Rejected | Covered (parametrised) |
| Required job produced no evidence | Rejected | Covered |
| Required job recorded as advisory | Rejected | Covered |
| Evidence recorded for another commit | Rejected | Covered |
| Duplicate evidence for a required job | Rejected | Covered |
| Malformed or unreadable evidence | Rejected | Covered |
| Assessed commit not a 40-character SHA | Rejected | Covered |
| Advisory failure or missing advisory evidence | Accepted + warning | Covered |
| Unrecognised job evidence | Accepted + warning | Covered |
| Coverage missing / malformed / wrong root / no rate / below 1.0 | Rejected | Covered |
| SBOM missing / not CycloneDX / empty / component without purl | Rejected | Covered |
| Workflow action on a tag or branch | Audit fails | Covered |
| Container action reference | Audit fails | Covered |
| Missing `permissions`, trigger or required job | Audit fails | Covered |
| Test matrix drifting from declared categories | Audit fails | Covered |
| Required job no longer records evidence | Audit fails | Covered |
| Local repository workflows and audit | Clean | `audit PASSED` |

Local end-to-end demonstration of the decision path (synthetic evidence for the
baseline commit, real coverage XML and real generated SBOM):

- with all required evidence `success` and both advisory jobs `failure`:
  `Decision: ACCEPTED`, warnings listed, exit 0;
- after deleting `smoke-test` evidence:
  `REJECTED: required job 'smoke-test' produced no evidence (missing)`, exit 1.

## 4. Verification executed (local)

| Check | Result |
| --- | --- |
| `uv lock --check` | pass |
| `ruff check src/ tests/` | pass |
| `ruff format --check src/ tests/` | 82 files already formatted |
| `mypy src/` (strict) | no issues in 43 source files |
| `import-linter lint` | 4 contracts kept, 0 broken |
| `semgrep --config .semgrep --error` (`src/`) | 0 findings |
| `python -m waxprep.supplychain.cli check` | 20 runtime packages (7 direct), 0 vulnerabilities, 0 blocking |
| `python -m waxprep.detector.cli` | 34 findings, 0 blocking |
| `python -m waxprep.ci.cli audit` | PASSED |
| `pytest tests/ -q --cov=waxprep --cov-fail-under=100` | 596 passed, 1 skipped, 9 xfailed, coverage 100.00% |
| `pytest tests/regression -m regression` | 86 passed (matrix command as CI runs it) |

Coverage of the new package is 100% of statements (410/410).

## 5. Not verified here, and why

- **GitHub Actions execution.** This environment cannot trigger a workflow run,
  and an agent statement is not evidence. The workflow must be observed on the
  Actions tab: `CI — Quality Gate` for the implementation commit should show all
  blocking jobs green and `CI Acceptance — Independent Evidence Verification`
  accepted. If a job fails, the acceptance report names the reason.
- **`Dependency Review` on a pull request.** It is a separate workflow and is not
  consumed by `needs`; it has to be configured as a required check in branch
  protection. This is a documented limitation, not an implemented control.
- **Branch protection.** Deliberately unchanged; direct pushes to `main` remain
  the workflow.
- **Zizmor and OpenSSF Scorecard.** Evaluated and deferred with reasons in
  `docs/CI_SECURITY.md`; neither is a dependency and neither is required for the
  acceptance guarantee.
- **Artifact retention beyond 30/90 days.** Evidence cannot be re-verified after
  its artifact expires.

## 6. Constraints respected

- Python 3.14 + `uv` foundation unchanged; no runtime dependency added.
- Every established quality system preserved; no threshold lowered; no blocking
  check converted to advisory (`pyright` and `vulture` were already advisory).
- Stage 08/09 behaviour untouched apart from pinning workflow action references.
- No application code, request path or deployment configuration modified.
