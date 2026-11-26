# Stage 10 — Continuous Integration (CI) Specification

Status: implemented. This document is the authoritative specification for the
Stage 10 acceptance system. Where the workflow and this document disagree, the
workflow is the defect.

## 1. Purpose

WaxPrep already had quality systems (Stages 05–09) and a GitHub Actions
workflow that ran them. Stage 10 does not add another inspector. It makes the
existing inspectors **independently executable, independently evidenced and
independently verifiable**, so that a change is accepted only because the
systems actually ran and succeeded for exactly that commit.

Nothing is accepted because an agent, a developer or a pull-request description
claims it is complete.

## 2. Scope

In scope:

- orchestration of the existing quality systems in `.github/workflows/quality-gate.yml`;
- machine-readable evidence for every job;
- an acceptance engine that decides from that evidence alone;
- validation of required reports (coverage XML, CycloneDX SBOM);
- a workflow audit (pinning, permissions, triggers, jobs, matrix, evidence);
- adversarial tests of the acceptance machinery itself.

Out of scope (deliberately unchanged):

- application behaviour, the request path and the production deployment;
- the Stage 09 supply-chain controls themselves;
- branch protection, required-check configuration and repository settings;
- replacing any quality system or lowering any threshold.

## 3. Architecture

```
code submitted (push to main, pull request to main, manual dispatch)
        │
        ├── ci-audit ................ workflow integrity (Stages 10)
        ├── quality-setup ........... uv sync + package cache
        ├── quality-gate ............ ruff, format, mypy, import-linter,
        │                             semgrep, Stage 09 gate, Stage 08 detector
        ├── tests ................... matrix: unit, integration, contract,
        │                             lifecycle, architecture, configuration,
        │                             regression
        ├── coverage-gate ........... full suite, --cov-fail-under=100
        ├── smoke-test .............. app boot + liveness/readiness
        ├── supply-chain-evidence ... CycloneDX SBOM (required), trust report
        ├── pyright ................. advisory
        └── vulture ................. advisory
                    │
                    ▼
        each job writes ci-evidence/<job>.json and uploads it
                    │
                    ▼
        ci-acceptance (if: always())
          · binds evidence to github.sha
          · loads every evidence record
          · validates coverage.xml and the SBOM contents
          · writes ci-acceptance/acceptance.json + job summary
          · exits non-zero unless the commit is ACCEPTED
```

The orchestrator runs systems; it does not decide whether code is good. The
acceptance job decides only whether **the required systems succeeded for this
commit with valid evidence**.

## 4. Execution model

| Responsibility | Job | Classification | Timeout |
| --- | --- | --- | --- |
| Workflow integrity | `ci-audit` | blocking | 10 min |
| Environment preparation | `quality-setup` | blocking | 10 min |
| Static analysis + Stage 08/09 gates | `quality-gate` | blocking | 10 min |
| Test categories (7 matrix jobs) | `tests` | blocking | 5 min |
| Coverage at 100% of measured scope | `coverage-gate` | blocking | 10 min |
| Boot + health endpoints | `smoke-test` | blocking | 5 min |
| SBOM + trust report | `supply-chain-evidence` | blocking | 10 min |
| Strict type check | `pyright` | advisory | 10 min |
| Dead code report | `vulture` | advisory | 5 min |
| Acceptance decision | `ci-acceptance` | blocking | 10 min |

Every job runs its own environment preparation. GitHub-hosted jobs are separate
machines, so a setup job cannot hand an installed environment to them. The
shared uv cache is an optimisation; every job still runs
`uv sync --extra dev --frozen`, so a cache hit is never treated as proof that
the environment is correct.

`regression` is a first-class matrix category because the Stage 10 adversarial
tests live in `tests/regression/`. `tests/detector/` and `tests/supplychain/`
are executed by `coverage-gate` as part of the full suite; they are not matrix
categories, and that is stated here rather than presented as separate
independent jobs.

