import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.common.errors import SourceError
from utils.common.validation import read_object, required_string
from utils.mappings.language import LANGUAGE_MAPPING
from utils.mappings.quality import map_quality_name
from utils.source.constants import SERVICES
from utils.source.custom_formats import CustomFormatIndex


def _optional_integer(record: dict[str, Any], key: str, default: int, path: Path) -> int:
    value = record.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SourceError(f"{path}: expected '{key}' to be an integer")
    return value


def _add_tag(rows: dict[str, list[dict[str, Any]]], name: str) -> None:
    if not any(row["name"] == name for row in rows["tags"]):
        rows["tags"].append({"name": name})


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
        group_name = required_string(group, "name", path)
        profiles = group.get("profiles")
        if not isinstance(profiles, dict):
            raise SourceError(f"{path}: group '{group_name}' profiles must be an object")
        for profile_id in profiles.values():
            if not isinstance(profile_id, str) or not profile_id:
                raise SourceError(f"{path}: group '{group_name}' contains an invalid profile id")
            tags_by_profile_id.setdefault(profile_id, set()).add(group_name)
    return tags_by_profile_id


def collect_quality_profiles(
    source_dir: Path,
    rows: dict[str, list[dict[str, Any]]],
    custom_formats: CustomFormatIndex,
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
        source = read_object(path)
        profile_id = required_string(source, "trash_id", path)
        profile_name = required_string(source, "name", path)
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
    item_name = required_string(item, "name", profile.path)
    allowed = item.get("allowed", False)
    if not isinstance(allowed, bool):
        raise SourceError(f"{profile.path}: quality '{item_name}' allowed must be a boolean")
    upgrade_until = int(item_name == cutoff_name)
    nested_items = item.get("items")
    if nested_items is None:
        quality_row = {
            "quality_profile_name": profile.name,
            "quality_name": map_quality_name(service, item_name, profile.path),
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
        quality_name = map_quality_name(service, member, profile.path)
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
    custom_formats: CustomFormatIndex,
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
    custom_formats: CustomFormatIndex,
) -> None:
    directory = source_dir / service / "cf-groups"
    if not directory.is_dir():
        raise SourceError(f"Missing in-scope TrashGuides directory: {directory}")
    for path in sorted(directory.glob("*.json")):
        group = read_object(path)
        if group.get("default") == "true":
            _apply_cf_group(path, group, service, profiles, custom_formats)


def _apply_cf_group(
    path: Path,
    group: dict[str, Any],
    service: str,
    profiles: dict[str, QualityProfile],
    custom_formats: CustomFormatIndex,
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
    custom_formats: CustomFormatIndex,
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
    custom_formats: CustomFormatIndex,
) -> None:
    trash_id = required_string(member, "trash_id", path)
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
