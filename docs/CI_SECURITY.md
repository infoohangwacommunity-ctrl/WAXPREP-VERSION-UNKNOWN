# CI Security

The CI workflow is part of the security boundary: whoever can change it can
change what "accepted" means. This document records the controls and the
reasoning behind them.

## 1. Permissions

The workflow declares `permissions: contents: read` at the top level; no job
adds permissions. Nothing in the pipeline pushes, comments, creates releases or
writes to the repository. Artifact upload/download is handled by the runner's
own token and needs no extra scope.

The separate `Dependency Review` workflow needs to read the pull request's
dependency diff. Its least-privilege permission set is therefore
`contents: read` **plus** `pull-requests: read`. Without the latter, the action
fails with `HTTP 403 Forbidden`. It still does not write to the repository, and
it runs on `pull_request` with no secrets.

The action also depends on GitHub's **dependency graph** for the repository. If
the graph is disabled, both the compare API and the SBOM API return 403/404 even
when the workflow permissions are correct. Enable the dependency graph (and
Dependabot alerts) in repository security settings; this is a repository
configuration prerequisite, not a code change.

`pull_request` (not `pull_request_target`) is used, so a fork's code never runs
with a privileged token or with repository secrets. No secrets are referenced by
the CI workflow at all.

## 2. Action pinning

Every third-party action is pinned to a full 40-character commit SHA:

| Action | Pinned commit |
| --- | --- |
| `actions/checkout` | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/setup-python` | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| `astral-sh/setup-uv` | `1db35dd8eee11c5894872e0b383ae6c406cf738d` |
| `actions/cache/restore` | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |
| `actions/cache/save` | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |
| `actions/upload-artifact` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| `actions/download-artifact` | `018cc2cf5baa6db3ef3c5f8a56943fffe632ef53` |
| `actions/dependency-review-action` | `bbc44d14a204704ccc493733616cd1e93a0321ec` |

Tags are mutable. `uv run python -m waxprep.ci.cli audit` fails the pipeline if a
workflow reference is a tag or branch instead of a SHA, or if a container action
is used. Dependabot updates the pinned SHAs through its `github-actions`
ecosystem entries.

## 3. Cache integrity

- The uv cache key includes `hashFiles('uv.lock')`, so a lockfile change misses
  the cache and warm-restores from the same OS only.
- A cache hit only skips the *download*. Every job still runs
  `uv sync --extra dev --frozen` before any check, so the environment is always
  rebuilt from the lockfile and its hashes.
- The cache stores package downloads, never the project's virtual environment
  or build output, and is written only by trusted triggers (push to `main` and
  pull requests from the same repository). Forks get a read-only cache and
  cannot upload into the key used by `main`.
- `uv lock --check` runs in `quality-gate` and `supply-chain-evidence`, so the
  lockfile cannot drift from `pyproject.toml` unnoticed.

## 4. Execution integrity

- Blocking checks run under `set -euo pipefail`; a failure aborts the job instead
  of being masked by a later command.
- Advisory jobs use `continue-on-error: true` on the tool step and record the
  step's **outcome**, so an advisory failure is visible in evidence instead of
  being hidden by `|| true`.
- Every job has `timeout-minutes`; a hung check becomes a failure, not an
  indefinite run.
- `ci-acceptance` runs under `if: always()`, so it still reports when upstream
  jobs fail — it never inherits a green status.
- Required reports are validated by content, not by existence.

## 5. Supply-chain and workflow scanning

The Stage 09 gate (pip-audit, lockfile hashes, source restrictions, licence
policy, OSV malicious-package intelligence) runs inside `quality-gate` as a
blocking control, and `Dependency Review` covers pull-request dependency
changes separately.

### Zizmor and OpenSSF Scorecard — evaluation

Both were evaluated for Stage 10 and **deferred**, not adopted:

- **Zizmor** (GitHub Actions security scanner) would add a deeper static analysis
  of workflow expressions, taint of untrusted inputs and permission scope. It is
  a separate Rust toolchain, which needs its own pinned install and update path.
  Its most immediately relevant checks for this repository — mutable action
  references, missing `permissions`, dangerous `pull_request_target` usage — are
  already enforced by `waxprep.ci.workflows` and covered by regression tests.
- **OpenSSF Scorecard** assesses repository-level practices (branch protection,
  review requirements, token permissions, signed releases). WaxPrep accepts
  direct pushes to `main` and publishes no releases, so several checks would
  report conditions that are currently intentional. Adding it now would produce
  a score that describes repository policy rather than this commit's quality.

Both remain recommended for a later, dedicated security stage, where the
toolchain, pinning strategy and the repository-policy decisions they measure can
be addressed together. Neither is required for Stage 10's acceptance guarantee.

## 6. Reporting a CI security problem

Treat a mutable action reference, an unexpected permission grant, a secret
reference or a workflow expression that interpolates untrusted input into a
`run:` block as a security defect. Fix it in a dedicated change, not as part of
an unrelated pull request, and add a regression test where the workflow audit
can express the rule.
