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
| Duplicate evidence exists for a required job | Rejected |
| A required job is recorded as advisory | Rejected |
| The assessed commit is not a full 40-character SHA | Rejected |
| The checked-out revision differs from `github.sha` | Rejected |
| Coverage XML is missing, malformed, wrong root or below 1.0 | Rejected |
| SBOM is missing, not CycloneDX, empty or has components without `purl` | Rejected |
| An advisory job failed or is missing | Accepted, with a warning |
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
timestamp, optional exit code. Per assessment: coverage XML and SBOM, validated
by content.

"Uploaded" is not "valid". The acceptance engine parses the XML and the SBOM and
rejects empty, truncated or structurally wrong files.

## 5. Commit binding

- The acceptance job asserts `git rev-parse HEAD == github.sha` before deciding.
- Every record must contain the same SHA.
- A record from another commit rejects the assessment.

This prevents an older accepted run from being presented as evidence for a newer
commit.

## 6. Reporting

The decision is written twice: `ci-acceptance/acceptance.json` for machines and
the job summary for humans. Both list the commit, the decision, every observed
job status, every blocking failure and every advisory warning. An advisory
failure is always labelled non-blocking.

## 7. Changing the policy

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
