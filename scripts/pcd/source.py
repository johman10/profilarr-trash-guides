import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from pcd.mappings import (
    INDEXER_FLAG_MAPPING,
    LANGUAGE_MAPPING,
    QUALITY_MODIFIER_MAPPING,
    RELEASE_TYPE_MAPPING,
    SOURCE_MAPPING,
)
from pcd.sql import empty_rows


SERVICES = ("radarr", "sonarr")
IMPLEMENTATIONS = {
    "ReleaseTitleSpecification": ("release_title", "Release Title"),
    "ReleaseGroupSpecification": ("release_group", "Release Group"),
    "ResolutionSpecification": ("resolution", "Resolution"),
    "SourceSpecification": ("source", "Source"),
    "LanguageSpecification": ("language", "Language"),
    "IndexerFlagSpecification": ("indexer_flag", "Indexer Flag"),
    "QualityModifierSpecification": ("quality_modifier", "Quality Modifier"),
    "ReleaseTypeSpecification": ("release_type", "Release Type"),
}
REGEX_IMPLEMENTATIONS = {"ReleaseTitleSpecification", "ReleaseGroupSpecification"}
QUALITY_ALIASES = {
    ("sonarr", "Bluray-1080p Remux"): "Remux-1080p",
    ("sonarr", "Bluray-2160p Remux"): "Remux-2160p",
}
CONDITION_DATA_TABLES = {
    "language": ("condition_languages", "language_name"),
    "source": ("condition_sources", "source"),
    "indexer_flag": ("condition_indexer_flags", "flag"),
    "quality_modifier": ("condition_quality_modifiers", "quality_modifier"),
    "release_type": ("condition_release_types", "release_type"),
    "resolution": ("condition_resolutions", "resolution"),
}


class SourceError(ValueError):
    """Raised when an in-scope TrashGuides record cannot be mapped."""


@dataclass(frozen=True)
class MappedCondition:
    name: str
    tag: str
    signature: tuple[Any, ...]
    condition_row: dict[str, Any]
    data_table: str | None
    data_row: dict[str, Any] | None
    regex_pattern: str | None


@dataclass
class CustomFormatContext:
    service: str
    regexes: dict[str, dict[str, Any]]
    rows: dict[str, list[dict[str, Any]]]
    tags: set[str]


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"Unable to read TrashGuides JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise SourceError(f"Expected a JSON object in {path}")
    return value


def _required_string(record: dict[str, Any], key: str, path: Path) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"{path}: expected a non-empty string field '{key}'")
    return " ".join(value.strip().split())


def _optional_integer(record: dict[str, Any], key: str, default: int, path: Path) -> int:
    value = record.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SourceError(f"{path}: expected '{key}' to be an integer")
    return value


def _rounded_size(record: dict[str, Any], key: str, path: Path, default: int | None = None) -> int:
    value = record.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SourceError(f"{path}: expected '{key}' to be a number")
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as error:
        raise SourceError(f"{path}: invalid quality-size value for '{key}'") from error
    if not decimal_value.is_finite():
        raise SourceError(f"{path}: quality-size value '{key}' must be finite")
    return int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _add_tag(rows: dict[str, list[dict[str, Any]]], name: str) -> None:
    if not any(row["name"] == name for row in rows["tags"]):
        rows["tags"].append({"name": name})


def _map_quality_name(service: str, name: Any, path: Path) -> str:
    if not isinstance(name, str) or not name.strip():
        raise SourceError(f"{path}: quality name must be a non-empty string")
    normalized_name = " ".join(name.strip().split())
    return QUALITY_ALIASES.get((service, normalized_name), normalized_name)


