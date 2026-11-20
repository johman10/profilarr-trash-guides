from pathlib import Path
from typing import Any

from utils.source.custom_formats import collect_custom_formats
from utils.source.naming import collect_naming
from utils.source.quality_profiles import collect_quality_profiles
from utils.source.quality_sizes import collect_quality_sizes
from utils.sql import empty_rows


def collect_source_rows(source_dir: Path) -> dict[str, list[dict[str, Any]]]:
    rows = empty_rows()
    custom_formats = collect_custom_formats(source_dir, rows)
    collect_quality_profiles(source_dir, rows, custom_formats)
    collect_quality_sizes(source_dir, rows)
    collect_naming(source_dir, rows)
    return rows
