import re
import sqlite3
from pathlib import Path
from typing import Any


TABLE_ORDER = (
    "tags",
    "regular_expressions",
    "custom_formats",
    "quality_profiles",
    "quality_groups",
    "custom_format_conditions",
    "regular_expression_tags",
    "custom_format_tags",
    "quality_profile_tags",
    "quality_profile_languages",
    "quality_group_members",
    "quality_profile_qualities",
    "quality_profile_custom_formats",
    "condition_patterns",
    "condition_languages",
    "condition_indexer_flags",
    "condition_sources",
    "condition_resolutions",
    "condition_quality_modifiers",
    "condition_release_types",
    "radarr_quality_definitions",
    "sonarr_quality_definitions",
    "radarr_naming",
    "sonarr_naming",
)


def empty_rows() -> dict[str, list[dict[str, Any]]]:
    return {table: [] for table in TABLE_ORDER}


def sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"Unsupported SQL value: {type(value).__name__}")


def render_inserts(rows: dict[str, list[dict[str, Any]]]) -> str:
    statements = []
    for table in TABLE_ORDER:
        for row in rows[table]:
            columns = ", ".join(row)
            values = ", ".join(sql_value(value) for value in row.values())
            statements.append(f"INSERT INTO {table} ({columns}) VALUES ({values});")
    return "\n".join(statements) + ("\n" if statements else "")


class SQLGenerationError(ValueError):
    """Raised when the source rows cannot be reconciled with existing PCD data."""


def operation_sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"^(\d+)\.", path.name)
    if match is None:
        raise SQLGenerationError(f"PCD operation filename must start with a number: {path.name}")
    return int(match.group(1)), path.name


def replay_operations(
    database: sqlite3.Connection,
    schema_operations: Path,
    pcd_operations: list[Path],
) -> None:
    database.execute("PRAGMA foreign_keys = ON")
    for operation in sorted(schema_operations.glob("*.sql"), key=operation_sort_key):
        database.executescript(operation.read_text(encoding="utf-8"))
    for operation in sorted(pcd_operations, key=operation_sort_key):
        database.executescript(operation.read_text(encoding="utf-8"))


def _quoted_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _identity_columns(database: sqlite3.Connection, table: str) -> tuple[str, ...]:
    table_identifier = _quoted_identifier(table)
    table_info = database.execute(f"PRAGMA table_info({table_identifier})").fetchall()
    if not table_info:
        raise SQLGenerationError(f"Missing schema table '{table}'")
    primary_key = tuple(
        row[1]
        for row in sorted((row for row in table_info if row[5]), key=lambda row: row[5])
    )
    if primary_key and primary_key != ("id",):
        return primary_key

    indexes = database.execute(f"PRAGMA index_list({table_identifier})").fetchall()
    candidates = []
    for index in indexes:
        if not index[2] or index[4]:
            continue
        columns = tuple(
            row[2]
            for row in database.execute(
                f"PRAGMA index_info({_quoted_identifier(index[1])})"
            ).fetchall()
        )
        if columns and "id" not in columns:
            candidates.append(columns)
    if table == "quality_profile_qualities":
        return ("quality_profile_name", "position")
    if not candidates:
        raise SQLGenerationError(f"No stable row identity is available for table '{table}'")
    return min(candidates, key=lambda columns: (len(columns), columns))


def _where_clause(values: dict[str, Any]) -> str:
    return " AND ".join(
        f"{_quoted_identifier(column)} IS {sql_value(value)}"
        for column, value in values.items()
    )


def _rows_by_identity(
    table: str,
    rows: list[dict[str, Any]],
    identity_columns: tuple[str, ...],
    label: str,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    indexed_rows = {}
    for row in rows:
        try:
            identity = tuple(row[column] for column in identity_columns)
        except KeyError as error:
            raise SQLGenerationError(
                f"{label} {table} row lacks identity column {error.args[0]!r}"
            ) from error
        if identity in indexed_rows:
            raise SQLGenerationError(f"{label} duplicate identity in table '{table}': {identity}")
        indexed_rows[identity] = row
    return indexed_rows


def _render_row_delta(
    table: str,
    identity_values: dict[str, Any],
    current_row: dict[str, Any],
    desired_row: dict[str, Any] | None,
    managed_columns: tuple[str, ...],
) -> str | None:
    table_identifier = _quoted_identifier(table)
    if desired_row is None:
        expected_values = {column: current_row[column] for column in managed_columns}
        expected_values.update(identity_values)
        return f"DELETE FROM {table_identifier} WHERE {_where_clause(expected_values)};"

    changed_values = {
        column: desired_row[column]
        for column in desired_row
        if column not in identity_values and current_row[column] != desired_row[column]
    }
    if not changed_values:
        return None
    set_values = ", ".join(
        f"{_quoted_identifier(column)} = {sql_value(value)}"
        for column, value in changed_values.items()
    )
    expected_values = {column: current_row[column] for column in managed_columns}
    return (
        f"UPDATE {table_identifier} SET {set_values} "
        f"WHERE {_where_clause(expected_values)};"
    )


def _render_insert(table: str, row: dict[str, Any]) -> str:
    columns = ", ".join(_quoted_identifier(column) for column in row)
    values = ", ".join(sql_value(value) for value in row.values())
    return f"INSERT INTO {_quoted_identifier(table)} ({columns}) VALUES ({values});"


def _read_table_rows(
    database: sqlite3.Connection,
    table: str,
) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    cursor = database.execute(f"SELECT * FROM {_quoted_identifier(table)}")
    column_names = [description[0] for description in cursor.description]
    current_rows = [
        dict(zip(column_names, values, strict=True))
        for values in cursor.fetchall()
    ]
    managed_columns = tuple(
        column
        for column in column_names
        if column not in {"id", "created_at", "updated_at"}
    )
    return current_rows, managed_columns


def _table_delta(
    database: sqlite3.Connection,
    table: str,
    desired_rows: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    current_rows, managed_columns = _read_table_rows(database, table)
    identity_columns = _identity_columns(database, table)
    desired_by_identity = _rows_by_identity(table, desired_rows, identity_columns, "Generated")
    current_by_identity = _rows_by_identity(table, current_rows, identity_columns, "Existing")
    deletes = []
    changes = []
    current_items = list(current_by_identity.items())
    if table == "quality_profile_qualities":
        current_items.sort(
            key=lambda item: desired_by_identity.get(item[0], {}).get("upgrade_until", 0)
        )
    for identity, current_row in current_items:
        identity_values = dict(zip(identity_columns, identity, strict=True))
        statement = _render_row_delta(
            table,
            identity_values,
            current_row,
            desired_by_identity.get(identity),
            managed_columns,
        )
        if statement is not None:
            (deletes if identity not in desired_by_identity else changes).append(statement)
    changes.extend(
        _render_insert(table, desired_row)
        for identity, desired_row in desired_by_identity.items()
        if identity not in current_by_identity
    )
    return deletes, changes


def render_delta(
    database: sqlite3.Connection,
    rows: dict[str, list[dict[str, Any]]],
) -> str:
    deletes: dict[str, list[str]] = {table: [] for table in TABLE_ORDER}
    changes: dict[str, list[str]] = {table: [] for table in TABLE_ORDER}
    for table in TABLE_ORDER:
        deletes[table], changes[table] = _table_delta(database, table, rows[table])

    statements = [
        statement
        for table in reversed(TABLE_ORDER)
        for statement in deletes[table]
    ]
    statements.extend(
        statement
        for table in TABLE_ORDER
        for statement in changes[table]
    )
    return "\n".join(statements) + ("\n" if statements else "")