def _condition_value(
    implementation: str,
    fields: dict[str, Any],
    service: str,
    path: Path,
) -> str:
    raw_value = fields.get("value")
    if implementation in REGEX_IMPLEMENTATIONS:
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise SourceError(f"{path}: {implementation} requires a non-empty fields.value pattern")
        return raw_value.strip()
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        raise SourceError(f"{path}: {implementation} requires an integer fields.value")
    if implementation == "ResolutionSpecification":
        return f"{raw_value}p"

    mappings = {
        "LanguageSpecification": LANGUAGE_MAPPING,
        "SourceSpecification": SOURCE_MAPPING,
        "IndexerFlagSpecification": INDEXER_FLAG_MAPPING,
        "QualityModifierSpecification": QUALITY_MODIFIER_MAPPING,
        "ReleaseTypeSpecification": RELEASE_TYPE_MAPPING,
    }
    value_mapping = mappings.get(implementation)
    if value_mapping is None or raw_value not in value_mapping.get(service, {}):
        raise SourceError(
            f"{path}: no {service} mapping for {implementation} value {raw_value}"
        )
    return value_mapping[service][raw_value]


def collect_custom_formats(
    source_dir: Path,
    rows: dict[str, list[dict[str, Any]]],
) -> dict[tuple[str, str], tuple[str, dict[str, int]]]:
    regexes: dict[str, dict[str, Any]] = {}
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]] = {}
    custom_format_names: set[str] = set()
    tags: set[str] = set()

    for service in SERVICES:
        custom_format_dir = source_dir / service / "cf"
        if not custom_format_dir.is_dir():
            raise SourceError(f"Missing in-scope TrashGuides directory: {custom_format_dir}")
        context = CustomFormatContext(service, regexes, rows, tags)

        for path in sorted(custom_format_dir.glob("*.json")):
            record = _read_object(path)
            trash_id, name, scores = _collect_custom_format(record, path, context)
            if name in custom_format_names:
                raise SourceError(f"{path}: duplicate generated custom-format name '{name}'")
            custom_format_names.add(name)
            custom_formats[(service, trash_id)] = (name, scores)

    for regex in sorted(regexes.values(), key=lambda item: item["name"]):
        rows["regular_expressions"].append(
            {"name": regex["name"], "pattern": regex["pattern"]}
        )
        rows["regular_expression_tags"].extend(
            {"regular_expression_name": regex["name"], "tag_name": tag}
            for tag in sorted(regex["tags"])
        )

    rows["tags"].extend({"name": tag} for tag in sorted(tags))
    return custom_formats


def _collect_custom_format(
    record: dict[str, Any],
    path: Path,
    context: CustomFormatContext,
) -> tuple[str, str, dict[str, int]]:
    trash_id = _required_string(record, "trash_id", path)
    raw_name = _required_string(record, "name", path)
    name = f"{context.service.title()} - {raw_name}"
    specifications = record.get("specifications")
    if not isinstance(specifications, list):
        raise SourceError(f"{path}: expected 'specifications' to be an array")

    description = record.get("trash_description")
    if description is not None and not isinstance(description, str):
        raise SourceError(f"{path}: 'trash_description' must be a string")
    include_in_rename = record.get("includeCustomFormatWhenRenaming", False)
    if not isinstance(include_in_rename, bool):
        raise SourceError(f"{path}: 'includeCustomFormatWhenRenaming' must be a boolean")
    score_record = record.get("trash_scores", {})
    if not isinstance(score_record, dict) or any(
        not isinstance(score_name, str)
        or not isinstance(score, int)
        or isinstance(score, bool)
        for score_name, score in score_record.items()
    ):
        raise SourceError(f"{path}: 'trash_scores' must map names to integer scores")

    context.rows["custom_formats"].append(
        {
            "name": name,
            "description": description,
            "include_in_rename": int(include_in_rename),
        }
    )
    service_tag = context.service.title()
    context.tags.add(service_tag)
    format_tags = _collect_conditions(specifications, path, name, raw_name, context)
    context.rows["custom_format_tags"].extend(
        {"custom_format_name": name, "tag_name": tag}
        for tag in sorted(format_tags)
    )
    return trash_id, name, dict(score_record)


