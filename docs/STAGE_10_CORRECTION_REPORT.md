# Stage 10 — Post-Implementation Correction Report

Response to the independent review of commit `9ae47fe` (Stage 10 initial
implementation). The architecture was accepted as the intended direction and was
not redesigned. This pass corrects the verification gaps the review identified.

- Correction commit: `f223389cb4f86a3b1ca380925db3493300ccf241`
- Reviewed commit: `9ae47feff8919463f23f9ea9e70045844ae43d79`
- Workflow run ID: **not available** — see §5.
- Final acceptance result: **local decision path verified; GitHub Actions
  execution not verified.** See §5 before reading this as a completion claim.

## 1. Status statement

The four review issues are corrected in code, tests and documentation, and every
check that can be executed in this environment was executed and passed (§4).

The one requirement this pass **cannot** satisfy is requirement 5, *actual
GitHub Actions execution*. The environment has no GitHub token, no `gh` CLI and
no API access, so no workflow run can be triggered or read from here, and no run
ID can be reported. That requirement therefore remains open. §5 states exactly
what must be observed on the Actions tab and what the acceptance report must say
for Stage 10 to be closed.

## 2. Issues found

| # | Issue | Severity | Status |
| --- | --- | --- | --- |
| 1 | The workflow auditor was mostly a text search: it proved job names and `--job <id>` strings existed, not that acceptance depended on every job, that jobs had timeouts, that evidence artifacts matched their download pattern, or that reports came from the right producer | High — a weakened pipeline could still audit clean | Corrected |
| 2 | Evidence records were weakly validated: `recorded_at` only had to be non-empty, `workflow_run_id` only had to be non-empty, and `exit_code` was never cross-checked against `status`, so a self-contradictory record could be stored | Medium — malformed evidence could look like success | Corrected |
| 3 | Advisory reporting collapsed four different situations into "failure" or "missing": tool passed, tool failed, tool never ran, and job infrastructure failure | Medium — a tool that never ran could read as a tool that failed, and a job that died in setup was indistinguishable | Corrected |
| 4 | `Dependency Review` is a separate workflow and is not part of the acceptance calculation; this had to stay explicit in the security documentation rather than implied | Low — documentation clarity | Corrected |
| 5 | Additional finding: a record's `job` field was not bound to its file name, so `smoke-test.json` could contain a `quality-gate` record and be read under the wrong identity | Medium | Corrected |
| 6 | Additional finding: an evidence upload from a directory other than `ci-evidence/` would still pass the audit, but acceptance downloads what the artifact contains | Medium | Corrected |
| 7 | Additional finding: a job could be added to the workflow that the acceptance policy neither classifies as required nor advisory, with no audit finding | Low | Corrected |

No blocking check was downgraded, no threshold was lowered, and no required job
was removed.

## 3. Corrections

### 3.1 Workflow auditor (`src/waxprep/ci/workflows.py`)

The auditor now parses the job structure (`jobs`, `steps`, `needs`, `if`,
`timeout-minutes`, `with.name`, `with.path` and the recorded evidence commands)
and enforces 18 rules. New checks, each with a regression test that removes
exactly the property it protects:

- `ci-acceptance` must depend on every required job and every advisory job
  (`acceptance-missing-dependency`) and on nothing undeclared
  (`acceptance-unknown-dependency`);
- `ci-acceptance` must run with `if: always()` (`acceptance-not-always`);
- every job must declare a positive `timeout-minutes` (`missing-timeout`);
- evidence is recorded per job for the exact expected id
  (`missing-evidence-recording`) and under the class the policy assigns it
  (`misclassified-evidence`) — a blocking job recorded as advisory, or the
  reverse, is a finding;
- every job uploads `ci-evidence-<job>` (`evidence-artifact-missing`) from
  `ci-evidence/` (`evidence-artifact-mismatch`), and the matrix job uploads
  `ci-evidence-tests-${{ matrix.category }}`;
- acceptance downloads `ci-evidence-*` and both required report artifacts
  (`acceptance-download-mismatch`);
- each required report is produced by its declared job (`coverage-report` by
  `coverage-gate`, `supply-chain-evidence` by `supply-chain-evidence`), and the
  file acceptance validates is that job's actual output in the directory it was
  downloaded to (`report-producer-mismatch`, `acceptance-report-missing`);
- a job that exists but is neither required nor advisory is reported
  (`unregistered-job`);
