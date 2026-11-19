# TRaSH-Guides to Profilarr v2 schema: source mapping

**Ticket context:** `.scratch/profilarr-v2-support/issues/07-map-trashguides-to-v2-schema.md`

## Scope and pinned sources

This is a source-to-schema inventory, not an implementation plan. It does not select a generator architecture.

| Source | Revision used |
|---|---|
| TRaSH-Guides `Guides`, `master` | [`0ecc2efc9f2434e2390c30aa75805cf233e785dc`](https://github.com/TRaSH-Guides/Guides/tree/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json) |
| Dictionarry `schema`, `main` | [`e1c2bd73d7003f254ad135eeefbbed7b47f095b1`](https://github.com/Dictionarry-Hub/schema/tree/e1c2bd73d7003f254ad135eeefbbed7b47f095b1) |
| This repository `stable` | [`932192ce1bf6a89fe9eb418d39390457857e0a1d`](https://github.com/johman10/profilarr-trash-guides/tree/932192ce1bf6a89fe9eb418d39390457857e0a1d) |
| Legacy v2 reference | [`v2-support` at `18a7b9ef4b1accba917943b9e2f1a50f811c15d9`](https://github.com/johman10/profilarr-trash-guides/tree/18a7b9ef4b1accba917943b9e2f1a50f811c15d9) |

There is no local or `origin` branch literally named `v2-support-old`; the available legacy reference is `v2-support`, used here only for comparison.

The schema repository manifest identifies schema version `1.1.0` and minimum Profilarr version `2.0.0` ([`pcd.json`](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/pcd.json)). The canonical tables and columns are in [`ops/0.schema.sql`](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/ops/0.schema.sql); [`docs/structure.md`](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/docs/structure.md) describes the PCD as ordered SQL operations.

## TRaSH JSON inventory

At the pinned TRaSH revision, `docs/json/` contains `guide-only/` and service trees for `radarr/` and `sonarr/`. Each service tree has `cf/`, `cf-groups/`, `quality-profiles/`, `quality-profile-groups/`, `naming/`, `quality-size/`, `conflicts.json`, and `dummy-files/`.

Observed file counts: Radarr has 243 custom formats, 40 CF groups, 39 quality profiles, and four quality-size files; Sonarr has 236 custom formats, 38 CF groups, 23 quality profiles, and two quality-size files. Both services have one naming JSON and one quality-profile-groups JSON. These are counts at the pinned source commit, not a claim that the checked-in `stable` output was generated from that exact TRaSH revision.

Useful representative records:

- Custom format: [`radarr/cf/hdr.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf/hdr.json) and [`radarr/cf/2160p.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf/2160p.json).
- CF group: [`radarr/cf-groups/hdr-formats-dv-boost.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf-groups/hdr-formats-dv-boost.json).
- Profiles: [`radarr/quality-profiles/uhd-bluray-web.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/quality-profiles/uhd-bluray-web.json) and [`sonarr/quality-profiles/web-1080p.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/sonarr/quality-profiles/web-1080p.json).
- Profile tags: [`radarr/quality-profile-groups/groups.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/quality-profile-groups/groups.json).
- Naming and size data: [`radarr/naming/radarr-naming.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/naming/radarr-naming.json), [`sonarr/naming/sonarr-naming.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/sonarr/naming/sonarr-naming.json), and [`radarr/quality-size/movie.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/quality-size/movie.json).
- Supplementary inputs: [`guide-only/language-prefer-german.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/guide-only/language-prefer-german.json), [`radarr/dummy-files/radarr-dummy-quality-profiles.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/dummy-files/radarr-dummy-quality-profiles.json), and [`radarr/conflicts.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/conflicts.json).

## Mapping to schema capabilities

### Custom formats and conditions

**Source facts.** Each `cf/*.json` record has `trash_id`, `name`, `includeCustomFormatWhenRenaming`, and `specifications`; `trash_scores` is present on most, not all, records. A specification has `name`, `implementation`, `negate`, `required`, and `fields`. At this revision, the implementations are `ReleaseTitleSpecification`, `ReleaseGroupSpecification`, `ResolutionSpecification`, `SourceSpecification`, `LanguageSpecification`, `IndexerFlagSpecification`, `QualityModifierSpecification`, and `ReleaseTypeSpecification`. The first two carry regex text at `fields.value`; other values are service-specific numeric IDs. `LanguageSpecification` additionally has a boolean `fields.exceptLanguage` in 12 specifications across the two services.

**Schema correspondence.** `custom_formats` and `custom_format_conditions` hold the entity and condition metadata. The condition discriminator plus type-specific tables map naturally as follows: release title/group → `condition_patterns` referencing `regular_expressions`; resolution → `condition_resolutions`; source → `condition_sources`; language → `condition_languages`; indexer flag → `condition_indexer_flags`; quality modifier → `condition_quality_modifiers`; release type → `condition_release_types`. `negate` and `required` are direct condition fields; the service is representable as `arr_type`. The schema has `custom_formats.include_in_rename`, and `condition_languages.except_language`, corresponding directly to the TRaSH booleans. The schema also defines size and year condition tables, but neither implementation appears in these pinned Radarr/Sonarr CF records.

**Transformations / interpretations.**

- `fields.value` numeric IDs need service-specific lookup, not a shared enum. The current generator has Radarr/Sonarr maps for language and source, and corresponding maps for flags, quality modifiers, and release types ([stable `custom_formats.py`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/utils/custom_formats.py), [`mappings/`](https://github.com/johman10/profilarr-trash-guides/tree/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/utils/mappings)). In the observed source snapshot, every encountered numeric value in these mapped classes has a current stable mapping.
- Regex strings live in condition `fields.value`; the optional `trash_regex` field is instead a Regex101 URL (95 CF files have it). The schema has optional `regular_expressions.regex101_id`, but extracting an ID from the source URL is a transformation. Current stable and the legacy v2 generator use the regex text but do not preserve that URL as `regex101_id`.
- The schema has no TRaSH `trash_id`/score-set provenance columns. IDs are still useful as import-time join keys: profile `formatItems` refers to IDs, while scores are stored under `trash_scores`. The stable generator resolves those IDs and emits the final profile score; it does not persist the source ID or all score alternatives.

### Quality profiles, quality lists, and profile tags

**Source facts.** Quality-profile records include `trash_id`, `name`, `trash_description`, sometimes `trash_url`, `upgradeAllowed`, `cutoff`, `minFormatScore`, `cutoffFormatScore`, `minUpgradeFormatScore`, `items`, and `formatItems`. Radarr also has `language`; Sonarr records have `trash_quality_definition` and some have `visible`. Profile `items` are ordered; each item has a name and `allowed`, and some have nested `items` arrays such as `WEB 2160p` containing `WEBRip-2160p` and `WEBDL-2160p`. `formatItems` maps display labels to CF Trash IDs. `trash_score_set` selects the named score set, with `default` as the fallback.

**Schema correspondence.** The profile scalar fields map to `quality_profiles` (`upgrades_allowed`, `minimum_custom_format_score`, `upgrade_until_score`, `upgrade_score_increment`). Ordered `items` map to `quality_profile_qualities.position` and `enabled`; the `cutoff` identifies the entry whose `upgrade_until` flag is set. Nested quality lists map to per-profile `quality_groups` and `quality_group_members`. Resolved CF assignments map to `quality_profile_custom_formats` with the selected score. The source `language` is conceptually expressible by `quality_profile_languages` (likely as a `simple` preference); that exact interpretation is an inference, not an explicit mapping in the source.

The separate `quality-profile-groups/groups.json` files are lists of named groups whose `profiles` maps profile slugs to Trash IDs. These labels can map to `quality_profile_tags`; they are distinct from the profile's own `group` field.

**Ambiguities / gaps.**

- A profile's `trash_quality_definition` points to a quality-size ID, but the schema has no profile-to-quality-definition relation. The definition rows themselves can be loaded; retaining this profile association has no direct column in this schema.
- `visible` has no corresponding profile field. `trash_url` also has no dedicated URL column (it can be included in descriptive text, but that is not equivalent structured data).
- `quality_profile_languages` can represent a language and type (`must`, `only`, `not`, `simple`), but the source profile JSON provides one language label, not an explicit schema modifier. Treating it as `simple` is an inference; the old v2 collector does not map it.
- The schema can preserve ordering for profile items and group members (member ordering is added by [`ops/3.quality-group-member-position.sql`](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/ops/3.quality-group-member-position.sql)). The legacy collector retains each profile item's array position, but converts the nested group-member list to a set and then sorts it for SQL output; that discards the source member order.

### CF groups and score selection

CF groups contain `name`, `trash_id`, `trash_description`, `custom_formats`, and `quality_profiles.include`. Group-level `default` is encoded as the string `"true"` when present, whereas each CF's `default` is a boolean. CF entries can carry `required` and their own `trash_id`. For example, [`hdr-formats-dv-boost.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf-groups/hdr-formats-dv-boost.json) has a required CF and a profile-include map.

The stable collector only expands groups whose group-level value is exactly `"true"`, and only adds member CFs whose `default` is boolean `true`; it applies them to the IDs in `quality_profiles.include` ([`cf_groups.py`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/utils/cf_groups.py)). The output is flattened into profile/CF score assignments. The v2 schema has tags and score assignments but no CF-group entity or direct representation of group defaults, required-member rules, or include/exclude policy; flattening can preserve selected behavior but not the original group rule.

### Naming and quality definitions

TRaSH naming JSONs are option maps, not a single row: Radarr has `folder` and `file` maps; Sonarr has `season`, `series`, and `episodes` maps, with standard/daily/anime episode variants. The schema has named Radarr and Sonarr naming rows with those format columns. The legacy collector emits variant rows and resolves missing sub-keys by prefix/default fallback. Stable currently copies only Radarr `file.standard`/`folder.default` and Sonarr default episode/series/season strings into one YAML config ([stable `media_management.py`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/utils/media_management.py)).

Quality-size JSON contains a `type` and a list of `{quality, min, preferred, max}`. TRaSH's [Glossary](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/Glossary/index.md) says these values are megabytes per minute. The schema's `radarr_quality_definitions` and `sonarr_quality_definitions` tables provide corresponding min/preferred/max columns, but declare them as integers without documenting units. The source includes decimal values (for example 17.1 and 12.5), while the legacy collector uses half-up integer rounding. Thus mapping to the current schema requires a precision decision; rounding is observable information loss. Stable reads only Radarr `movie.json` and Sonarr [`series.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/sonarr/quality-size/series.json), while the source also has Radarr `anime`, `sqp-streaming`, `sqp-uhd` and Sonarr `anime` definitions.

## Comparison with checked-in stable output

At stable commit `932192c`, the checked-in output contains 479 `custom_formats/` files, 62 `profiles/` files, 1,346 `regex_patterns/` files, and three `media_management/` YAML files. Representative artifacts are [`Radarr - HDR.yml`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/custom_formats/Radarr%20-%20HDR.yml) and [`Radarr - UHD Bluray + WEB.yml`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/profiles/Radarr%20-%20UHD%20Bluray%20%2B%20WEB.yml).

The stable generator's source paths and collectors are explicit in [`scripts/generate.py`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/generate.py): it reads service `cf/`, `cf-groups/`, `quality-profiles/`, plus naming and quality-size data for media management. It emits one YAML condition per supported spec, prefixed service names, mapped enum values, and regex references. It currently:

- comments out `includeCustomFormatWhenRenaming` persistence, emits `tests: []`, and does not preserve `trash_regex` or source CF `trash_description` as metadata ([`custom_formats.py`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/utils/custom_formats.py), [`regex_patterns.py`](https://github.com/johman10/profilarr-trash-guides/blob/932192ce1bf6a89fe9eb418d39390457857e0a1d/scripts/utils/regex_patterns.py));
- ignores `exceptLanguage` while writing language conditions, despite the v2 schema having `condition_languages.except_language`;
- resolves profile score sets to final scores and drops zero-scored entries; writes profile language as a lowercase string, but uses only service tags rather than quality-profile group tags;
- expands only default CF-group rules, and only emits the default naming / movie-series size definitions described above;
- writes `misc.yml` from local constants rather than a TRaSH JSON media-settings record.

The generated YAML is a flattened representation; the schema's normalized relationships (tags, condition subtype tables, quality groups, profile-language links, and media-management rows) are not present as explicit relationships in this output format.

## Legacy v2 reference comparison

The available legacy v2 branch is `v2-support` at `18a7b9e`; its generator writes an initial SQL operation ([`scripts/generate.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/generate.py), [`sql_writer.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/sql_writer.py)). The specific collectors are [`custom_format_collector.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/collectors/custom_format_collector.py), [`quality_profile_collector.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/collectors/quality_profile_collector.py), [`quality_definition_collector.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/collectors/quality_definition_collector.py), [`naming_collector.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/collectors/naming_collector.py), and [`regex_collector.py`](https://github.com/johman10/profilarr-trash-guides/blob/18a7b9ef4b1accba917943b9e2f1a50f811c15d9/scripts/collectors/regex_collector.py). Relative to stable it:

- keeps `includeCustomFormatWhenRenaming`, maps `exceptLanguage`, and merges same-name, equivalent CFs across services;
- maps profile groups to profile tags, retains ordered profile-item positions, stores score-set-resolved scores, and collects all service quality-size files and naming variants;
- rounds decimal quality-size values half-up, loses nested quality-group member order through set/sort handling, and does not consume `cf-groups/`, `guide-only/`, profile `language`/`visible`/`trash_quality_definition`, `trash_regex` URLs, or test data.

These are observations about that commit only, not a recommendation to reuse its generator.

## Remaining source gaps and decisions for follow-up

1. **Guide-only records:** `docs/json/guide-only/` has five language helper CF-like records, each using `trash_id: "guide-only"` rather than a normal unique ID, and no service/profile assignment (example: [`language-prefer-german.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/guide-only/language-prefer-german.json)). The service-directory collectors in stable and the legacy v2 branch do not read them. They are source content, but not unambiguous CF/profile assignments.
2. **Tests:** the schema supports `custom_format_tests`; TRaSH [`radarr/dummy-files/radarr-dummy-quality-profiles.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/dummy-files/radarr-dummy-quality-profiles.json) and its Sonarr counterpart contain dummy quality-profile templates, not per-CF title/expected-match fixtures. No direct source test rows were found in the exported JSON.
3. **Other JSON:** [`radarr/conflicts.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/conflicts.json) and its Sonarr counterpart have no corresponding schema entity, and neither generator imports them. They represent source constraints that need separate interpretation if conflicts are in scope.
4. **Preservation choices:** `trash_url`, `trash_regex`, optional descriptions, profile visibility, and profile-to-quality-definition links are present or derivable in source but lack direct current collector/schema fields as described above.
5. **Precision and ordering:** quality-size decimals need an agreed integer representation, and group-member order is available in source and schema but is lost by the legacy set-based path.

These findings distinguish schema capacity from what the current generator persists. They do not decide how to organize a future generator or which optional source metadata should be retained.
