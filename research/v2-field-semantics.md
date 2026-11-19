# Profilarr v2 field semantics

Research date: 2026-11-19

Context pointer preserved in the main worktree: `.scratch/profilarr-v2-support/issues/10-research-v2-field-semantics.md`.

## Findings

### `radarr_quality_definitions` and `sonarr_quality_definitions`

**Documented in the Dictionarry schema:** both tables store `min_size`, `max_size`, and `preferred_size` in columns declared `INTEGER`. The schema does not state a unit or define a precision rule for these columns. Its `pcd.json` identifies Profilarr `2.0.0` as the minimum supported application version, so this is the relevant v2 schema repository; the SQL file's “PCD SCHEMA v1” label is the portable-data schema version, not the app version. ([schema SQL](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/ops/0.schema.sql#L330-L352), [schema manifest](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/pcd.json#L1-L22))

**Documented by Profilarr's v2 application UI:** the editor identifies **MB per minute (MB/min)** as the base unit for these values. It provides alternate display units (Radarr: GB/hour, GB/90 minutes, GB/2 hours; Sonarr: MB/30 minutes, GB/45 minutes, GB/hour) via conversions from that base. Its fields use `step={1}` in MB/min. Therefore the application editor's expected input/storage granularity is **1 MB/min** (whole-number increments), with fractional display values possible after unit conversion. ([editor unit definitions and conversion](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/routes/media-management/%5BdatabaseId%5D/quality-definitions/components/QualityDefinitionsForm.svelte#L164-L197), [fields and step](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/routes/media-management/%5BdatabaseId%5D/quality-definitions/components/QualityDefinitionsForm.svelte#L481-L536), [step precision normalization](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/lib/client/ui/form/NumberInput.svelte#L126-L167))

**Qualification / inference:** “integer MB/min” is the editor/schema expectation, not a fully enforced storage contract. SQLite's `INTEGER` declaration is an affinity, and Profilarr's portable-data validator checks these values only for JavaScript `number` type, not integer-ness. Also, the editor treats zero `max_size` / `preferred_size` as “unlimited” in the Arr-facing data and uses its scale maximum internally before saving zero. ([portable-data validator](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/lib/server/pcd/entities/validate.ts#L236-L257), [editor normalization and save mapping](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/routes/media-management/%5BdatabaseId%5D/quality-definitions/components/QualityDefinitionsForm.svelte#L86-L111), [editor save mapping](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/routes/media-management/%5BdatabaseId%5D/quality-definitions/components/QualityDefinitionsForm.svelte#L300-L319))

### `quality_profile_languages.type`

**Documented in the schema:** `type` is `VARCHAR(20) NOT NULL DEFAULT 'simple'`. A comment lists `must`, `only`, `not`, and `simple` (“default language preference”). The SQL column has no enum or `CHECK` constraint. Profilarr's quality-profile transformer also types the value as that four-literal union. ([schema declaration](https://github.com/Dictionarry-Hub/schema/blob/e1c2bd73d7003f254ad135eeefbbed7b47f095b1/ops/0.schema.sql#L150-L157), [application type](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/lib/server/sync/qualityProfiles/transformer.ts#L47-L51))

**Observed consumer behavior in Profilarr's quality-profile sync path:** the fetcher selects and carries `qpl.type` into the typed in-memory language config. The transformer does not branch on that value: for Radarr it maps the profile language **name** to an Arr language and includes it; for Sonarr it omits the language field (the code comment says Sonarr uses custom formats for language filtering). ([fetch/cast](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/lib/server/sync/qualityProfiles/transformer.ts#L345-L359), [Radarr-only language mapping](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/lib/server/sync/qualityProfiles/transformer.ts#L189-L193), [language mapping by name](https://github.com/Dictionarry-Hub/profilarr/blob/db69167b995cc60be277976dedebbd884a46eca7/src/lib/server/sync/mappings.ts#L474-L480))

**Not confirmed:** the sources establish that these four literals are documented values, but do not explain the intended semantics of `must`, `only`, or `not`. No type-specific behavior was found in the cited profile-fetch/transform path. This does not establish that no other application surface or external consumer uses the values.

### Public v2 documentation

Profilarr's public Media Management and Quality Profiles docs are not a detailed contract for these fields: the Media Management page is a TODO placeholder, while the Quality Profiles page gives only broad editing scope and notes that language is used only by Radarr. Neither documents size units/precision or meanings for the language `type` values. ([Media Management docs](https://profilarr.com/build/media-management), [Quality Profiles docs](https://profilarr.com/build/quality-profiles))

## Source scope

The application source was inspected at commit [`db69167`](https://github.com/Dictionarry-Hub/profilarr/tree/db69167b995cc60be277976dedebbd884a46eca7); the schema repository was inspected at [`e1c2bd7`](https://github.com/Dictionarry-Hub/schema/tree/e1c2bd73d7003f254ad135eeefbbed7b47f095b1). Public docs were checked on 2026-11-19. Conclusions above are limited to these sources and the cited code paths.