- a non-mapping job definition is reported (`workflow-invalid`) instead of being
  skipped silently.

`docs/CI_OPERATIONS.md` §8 lists every rule.

### 3.2 Evidence validation (`src/waxprep/ci/evidence.py`)

- job id must be a lowercase identifier (letters, digits, hyphens) and must match
  the record's file name;
- `workflow_run_id` must be `<run id>` or `<run id>-<attempt>`, numeric;
- `recorded_at` must be an ISO 8601 timestamp **with** a timezone;
- `exit_code` must agree with `status`: `success` with a non-zero code, or a
  non-success with code 0, is rejected;
- `phase` (`check` | `setup`) is recorded and validated;
- the same validations run in `build_record`, so the workflow fails at record
  time rather than storing a contradictory record.

The record model is otherwise unchanged, and existing records remain readable
(an absent `phase` defaults to `check`).

### 3.3 Advisory reporting (`src/waxprep/ci/acceptance.py`, `report.py`, workflow)

Advisory jobs record the tool step's own outcome, and the workflow adds
`--phase setup` when that step never ran (`steps.<id>.outcome` is empty, so the
recorded status falls back to the job status). The decision reports one state per
advisory job and the summary renders it in its own table:

| State | Meaning |
| --- | --- |
| `passed` | The tool ran and exited zero |
| `failed` | The tool ran and failed (exit code included when recorded) |
| `not-executed` | The job was skipped, so the tool never ran |
| `infrastructure-failure` | The job failed during setup, before the tool |
| `cancelled` | The run was cancelled before the tool finished |
| `missing` | No evidence was produced at all |
| `stale-evidence` | The record names a different commit |

None of these states changes the decision. They exist so that a check that never
ran is never described as having passed. An advisory record filed as `blocking`
is flagged as ignored.

### 3.4 Acceptance-engine verification

`tests/regression/` now covers, through the public API and the CLI:

failed, cancelled and skipped required jobs; missing evidence; an empty
artifact-download directory; duplicate evidence; stale-commit evidence;
unreadable and malformed evidence (invalid job/file pair, run id, timestamp,
exit code); missing, invalid, wrong-root, non-numeric and below-threshold
coverage; missing, invalid, empty and `purl`-less SBOM; unrecognised job
evidence; advisory pass/fail/never-ran/infrastructure/cancelled/missing/stale;
non-updating `needs`; removed timeouts; artifact-name drift; report-producer
mismatches.

### 3.5 Documentation

`docs/STAGE_10_CI_SPECIFICATION.md` (evidence model, acceptance rules, audit
scope), `docs/CI_ACCEPTANCE_POLICY.md` (decision table, record integrity, audit
enforcement), `docs/CI_OPERATIONS.md` (advisory states, rule table, add-a-job
procedure), `README.md`, `docs/CONTRIBUTING.md` and
`docs/PR_REVIEW_CHECKLIST.md` were reconciled with the implementation.
`docs/CI_SECURITY.md` and the policy continue to state that `Dependency Review`
is separate and is **not** part of the acceptance decision.

## 4. Verification executed (local)

| Check | Command | Result |
| --- | --- | --- |
| Lockfile | `uv lock --check` | pass |
| Lint | `uv run ruff check src/ tests/` | pass |
| Format | `uv run ruff format --check src/ tests/` | pass (82 files) |
| Types | `uv run mypy src/` | pass, 43 files |
| Architecture | `uv run import-linter lint --no-logo` | 4 contracts kept, 0 broken |
| Security | `uv run semgrep --config .semgrep --error --exclude src/waxprep/detector src/` | 0 findings |
| Supply chain | `uv run python -m waxprep.supplychain.cli check --format summary` | 20 packages, 0 vulnerabilities, 0 blocking |
| Hardcoding detector | `uv run python -m waxprep.detector.cli --format summary` | 34 findings, 0 blocking |
| Workflow audit | `uv run python -m waxprep.ci.cli audit` | PASSED |
| Full suite | `uv run pytest tests/ --cov=waxprep --cov-fail-under=100` | **667 passed, 1 skipped, 9 xfailed; coverage 100.00%** |
| Matrix command as CI runs it | `uv run pytest tests/regression -m regression -o addopts=""` | **157 passed** |

Every file in `src/waxprep/ci/` is at 100% statement coverage; the threshold was
not changed.

Local decision-path demonstrations (synthetic records for the correction commit,
real generated SBOM and real coverage XML):

