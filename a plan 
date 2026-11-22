Worked for 6m 3s

I understand what you’re asking. You don’t just want someone to tell you that Stage 07 is complete. You want an independent investigation that compares what the team says was implemented, what the actual code does, what the commit history shows, and what the documentation tells future developers.

I inspected the repository’s `main` branch, examined the 48 commits returned by the repository history search, and fetched the actual workflow, configuration, tests, architecture files and supporting documentation.

My conclusion: Stage 07 has substantial implementation in place, but the repository is not yet in a state where I would honestly describe everything as verified, consistent and production-ready. I found real documentation contradictions and several workflow weaknesses.

I have not changed anything on `main`.

### WaxPrep — Independent Stage 01–07 Repository Audit

# WAXPREP — INDEPENDENT REPOSITORY AUDIT
## Stages 01–07: Implementation, Documentation, Architecture and Quality Gate

**Repository:** [infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN)

**Branch examined:** `main`

**Latest commit examined:** `a5cffbbd2aa099ae41ae49759efbeb40c8d3f910`

**Audit date:** 22 November 2026

**Purpose:** Independently determine whether the implementation, documentation, automated quality gate and engineering standards agree with one another.

---

# 1. Executive conclusion

The repository has made real progress.

Stages 01–04 established the initial application foundation, architecture and identity system. Stage 05 introduced the testing foundation. Stage 06 introduced static-analysis tooling. Stage 07 then consolidated the automated quality gate.

However, completing the implementation of a quality gate does not automatically mean that the repository's documentation, engineering rules and workflow are correct.

I identified five major areas requiring attention:

1. **Documentation accuracy:** Several important documents still describe older stages, older workflows, deleted files or previously implemented plans as though they represent the current repository.
2. **Architecture consistency:** The rules governing communication between `core`, `messaging`, `context`, `services`, `registries` and `adapters` contradict one another across different documents.
3. **Quality gate reliability:** The current workflow does not run on pull requests, and some checks described as part of the gate are advisory rather than blocking.
4. **Test and command consistency:** Some documented commands are incompatible with the dependency configuration, some fixture documentation is demonstrably incorrect, and local quality-gate commands disagree.
5. **Verification evidence:** A 100% coverage threshold and a green-looking workflow structure are not sufficient evidence that every required quality check is actually enforcing the intended rules.

**Overall assessment:** Stage 07 has been substantially implemented, but documentation alignment, merge protection and enforcement verification remain outstanding.

This is not an accusation against the development team. Some of these problems originated in earlier stages and remained after later implementation changed the underlying system.

# 2. What the commit history actually reveals

The commit history is important because it shows how the project reached its current state.

### Stage 01–02: Foundation

The initial foundation commit was made on 8 November 2026.

The project established:

- Python and dependency management.
- FastAPI and Uvicorn.
- Channel, model and tool registries.
- Fake adapters.
- Configuration management.
- Health endpoints.
- Basic runtime structure.

The later November 16 changes improved initialization, request correlation, exception handling and application lifecycle management.

These were meaningful foundation improvements.

### Stage 03: Architecture

The project introduced the `core`, `messaging`, `context` and `services` packages, along with architectural boundary documentation and tests.

Subsequent cleanup removed empty or misleading skeleton files and strengthened some boundary tests.

However, as explained later, not every architectural relationship is actually enforced as strongly as the documentation suggests.

### Stage 04: Identity

The project introduced Wax ID using UUIDv7, together with validation and tests.

The November 17 commits also addressed foundational issues discovered during independent reviews.

These changes are present in the history and should not be dismissed.

### Stage 05: Testing foundation

The project reorganized tests into categories such as:

- Unit
- Integration
- Contract
- Lifecycle
- Architecture
- Configuration
- Regression

The later commits addressed incorrect test commands, CI setup and test organization.

A notable correction was made in commit `14588b0e58`: the project switched to `uv sync --extra dev` rather than the older `uv sync --dev` command for its configured optional dependencies.

The resulting test structure is substantially more mature than the original flat test arrangement.

