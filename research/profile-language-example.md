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
