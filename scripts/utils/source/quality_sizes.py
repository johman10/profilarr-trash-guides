from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from utils.common.errors import SourceError
from utils.common.validation import read_object, required_string
from utils.mappings.quality import map_quality_name
from utils.source.constants import SERVICES


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


def collect_quality_sizes(
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
            definition = read_object(path)
            raw_type = required_string(definition, "type", path)
            name = quality_type_names.get(raw_type.casefold(), raw_type.replace("-", " ").title())
            qualities = definition.get("qualities")
            if not isinstance(qualities, list):
                raise SourceError(f"{path}: expected 'qualities' to be an array")
            for item in qualities:
                if not isinstance(item, dict):
                    raise SourceError(f"{path}: each quality-size definition must be an object")
                quality_name = map_quality_name(service, item.get("quality"), path)
                rows[table].append(
                    {
                        "name": name,
                        "quality_name": quality_name,
                        "min_size": _rounded_size(item, "min", path, 0),
                        "max_size": _rounded_size(item, "max", path),
                        "preferred_size": _rounded_size(item, "preferred", path),
                    }
                )