### Stage 06: Static analysis

The November 18 commits introduced static-analysis tooling and research.

The project added or configured:

- Ruff
- Mypy
- Pyright
- Import Linter
- Semgrep
- Vulture

The implementation encountered command and configuration issues, which were addressed in subsequent commits.

The research document remains useful as historical material, but it should no longer be treated as the current implementation specification.

### Stage 07: Quality gate

The November 21–22 history contains a particularly important sequence.

The team repeatedly changed the quality-gate workflow:

- Added the consolidated quality-gate workflow.
- Changed the cache implementation.
- Removed cache steps.
- Redesigned the workflow with independent jobs.
- Restored parts of the earlier workflow.
- Corrected malformed YAML.
- Restored the pyright, Vulture, smoke-test and aggregate jobs.
- Changed dependency auditing to advisory.
- Changed the cache action references again.

This history matters because it explains some of the confusion surrounding the cache workflow.

The cache was removed in commit `095c492da6` on November 21.

But later, commit `2b0b816bdb` on November 22 restored the cache restore/save steps when the workflow was rebuilt.

The latest commit, `a5cffbbd2a`, then changed the cache references to `@v4`.

Therefore, **the current cache behaviour is not unexplained: the current workflow explicitly contains cache steps.**

The relevant history can be reviewed here:

- [Stage 07 implementation](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/commit/a9323e6aa53b224fb364f59eed2c63ae029c6534)
- [Cache removal](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/commit/095c492da62248957f6d6e689ff952ada438fabe)
- [Workflow redesign](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/commit/b7eb33d69f08a815edf07ac33e31db4f6165bb70)
- [Workflow restoration](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/commit/2b0b816bdb447bcc01f70ed46605cd7b65d35bd0)
- [Latest cache change](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/commit/a5cffbbd2aa099ae41ae49759efbeb40c8d3f910)

**Finding:** The implementation history contains several rounds of corrections. The team must distinguish between changes that were temporarily implemented, subsequently removed and finally restored. Reading only the latest commit message does not tell the full story.

# 3. Critical finding: The Stage 07 audit report is outdated

Document: `STAGE_07_STATIC_ANALYSIS.md`

[Open the document](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/blob/main/STAGE_07_STATIC_ANALYSIS.md)

This document currently describes itself as:

**Status: Audit only — no configuration changes implemented.**

That description is misleading as a description of the current repository.

The document also describes an older configuration:

- It refers to `.github/workflows/test.yml`.
- It refers to `vulture.cfg.py`.
- It describes Pyright as blocking.
- It describes old import-linter contracts.
- It describes Semgrep local commands that no longer match the current Makefile and Justfile.
- It says dependency auditing is missing.

But the current repository has a different situation.

| Subject | What the report says | What currently exists |
|---|---|---|
| CI workflow | `test.yml` | `quality-gate.yml` |
| Vulture configuration | Separate `vulture.cfg.py` | Vulture settings in `pyproject.toml` |
| Pyright | Blocking | Advisory |
| Pip-audit | Missing | Present, but advisory |
| Semgrep | Local command lacks `--error` | Makefile, Justfile and CI use `--error` |
| Import Linter | Older contracts | Four active contracts with different rules |

There is also an internal contradiction concerning Vulture.

The audit report acknowledges that Vulture reads configuration from `pyproject.toml`, where an `ignore_names` list exists. It then argues that the whitelist is ineffective because a separate `vulture.cfg.py` file is not passed.

The separate file does not currently exist at the repository root. The current Pyproject configuration is therefore the relevant configuration to verify.

The team should not implement recommendations from this audit report without first checking whether the recommendation has already been implemented.

**Required correction:** Replace this document with a current Stage 07 implementation audit, or preserve it explicitly as a historical snapshot. It must not be presented as the current state.

# 4. Critical finding: README still describes an older project

Document: `README.md`

[Open README](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/blob/main/README.md)

The README identifies the repository as:

**WaxPrep Foundation — Stages 01–05.**

It also says the repository contains only Stages 01, 02, 03, 04 and 05.