- all required jobs `success`, `pyright` failed with exit code 2, `vulture` in
  `phase: setup` → `Decision: ACCEPTED`, warnings
  `advisory job 'pyright' executed and failed (failure, exit code 2, non-blocking)`
  and `advisory job 'vulture' finished as failure before its check ran:
  infrastructure failure, not a check result (non-blocking)`, exit 0;
- `smoke-test` evidence removed → `REJECTED: required job 'smoke-test' produced
  no evidence (missing)`, exit 1.

These are demonstrations of the decision logic. They are not acceptance evidence
for any commit, and they are not a substitute for §5.

## 5. Actual GitHub Actions execution — NOT provided

Requirement 5 asks for real run evidence for `ci-audit`, all seven test matrix
categories, `quality-gate`, `coverage-gate`, `smoke-test`,
`supply-chain-evidence`, both advisory checks and the final acceptance job.

This environment cannot produce it: there is no GitHub credential, no `gh` CLI
and no repository API access, so no run can be triggered or read, and the
`workflow_run_id` field of this report is necessarily empty. Local test output
is not GitHub Actions evidence and is not presented as such.

To close Stage 10, on **Actions → CI — Quality Gate → the run for the pushed
commit**:

1. every blocking job listed above shows green;
2. `CI Acceptance — Independent Evidence Verification` succeeded;
3. its job summary and the `ci-acceptance-<sha>` artifact
   (`acceptance.json`) report `"accepted": true`, `"commit"` equal to that
   commit, `"failures": []`, and an `advisory` entry per advisory job;
4. the run ID from the run URL is recorded here.

If any job is red, `acceptance.json` names the unmet requirement in `failures`;
that is the recovery path, not a re-run of the decision.

## 6. Test counts

| Suite | Before (`9ae47fe`) | After |
| --- | --- | --- |
| Full suite | 596 passed, 1 skipped, 9 xfailed | 667 passed, 1 skipped, 9 xfailed |
| Coverage | 100.00% | 100.00% |
| Stage 10 regression | 86 passed | 157 passed |
| Workflow audit rules | 6 | 18 |

## 7. Files changed in this pass

| File | Change |
| --- | --- |
| `src/waxprep/ci/workflows.py` | Structural audit: needs, `if`, timeouts, artifact names/paths, report wiring, classification, registration |
| `src/waxprep/ci/evidence.py` | Job/file binding, run-id, timestamp, exit-code consistency and phase validation |
| `src/waxprep/ci/acceptance.py` | `ExecutionPhase`, `AdvisoryState`, per-state advisory reporting |
| `src/waxprep/ci/report.py` | Advisory execution table in JSON and Markdown |
| `src/waxprep/ci/cli.py` | `--phase` for `record` |
| `src/waxprep/ci/__init__.py` | Public exports for the new types |
| `.github/workflows/quality-gate.yml` | Advisory records carry the tool outcome and `--phase` |
| `tests/regression/test_ci_workflows.py` | Rewritten around the real workflow; every audit rule has a mutation test |
| `tests/regression/test_ci_acceptance.py` | Advisory states, misclassification, stale/missing advisory evidence |
| `tests/regression/test_ci_evidence.py` | Malformed-record cases |
| `tests/regression/test_ci_cli.py` | Phase recording, rejection paths, advisory table |
| `README.md`, `docs/CI_*.md`, `docs/STAGE_10_CI_SPECIFICATION.md`, `docs/CONTRIBUTING.md`, `docs/PR_REVIEW_CHECKLIST.md` | Reconciled with the corrected behaviour |

## 8. Remaining limitations

- **No GitHub Actions run evidence** (§5). Requirement 5 is open.
- `Dependency Review` remains a separate workflow: its result is not consumed by
  `needs`, is not part of the acceptance decision, and must be configured as a
  required check in branch protection if the repository wants it enforced.
- The auditor proves structure, not GitHub expression semantics. A workflow that
  satisfies every rule can still fail or behave unexpectedly at run time; only
  the run's evidence establishes what executed.
- `recorded_at` proves the record's own claim about time. It is validated for
  format and timezone, not compared against the run's real start time, because
  the artifact does not carry the run's timestamps.
- Artifact retention bounds how long a decision can be re-verified (evidence 30
  days, supply-chain evidence and acceptance decision 90 days).
- Branch protection is unchanged; direct pushes to `main` remain the workflow.
