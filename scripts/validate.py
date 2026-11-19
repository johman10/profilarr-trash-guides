import json
import sqlite3
import sys
from pathlib import Path

from generate import SCHEMA_DEPENDENCY, SCHEMA_VERSION
from pcd.sql import SQLGenerationError, operation_sort_key, replay_operations


ROOT = Path(__file__).resolve().parent


class ValidationError(ValueError):
    """Raised when a generated PCD cannot be loaded against its pinned schema."""


def validate(output_dir: Path) -> None:
    manifest_path = output_dir / "pcd.json"
    if not manifest_path.is_file():
        raise ValidationError(f"Missing PCD manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"Unable to read PCD manifest {manifest_path}: {error}") from error
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict) or dependencies.get(SCHEMA_DEPENDENCY) != SCHEMA_VERSION:
        raise ValidationError(
            f"{manifest_path} must pin {SCHEMA_DEPENDENCY} to {SCHEMA_VERSION}"
        )

    schema_operations = ROOT / "schema" / SCHEMA_VERSION / "ops"
    if not schema_operations.is_dir():
        raise ValidationError(f"Missing pinned schema operations: {schema_operations}")
    try:
        operations = sorted((output_dir / "ops").glob("*.sql"), key=operation_sort_key)
    except SQLGenerationError as error:
        raise ValidationError(str(error)) from error
    if not operations:
        raise ValidationError(f"No PCD operations found in {output_dir / 'ops'}")

    database = sqlite3.connect(":memory:")
    try:
        replay_operations(database, schema_operations, operations)
        violations = database.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValidationError(f"PCD operations contain foreign-key violations: {violations}")
    except (OSError, sqlite3.Error, SQLGenerationError) as error:
        raise ValidationError(f"Unable to apply PCD operations: {error}") from error
    finally:
        database.close()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: python scripts/validate.py <pcd_dir>", file=sys.stderr)
        return 2
    try:
        validate(Path(args[0]))
    except ValidationError as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Validated PCD in {args[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
