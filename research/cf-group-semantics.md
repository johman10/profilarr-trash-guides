# TRaSH-Guides custom-format group semantics

**Research context pointer:** `.scratch/profilarr-v2-support/issues/12-research-cf-group-semantics.md` (context only; not a source, and its contents were not needed).

**Source snapshot:** TRaSH-Guides/Guides commit [`0ecc2efc9f2434e2390c30aa75805cf233e785dc`](https://github.com/TRaSH-Guides/Guides/commit/0ecc2efc9f2434e2390c30aa75805cf233e785dc), dated 2026-11-18 05:48:30 UTC. The paths and line links below are pinned to this revision.

## Findings

These JSON group definitions are metadata for sync tools; they are not directly importable into Radarr. Therefore, the “effective set” below describes what the metadata says a synchronizer should offer or include, not a guarantee of what any particular tool installed or activated. ([Radarr custom-format groups guide, lines 3–7](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/Guide-Sync/radarr-cf-groups.md#L3-L7))

### Documented semantics

- **Group `default`:** A group is optional and disabled by default; setting its group-level `default` to the string `"true"` enables it by default. It remains possible for the user to disable the whole group. If the key is absent, the contributor guide says there is no need to specify `"default": "false"`. ([`CONTRIBUTING.md`, lines 306–320](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/CONTRIBUTING.md#L306-L320))
- **Member `required`:** When its group is enabled, `required: true` enables all members, without offering an individual choice for those members. The user can still disable the group as a whole. With `required: false`, members can be selected individually and are unchecked by default. ([`CONTRIBUTING.md`, lines 324–328](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/CONTRIBUTING.md#L324-L328))
- **Member `default`:** For individually selectable members, `default: true` means selected by default. The schema confirms that group-level `default` is a string while member-level `default` is an optional boolean. ([`CONTRIBUTING.md`, lines 327–334](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/CONTRIBUTING.md#L327-L334); [`schemas/cf-groups.schema.json`, lines 17–20 and 35–43](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/schemas/cf-groups.schema.json#L17-L43)). The docs do not state a separate effect for member `default` when the member is `required: true`; examples containing both flags do not by themselves establish one.
- **`quality_profiles.include`:** The group maps profile names to profile Trash IDs under `quality_profiles.include`; the guide describes these as the profiles that receive the CF group. The schema requires a nonempty `include` map. The group reference page presents this information as “Applicable Quality Profiles.” ([`CONTRIBUTING.md`, lines 335–336](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/CONTRIBUTING.md#L335-L336); [`schemas/cf-groups.schema.json`, lines 46–62](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/schemas/cf-groups.schema.json#L46-L62); [Radarr group guide, lines 42–49](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/Guide-Sync/radarr-cf-groups.md#L42-L49))

### Effective-set interpretation (inference)

For a given profile, `quality_profiles.include` determines which groups are applicable to it; a group not listed there is not part of that profile’s group set. For an applicable group, the group-level default controls its initial enabled state. If enabled, required members are included together, while optional members are included according to their individual selection state (initially checked by `default: true`, otherwise unchecked by default). Disabling the group excludes the group’s members together. This combines the documented rules above; it is an interpretation for a consumer of the metadata, not a claim that TRaSH Guides itself performs a runtime assignment.

The contributor guide separately describes a profile’s direct `formatItems` as mandatory formats, excluding formats added with CF groups. This supports treating direct profile formats and group-derived formats as separate inputs to a profile’s final set. ([`CONTRIBUTING.md`, lines 285–290](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/CONTRIBUTING.md#L285-L290))

## Concrete examples

1. **HDR group:** [`docs/json/radarr/cf-groups/hdr-formats-hdr.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf-groups/hdr-formats-hdr.json#L2-L15) has group `default: "true"`, an HDR member marked `required: true`, and includes `Base Profile` (lines 38–40). Per the documented rules, HDR is included for that profile if the group remains enabled by default; the user may still disable the entire group.
2. **Unwanted Formats group:** [`docs/json/radarr/cf-groups/unwanted-formats.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf-groups/unwanted-formats.json#L2-L17) defaults on and includes `Base Profile`. The `3D` member is optional with `default: true` (lines 68–76), so it starts checked. `No-RlsGroup` is optional and has no member `default` (lines 100–112), so it starts unchecked. While the group is enabled, these optional members can be individually selected or deselected.
3. **Required Repack/Proper group:** [`docs/json/radarr/cf-groups/required-repack-proper.json`](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf-groups/required-repack-proper.json#L2-L17) defaults on and includes `Base Profile`; its three members are marked required (lines 20–29). This illustrates the distinct group-level initial toggle and member-level no-individual-choice behavior.

## Source index

- [Contributor guidance (`CONTRIBUTING.md`)](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/CONTRIBUTING.md#L285-L336)
- [CF group schema (`schemas/cf-groups.schema.json`)](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/schemas/cf-groups.schema.json#L17-L62)
- [Radarr CF group reference](https://github.com/TRaSH-Guides/Guides/blob/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/Guide-Sync/radarr-cf-groups.md#L3-L49)
- [HDR, Unwanted Formats, and Required Repack/Proper JSON examples](https://github.com/TRaSH-Guides/Guides/tree/0ecc2efc9f2434e2390c30aa75805cf233e785dc/docs/json/radarr/cf-groups)