That is no longer an accurate description of the current repository.

The actual repository now contains Stage 06 static-analysis work and Stage 07 quality-gate infrastructure.

The README does not adequately describe:

- The current quality-gate workflow.
- The current blocking checks.
- The advisory checks.
- The Makefile quality-gate commands.
- The current import-linter contracts.
- The actual CI trigger behaviour.
- The distinction between implementation stages and the product features that remain unimplemented.

The project metadata also remains behind.

`pyproject.toml` still describes the project as Stages 01–05, while `main.py` still describes the application as Stages 01–04.

These are not necessarily application-breaking defects. They are documentation and metadata defects that make the project's state difficult to understand.

**Required correction:** Establish one current project-status description and synchronize the README, project metadata and application description.

Important: Stage 07 completion does not mean that WaxPrep's actual AI tutoring functionality has been implemented. The current repository is still a foundation project. Its README explicitly excludes real WhatsApp and Telegram handlers, database infrastructure, tutor logic and the intelligence layer.

The team must not confuse completion of the engineering foundation with completion of the final product.

# 5. Critical finding: Architecture rules contradict one another

This is one of the most important findings because architecture rules are supposed to prevent developers and AI agents from introducing unwanted dependencies.

The repository currently describes different dependency rules depending on which document a developer reads.

### Messaging dependencies

The README says messaging can import from:

- `core`
- `registries`

It explicitly says messaging must not import from `context` or `services`.

However:

`STAGE_03_ARCHITECTURE.md` describes messaging as depending on `core` and `context`.

It also contains a section explaining that messaging handlers may need to read learner context.

`PR_REVIEW_CHECKLIST.md` says messaging depends on `core` and `context` only.

`src/waxprep/messaging/__init__.py` says messaging may depend on registries.

`docs/ENGINEERING-STANDARDS.md` describes messaging as depending on `core` and registries, without allowing context.

These rules do not agree.

A developer following one document could introduce an import that another document prohibits.

### Adapters and core

The current `.importlinter` file explicitly prohibits adapters from importing `core`.

That agrees with the project's written rule that adapters depend on registry protocols instead.

The current import-linter contract also blocks adapters from importing concrete modules in messaging, context, services, registries and other listed packages.

This is a positive correction compared with the earlier Stage 07 audit report, which described a different adapter-to-core rule.

### The missing enforcement problem

The current `.importlinter` file has four active contracts.

It enforces selected forbidden dependencies, including core isolation and adapter isolation.

However, the second contract for outer-to-inner directionality was removed because the installed Import Linter version did not support the configured `allowed` contract type.

The repository comments say architecture tests cover those allowed relationships instead.

I inspected `tests/architecture/test_boundaries.py`.

Some of those tests are weaker than their names suggest.

For example:

- A messaging test checks that `__init__.py` mentions `core`.
- It then checks that `waxprep.core` can be imported by Python.
- That does not prove messaging actually follows the intended dependency direction.
- The messaging adapter test checks `from ... import ...` statements but does not cover every form of ordinary `import`.
- Some tests skip package `__init__.py` files.
- There is no comprehensive rule matrix that verifies every package's permitted and forbidden imports.

This means the project has real architecture checks, but it should not claim that every documented architecture relationship is comprehensively enforced.

### Required correction

Create one authoritative dependency matrix covering:

- `core`
- `messaging`
- `context`
- `services`
- `registries`
- `adapters`
- `middleware`
- `main`

Then make the README, engineering standards, contributor guide, architecture guide, pull-request checklist and package documentation follow exactly the same rules.

The enforcement must inspect both `import` and `from ... import` statements, including package initialization files.

It should test actual source dependencies rather than merely checking that a package's documentation mentions another package.

# 6. Critical finding: Current quality gate does not protect pull requests

Workflow: `.github/workflows/quality-gate.yml`

[Open the workflow](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/blob/main/.github/workflows/quality-gate.yml)

The current workflow has this trigger:

**Push to main.**

It does not currently include a `pull_request` trigger.

This is a serious distinction.

