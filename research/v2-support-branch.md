# `v2-support` branch research

**Ticket context pointer:** `.scratch/profilarr-v2-support/issues/02-research-v2-support-branch.md`

This report records repository state and source evidence for comparing `v2-support` with `stable`. It does not select a foundation.

## Ref and history snapshot

At inspection, `stable` pointed to `932192ce1bf6a89fe9eb418d39390457857e0a1d` (2026-11-18), and `v2-support` pointed to `18a7b9ef4b1accba917943b9e2f1a50f811c15d9` (2026-07-24). The refs share merge base `7acf473f604a1d2ec65288335d481b00038c0079`; `stable...v2-support` has 43 stable-only commits and 12 v2-only commits. Thus the checked-out v2 implementation predates the stable tip and the branches have materially diverged.

The v2-specific sequence begins with `3abdd52b96fcc37e06c3409fea83133c8e05de28` (“Initial attempt at v2 integration”). It includes cleanup/rebuild commits `75a9aab` and `10186dd`; `10186dd751cb34322c1e2b7b3e4dbb1d2df49322` removed earlier PCD metadata/SQL-generator implementation and test files. Later commits include `6ba2fb3` (“Finalise generation of the initial file”) and the current tip `18a7b9e` (“Improve code quality”). These are the observed branch-history checkpoints, not a judgment about their quality.

## Implementation on `v2-support`

At `v2-support@18a7b9ef4b1accba917943b9e2f1a50f811c15d9`, `scripts/generate.py` accepts input and output directories, stops when `ops/` already contains files, invokes regex, custom-format, profile, quality-definition, and naming collectors, and calls `write_initial_sql` (`scripts/generate.py:15-51`). Its checked-in generated structure includes `ops/1.initial.sql`, `pcd.json`, and `.gitkeep` placeholders in `deps/` and `tweaks/`; the v2 tree does not contain `media_management/`, `custom_formats/`, `profiles/`, or `regex_patterns/`.

The SQL writer serializes tags and regexes, custom formats and their conditions/relationships, profile data and profile-to-format scores, quality definitions, and Radarr/Sonarr naming (`scripts/sql_writer.py:45-118`, `:173-241`, `:244-310`). The initial checked-in SQL begins with tag inserts (`ops/1.initial.sql:1-16`). The PCD descriptor declares schema dependency `1.1.0` and minimum Profilarr version `2.0.0` (`pcd.json:1-31`).

The v2 collectors and writer encode several data constraints:

- Supported custom-format condition implementations map to condition types, and regex conditions must resolve to a collected regex (`scripts/collectors/custom_format_collector.py:27-69`). Duplicate condition names are skipped; matching custom formats can be merged across services (`:119-169`, `:172-224`).
- Regexes are deduplicated by pattern (`scripts/collectors/regex_collector.py:11-80`). The writer exits for duplicate service/TRaSH-ID mappings or profile references to missing custom formats (`scripts/sql_writer.py:25-43`, `:244-270`).
- Numeric condition values use hard-coded Radarr/Sonarr mapping tables (`scripts/constants.py:28-159`; `scripts/common.py:27-67`).

## Differences from `stable`

At `stable@932192ce1bf6a89fe9eb418d39390457857e0a1d`, `scripts/generate.py` clears and repopulates per-entity YAML output directories, including `regex_patterns/`, `custom_formats/`, `profiles/`, and `media_management/` (`scripts/generate.py:16-47`, `:49-93`). That tree contains 1,346 regex-pattern files, 479 custom-format files, 62 profile files, and three media-management files; those output directories are absent at the v2 tip. The direct tree comparison reports 1,929 changed files.

The branch comparison also shows that stable's helper modules for custom formats, profiles, regexes, media management, mappings, and file handling are deleted on `v2-support`; v2 instead adds `scripts/collectors/`, `common.py`, `constants.py`, `models.py`, `parsing.py`, and `sql_writer.py`. The generator and generation workflow are modified rather than carried forward unchanged. Existing stable tests check custom-format-to-regex and profile-to-custom-format references (`stable:tests/test_custom_formats.py:50-88`; `stable:tests/test_profiles.py:53-90`).

## Constraints and source-material inventory

- **Different generation/output contract:** stable emits a collection of YAML files; v2 emits an initial SQL migration and PCD descriptor. The outputs, generation entry point, and CI-generated file set differ (`stable:scripts/generate.py:16-93`; `v2-support:scripts/generate.py:15-51`; `v2-support:scripts/sql_writer.py:45-310`).
- **Documented-output mismatch on v2:** the README says generation produces `pcd.json` and `media_management/` (`v2-support:README.md:43-46`), while the generator calls the SQL writer and the v2 tree has no `media_management/` directory (`v2-support:scripts/generate.py:34-51`). The workflow stages `ops/`, `pcd.json`, and `media_management/` for drift checks and scheduled/manual commits (`v2-support:.github/workflows/generate.yml:48-68`).
- **Test/workflow mismatch visible on v2:** the README lists test modules, but the v2 tree's only test file is `tests/__init__.py`; the workflow invokes `pytest tests/` and separately refers to a Docker-import test with `continue-on-error` (`v2-support:README.md`; `v2-support:.github/workflows/generate.yml:39-46`; v2 tree at `18a7b9e`).
- **Existing stable data and validation:** the stable output directories hold the counts above, and stable's tests express cross-reference checks for regex and custom-format/profile relationships (`stable:tests/test_custom_formats.py:50-88`; `stable:tests/test_profiles.py:53-90`).
- **Existing v2 parser/collector/writer material:** the files and rules listed in the implementation section are present at `v2-support@18a7b9e`; numeric conversions and linkage checks are implemented in explicit mapping, collector, and writer code cited above.

## Research-note convention

The repository's issue-tracker documentation places local issue/spec notes under `.scratch/`, uses numbered child tickets, and describes an `## Answer` section when resolving a ticket (`docs/agents/issue-tracker.md:3-11`, `:23-30`). No separate repository convention or existing `research/` directory was found at inspection; `research/v2-support-branch.md` is the requested report location.
