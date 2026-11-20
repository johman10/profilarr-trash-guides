import json
import sqlite3
import sys
from pathlib import Path

from utils.common.errors import SourceError
from utils.curated import CuratedError, collect_curated_rows
from utils.source.collect import collect_source_rows
from utils.sql import (
    SQLGenerationError,
    operation_sort_key,
    render_delta,
    render_inserts,
    replay_operations,
)


SCHEMA_DEPENDENCY = "https://github.com/Dictionarry-Hub/schema"
SCHEMA_VERSION = "1.1.0"
CURATED_SETTINGS = Path(__file__).resolve().parent.parent / "config" / "curated-settings.json"


class GenerationError(ValueError):
    """Raised when PCD output cannot be generated safely."""


def _validate_manifest(manifest_path: Path) -> None:
    if not manifest_path.is_file():
        raise GenerationError(f"Missing PCD manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GenerationError(f"Unable to read PCD manifest {manifest_path}: {error}") from error
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict) or dependencies.get(SCHEMA_DEPENDENCY) != SCHEMA_VERSION:
        raise GenerationError(
            f"{manifest_path} must pin {SCHEMA_DEPENDENCY} to {SCHEMA_VERSION}"
        )


def generate(input_dir: Path, output_dir: Path) -> Path | None:
    _validate_manifest(output_dir / "pcd.json")
    operations_dir = output_dir / "ops"
    operations_dir.mkdir(parents=True, exist_ok=True)
    try:
        existing_operations = sorted(operations_dir.glob("*.sql"), key=operation_sort_key)
    except SQLGenerationError as error:
        raise GenerationError(str(error)) from error
    operation_numbers = [operation_sort_key(path)[0] for path in existing_operations]
    if len(operation_numbers) != len(set(operation_numbers)):
        raise GenerationError("PCD operation numbers must be unique")
    rows = collect_source_rows(input_dir)
    collect_curated_rows(CURATED_SETTINGS, rows)

    database = sqlite3.connect(":memory:")
    try:
        replay_operations(
            database,
            Path(__file__).parent / "schema" / SCHEMA_VERSION / "ops",
            existing_operations,
        )
        operation_sql = render_delta(database, rows) if existing_operations else render_inserts(rows)
        if not operation_sql:
            return None
        database.executescript(operation_sql)
        violations = database.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise GenerationError(f"Generated operations contain foreign-key violations: {violations}")
    except (OSError, sqlite3.Error, SQLGenerationError) as error:
        raise GenerationError(f"Unable to validate generated operations: {error}") from error
    finally:
        database.close()

    next_operation_number = operation_numbers[-1] + 1 if operation_numbers else 1
    operation_name = "initial" if not existing_operations else "update"
    operation_path = operations_dir / f"{next_operation_number}.{operation_name}.sql"
    operation_path.write_text(operation_sql, encoding="utf-8")
    return operation_path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("Usage: python scripts/generate.py <input_dir> <output_dir>", file=sys.stderr)
        return 2

    try:
        operation = generate(Path(args[0]), Path(args[1]))
    except (GenerationError, SourceError, CuratedError) as error:
        print(f"Generation failed: {error}", file=sys.stderr)
        return 1
    if operation is None:
        print("No changes; no new PCD operation generated")
    else:
        print(f"Generated {operation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