A workflow that runs after code reaches `main` is not the same as a workflow that checks a proposed change before it is merged into `main`.

The current workflow therefore does not provide the pre-merge protection that the phrase "blocking quality gate" may suggest.

A correct merge-protection arrangement should involve:

1. Pull requests targeting `main` trigger the required checks.
2. The aggregate quality-gate result is configured as a required status check.
3. Failed or cancelled mandatory checks prevent merging.
4. Automatic merging is allowed only after all required checks pass.
5. Direct pushes to `main` are restricted according to the repository's chosen protection policy.

The workflow file alone cannot configure all of these repository settings.

I could inspect the workflow definition, but I could not independently confirm the active branch-protection or repository-ruleset settings from the available repository access.

Therefore, nobody should claim that automatic merge protection is fully configured without verifying those settings.

**Important:** Do not enable unrestricted automatic merging. Enable automatic merging only behind a correctly configured required-check policy.

# 7. Critical finding: The aggregate job has a reporting problem

The workflow contains an aggregate job named:

**Gate Aggregate — Overall Status**

It depends on:

- `quality-setup`
- `quality-gate`
- `tests`
- `coverage-gate`
- `smoke-test`

That is a sensible list of blocking jobs.

However, its summary also tries to display the results of:

- `pyright`
- `vulture`

Those jobs are not included in the aggregate job's `needs` list.

Consequently, the aggregate job does not have those jobs available as normal dependencies through its `needs` context.

The summary cannot be trusted to report their actual results as written.

There are two valid approaches:

- Keep advisory jobs independent and omit their results from the aggregate summary.
- Explicitly collect their results through a separate reporting mechanism, while ensuring that their failures never become blocking.

The team must not simply add advisory jobs to the aggregate's dependencies and leave the current generic failure expression unchanged. That could accidentally make advisory failures block the gate.

The distinction between blocking and advisory must remain explicit.

# 8. Critical finding: Dependency vulnerability auditing is being bypassed

The current workflow includes Pip-audit.

This is good.

However, the workflow executes it in advisory mode using error-suppression logic.

The relevant comment identifies a known vulnerability in `wcmatch 8.5.2`, identified as `GHSA-53pm-wgxf-c6qf`, and says Semgrep's dependency constraint prevents installing the stated fixed version.

That explains why the team changed the audit to advisory mode.

But there is an important problem.

The current approach suppresses the audit failure generally, not just the one known vulnerability.

That means a future, unrelated dependency vulnerability may also fail to stop the workflow.

The Makefile has the same general weakness: its Pip-audit command prints a message after failure, allowing the Make target to finish successfully.

The Justfile behaves differently: its Pip-audit command is direct and can fail.

Therefore:

**The local Makefile, Justfile and CI do not enforce the same dependency-security policy.**

Required correction:

- Document the known vulnerability as a tracked exception.
- Give the exception an owner, justification and review date.
- Preserve failure for unrelated vulnerabilities.
- Make the CI, Makefile and Justfile use the same policy.
- Reassess the Semgrep dependency constraint rather than silently accepting a permanently weakened audit.

# 9. Current blocking versus advisory checks

The current workflow has the following practical structure.

| Check | Current behaviour |
|---|---|
| Ruff lint | Blocking |
| Ruff format | Blocking |
| Mypy | Blocking |
| Import Linter | Blocking |
| Semgrep | Blocking |
| Pip-audit | Advisory |
| Unit/integration/contract/lifecycle/architecture/configuration tests | Blocking |
| Full-suite coverage | Blocking, 100% threshold |
| Application smoke test | Blocking |
| Pyright | Advisory |
| Vulture | Advisory |
| Aggregate gate | Blocking for its listed mandatory dependencies |

This is the actual distinction the team must document.

There is an important subtlety: Pyright is configured as strict in `pyproject.toml`, but its CI command explicitly ignores failure.

A strict configuration does not automatically make a check blocking.

Similarly, Vulture is run in advisory mode.

The team must stop describing all configured tools as mandatory blocking checks.

### Other gaps in the current quality gate