def _map_condition(specification: dict[str, Any], service: str, path: Path) -> MappedCondition:
    implementation = specification.get("implementation")
    mapped_type = IMPLEMENTATIONS.get(implementation)
    if mapped_type is None:
        raise SourceError(f"{path}: unsupported specification implementation {implementation!r}")
    condition_type, tag = mapped_type
    name = _required_string(specification, "name", path)
    fields = specification.get("fields")
    if not isinstance(fields, dict):
        raise SourceError(f"{path}: specification '{name}' requires an object 'fields'")
    value = _condition_value(implementation, fields, service, path)
    negate = specification.get("negate", False)
    required = specification.get("required", False)
    if not isinstance(negate, bool) or not isinstance(required, bool):
        raise SourceError(f"{path}: condition '{name}' negate and required must be booleans")
    except_language = fields.get("exceptLanguage", False)
    if condition_type == "language" and not isinstance(except_language, bool):
        raise SourceError(f"{path}: fields.exceptLanguage must be a boolean")
    data_mapping = CONDITION_DATA_TABLES.get(condition_type)
    data_row = None
    if data_mapping is not None:
        data_row = {"condition_name": name, data_mapping[1]: value}
        if condition_type == "language":
            data_row["except_language"] = int(except_language)
    return MappedCondition(
        name=name,
        tag=tag,
        signature=(implementation, value, negate, required, except_language),
        condition_row=_condition_row(name, condition_type, service, negate, required),
        data_table=data_mapping[0] if data_mapping is not None else None,
        data_row=data_row,
        regex_pattern=value if implementation in REGEX_IMPLEMENTATIONS else None,
    )


def _condition_row(
    name: str,
    condition_type: str,
    service: str,
    negate: bool,
    required: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "type": condition_type,
        "arr_type": service,
        "negate": int(negate),
        "required": int(required),
    }


def _collect_conditions(
    specifications: list[Any],
    path: Path,
    custom_format_name: str,
    raw_name: str,
    context: CustomFormatContext,
) -> set[str]:
    seen: dict[str, tuple[Any, ...]] = {}
    service_tag = context.service.title()
    format_tags = {service_tag}
    for specification in specifications:
        if not isinstance(specification, dict):
            raise SourceError(f"{path}: each specification must be an object")
        mapped = _map_condition(specification, context.service, path)
        existing = seen.get(mapped.name)
        if existing is not None:
            if existing != mapped.signature:
                raise SourceError(
                    f"{path}: conflicting duplicate condition name '{mapped.name}' "
                    f"in custom format '{raw_name}'"
                )
            continue
        seen[mapped.name] = mapped.signature
        _append_mapped_condition(mapped, custom_format_name, service_tag, context)
        format_tags.add(mapped.tag)
    return format_tags


def _append_mapped_condition(
    mapped: MappedCondition,
    custom_format_name: str,
    service_tag: str,
    context: CustomFormatContext,
) -> None:
    condition_row = dict(mapped.condition_row)
    condition_row["custom_format_name"] = custom_format_name
    context.rows["custom_format_conditions"].append(condition_row)
    context.tags.add(mapped.tag)

    if mapped.regex_pattern is not None:
        regex = context.regexes.get(mapped.regex_pattern)
        if regex is None:
            suffix = hashlib.sha256(mapped.regex_pattern.encode("utf-8")).hexdigest()[:10]
            regex_name = f"{mapped.name} [{suffix}]"
            regex = {"name": regex_name, "pattern": mapped.regex_pattern, "tags": set()}
            context.regexes[mapped.regex_pattern] = regex
        regex["tags"].add(service_tag)
        context.rows["condition_patterns"].append(
            {
                "custom_format_name": custom_format_name,
                "condition_name": mapped.name,
                "regular_expression_name": regex["name"],
            }
        )
    elif mapped.data_table is not None and mapped.data_row is not None:
        data_row = dict(mapped.data_row)
        data_row["custom_format_name"] = custom_format_name
        context.rows[mapped.data_table].append(data_row)


def _collect_profile_tags(source_dir: Path, service: str) -> dict[str, set[str]]:
    path = source_dir / service / "quality-profile-groups" / "groups.json"
    if not path.is_file():
        raise SourceError(f"Missing in-scope TrashGuides file: {path}")
    try:
        groups = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"Unable to read TrashGuides JSON {path}: {error}") from error
    if not isinstance(groups, list):
        raise SourceError(f"{path}: expected an array of quality-profile groups")

    tags_by_profile_id: dict[str, set[str]] = {}
    for group in groups:
        if not isinstance(group, dict):
            raise SourceError(f"{path}: each quality-profile group must be an object")
        group_name = _required_string(group, "name", path)
        profiles = group.get("profiles")
        if not isinstance(profiles, dict):
            raise SourceError(f"{path}: group '{group_name}' profiles must be an object")
        for profile_id in profiles.values():
            if not isinstance(profile_id, str) or not profile_id:
                raise SourceError(f"{path}: group '{group_name}' contains an invalid profile id")
            tags_by_profile_id.setdefault(profile_id, set()).add(group_name)
    return tags_by_profile_id


