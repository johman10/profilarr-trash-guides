import json
from pathlib import Path
from typing import Any


MEDIA_FIELDS = {"name", "propers_repacks", "enable_media_info"}
DELAY_FIELDS = {
    "name",
    "preferred_protocol",
    "usenet_delay",
    "torrent_delay",
    "bypass_if_highest_quality",
    "bypass_if_above_custom_format_score",
    "minimum_custom_format_score",
}
TABLE_FIELDS = {
    "radarr_media_settings": MEDIA_FIELDS,
    "sonarr_media_settings": MEDIA_FIELDS,
    "delay_profiles": DELAY_FIELDS,
}
PROTOCOLS = {"prefer_usenet", "prefer_torrent", "only_usenet", "only_torrent"}
PROPERS_REPACKS = {"doNotPrefer", "preferAndUpgrade", "doNotUpgradeAutomatically"}
MIN_SQLITE_INTEGER = -(2**63)
MAX_SQLITE_INTEGER = 2**63 - 1


class CuratedError(ValueError):
    """Raised when repository-maintained settings are invalid."""


def _integer(value: Any, label: str, minimum: int = MIN_SQLITE_INTEGER) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= MAX_SQLITE_INTEGER:
        raise CuratedError(f"{label} must be an integer between {minimum} and {MAX_SQLITE_INTEGER}")


def _validate_record(table: str, record: Any, label: str) -> dict[str, Any]:
    if not isinstance(record, dict) or set(record) != TABLE_FIELDS[table]:
        raise CuratedError(f"{label} must be an object with exactly {sorted(TABLE_FIELDS[table])}")
    name = record["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 100 or name != name.strip():
        raise CuratedError(f"{label}: name must be non-empty, trimmed, and at most 100 characters")
    if table == "delay_profiles":
        _validate_delay(record, label)
    else:
        propers_repacks = record["propers_repacks"]
        if not isinstance(propers_repacks, str) or propers_repacks not in PROPERS_REPACKS:
            raise CuratedError(f"{label}: invalid propers_repacks")
        if not isinstance(record["enable_media_info"], bool):
            raise CuratedError(f"{label}: enable_media_info must be a boolean")
    return record


def _validate_delay(record: dict[str, Any], label: str) -> None:
    protocol = record["preferred_protocol"]
    if not isinstance(protocol, str) or protocol not in PROTOCOLS:
        raise CuratedError(f"{label}: invalid preferred_protocol")
    for field, excluded_protocol in (
        ("usenet_delay", "only_torrent"),
        ("torrent_delay", "only_usenet"),
    ):
        value = record[field]
        if protocol == excluded_protocol:
            if value is not None:
                raise CuratedError(f"{label}: {field} must be null for {protocol}")
        else:
            _integer(value, f"{label}: {field}", minimum=0)
    for field in ("bypass_if_highest_quality", "bypass_if_above_custom_format_score"):
        if not isinstance(record[field], bool):
            raise CuratedError(f"{label}: {field} must be a boolean")
    score = record["minimum_custom_format_score"]
    if record["bypass_if_above_custom_format_score"]:
        _integer(score, f"{label}: minimum_custom_format_score")
    elif score is not None:
        raise CuratedError(f"{label}: minimum_custom_format_score must be null when bypass is off")


def collect_curated_rows(path: Path, rows: dict[str, list[dict[str, Any]]]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CuratedError(f"Unable to read curated settings {path}: {error}") from error
    if not isinstance(data, dict) or set(data) != set(TABLE_FIELDS):
        raise CuratedError(f"{path}: expected exactly these tables: {sorted(TABLE_FIELDS)}")
    for table in TABLE_FIELDS:
        records = data[table]
        if not isinstance(records, list):
            raise CuratedError(f"{path}: {table} must be an array")
        names: set[str] = set()
        for index, value in enumerate(records):
            label = f"{path}: {table}[{index}]"
            record = _validate_record(table, value, label)
            if record["name"] in names:
                raise CuratedError(f"{label}: duplicate name {record['name']!r}")
            names.add(record["name"])
            rows[table].append(record)
