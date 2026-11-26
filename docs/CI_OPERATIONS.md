# CI Operations

How to run, read, investigate and re-run the Stage 10 acceptance system.

## 1. What runs when

| Event | Workflow |
| --- | --- |
| Push to `main` | `CI — Quality Gate` (`quality-gate.yml`) |
| Pull request targeting `main` (opened, synchronised, reopened) | `CI — Quality Gate` + `Dependency Review` |
| Manual | `CI — Quality Gate` via **Actions → CI — Quality Gate → Run workflow** |
| Weekly schedule and push to `main` | `Dependency Security` (`dependency-security.yml`) |

A pull-request run is superseded by a newer run for the same ref
(`cancel-in-progress`). A `main` run is never cancelled, because its evidence is
the record for that commit.

## 2. Reading the result

Open **Actions → CI — Quality Gate → the run for the commit**. The run view
lists one job per responsibility. The authoritative result is the
`CI Acceptance — Independent Evidence Verification` job:

- its **Summary** contains the Markdown acceptance report (commit, decision,
  per-job status, failures, warnings);
- its artifact `ci-acceptance-<sha>` contains the same decision as JSON
  (`acceptance.json`).

Every job also uploads `ci-evidence-<job>` with its own record. Reading those
records answers "what ran, for which commit, and how did it end?" without
trusting the run's badge.

A run is **ACCEPTED** only if that job succeeded. If any earlier job failed,
the acceptance job still runs (`if: always()`), reports exactly which
requirements were unmet, and fails.

## 3. Interpreting statuses

| Recorded status | Meaning | Blocking effect |
| --- | --- | --- |
| `success` | The job executed and exited zero | none |
| `failure` | The job executed and failed | rejection |
| `cancelled` | The run was cancelled before the job finished | rejection |
| `skipped` | The job did not execute | rejection |
| missing record | No evidence was produced | rejection |

For advisory jobs (`pyright`, `vulture`) the same statuses appear, but only as
warnings. Their workflow step uses `continue-on-error: true`, so the job is
green while the record preserves the tool's real outcome (`steps.<id>.outcome`).
Because a step that never ran has an empty outcome, the workflow also records
`--phase setup` when the job failed before reaching the tool. The acceptance
report therefore reports advisory jobs by execution state:

| State | Meaning |
| --- | --- |
| `passed` | The tool ran and exited zero |
| `failed` | The tool ran and failed (the record carries the exit code) |
| `not-executed` | The job was skipped, so the tool never ran |
| `infrastructure-failure` | The job failed during setup (uv sync, cache), before the tool |
| `cancelled` | The run was cancelled before the tool finished |
| `missing` | No evidence artifact was produced at all |
| `stale-evidence` | The record names a different commit |

None of these states changes the decision. They exist so that a tool that never
ran is never described as a tool that passed.

## 4. Investigating a rejection

1. Read the acceptance report's **Failures** list. It names each job and the
   reason (`finished as failure`, `produced no evidence`, `recorded commit …
   expected …`, `is missing`, `below the required …`).
2. Open that job's log. Blocking static checks abort on the first failing
   command because they run under `set -euo pipefail`.
3. For coverage, read the `coverage-report` artifact and the
   `--cov-report=term-missing` output. The measured scope is `waxprep` minus
   `waxprep/detector/quality_gate.py` (documented exclusion); 100% means 100% of
   that scope, not of every file in the repository.
4. For supply-chain, read the `supply-chain-evidence` artifact. A policy failure
   names the check id (`SC-0xx`).
5. For missing evidence or reports, confirm the job actually started. A job that
   never started (queue cancellation, runner loss) produces no evidence by
   design and cannot be accepted.

## 5. Re-running

- **Re-run all jobs** from the run page. Evidence is rewritten for the same
  commit; the decision is recomputed from the new records.
- **Re-run failed jobs** is safe: the acceptance job re-downloads whatever
  evidence exists. If a re-run job is skipped, its evidence can be missing and
  acceptance will reject — re-run the acceptance job afterwards.
- A newer commit always needs its own run. An earlier accepted run is never
  evidence for a later commit, and the acceptance engine rejects evidence whose
  commit does not match.

## 6. Local equivalents

```bash
# Workflow audit (pinning, permissions, triggers, jobs, matrix, evidence)
uv run python -m waxprep.ci.cli audit

# Blocking quality gate, as CI runs it
make check            # or: just check

# Any single system
uv run python -m waxprep.detector.cli --format summary     # Stage 08
uv run python -m waxprep.supplychain.cli check --format summary   # Stage 09
uv run pytest tests/regression -q                          # Stage 10 adversarial tests
```

Local runs cannot create acceptance evidence for a commit; only the workflow
can. Local green output is useful for diagnosis, not for acceptance.

## 7. Adding or changing a required job

1. Add the job to `.github/workflows/quality-gate.yml` with a `timeout-minutes`,
   explicit pinned action SHAs and an evidence step (`--job <id> --class
   blocking`).
2. Add the id to `REQUIRED_JOBS` in `src/waxprep/ci/acceptance.py`.
3. Add the id to `needs` of `ci-acceptance`.
4. Run `uv run python -m waxprep.ci.cli audit`; it fails until the job records
   and uploads evidence under `ci-evidence-<id>`, is classified correctly, has a
   positive timeout, and is listed in `needs` of `ci-acceptance`.
5. Add or update a regression test in `tests/regression/`.

Removing a required job requires the same changes in reverse and must be
justified in the pull request; the acceptance policy forbids silently
downgrading a blocking check to advisory.

## 8. What the audit enforces

`uv run python -m waxprep.ci.cli audit` is a blocking job (`ci-audit`). Its
rules:

| Rule | Fails when |
| --- | --- |
| `workflow-invalid` | The file is not valid YAML, has no `jobs`/triggers, or a job is not a mapping |
| `workflow-permissions` | Least-privilege `permissions` are absent |
| `missing-trigger` | `push`, `pull_request` or `workflow_dispatch` is missing |
| `action-not-pinned` | An action reference is a tag, branch or `docker://` image |
| `missing-job` | A required, advisory or acceptance job is absent |
| `unregistered-job` | A job exists that is neither required nor advisory |
| `matrix-mismatch` | The test matrix diverges from `TEST_CATEGORIES` |
| `missing-evidence-recording` | A job does not record evidence for the expected id |
| `misclassified-evidence` | A job records evidence as the wrong blocking/advisory class |
| `evidence-artifact-missing` / `evidence-artifact-mismatch` | A job does not upload `ci-evidence-<job>` from `ci-evidence/` |
| `acceptance-download-mismatch` | `ci-acceptance` does not download `ci-evidence-*` or a required report |
| `report-producer-mismatch` | A required report is not produced by its declared job, or acceptance validates another file |
| `acceptance-report-missing` | Acceptance has no `--coverage` or `--sbom` argument |
| `acceptance-not-always` | `ci-acceptance` does not use `if: always()` |
| `acceptance-missing-dependency` / `acceptance-unknown-dependency` | `needs` omits a required job, or names an undeclared one |
| `missing-timeout` | A job has no positive `timeout-minutes` |

The audit does not evaluate GitHub expression semantics; only the run's evidence
can establish what actually executed.

## 9. Required checks in branch protection

The repository accepts direct pushes to `main`, so branch protection is not part
of Stage 10. If protection is enabled later, the required checks should be:

- `CI Acceptance — Independent Evidence Verification`
- `Dependency Review — New Vulnerabilities and Licenses`

The first already aggregates every blocking quality system. The second cannot
be aggregated inside the CI workflow because it is a separate workflow.