def _collect_quality_profiles(
    source_dir: Path,
    rows: dict[str, list[dict[str, Any]]],
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]],
) -> None:
    for service in SERVICES:
        profile_dir = source_dir / service / "quality-profiles"
        if not profile_dir.is_dir():
            raise SourceError(f"Missing in-scope TrashGuides directory: {profile_dir}")
        profile_tags_by_id = _collect_profile_tags(source_dir, service)
        profiles = _read_profile_records(profile_dir, service)
        for profile in profiles.values():
            _append_profile_rows(profile, service, profile_tags_by_id, rows)
            _append_direct_profile_assignments(profile, service, custom_formats)
        _collect_cf_group_assignments(source_dir, service, profiles, custom_formats)
        _append_profile_custom_formats(profiles, service, rows)


@dataclass
class QualityProfile:
    path: Path
    source: dict[str, Any]
    profile_id: str
    name: str
    score_set: str
    format_items: dict[str, str]
    assignments: dict[str, int]


def _read_profile_records(profile_dir: Path, service: str) -> dict[str, QualityProfile]:
    profiles = {}
    names = set()
    for path in sorted(profile_dir.glob("*.json")):
        source = _read_object(path)
        profile_id = _required_string(source, "trash_id", path)
        profile_name = _required_string(source, "name", path)
        output_name = f"{service.title()} - {profile_name}"
        if profile_id in profiles or output_name in names:
            raise SourceError(f"{path}: duplicate quality-profile id or name '{output_name}'")
        score_set = source.get("trash_score_set", "default")
        if not isinstance(score_set, str) or not score_set:
            raise SourceError(f"{path}: 'trash_score_set' must be a non-empty string")
        format_items = source.get("formatItems", {})
        if not isinstance(format_items, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in format_items.items()
        ):
            raise SourceError(f"{path}: 'formatItems' must map names to custom-format ids")
        profiles[profile_id] = QualityProfile(
            path=path,
            source=source,
            profile_id=profile_id,
            name=output_name,
            score_set=score_set,
            format_items=format_items,
            assignments={},
        )
        names.add(output_name)
    return profiles


