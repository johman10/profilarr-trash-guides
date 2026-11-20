import json
from pathlib import Path
from typing import Any

from utils.common.errors import SourceError


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"Unable to read TrashGuides JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise SourceError(f"Expected a JSON object in {path}")
    return value


def required_string(record: dict[str, Any], key: str, path: Path) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"{path}: expected a non-empty string field '{key}'")
    return " ".join(value.strip().split())
