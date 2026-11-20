# Unofficial TRaSH-Guides PCD for Profilarr v2

This repository generates a [Profilarr Compliant Database (PCD)](https://github.com/Dictionarry-Hub/schema)
from the JSON configuration in [TRaSH-Guides](https://github.com/TRaSH-Guides/Guides).
The PCD manifest pins the shared schema version, and generated SQL operations are
validated against that schema before they are published.

The `stable` branch is the maintained, backwards-compatible Profilarr v1 line.
The `v2` branch is the maintained Profilarr v2 line and the target default
branch for this transition. Choose `stable` for Profilarr v1 and `v2` for
Profilarr v2.

The generated configurations are based on TRaSH-Guides, whose MIT license and
copyright notice are included in [TRASH-GUIDES-LICENSE.txt](./TRASH-GUIDES-LICENSE.txt).

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- A local TRaSH-Guides checkout containing `docs/json/`

Install the project and development dependencies:

```bash
uv sync --extra dev
```

## Generate and validate

From the repository root, provide the JSON directory from a TRaSH-Guides checkout:

```bash
uv run scripts/generate.py /path/to/Guides/docs/json .
uv run scripts/validate.py .
```

The first run creates `ops/1.initial.sql`. Later runs replay the existing
operations and append a numbered, guarded SQL delta only when source data changes.
Previously generated operations are never rewritten. Review and commit each new
operation with the source or mapping change that produced it.

### Curated media settings and delay profiles

The generator also reads [config/curated-settings.json](./config/curated-settings.json).
Maintainers can add, edit, or remove named Radarr media settings, Sonarr media
settings, and shared delay profiles in the corresponding arrays. Each record
must include all fields shown in the file; booleans are JSON `true` or `false`.
Delay values are non-negative minutes. For an `only_usenet` or `only_torrent`
profile, the other protocol's delay must be `null`. The minimum custom-format
score must be an integer when its bypass is enabled and `null` otherwise.
Invalid records or duplicate names within an array stop generation.

The initial media settings use `doNotPrefer` for Propers and Repacks, as
recommended by TRaSH-Guides. Enabling MediaInfo and the default delay profile
are repository choices, not TRaSH-Guides recommendations. The delay profile
prefers Usenet but sets both delays to zero and disables both bypasses, so it
does not intentionally wait for Usenet. Profilarr users choose and sync these
records; this generator does not change running Radarr or Sonarr instances.
Changes, including removals, produce guarded append-only operations alongside
updates from TRaSH-Guides.

The pinned schema files under `scripts/schema/1.1.0/` are an offline validation
snapshot; the PCD itself declares the schema dependency in `pcd.json`.

## Tests and lint

```bash
uv run pytest -q
uv run pylint scripts tests
```

The tests exercise the generation CLI, append-only updates, fractional
quality-size rounding, naming and profile mappings, and SQL loading with foreign
key validation against the pinned schema.

## GitHub Actions

- **Sync TRaSH-Guides: stable + v2** (`sync-trash-guides.yml`) runs daily on the
  `v2` default branch and can be dispatched manually. It runs independent jobs
  against the default TRaSH-Guides branch, using each target branch's generator.
  The `stable` job runs the v1 generator and tests before pushing; the `v2` job
  validates the PCD schema, runs tests and lint, and checks the generated PCD
  import before pushing. A failure on one line does not block the other.
- **Validate Profilarr v2 PCD** (`validate-v2-pcd.yml`) runs generation,
  schema validation, tests, and the PR import check on v2 pushes and pull
  requests. It has read-only repository permissions.
- **Lint Profilarr v2** (`lint.yml`) runs pylint on v2 pushes and pull requests.
- The `stable` branch's **Sync Profilarr v1 data** (`sync-stable.yml`) remains
  manually dispatchable for v1-only updates. Its daily schedule is active while
  `stable` is the default branch; the combined sync workflow handles daily v1
  updates once `v2` becomes the default.