def _append_profile_rows(
    profile: QualityProfile,
    service: str,
    profile_tags_by_id: dict[str, set[str]],
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    source = profile.source
    description = source.get("trash_description")
    if description is not None and not isinstance(description, str):
        raise SourceError(f"{profile.path}: 'trash_description' must be a string")
    upgrades_allowed = source.get("upgradeAllowed", True)
    if not isinstance(upgrades_allowed, bool):
        raise SourceError(f"{profile.path}: 'upgradeAllowed' must be a boolean")
    rows["quality_profiles"].append(
        {
            "name": profile.name,
            "description": description,
            "upgrades_allowed": int(upgrades_allowed),
            "minimum_custom_format_score": _optional_integer(
                source, "minFormatScore", 0, profile.path
            ),
            "upgrade_until_score": _optional_integer(
                source, "cutoffFormatScore", 0, profile.path
            ),
            "upgrade_score_increment": _optional_integer(
                source, "minUpgradeFormatScore", 1, profile.path
            ),
        }
    )
    _append_profile_tags(profile, service, profile_tags_by_id, rows)
    _append_profile_language(profile, service, rows)
    _append_profile_quality_items(profile, service, rows)


def _append_profile_tags(
    profile: QualityProfile,
    service: str,
    profile_tags_by_id: dict[str, set[str]],
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    profile_tags = profile_tags_by_id.get(profile.profile_id, set())
    profile_tags.add(service.title())
    for tag in sorted(profile_tags):
        _add_tag(rows, tag)
        rows["quality_profile_tags"].append(
            {"quality_profile_name": profile.name, "tag_name": tag}
        )


def _append_profile_language(
    profile: QualityProfile,
    service: str,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    if service != "radarr" or "language" not in profile.source:
        return
    language = profile.source["language"]
    if not isinstance(language, str) or not language.strip():
        raise SourceError(f"{profile.path}: profile language must be a non-empty string")
    known_languages = {
        value.casefold(): value
        for values in LANGUAGE_MAPPING.values()
        for value in values.values()
    }
    canonical_language = known_languages.get(language.strip().casefold())
    if canonical_language is None:
        raise SourceError(f"{profile.path}: no Profilarr v2 language mapping for {language!r}")
    rows["quality_profile_languages"].append(
        {
            "quality_profile_name": profile.name,
            "language_name": canonical_language,
            "type": "simple",
        }
    )


def _append_profile_quality_items(
    profile: QualityProfile,
    service: str,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    items = profile.source.get("items")
    if not isinstance(items, list):
        raise SourceError(f"{profile.path}: expected 'items' to be an array")
    cutoff_name = profile.source.get("cutoff")
    if cutoff_name is not None and not isinstance(cutoff_name, str):
        raise SourceError(f"{profile.path}: 'cutoff' must be a string")
    found_cutoff = cutoff_name is None
    seen_groups: set[str] = set()
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            raise SourceError(f"{profile.path}: each quality-profile item must be an object")
        found_cutoff = _append_quality_item(
            profile,
            service,
            item,
            position,
            rows,
            cutoff_name=cutoff_name,
            seen_groups=seen_groups,
        ) or found_cutoff
    if not found_cutoff:
        raise SourceError(f"{profile.path}: cutoff quality {cutoff_name!r} is not a profile item")


def _append_quality_item(
    profile: QualityProfile,
    service: str,
    item: dict[str, Any],
    position: int,
    rows: dict[str, list[dict[str, Any]]],
    *,
    cutoff_name: str | None,
    seen_groups: set[str],
) -> bool:
    item_name = _required_string(item, "name", profile.path)
    allowed = item.get("allowed", False)
    if not isinstance(allowed, bool):
        raise SourceError(f"{profile.path}: quality '{item_name}' allowed must be a boolean")
    upgrade_until = int(item_name == cutoff_name)
    nested_items = item.get("items")
    if nested_items is None:
        quality_row = {
            "quality_profile_name": profile.name,
            "quality_name": _map_quality_name(service, item_name, profile.path),
            "quality_group_name": None,
            "position": position,
            "enabled": int(allowed),
            "upgrade_until": upgrade_until,
        }
        rows["quality_profile_qualities"].append(quality_row)
        return bool(upgrade_until)

    _append_quality_group(
        profile, service, item_name, nested_items, rows, seen_groups=seen_groups
    )
    rows["quality_profile_qualities"].append(
        {
            "quality_profile_name": profile.name,
            "quality_name": None,
            "quality_group_name": item_name,
            "position": position,
            "enabled": int(allowed),
            "upgrade_until": upgrade_until,
        }
    )
    return bool(upgrade_until)


def _append_quality_group(
    profile: QualityProfile,
    service: str,
    group_name: str,
    members: Any,
    rows: dict[str, list[dict[str, Any]]],
    *,
    seen_groups: set[str],
) -> None:
    if not isinstance(members, list) or not members:
        raise SourceError(f"{profile.path}: quality group '{group_name}' must have members")
    if group_name in seen_groups:
        raise SourceError(f"{profile.path}: duplicate quality group '{group_name}'")
    seen_groups.add(group_name)
    rows["quality_groups"].append(
        {"quality_profile_name": profile.name, "name": group_name}
    )
    seen_members: set[str] = set()
    for position, member in enumerate(members):
        quality_name = _map_quality_name(service, member, profile.path)
        if quality_name in seen_members:
            raise SourceError(
                f"{profile.path}: duplicate quality '{quality_name}' in group '{group_name}'"
            )
        seen_members.add(quality_name)
        rows["quality_group_members"].append(
            {
                "quality_profile_name": profile.name,
                "quality_group_name": group_name,
                "quality_name": quality_name,
                "position": position,
            }
        )


def _append_direct_profile_assignments(
    profile: QualityProfile,
    service: str,
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]],
) -> None:
    for trash_id in profile.format_items.values():
        custom_format = custom_formats.get((service, trash_id))
        if custom_format is None:
            raise SourceError(
                f"{profile.path}: profile '{profile.name}' references unknown custom-format id "
                f"'{trash_id}'"
            )
        name, scores = custom_format
        score = scores.get(profile.score_set, scores.get("default", 0))
        _add_assignment(profile.assignments, name, score, profile.path)


def _collect_cf_group_assignments(
    source_dir: Path,
    service: str,
    profiles: dict[str, QualityProfile],
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]],
) -> None:
    directory = source_dir / service / "cf-groups"
    if not directory.is_dir():
        raise SourceError(f"Missing in-scope TrashGuides directory: {directory}")
    for path in sorted(directory.glob("*.json")):
        group = _read_object(path)
        if group.get("default") == "true":
            _apply_cf_group(path, group, service, profiles, custom_formats)