**Semgrep uses `--config auto`.**

This obtains rules from Semgrep's remote automatic ruleset. The rules applied can change independently of this repository.

For a highly controlled gate, the team should decide whether to adopt a pinned or locally maintained ruleset.

**No dedicated secret-scanning job appears in the current workflow.**

Ruff's security-related rules do not replace scanning the repository and its history for exposed credentials.

**No dedicated complexity gate appears in the current workflow.**

**No dedicated documentation-quality gate appears in the current workflow.**

Those are potential quality-gate improvements, not reasons to install every possible tool immediately. Each proposed check should be assessed for value, noise and maintenance cost.

# 10. Tests and testing documentation contain factual inconsistencies

Document: `tests/README.md`

[Open tests documentation](https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/blob/main/tests/README.md)

I found several issues.

### A. The fixture documentation is false

The document states:

"All fixtures are opt-in — none are autouse."

But `tests/conftest.py` contains an explicitly autouse fixture called `_reset_main_globals`.

That fixture runs automatically and restores global state in `waxprep.main` after tests.

The code and its own comments correctly describe this behaviour.

The README is therefore wrong.

### B. The CI workflow description is obsolete

The testing README describes:

- `.github/workflows/test.yml`
- Older push and pull-request triggers.
- A daily cron schedule.
- Older independent CI job names.
- A different workflow structure.

The actual workflow is now `quality-gate.yml`, and its current trigger is push to `main` only.

### C. The commands need correction

The testing README uses commands such as `uv run --dev pytest`.

The repository uses `[project.optional-dependencies]` with a `dev` optional extra, and a previous commit explicitly corrected the project to use `uv sync --extra dev`.

The team should standardize the documentation around the configured optional dependency installation method.

### D. Regression category is not currently in the test matrix

The current workflow matrix contains six categories:

- Unit
- Integration
- Contract
- Lifecycle
- Architecture
- Configuration

It does not contain a separate regression job.

The Stage 07 implementation history says the regression directory was empty and was therefore removed from the matrix.

This is understandable, but the documentation should distinguish between an empty placeholder category and an actively executed category.

The full coverage job still runs the full test suite, so any tests later added to the regression directory would be included in that full-suite run.

### E. The speed claim is not verified

The testing README claims the full suite runs in under 30 seconds.

That may have been true during an earlier test run, but it should not be presented as a guaranteed current benchmark without current workflow evidence.

# 11. The no-hardcoding policy is not accurately described

This is an important distinction for WaxPrep.

The project repeatedly says:

- No hardcoded ports.
- No hardcoded timeouts.
- No hardcoded grace periods.
- No hardcoded configuration values.
- All configuration comes from environment variables.

However, `src/waxprep/config.py` contains defaults:

- Environment: `development`
- Host: `0.0.0.0`
- Port: `8000`
- Shutdown grace period: `30`
- Log level: `info`

These values are configurable through the environment, but they are still defined as code defaults.

The configuration tests also expect some of those defaults.

The correct conclusion is not necessarily that the application is badly implemented.

Environment-overridable defaults can be a reasonable design.

The problem is that the documentation calls this "no hardcoding" without explaining the difference between:

- A configuration default.
- A value embedded directly in business logic.
- A secret or provider-specific value.
- A fixed keyword or vocabulary decision.

The tests also do not demonstrate environment overrides for every setting.

**Required correction:** Define the precise no-hardcoding policy. Then test and document it accurately. Do not use a test that checks a default value as proof that the value is not hardcoded.

This distinction is especially important because WaxPrep has a separate long-term goal of preventing fixed vocabulary, hidden keyword mappings and hardcoded conversational behaviour.

Configuration hygiene and conversational hardcoding are related, but they are not the same problem.

# 12. Other outdated or misleading documentation

The following documents need review.

