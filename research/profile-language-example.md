# TRaSH Radarr profile language example

## Revisions examined

| Repository | Branch/ref pinned | Commit |
|---|---|---|
| [TRaSH-Guides/Guides](https://github.com/TRaSH-Guides/Guides) | `master` | [`0ecc2efc9f2434e2390c30aa75805cf233e785dc`](https://github.com/TRaSH-Guides/Guides/commit/0ecc2efc9f2434e2390c30aa75805cf233e785dc) |
| [Dictionarry-Hub/trash-pcd](https://github.com/Dictionarry-Hub/trash-pcd) | `main` | [`2322a61e1194bc75140abfd305ed0070e4d79881`](https://github.com/Dictionarry-Hub/trash-pcd/commit/2322a61e1194bc75140abfd305ed0070e4d79881) |

Both files below are linked at those pinned commits.

## Source facts

The TRaSH Radarr profile is [`docs/json/radarr/quality-profiles/sqp-1-1080p.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/quality-profiles/sqp-1-1080p.json#L1-L13). Lines 2–3 identify it as `[SQP] SQP-1 (1080p)`; line 12 sets `"language": "Original"`.

The relevant source JSON fields are:

```json
{
  "trash_id": "0896c29d74de619df168d23b98104b22",
  "name": "[SQP] SQP-1 (1080p)",
  "language": "Original"
}
```

The PCD operation [`ops/27.update-sqp-1.sql`](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/27.update-sqp-1.sql#L7-L14) contains:

```sql
INSERT INTO quality_profile_languages (quality_profile_name, language_name, type)
SELECT 'SQP-1 (1080p)', 'Original', 'simple'
WHERE NOT EXISTS (
  SELECT 1 FROM quality_profile_languages
  WHERE quality_profile_name = 'SQP-1 (1080p)'
);
```

**PCD row: yes, represented by an insert operation with `type = 'simple'`.** The operation set specifies the tuple `('SQP-1 (1080p)', 'Original', 'simple')`. It is an insert-if-absent operation, rather than a query against a checked-in materialized database snapshot.

## Custom formats and language conditions

The source profile's complete `formatItems` map is at [lines 51–84 of the profile JSON](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/quality-profiles/sqp-1-1080p.json#L51-L84). Its listed entries include audio formats, source/quality tiers, and release attributes; it does not reference a language-specific custom format such as `Language: Not Original`.

That separate TRaSH custom format exists at [`docs/json/radarr/cf/language-not-original.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf/language-not-original.json#L12-L24): its specification uses `LanguageSpecification` with `fields.value: -2`. The selected profile's `formatItems` map does not include that custom format.

The PCD profile-specific SQL also shows non-language custom-format operations: audio score adjustments in [`27.update-sqp-1.sql`, lines 16–67](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/27.update-sqp-1.sql#L16-L67), and other custom-format updates in [`59.update-default-cfs-for-sqp-profiles.sql`](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/59.update-default-cfs-for-sqp-profiles.sql#L55-L97), [`147.add-no-rlsgroup-to-sqp-profiles.sql`](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/147.add-no-rlsgroup-to-sqp-profiles.sql#L7-L16), and [`155.add-new-custom-format-imf-to-general-streaming-services.sql`](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/155.add-new-custom-format-imf-to-general-streaming-services.sql#L164-L173). These records do not show a language-specific custom format assignment for this profile.

## Interpretation

The PCD profile name matches the source name after dropping the `[SQP]` label, and both records use `Original`. In this example the PCD operation stores the language under `quality_profile_languages` with `type = 'simple'`; the selected source profile does not also reference a language-specific custom format. This describes this pinned example only.

## Follow-up: custom-format conditions and profile-language types

### Source and PCD facts

The TRaSH custom format [`docs/json/radarr/cf/language-not-original.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf/language-not-original.json#L1-L25) has `trash_id` `d6e9318c875905d6cfb5bee961afcea9`, name `Language: Not Original`, and one specification: `LanguageSpecification`, `negate: true`, `required: false`, `fields.value: -2` (lines 15–24).

At the pinned PCD revision, `ops/1.initial.sql` records the corresponding custom format and condition:

- The custom-format row names `Language: Not Original` ([`ops/1.initial.sql`, line 1987](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/1.initial.sql#L1987)).
- The `custom_format_conditions` row is `('Language: Not Original', 'Not Original Language', 'language', 'radarr', 1, 0)` for `(custom_format_name, name, type, arr_type, negate, required)` ([`ops/1.initial.sql`, line 4123](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/1.initial.sql#L4123)).
- The separate `condition_languages` row is `('Language: Not Original', 'Not Original Language', 'Original', 0)` for `(custom_format_name, condition_name, language_name, except_language)` ([`ops/1.initial.sql`, line 11049](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/1.initial.sql#L11049)).

Thus the PCD SQL stores the target language as `Original` and `except_language = 0`; the custom-format condition separately stores `negate = 1` and `required = 0`. Later pinned operations change this condition's `arr_type` (`ops/62.fix-not-original.sql`, [lines 7–15](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/62.fix-not-original.sql#L7-L15); `ops/63.change-language-cf-to-double-sided.sql`, [lines 18–27](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/63.change-language-cf-to-double-sided.sql#L18-L27)); they do not change the `condition_languages` row.

Custom formats are linked and scored through a separate `quality_profile_custom_formats` row. For example, [`ops/58.update-default-cfs-for-standard-sonarr-profiles.sql`, lines 48–55](https://github.com/Dictionarry-Hub/trash-pcd/blob/2322a61e1194bc75140abfd305ed0070e4d79881/ops/58.update-default-cfs-for-standard-sonarr-profiles.sql#L48-L55) adds `Language: Not Original` to `WEB-1080p` with `arr_type = 'sonarr'` and score `-10000`.

I scanned the 168 `.sql` files under [`ops/` at the pinned PCD commit](https://github.com/Dictionarry-Hub/trash-pcd/tree/2322a61e1194bc75140abfd305ed0070e4d79881/ops). The scan found 22 `quality_profile_languages` insert values; all use `type = 'simple'`. No `must`, `only`, or `not` values, or type-changing updates, were found in those pinned operations.

I also inspected all 39 Radarr quality-profile JSON files in the [pinned TRaSH profile directory](https://github.com/TRaSH-Guides/Guides/tree/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/quality-profiles). Every file has a `language` value, and none has a top-level `type` property. Values include `Original`, `French`, and `Any`; no non-simple profile-language type example appears in those files at this revision.

### Interpretation

These are different records with different roles in the inspected SQL. `quality_profile_languages` stores a profile's language value and its `type` (the observed PCD operations use `simple`). A custom-format language condition is represented by a `custom_format_conditions` row and its associated `condition_languages` row; a profile can then attach and score that custom format through `quality_profile_custom_formats`. In this example, the word “Not” is reflected in the condition's `negate = 1`, while `except_language` is a separate field set to `0`; neither is a `quality_profile_languages.type` value.

The absence findings above are limited to the specified TRaSH Radarr quality-profile JSON files and PCD `ops/` SQL files at the pinned commits listed in this report.