def _apply_cf_group(
    path: Path,
    group: dict[str, Any],
    service: str,
    profiles: dict[str, QualityProfile],
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]],
) -> None:
    quality_profiles = group.get("quality_profiles")
    include = quality_profiles.get("include") if isinstance(quality_profiles, dict) else None
    if not isinstance(include, dict):
        raise SourceError(f"{path}: enabled CF group requires quality_profiles.include")
    members = group.get("custom_formats")
    if not isinstance(members, list):
        raise SourceError(f"{path}: enabled CF group requires a custom_formats array")
    for profile_id in include.values():
        profile = profiles.get(profile_id) if isinstance(profile_id, str) else None
        if profile is None:
            raise SourceError(
                f"{path}: enabled CF group references unknown {service} profile id {profile_id!r}"
            )
        _apply_cf_group_members(path, members, service, profile, custom_formats)


def _apply_cf_group_members(
    path: Path,
    members: list[Any],
    service: str,
    profile: QualityProfile,
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]],
) -> None:
    for member in members:
        if not isinstance(member, dict):
            raise SourceError(f"{path}: each CF group member must be an object")
        required = member.get("required", False)
        default = member.get("default", False)
        if not isinstance(required, bool) or not isinstance(default, bool):
            raise SourceError(f"{path}: CF group member required/default values must be booleans")
        if required or default:
            _add_cf_group_member(path, member, service, profile, custom_formats)


def _add_cf_group_member(
    path: Path,
    member: dict[str, Any],
    service: str,
    profile: QualityProfile,
    custom_formats: dict[tuple[str, str], tuple[str, dict[str, int]]],
) -> None:
    trash_id = _required_string(member, "trash_id", path)
    custom_format = custom_formats.get((service, trash_id))
    if custom_format is None:
        raise SourceError(
            f"{path}: selected CF group member references unknown {service} "
            f"custom-format id '{trash_id}'"
        )
    name, scores = custom_format
    score = scores.get(profile.score_set, scores.get("default", 0))
    _add_assignment(profile.assignments, name, score, path)