## 5. Evidence model

Each job writes one record:

```json
{
  "job": "coverage-gate",
  "check_class": "blocking",
  "status": "success",
  "commit": "<40-character SHA>",
  "workflow_run_id": "1234567890-1",
  "recorded_at": "2026-11-25T00:00:00+00:00",
  "exit_code": null,
  "phase": "check"
}
```

`status` is the GitHub job outcome (`job.status`) or, for advisory jobs, the
outcome of the tool's own step (`steps.<id>.outcome`). A record is written with
`if: always()`, so a failed job still produces evidence of its failure.

A record is validated before it can count:

- the job id must be a lowercase identifier and must match the record's file
  name, so a record cannot be filed as one job and read as another;
- `workflow_run_id` must be `<run id>` or `<run id>-<attempt>` with numeric
  parts;
- `recorded_at` must be an ISO 8601 timestamp that carries a timezone;
- `exit_code` must agree with `status`: `success` with a non-zero code, or a
  failure with code 0, is malformed evidence, not a pass.

`phase` is `check` when the recorded status is the check's own outcome, and
`setup` when the job never reached its check. An advisory record with
`phase: setup` is reported as an infrastructure failure, never as a failed or a
passed check.

Evidence is uploaded per job (`ci-evidence-<job>`) with 30-day retention.
Required reports have longer retention: coverage 30 days, supply-chain evidence
and the acceptance decision 90 days.

## 6. Acceptance rules

A commit is **accepted** only when all of the following hold:

1. the assessed commit is a full lowercase 40-character SHA;
2. every required job has exactly one evidence record;
3. every required record is classified `blocking`;
4. every required record names the assessed commit;
5. every required record has status `success`;
6. the checked-out revision equals `github.sha`;
7. `coverage.xml` exists, is well-formed, and its `line-rate` meets the policy
   minimum (1.0);
8. the CycloneDX SBOM exists, declares `bomFormat: CycloneDX`, and every
   component carries a `purl`;
9. every required record is well formed (job/file-name pair, run identifier,
   timestamp, exit code consistent with status).

Any other outcome — failure, cancellation, skip, missing record, malformed
record, stale commit, missing or invalid report, unrecognised status — is a
rejection with a stated reason. Advisory outcomes never cause rejection; they
are listed as warnings in the same report.

The decision logic lives in `src/waxprep/ci/acceptance.py` and is pure, so it is
tested directly against synthetic evidence. The workflow supplies evidence; it
cannot influence the rules.

## 7. Non-negotiables

- A required check that did not run is never a pass.
- A result from a different commit is never reused.
- Duplicate evidence is never resolved into a pass.
- Advisory results are never reported as blocking failures, and blocking
  failures are never downgraded to advisory ones.
- No threshold (coverage, lint, type, security) is weakened to obtain green CI.
- Acceptance evidence is machine-readable and archived.

## 8. Known limitations

- GitHub's `Dependency Review` runs in a separate workflow. Its result cannot be
  consumed by `needs`; it must be configured as a required check in branch
  protection. See `docs/CI_OPERATIONS.md`.
- An infrastructure failure before a job's first step produces no evidence and
  therefore a rejection, not a retry. A re-run is the recovery path.
- The acceptance engine reads artifacts from the current run only; artifact
  retention limits how long a decision can be re-verified.
- The workflow audit checks structure, not GitHub expression semantics. It
  verifies mutable action references, missing permissions, missing triggers and
  jobs, matrix drift, absent or misclassified evidence recording, evidence
  artifact names and paths, the acceptance download pattern, that each required
  report is downloaded from its producing job, that `ci-acceptance` depends on
  every required and advisory job and runs with `if: always()`, that every job
  has a positive timeout, and that no job sits outside the acceptance policy. It
  cannot evaluate what `${{ }}` expressions produce at run time, so a workflow
  that satisfies every structural rule could still fail when executed. That is
  why execution evidence — not the audit — decides acceptance.
