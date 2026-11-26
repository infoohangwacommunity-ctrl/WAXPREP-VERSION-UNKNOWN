# CI Acceptance Policy

The rule set that decides whether a commit is accepted. Implemented in
`src/waxprep/ci/acceptance.py`; enforced by the `ci-acceptance` job.

## 1. Definitions

- **Required job** — a job listed in `REQUIRED_JOBS`. Its success is necessary
  for acceptance.
- **Advisory job** — a job listed in `ADVISORY_JOBS`. Its outcome is reported
  but never changes the decision.
- **Evidence** — the JSON record a job writes to `ci-evidence/`, uploaded as an
  artifact.
- **Required report** — an artifact whose *contents* are validated: the
  coverage XML and the CycloneDX SBOM.
- **Acceptance** — a decision bound to one full commit SHA.

## 2. Decision table

| Situation | Decision |
| --- | --- |
| Every required job succeeded with evidence for this commit, reports valid | Accepted |
| A required job failed | Rejected |
| A required job was cancelled | Rejected |
| A required job was skipped | Rejected |
| A required job produced no evidence | Rejected |
| A required job's evidence names another commit | Rejected |
| Evidence is malformed or unreadable | Rejected |
| A record's job id does not match its file name | Rejected |
| A record's run identifier is not `<run id>` or `<run id>-<attempt>` | Rejected |
| A record's timestamp is not ISO 8601 with a timezone | Rejected |
| A record's exit code contradicts its status | Rejected |
| Duplicate evidence exists for a required job | Rejected |
| A required job is recorded as advisory | Rejected |
| The assessed commit is not a full 40-character SHA | Rejected |
| The checked-out revision differs from `github.sha` | Rejected |
| Coverage XML is missing, malformed, wrong root or below 1.0 | Rejected |
| SBOM is missing, not CycloneDX, empty or has components without `purl` | Rejected |
| An advisory check executed and passed | Accepted, no warning |
| An advisory check executed and failed | Accepted, warning `failed` |
| An advisory job never reached its check (infrastructure failure) | Accepted, warning `infrastructure-failure` |
| An advisory job was skipped or cancelled | Accepted, warning `not-executed` / `cancelled` |
| An advisory job produced no evidence | Accepted, warning `missing` |
| An unrecognised job wrote evidence | Accepted, with a warning |

There is no override flag. A rejection is resolved by fixing the cause and
running again, never by editing the decision.

## 3. Blocking versus advisory

A check is blocking when its failure makes the software unacceptable. In
Stage 10:

- **Blocking:** workflow audit, environment preparation, ruff, ruff format,
  mypy (strict), import-linter, semgrep, Stage 09 supply-chain gate, Stage 08
  detector (its blocking rules), every test category, coverage at 100% of the
  measured scope, smoke test, SBOM generation.
- **Advisory:** pyright (strict type check), vulture (dead code report).

A blocking check is never reclassified to advisory to obtain a green pipeline.
Pyright and vulture are advisory because the project already enforces strict
types with mypy and treats dead-code findings as review material; that decision
predates Stage 10 and is documented in `pyproject.toml`.

## 4. Evidence requirements

Per job record: job id, classification, status, commit, workflow run id,
timestamp, optional exit code, execution phase. Per assessment: coverage XML and
SBOM, validated by content.

"Uploaded" is not "valid". The acceptance engine parses the XML and the SBOM and
rejects empty, truncated or structurally wrong files.

A record is also checked internally, so that a malformed file can never be read
as success:

- the job id must match the record's file name;
- `workflow_run_id` must be numeric (`<run id>` or `<run id>-<attempt>`);
- `recorded_at` must be an ISO 8601 timestamp with a timezone;
- `exit_code` must agree with `status` (a `success` with a non-zero code, or a
  failure with code 0, is malformed).

`phase` records whether the status is the check's own outcome (`check`) or the
job failed before reaching it (`setup`). This is what lets advisory reporting
distinguish a failed check from an infrastructure failure.

## 5. Commit binding

- The acceptance job asserts `git rev-parse HEAD == github.sha` before deciding.
- Every record must contain the same SHA.
- A record from another commit rejects the assessment.

This prevents an older accepted run from being presented as evidence for a newer
commit.

## 6. Reporting

The decision is written twice: `ci-acceptance/acceptance.json` for machines and
the job summary for humans. Both list the commit, the decision, every observed
job status, every blocking failure and every advisory warning. The report also
has a dedicated advisory table that states, per advisory job, whether it
`passed`, `failed`, was `not-executed`, hit an `infrastructure-failure`, was
`cancelled`, or produced no evidence (`missing`) or evidence from another commit
(`stale-evidence`). An advisory result is always labelled non-blocking, and a
check that never ran is never described as having passed.

## 7. The workflow audit enforces the policy

The policy is only as strong as the definition that implements it, so
`src/waxprep/ci/workflows.py` checks the workflow structure against this
document. The audit fails when:

- an action reference is a mutable tag, a branch or a container image;
- least-privilege `permissions` are absent, or a required trigger is missing;
- a required, advisory or acceptance job is absent, or a job exists that is
  neither required nor advisory;
- the test matrix diverges from `TEST_CATEGORIES`;
- a job does not record evidence, records it for the wrong id, or records it
  under the wrong classification;
- a job does not upload its `ci-evidence-<job>` artifact, or uploads it from a
  directory other than `ci-evidence/`;
- the acceptance job does not download `ci-evidence-*` or a required report
  artifact;
- a required report is not produced by its declared job, or the acceptance job
  validates a file that is not that job's output;
- the acceptance job does not run with `if: always()`;
- the acceptance job does not depend on every required and advisory job;
- a job has no positive `timeout-minutes`.

The audit proves these structural properties. It cannot prove that GitHub
expressions evaluate as intended at run time; only the run's evidence can.

## 8. Changing the policy

Policy changes require:

1. an edit to `REQUIRED_JOBS`/`ADVISORY_JOBS` and any rule in
   `src/waxprep/ci/acceptance.py`;
2. matching workflow changes (`needs`, evidence steps);
3. regression tests that still prove skipped, cancelled, failed, missing and
   stale evidence are rejected;
4. a note in this document.

Adding a required job is always allowed. Removing one, or turning a blocking
check into an advisory one, needs an explicit justification in the pull request
and must not be done to make a failing pipeline pass.
