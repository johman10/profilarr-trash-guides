# Unofficial TRaSH-Guides PCD for Profilarr v2

This repository generates a [Profilarr Compliant Database (PCD)](https://github.com/Dictionarry-Hub/schema)
from the JSON configuration in [TRaSH-Guides](https://github.com/TRaSH-Guides/Guides).
The PCD manifest pins the shared schema version, and generated SQL operations are
validated against that schema before they are published.

The v2 implementation is developed on the `v2-support` branch while `stable`
continues to host the existing Profilarr v1 database.

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

The `v2-support` branch runs generation, schema validation, tests, and lint on
pushes and pull requests. Scheduled runs are deferred until v2 becomes the
default branch; manual generation is launched from the workflow retained on
`stable`.
