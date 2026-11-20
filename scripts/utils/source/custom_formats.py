import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.common.errors import SourceError
from utils.common.validation import read_object, required_string
from utils.mappings.indexer_flags import INDEXER_FLAG_MAPPING
from utils.mappings.language import LANGUAGE_MAPPING
from utils.mappings.quality_modifiers import QUALITY_MODIFIER_MAPPING
from utils.mappings.release_type import RELEASE_TYPE_MAPPING
from utils.mappings.source import SOURCE_MAPPING
from utils.source.constants import SERVICES


CustomFormatIndex = dict[tuple[str, str], tuple[str, dict[str, int]]]


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


CONDITION_DATA_TABLES = {
    "language": ("condition_languages", "language_name"),
    "source": ("condition_sources", "source"),
    "indexer_flag": ("condition_indexer_flags", "flag"),
    "quality_modifier": ("condition_quality_modifiers", "quality_modifier"),
    "release_type": ("condition_release_types", "release_type"),
    "resolution": ("condition_resolutions", "resolution"),
}


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
) -> CustomFormatIndex:
    regexes: dict[str, dict[str, Any]] = {}
    custom_formats: CustomFormatIndex = {}
    custom_format_names: set[str] = set()
    tags: set[str] = set()

    for service in SERVICES:
        custom_format_dir = source_dir / service / "cf"
        if not custom_format_dir.is_dir():
            raise SourceError(f"Missing in-scope TrashGuides directory: {custom_format_dir}")
        context = CustomFormatContext(service, regexes, rows, tags)

        for path in sorted(custom_format_dir.glob("*.json")):
            record = read_object(path)
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
    trash_id = required_string(record, "trash_id", path)
    raw_name = required_string(record, "name", path)
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
    name = required_string(specification, "name", path)
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
