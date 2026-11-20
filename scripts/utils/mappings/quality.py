from pathlib import Path
from typing import Any

from utils.common.errors import SourceError


QUALITY_ALIASES = {
    ("sonarr", "Bluray-1080p Remux"): "Remux-1080p",
    ("sonarr", "Bluray-2160p Remux"): "Remux-2160p",
}


def map_quality_name(service: str, name: Any, path: Path) -> str:
    if not isinstance(name, str) or not name.strip():
        raise SourceError(f"{path}: quality name must be a non-empty string")
    normalized_name = " ".join(name.strip().split())
    return QUALITY_ALIASES.get((service, normalized_name), normalized_name)