| Document | Finding | Required action |
|---|---|---|
| `README.md` | Stops at Stage 05 | Update current status and Stage 06–07 |
| `pyproject.toml` | Project description says Stages 01–05 | Align metadata |
| `STAGE_07_STATIC_ANALYSIS.md` | Describes outdated files and check status | Replace with current audit or archive |
| `docs/STAGE06_STATIC_ANALYSIS_RESEARCH.md` | Historical planning document | Clearly label as a historical snapshot |
| `tests/README.md` | Incorrect fixture, workflow and command descriptions | Correct against current code |
| `CONTRIBUTING.md` | Old setup command and old test structure | Update |
| `docs/ENGINEERING-STANDARDS.md` | Generic architecture diagram conflicts with the actual package structure | Replace with WaxPrep's actual architecture |
| `PR_REVIEW_CHECKLIST.md` | Messaging dependency rules conflict with other documentation | Align |
| `STAGE_03_ARCHITECTURE.md` | Messaging/context relationship conflicts with README | Resolve and label historical decisions |
| `ARCHITECTURE_BOUNDARIES.md` | Contains older or conflicting architecture descriptions | Reconcile |
| `STAGE_01_02_SPEC.md` | Historical specification but contains overbroad no-hardcoding claims | Label historical and correct where necessary |
| `TEST_PLAN_STAGE_03.md` | Says 75 tests are currently passing | Label as a historical Stage 03 snapshot |
| `IMPLEMENTATION_PLAN.md` | Completed Stage 01–02 implementation plan still reads like a plan | Mark completed/historical |
| `a plan ` | Stage 05 plan with obsolete instructions and a trailing-space filename | Rename and mark as historical or replace with implementation record |

The Stage 06 research document is not inherently wrong for describing what was known on November 18.

The problem is presenting it as current guidance without saying that later commits changed the implementation.

Historical documents should be retained when useful, but they must be clearly separated from active engineering instructions.

# 13. Makefile and Justfile are not consistent

The repository currently has both a Makefile and a Justfile.

This creates two ways of running the same quality gate.

I found these issues:

- Makefile Pip-audit suppresses failure.
- Justfile Pip-audit does not suppress failure.
- The CI workflow also suppresses Pip-audit failure.
- The Justfile contains duplicate `test` and `coverage` recipe definitions.
- Local test and coverage commands can run the full suite separately, potentially repeating work.
- The Makefile claims to run the complete local equivalent of CI, but the security policy does not match the Justfile exactly.

The duplicates must be investigated against the installed Just version and resolved. They should not remain as competing definitions.

**Recommendation:** Choose one canonical local gate command and make any alternative entry point delegate to the same underlying checks. Avoid maintaining two independently evolving quality-gate definitions.

# 14. What is genuinely good and should be preserved

The audit should not be interpreted as a recommendation to throw away Stage 07.

Several implementation decisions are sound and should be retained.

- The project uses Python 3.14 and uv.
- The project has a clear foundation rather than prematurely implementing the entire tutor.
- It separates core logic from external adapters.
- Registry initialization is explicit rather than relying on import-time registration.
- It has request correlation IDs.
- It has lifecycle and health checks.
- It has test categories.
- It uses Ruff and strict Mypy.
- It has architecture contracts through Import Linter.
- It uses Semgrep for security-related code analysis.
- It enforces a 100% coverage threshold.
- It performs an application smoke test.
- It separates Pyright and Vulture as advisory checks.
- It has a final aggregate gate for mandatory jobs.
- It pins several external GitHub Actions by full commit SHA.

The corrections should strengthen this foundation, not replace it with unnecessary tooling or architectural complexity.

# 15. Prioritized remediation plan

The following order is recommended.

## Priority 0 — Fix merge protection and trust in the gate

1. Add pull-request execution for changes targeting `main`.
2. Configure the aggregate quality-gate check as a required status check in repository rules or branch protection.
3. Restrict direct pushes according to the selected merge policy.
4. Verify that required checks cannot be bypassed.
5. Enable automatic merging only after the required checks are genuinely enforced.
6. Correct the aggregate job's advisory-result reporting.
7. Verify actual GitHub Actions runs rather than assuming that a valid workflow file has passed.

## Priority 1 — Correct documentation that can mislead developers

