from pathlib import Path
from typing import Any

from utils.common.errors import SourceError
from utils.common.validation import read_object
from utils.source.constants import SERVICES


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


def collect_naming(
    source_dir: Path,
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    for service in SERVICES:
        filename = f"{service}-naming.json"
        path = source_dir / service / "naming" / filename
        naming = read_object(path)
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
