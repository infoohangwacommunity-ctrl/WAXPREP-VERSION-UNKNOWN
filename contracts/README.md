# Published Contract Schemas

This directory is generated from `src/waxprep/contracts/`. Do not hand-edit the
JSON files.

- `manifest.json` lists the current contract identities and files.
- `name@version.schema.json` is one deterministic JSON Schema Draft 2020-12 file.
- A version bump adds a new file; historical versions are not overwritten.

Regenerate after an intentional model change:

```bash
uv run python -m waxprep.contracts.cli generate
```

CI blocks a model change whose committed schemas are stale:

```bash
uv run python -m waxprep.contracts.cli check --schemas contracts/schemas
```

Review schema diffs as contract changes, not formatting noise. Use `compat` to
classify an old/new pair; see `docs/CONTRACT_EVOLUTION.md`.

## Baseline and decisions

- `contracts/baseline/` is the last accepted published schema set.
- `contracts/compatibility-decisions.toml` records reviewed exceptions and
  conditional changes.

CI runs `enforce` against the baseline. Do not edit a published version to make
the check pass; publish a new version. A same-version schema change is rejected
unless an explicit decision exists.
