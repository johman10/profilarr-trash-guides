import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_OPERATIONS = ROOT / "scripts" / "schema" / "1.1.0" / "ops"


def _write_json(root: Path, relative_path: str, payload: object) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _validate_output(output_dir: Path) -> sqlite3.Connection:
    database = sqlite3.connect(":memory:")
    database.execute("PRAGMA foreign_keys = ON")

    for operation in sorted(SCHEMA_OPERATIONS.glob("*.sql")):
        database.executescript(operation.read_text(encoding="utf-8"))
    for operation in sorted((output_dir / "ops").glob("*.sql")):
        database.executescript(operation.read_text(encoding="utf-8"))

    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    return database


def test_cli_generates_schema_valid_custom_format(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    shutil.copyfile(ROOT / "pcd.json", output_dir / "pcd.json")

    _write_json(
        source_dir,
        "radarr/cf/hdr.json",
        {
            "trash_id": "hdr-id",
            "name": "HDR",
            "trash_description": "HDR's release condition.",
            "includeCustomFormatWhenRenaming": True,
            "specifications": [
                {
                    "name": "HDR title",
                    "implementation": "ReleaseTitleSpecification",
                    "negate": True,
                    "required": True,
                    "fields": {"value": r"\bHDR\b"},
                },
                {
                    "name": "HDR title",
                    "implementation": "ReleaseTitleSpecification",
                    "negate": True,
                    "required": True,
                    "fields": {"value": r"\bHDR\b"},
                },
            ],
        },
    )
    for service in ("radarr", "sonarr"):
        for directory in (
            "cf",
            "cf-groups",
            "quality-profiles",
            "quality-profile-groups",
            "quality-size",
            "naming",
        ):
            (source_dir / service / directory).mkdir(parents=True, exist_ok=True)
    _write_json(
        source_dir,
        "radarr/naming/radarr-naming.json",
        {"file": {"standard": "{Movie Title}"}, "folder": {"default": "{Movie Title}"}},
    )
    _write_json(
        source_dir,
        "sonarr/naming/sonarr-naming.json",
        {
            "episodes": {
                "standard": {"default": "{Series Title}"},
                "daily": {"default": "{Series Title}"},
                "anime": {"default": "{Series Title}"},
            },
            "series": {"default": "{Series Title}"},
            "season": {"default": "Season {season:00}"},
        },
    )
    _write_json(source_dir, "radarr/quality-size/movie.json", {"type": "movie", "qualities": []})
    _write_json(source_dir, "sonarr/quality-size/series.json", {"type": "series", "qualities": []})
    _write_json(source_dir, "radarr/quality-profile-groups/groups.json", [])
    _write_json(source_dir, "sonarr/quality-profile-groups/groups.json", [])

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate.py"), str(source_dir), str(output_dir)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    manifest = json.loads((output_dir / "pcd.json").read_text(encoding="utf-8"))
    assert manifest["dependencies"]["https://github.com/Dictionarry-Hub/schema"] == "1.1.0"

    database = _validate_output(output_dir)
    custom_format = database.execute(
        "SELECT description, include_in_rename FROM custom_formats WHERE name = ?",
        ("Radarr - HDR",),
    ).fetchone()
    assert custom_format == ("HDR's release condition.", 1)

    condition = database.execute(
        """
        SELECT type, arr_type, negate, required, regular_expressions.pattern
        FROM custom_format_conditions
        JOIN condition_patterns
          ON condition_patterns.custom_format_name = custom_format_conditions.custom_format_name
         AND condition_patterns.condition_name = custom_format_conditions.name
        JOIN regular_expressions
          ON regular_expressions.name = condition_patterns.regular_expression_name
        WHERE custom_format_conditions.custom_format_name = ?
          AND custom_format_conditions.name = ?
        """,
        ("Radarr - HDR", "HDR title"),
    ).fetchone()
    assert condition == ("release_title", "radarr", 1, 1, r"\bHDR\b")

    database.close()
    validation = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate.py"), str(output_dir)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert validation.returncode == 0, validation.stderr or validation.stdout


def _basic_source_tree(root: Path) -> None:
    for service in ("radarr", "sonarr"):
        for directory in (
            "cf",
            "cf-groups",
            "quality-profiles",
            "quality-profile-groups",
            "quality-size",
            "naming",
        ):
            (root / service / directory).mkdir(parents=True, exist_ok=True)
    _write_json(
        root,
        "radarr/naming/radarr-naming.json",
        {"file": {"standard": "{Movie Title}"}, "folder": {"default": "{Movie Title}"}},
    )
    _write_json(
        root,
        "sonarr/naming/sonarr-naming.json",
        {
            "episodes": {
                "standard": {"default": "{Series Title}"},
                "daily": {"default": "{Series Title}"},
                "anime": {"default": "{Series Title}"},
            },
            "series": {"default": "{Series Title}"},
            "season": {"default": "Season {season:00}"},
        },
    )
    _write_json(root, "radarr/quality-size/movie.json", {"type": "movie", "qualities": []})
    _write_json(root, "sonarr/quality-size/series.json", {"type": "series", "qualities": []})
    _write_json(root, "radarr/quality-profile-groups/groups.json", [])
    _write_json(root, "sonarr/quality-profile-groups/groups.json", [])


def _run_generation(
    source_dir: Path, output_dir: Path, script: Path = ROOT / "scripts" / "generate.py"
) -> subprocess.CompletedProcess[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "pcd.json", output_dir / "pcd.json")
    return subprocess.run(
        [sys.executable, str(script), str(source_dir), str(output_dir)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _copy_generator(root: Path) -> tuple[Path, Path]:
    shutil.copytree(ROOT / "scripts", root / "scripts")
    shutil.copytree(ROOT / "config", root / "config")
    return root / "scripts" / "generate.py", root / "config" / "curated-settings.json"


def test_curated_settings_generate_and_reconcile(tmp_path: Path) -> None:
    source_dir, output_dir = tmp_path / "source", tmp_path / "output"
    _basic_source_tree(source_dir)
    script, config = _copy_generator(tmp_path / "generator")
    initial = _run_generation(source_dir, output_dir, script)
    assert initial.returncode == 0, initial.stderr

    database = _validate_output(output_dir)
    for service in ("radarr", "sonarr"):
        assert database.execute(
            f"SELECT name, propers_repacks, enable_media_info FROM {service}_media_settings"
        ).fetchall() == [("Default", "doNotPrefer", 1)]
    assert database.execute(
        "SELECT name, preferred_protocol, usenet_delay, torrent_delay, "
        "bypass_if_highest_quality, bypass_if_above_custom_format_score, "
        "minimum_custom_format_score FROM delay_profiles"
    ).fetchall() == [("Default", "prefer_usenet", 0, 0, 0, 0, None)]
    database.close()

    curated = json.loads(config.read_text(encoding="utf-8"))
    curated["radarr_media_settings"][0]["enable_media_info"] = False
    curated["sonarr_media_settings"] = []
    curated["delay_profiles"][0].update(
        preferred_protocol="only_torrent", usenet_delay=None, torrent_delay=30
    )
    curated["delay_profiles"].append({
        **curated["delay_profiles"][0],
        "name": "Second",
        "bypass_if_above_custom_format_score": True,
        "minimum_custom_format_score": 100,
    })
    config.write_text(json.dumps(curated), encoding="utf-8")
    update = _run_generation(source_dir, output_dir, script)
    assert update.returncode == 0, update.stderr
    update_sql = (output_dir / "ops" / "2.update.sql").read_text(encoding="utf-8")
    assert 'DELETE FROM "sonarr_media_settings"' in update_sql
    assert '"enable_media_info" IS 1' in update_sql

    database = _validate_output(output_dir)
    assert database.execute("SELECT enable_media_info FROM radarr_media_settings").fetchall() == [(0,)]
    assert database.execute("SELECT name FROM sonarr_media_settings").fetchall() == []
    assert database.execute(
        "SELECT name, preferred_protocol, usenet_delay, torrent_delay, minimum_custom_format_score "
        "FROM delay_profiles ORDER BY name"
    ).fetchall() == [
        ("Default", "only_torrent", None, 30, None),
        ("Second", "only_torrent", None, 30, 100),
    ]
    database.close()

    database = sqlite3.connect(":memory:")
    for operation in sorted(SCHEMA_OPERATIONS.glob("*.sql")):
        database.executescript(operation.read_text(encoding="utf-8"))
    database.executescript((output_dir / "ops" / "1.initial.sql").read_text(encoding="utf-8"))
    database.execute("UPDATE radarr_media_settings SET propers_repacks = 'preferAndUpgrade'")
    database.execute("UPDATE sonarr_media_settings SET propers_repacks = 'preferAndUpgrade'")
    database.executescript(update_sql)
    assert database.execute(
        "SELECT propers_repacks, enable_media_info FROM radarr_media_settings"
    ).fetchall() == [("preferAndUpgrade", 1)]
    assert database.execute("SELECT propers_repacks FROM sonarr_media_settings").fetchall() == [
        ("preferAndUpgrade",)
    ]
    database.close()

    rerun = _run_generation(source_dir, output_dir, script)
    assert rerun.returncode == 0, rerun.stderr
    assert len(list((output_dir / "ops").glob("*.sql"))) == 2


@pytest.mark.parametrize(
    "invalid",
    ["duplicate", "negative", "boolean_delay", "protocol", "score", "unused_score", "media_type"],
)
def test_invalid_curated_settings_do_not_create_operation(tmp_path: Path, invalid: str) -> None:
    source_dir, output_dir = tmp_path / "source", tmp_path / "output"
    _basic_source_tree(source_dir)
    script, config = _copy_generator(tmp_path / "generator")
    initial = _run_generation(source_dir, output_dir, script)
    assert initial.returncode == 0, initial.stderr
    curated = json.loads(config.read_text(encoding="utf-8"))
    delay = curated["delay_profiles"][0]
    if invalid == "duplicate":
        curated["delay_profiles"].append(delay.copy())
    elif invalid == "negative":
        delay["usenet_delay"] = -1
    elif invalid == "boolean_delay":
        delay["usenet_delay"] = True
    elif invalid == "protocol":
        delay["preferred_protocol"] = "only_torrent"
    elif invalid == "score":
        delay["bypass_if_above_custom_format_score"] = True
    elif invalid == "unused_score":
        delay["minimum_custom_format_score"] = 100
    else:
        curated["radarr_media_settings"][0]["propers_repacks"] = []
    config.write_text(json.dumps(curated), encoding="utf-8")

    result = _run_generation(source_dir, output_dir, script)
    assert result.returncode == 1
    assert "Generation failed:" in result.stderr
    assert sorted(path.name for path in (output_dir / "ops").glob("*.sql")) == ["1.initial.sql"]


def _custom_format(trash_id: str, name: str, score: int) -> dict[str, object]:
    return {
        "trash_id": trash_id,
        "name": name,
        "trash_scores": {"default": score},
        "specifications": [
            {
                "name": f"{name} title",
                "implementation": "ReleaseTitleSpecification",
                "fields": {"value": name},
            }
        ],
    }


def test_profile_mapping_includes_only_default_and_required_group_members(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    _basic_source_tree(source_dir)

    _write_json(source_dir, "radarr/cf/explicit.json", _custom_format("explicit-id", "Explicit", 80))
    _write_json(source_dir, "radarr/cf/required.json", _custom_format("required-id", "Required", 20))
    _write_json(source_dir, "radarr/cf/default.json", _custom_format("default-id", "Default", 30))
    _write_json(source_dir, "radarr/cf/optional.json", _custom_format("optional-id", "Optional", 40))
    _write_json(
        source_dir,
        "radarr/quality-profiles/test-profile.json",
        {
            "trash_id": "profile-id",
            "name": "Test Profile",
            "trash_description": "Test profile",
            "upgradeAllowed": True,
            "minFormatScore": 0,
            "cutoffFormatScore": 100,
            "minUpgradeFormatScore": 5,
            "cutoff": "WEB 1080p",
            "language": "Original",
            "trash_score_set": "default",
            "items": [
                {"name": "HDTV-1080p", "allowed": True},
                {
                    "name": "WEB 1080p",
                    "allowed": True,
                    "items": ["WEBDL-1080p", "WEBRip-1080p"],
                },
            ],
            "formatItems": {"Explicit": "explicit-id"},
        },
    )
    _write_json(
        source_dir,
        "sonarr/quality-profiles/test-profile.json",
        {
            "trash_id": "sonarr-profile-id",
            "name": "Test Profile",
            "language": "English",
            "cutoff": "HDTV-1080p",
            "items": [{"name": "HDTV-1080p", "allowed": True}],
            "formatItems": {},
        },
    )
    _write_json(
        source_dir,
        "radarr/cf-groups/default-group.json",
        {
            "default": "true",
            "custom_formats": [
                {"name": "Required", "trash_id": "required-id", "required": True},
                {"name": "Default", "trash_id": "default-id", "default": True},
                {"name": "Optional", "trash_id": "optional-id"},
            ],
            "quality_profiles": {"include": {"Test Profile": "profile-id"}},
        },
    )
    _write_json(
        source_dir,
        "radarr/cf-groups/disabled-group.json",
        {
            "default": "false",
            "custom_formats": [{"name": "Optional", "trash_id": "optional-id", "required": True}],
            "quality_profiles": {"include": {"Test Profile": "profile-id"}},
        },
    )
    _write_json(
        source_dir,
        "radarr/quality-profile-groups/groups.json",
        [{"name": "Standard", "profiles": {"test-profile": "profile-id"}}],
    )

    result = _run_generation(source_dir, output_dir)

    assert result.returncode == 0, result.stderr or result.stdout
    database = _validate_output(output_dir)
    profile_name = "Radarr - Test Profile"
    assert database.execute(
        "SELECT language_name, type FROM quality_profile_languages WHERE quality_profile_name = ?",
        (profile_name,),
    ).fetchall() == [("Original", "simple")]
    assert database.execute(
        "SELECT quality_profile_name FROM quality_profile_languages "
        "WHERE quality_profile_name = ?",
        ("Sonarr - Test Profile",),
    ).fetchall() == []
    assert database.execute(
        "SELECT tag_name FROM quality_profile_tags WHERE quality_profile_name = ? ORDER BY tag_name",
        (profile_name,),
    ).fetchall() == [("Radarr",), ("Standard",)]
    assert database.execute(
        """
        SELECT quality_name, quality_group_name, position, enabled, upgrade_until
        FROM quality_profile_qualities
        WHERE quality_profile_name = ? ORDER BY position
        """,
        (profile_name,),
    ).fetchall() == [
        ("HDTV-1080p", None, 0, 1, 0),
        (None, "WEB 1080p", 1, 1, 1),
    ]
    assert database.execute(
        """
        SELECT quality_name, position FROM quality_group_members
        WHERE quality_profile_name = ? AND quality_group_name = ? ORDER BY position
        """,
        (profile_name, "WEB 1080p"),
    ).fetchall() == [("WEBDL-1080p", 0), ("WEBRip-1080p", 1)]
    assert database.execute(
        """
        SELECT custom_format_name, score FROM quality_profile_custom_formats
        WHERE quality_profile_name = ? ORDER BY custom_format_name
        """,
        (profile_name,),
    ).fetchall() == [
        ("Radarr - Default", 30),
        ("Radarr - Explicit", 80),
        ("Radarr - Required", 20),
    ]
    database.close()


def test_quality_definitions_round_fractional_sizes_half_up(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    _basic_source_tree(source_dir)
    _write_json(
        source_dir,
        "radarr/quality-size/movie.json",
        {
            "type": "movie",
            "qualities": [
                {"quality": "HDTV-720p", "min": 12.5, "preferred": 16.5, "max": 100.5}
            ],
        },
    )
    _write_json(
        source_dir,
        "sonarr/quality-size/series.json",
        {
            "type": "series",
            "qualities": [
                {
                    "quality": "Bluray-1080p Remux",
                    "min": 1,
                    "preferred": 2.5,
                    "max": 3.5,
                }
            ],
        },
    )

    result = _run_generation(source_dir, output_dir)

    assert result.returncode == 0, result.stderr or result.stdout
    database = _validate_output(output_dir)
    assert database.execute(
        "SELECT min_size, preferred_size, max_size FROM radarr_quality_definitions"
    ).fetchall() == [(13, 17, 101)]
    assert database.execute(
        "SELECT name, quality_name, min_size, preferred_size, max_size FROM sonarr_quality_definitions"
    ).fetchall() == [("Series", "Remux-1080p", 1, 3, 4)]
    database.close()


def test_naming_variants_resolve_service_specific_formats(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    _basic_source_tree(source_dir)
    _write_json(
        source_dir,
        "radarr/naming/radarr-naming.json",
        {
            "file": {
                "standard": "{Movie Title}",
                "plex-imdb": "{Movie Title} [{imdb-id}]",
            },
            "folder": {
                "default": "{Movie Title}",
                "plex-imdb": "{Movie Title} ({imdb-id})",
            },
        },
    )
    _write_json(
        source_dir,
        "sonarr/naming/sonarr-naming.json",
        {
            "episodes": {
                "standard": {"default": "{Series Title} - S{season:00}E{episode:00}"},
                "daily": {"default": "{Series Title} - {Air-Date}"},
                "anime": {"default": "{Series Title} - {absolute:000}"},
            },
            "series": {"default": "{Series Title}", "plex-imdb": "{Series Title} [{imdb-id}]"},
            "season": {"default": "Season {season:00}"},
        },
    )

    result = _run_generation(source_dir, output_dir)

    assert result.returncode == 0, result.stderr or result.stdout
    database = _validate_output(output_dir)
    assert database.execute(
        """
        SELECT name, movie_format, movie_folder_format
        FROM radarr_naming ORDER BY name
        """
    ).fetchall() == [
        ("plex-imdb", "{Movie Title} [{imdb-id}]", "{Movie Title} ({imdb-id})"),
        ("standard", "{Movie Title}", "{Movie Title}"),
    ]
    assert database.execute(
        """
        SELECT name, standard_episode_format, daily_episode_format,
               anime_episode_format, series_folder_format, season_folder_format
        FROM sonarr_naming ORDER BY name
        """
    ).fetchall() == [
        (
            "default",
            "{Series Title} - S{season:00}E{episode:00}",
            "{Series Title} - {Air-Date}",
            "{Series Title} - {absolute:000}",
            "{Series Title}",
            "Season {season:00}",
        ),
        (
            "plex-imdb",
            "{Series Title} - S{season:00}E{episode:00}",
            "{Series Title} - {Air-Date}",
            "{Series Title} - {absolute:000}",
            "{Series Title} [{imdb-id}]",
            "Season {season:00}",
        ),
    ]
    database.close()


def test_generator_appends_guarded_deltas_without_rewriting_operations(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    _basic_source_tree(source_dir)
    custom_format = _custom_format("hdr-id", "HDR", 100)
    custom_format["trash_description"] = "HDR condition"
    _write_json(source_dir, "radarr/cf/hdr.json", custom_format)

    initial_result = _run_generation(source_dir, output_dir)
    assert initial_result.returncode == 0, initial_result.stderr or initial_result.stdout
    initial_operation = output_dir / "ops" / "1.initial.sql"
    initial_sql = initial_operation.read_text(encoding="utf-8")

    custom_format["trash_description"] = "Updated HDR condition"
    _write_json(source_dir, "radarr/cf/hdr.json", custom_format)
    update_result = _run_generation(source_dir, output_dir)

    assert update_result.returncode == 0, update_result.stderr or update_result.stdout
    update_operation = output_dir / "ops" / "2.update.sql"
    update_sql = update_operation.read_text(encoding="utf-8")
    assert initial_operation.read_text(encoding="utf-8") == initial_sql
    assert '"description" IS \'HDR condition\'' in update_sql

    database = _validate_output(output_dir)
    assert database.execute(
        "SELECT description FROM custom_formats WHERE name = ?",
        ("Radarr - HDR",),
    ).fetchone() == ("Updated HDR condition",)
    database.close()

    rerun_result = _run_generation(source_dir, output_dir)
    assert rerun_result.returncode == 0, rerun_result.stderr or rerun_result.stdout
    assert sorted(path.name for path in (output_dir / "ops").glob("*.sql")) == [
        "1.initial.sql",
        "2.update.sql",
    ]

    database = sqlite3.connect(":memory:")
    database.execute("PRAGMA foreign_keys = ON")
    for operation in sorted(SCHEMA_OPERATIONS.glob("*.sql")):
        database.executescript(operation.read_text(encoding="utf-8"))
    database.executescript(initial_sql)
    database.execute(
        "UPDATE custom_formats SET description = ? WHERE name = ?",
        ("Local description", "Radarr - HDR"),
    )
    database.executescript(update_sql)
    assert database.execute(
        "SELECT description FROM custom_formats WHERE name = ?",
        ("Radarr - HDR",),
    ).fetchone() == ("Local description",)
    database.close()


def test_generator_removes_obsolete_rows_before_their_parents(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    _basic_source_tree(source_dir)
    _write_json(source_dir, "radarr/cf/hdr.json", _custom_format("hdr-id", "HDR", 100))
    initial_result = _run_generation(source_dir, output_dir)
    assert initial_result.returncode == 0, initial_result.stderr or initial_result.stdout

    (source_dir / "radarr" / "cf" / "hdr.json").unlink()
    update_result = _run_generation(source_dir, output_dir)

    assert update_result.returncode == 0, update_result.stderr or update_result.stdout
    update_operation = output_dir / "ops" / "2.update.sql"
    update_sql = update_operation.read_text(encoding="utf-8")
    assert update_sql.index('DELETE FROM "condition_patterns"') < update_sql.index(
        'DELETE FROM "custom_formats"'
    )
    database = _validate_output(output_dir)
    assert database.execute(
        "SELECT COUNT(*) FROM custom_formats WHERE name = ?",
        ("Radarr - HDR",),
    ).fetchone() == (0,)
    assert database.execute(
        "SELECT COUNT(*) FROM custom_format_conditions WHERE custom_format_name = ?",
        ("Radarr - HDR",),
    ).fetchone() == (0,)
    database.close()


def test_generator_clears_old_cutoff_before_setting_new_cutoff(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    _basic_source_tree(source_dir)
    profile = {
        "trash_id": "profile-id",
        "name": "Cutoff",
        "cutoff": "WEB 1080p",
        "items": [
            {"name": "HDTV-1080p", "allowed": True},
            {
                "name": "WEB 1080p",
                "allowed": True,
                "items": ["WEBDL-1080p", "WEBRip-1080p"],
            },
        ],
        "formatItems": {},
    }
    _write_json(source_dir, "radarr/quality-profiles/cutoff.json", profile)
    initial_result = _run_generation(source_dir, output_dir)
    assert initial_result.returncode == 0, initial_result.stderr or initial_result.stdout

    profile["cutoff"] = "HDTV-1080p"
    _write_json(source_dir, "radarr/quality-profiles/cutoff.json", profile)
    update_result = _run_generation(source_dir, output_dir)

    assert update_result.returncode == 0, update_result.stderr or update_result.stdout
    database = _validate_output(output_dir)
    assert database.execute(
        """
        SELECT position, upgrade_until FROM quality_profile_qualities
        WHERE quality_profile_name = ? ORDER BY position
        """,
        ("Radarr - Cutoff",),
    ).fetchall() == [(0, 1), (1, 0)]
    database.close()