def _append_profile_custom_formats(
    profiles: dict[str, QualityProfile],
    service: str,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    for profile in profiles.values():
        for custom_format_name, score in sorted(profile.assignments.items()):
            rows["quality_profile_custom_formats"].append(
                {
                    "quality_profile_name": profile.name,
                    "custom_format_name": custom_format_name,
                    "arr_type": service,
                    "score": score,
                }
            )


def _collect_quality_sizes(
    source_dir: Path,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    quality_type_names = {
        "movie": "Movie",
        "series": "Series",
        "anime": "Anime",
        "sqp-streaming": "SQP Streaming",
        "sqp-uhd": "SQP UHD",
    }
    for service in SERVICES:
        directory = source_dir / service / "quality-size"
        if not directory.is_dir():
            raise SourceError(f"Missing in-scope TrashGuides directory: {directory}")
        table = f"{service}_quality_definitions"
        for path in sorted(directory.glob("*.json")):
            definition = _read_object(path)
            raw_type = _required_string(definition, "type", path)
            name = quality_type_names.get(raw_type.casefold(), raw_type.replace("-", " ").title())
            qualities = definition.get("qualities")
            if not isinstance(qualities, list):
                raise SourceError(f"{path}: expected 'qualities' to be an array")
            for item in qualities:
                if not isinstance(item, dict):
                    raise SourceError(f"{path}: each quality-size definition must be an object")
                quality_name = _map_quality_name(service, item.get("quality"), path)
                rows[table].append(
                    {
                        "name": name,
                        "quality_name": quality_name,
                        "min_size": _rounded_size(item, "min", path, 0),
                        "max_size": _rounded_size(item, "max", path),
                        "preferred_size": _rounded_size(item, "preferred", path),
                    }
                )


def _naming_formats(value: Any, label: str, path: Path) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise SourceError(f"{path}: expected '{label}' to be a non-empty object")
    if any(
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(format_string, str)
        or not format_string.strip()
        for name, format_string in value.items()
    ):
        raise SourceError(f"{path}: '{label}' must map names to non-empty format strings")
    return value


def _naming_format_for(
    formats: dict[str, str],
    variant: str,
    label: str,
    path: Path,
) -> str:
    candidates = (variant, variant.split("-", 1)[0], "default")
    for candidate in candidates:
        if candidate in formats:
            return formats[candidate]
    raise SourceError(f"{path}: no '{label}' format for naming variant '{variant}'")


def _collect_naming(
    source_dir: Path,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    for service in SERVICES:
        filename = f"{service}-naming.json"
        path = source_dir / service / "naming" / filename
        naming = _read_object(path)
        if service == "radarr":
            file_formats = _naming_formats(naming.get("file"), "file", path)
            folder_formats = _naming_formats(naming.get("folder"), "folder", path)
            for variant, movie_format in sorted(file_formats.items()):
                rows["radarr_naming"].append(
                    {
                        "name": variant,
                        "movie_format": movie_format,
                        "movie_folder_format": _naming_format_for(
                            folder_formats, variant, "folder", path
                        ),
                    }
                )
            continue

        _collect_sonarr_naming(path, naming, rows)


def _collect_sonarr_naming(
    path: Path,
    naming: dict[str, Any],
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    episodes = naming.get("episodes")
    if not isinstance(episodes, dict):
        raise SourceError(f"{path}: expected 'episodes' to be an object")
    episode_formats = {
        episode_type: _naming_formats(episodes.get(episode_type), f"episodes.{episode_type}", path)
        for episode_type in ("standard", "daily", "anime")
    }
    series_formats = _naming_formats(naming.get("series"), "series", path)
    season_formats = _naming_formats(naming.get("season"), "season", path)
    variants = set(series_formats)
    for formats in (*episode_formats.values(), season_formats):
        variants.update(formats)
    for variant in sorted(variants):
        rows["sonarr_naming"].append(
            {
                "name": variant,
                "standard_episode_format": _naming_format_for(
                    episode_formats["standard"], variant, "episodes.standard", path
                ),
                "daily_episode_format": _naming_format_for(
                    episode_formats["daily"], variant, "episodes.daily", path
                ),
                "anime_episode_format": _naming_format_for(
                    episode_formats["anime"], variant, "episodes.anime", path
                ),
                "series_folder_format": _naming_format_for(
                    series_formats, variant, "series", path
                ),
                "season_folder_format": _naming_format_for(
                    season_formats, variant, "season", path
                ),
            }
        )


def _add_assignment(
    assignments: dict[str, int],
    custom_format_name: str,
    score: int,
    path: Path,
) -> None:
    existing_score = assignments.get(custom_format_name)
    if existing_score is not None and existing_score != score:
        raise SourceError(
            f"{path}: custom format '{custom_format_name}' has conflicting profile scores "
            f"{existing_score} and {score}"
        )
    assignments[custom_format_name] = score


def collect_source_rows(source_dir: Path) -> dict[str, list[dict[str, Any]]]:
    rows = empty_rows()
    custom_formats = collect_custom_formats(source_dir, rows)
    _collect_quality_profiles(source_dir, rows, custom_formats)
    _collect_quality_sizes(source_dir, rows)
    _collect_naming(source_dir, rows)
    return rows