1. Update README and project metadata.
2. Replace the outdated Stage 07 audit.
3. Correct `tests/README.md`.
4. Correct CONTRIBUTING setup instructions.
5. Synchronize the architecture rules across all documentation.
6. Clearly label historical stage plans and research reports.
7. Rename the root `a plan ` file to a meaningful filename.

## Priority 2 — Strengthen architecture enforcement

1. Establish one authoritative dependency matrix.
2. Make the architecture tests verify actual source imports.
3. Check both import syntax forms.
4. Include package initialization files.
5. Verify forbidden dependencies for all relevant packages.
6. Verify permitted dependencies where those relationships are part of the architecture contract.
7. Add regression tests proving that deliberately introduced violations cause failures.

## Priority 3 — Make local and CI checks identical

1. Resolve duplicate Justfile recipes.
2. Choose one canonical quality-gate command.
3. Unify Makefile, Justfile and workflow behaviour.
4. Track the known Pip-audit exception explicitly.
5. Ensure unrelated dependency vulnerabilities still fail the gate.
6. Decide whether Semgrep's automatic remote rules are sufficiently stable.
7. Correct the smoke test to use readiness polling and reliable cleanup rather than relying solely on a fixed sleep.

## Priority 4 — Improve security and quality coverage

Evaluate:

- Repository secret scanning.
- Dependency security scanning.
- More focused Semgrep rules.
- Complexity analysis.
- Documentation checks.
- Branch and coverage testing.

Do not install tools simply because they are popular. Each tool needs a documented purpose, a defined severity policy, an owner and an explanation of what it can and cannot detect.

# 16. Evidence required before declaring Stage 07 fully verified

The team should not report "everything is complete" until it can provide the following:

1. A successful pull-request workflow run against the current `main`.
2. Evidence that the required aggregate check is configured in the repository's merge rules.
3. Evidence that a deliberately failing mandatory check prevents merging.
4. Evidence that an advisory failure does not prevent merging.
5. Evidence that the full test suite passes with the configured 100% coverage threshold.
6. Evidence that the smoke test detects an application that fails to become ready.
7. Evidence that each architecture boundary test catches a deliberately introduced violation.
8. Evidence that Pip-audit still fails for an unrelated vulnerability.
9. Confirmation that the Makefile and Justfile give consistent results.
10. A documentation review showing that current engineering instructions agree with the actual implementation.

A successful run is evidence that the checks executed successfully. It is not proof that the checks cover every intended risk.

# 17. Final instruction to the development team

Do not respond to this audit with a general statement that everything is okay.

For every finding, provide:

- The exact file and location.
- Whether the finding is confirmed, partially confirmed or not reproducible.
- The reason it exists.
- Whether the issue has already been fixed elsewhere.
- The proposed correction.
- The test or evidence that will demonstrate the correction.
- The commit that implements it.

Do not blindly follow every recommendation in older planning documents. Some recommendations have already been implemented; others are no longer appropriate.

Do not remove existing working architecture merely to make documentation easier.

Do not reduce the coverage threshold, weaken mandatory checks, suppress whole classes of security failures or change architectural rules without an explicit justification.

Do not automatically merge unverified changes.

The final goal is a repository where the source code, architecture, tests, automated workflow and documentation all describe the same system.

**The most important requirement is truthfulness of project state: no outdated document should be mistaken for current implementation, no advisory check should be described as blocking, and no unverified workflow should be reported as a successful merge gate.**

### 14\. One important limitation of this audit

I inspected the actual workflow definition and the repository status response, but I could not independently retrieve a complete set of the latest GitHub Actions run logs or verify the repository's active branch-protection settings. The combined commit-status endpoint returned no classic status entries; that alone does not establish whether Actions succeeded or failed.

So I am deliberately not telling you the latest quality-gate run passed. That needs to be demonstrated from the actual Actions run.

The next useful step is to turn these findings into a controlled correction plan and a reviewed pull request, rather than allowing the team to make another round of unrelated changes directly on `main`.

Prepare the Stage 07 correction PR

Should I proceed with that correction PR next?
