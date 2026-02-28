"""Apply SQL schema and migration scripts using SQLAlchemy.

Usage examples:
    set RPG_DATABASE_URL=mysql+mysqlconnector://user:pass@localhost:3306/rpg_game
    python -m rpg.infrastructure.db.mysql.migrate

    python -m rpg.infrastructure.db.mysql.migrate --dry-run
    python -m rpg.infrastructure.db.mysql.migrate --script path/to/legacy_script.sql
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Set

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True)
class MigrationPlan:
    files: list[Path]
    statements: list[str]


@dataclass(frozen=True)
class MigrationFilePlan:
    file_path: Path
    statements: list[str]


MIGRATION_NAME_PATTERN = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$", re.IGNORECASE)


def _default_script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations" / "_apply_all.sql"


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations"


def _base_schema_files() -> list[Path]:
    base_dir = Path(__file__).resolve().parents[2]
    return [base_dir / "create_tables.sql", base_dir / "create_history_tables.sql"]


def discover_linear_migration_files() -> list[Path]:
    migration_dir = _migrations_dir()
    candidates = [path for path in migration_dir.glob("*.sql") if not path.name.startswith("_")]
    invalid = [path.name for path in candidates if MIGRATION_NAME_PATTERN.match(path.name) is None]
    if invalid:
        invalid_list = ", ".join(sorted(invalid))
        raise ValueError(f"Invalid migration filename(s): {invalid_list}. Expected pattern: NNN_description.sql")

    ordered = sorted(candidates, key=lambda path: path.name)
    expected = 1
    for path in ordered:
        match = MIGRATION_NAME_PATTERN.match(path.name)
        if match is None:
            continue
        number = int(match.group(1))
        if number != expected:
            raise ValueError(
                f"Migration numbering gap or out-of-order file detected at {path.name}. "
                f"Expected prefix {expected:03d}."
            )
        expected += 1
    return ordered


def _extract_source_target(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("--") or stripped.startswith("#"):
        return None
    if not stripped.upper().startswith("SOURCE "):
        return None
    target = stripped[7:].strip().rstrip(";").strip()
    if target.startswith(("'", '"')) and target.endswith(("'", '"')) and len(target) >= 2:
        target = target[1:-1]
    return target


def _split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    size = len(sql_text)

    while i < size:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < size else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not (in_single or in_double or in_backtick):
            if ch == "-" and nxt == "-":
                in_line_comment = True
                i += 2
                continue
            if ch == "#":
                in_line_comment = True
                i += 1
                continue
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue

        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
            buffer.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
            buffer.append(ch)
            i += 1
            continue
        if ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            buffer.append(ch)
            i += 1
            continue

        if ch == ";" and not (in_single or in_double or in_backtick):
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            i += 1
            continue

        buffer.append(ch)
        i += 1

    trailing = "".join(buffer).strip()
    if trailing:
        statements.append(trailing)
    return statements


def _collect_plan(script_path: Path, seen: Set[Path] | None = None) -> MigrationPlan:
    script_path = script_path.resolve()
    seen = seen or set()
    if script_path in seen:
        raise ValueError(f"Circular SOURCE reference detected at: {script_path}")
    if not script_path.exists():
        raise FileNotFoundError(f"Migration script not found: {script_path}")

    seen.add(script_path)
    files: list[Path] = [script_path]
    statements: list[str] = []
    non_source_lines: list[str] = []

    for line in script_path.read_text(encoding="utf-8").splitlines():
        source_target = _extract_source_target(line)
        if source_target is None:
            non_source_lines.append(line)
            continue

        nested_path = (script_path.parent / source_target).resolve()
        nested_plan = _collect_plan(nested_path, seen)
        files.extend(path for path in nested_plan.files if path not in files)
        statements.extend(nested_plan.statements)

    non_source_sql = "\n".join(non_source_lines)
    statements.extend(_split_sql_statements(non_source_sql))

    seen.remove(script_path)
    return MigrationPlan(files=files, statements=statements)


def build_migration_plan(script_path: Path | str | None = None) -> MigrationPlan:
    resolved = Path(script_path).resolve() if script_path else _default_script_path()
    return _collect_plan(resolved)


def build_linear_migration_plan() -> list[MigrationFilePlan]:
    plans: list[MigrationFilePlan] = []
    for file_path in _base_schema_files() + discover_linear_migration_files():
        statements = _split_sql_statements(file_path.read_text(encoding="utf-8"))
        plans.append(MigrationFilePlan(file_path=file_path.resolve(), statements=statements))
    return plans


def _ensure_schema_migrations_table(conn) -> None:
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _already_applied(conn, migration_name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT migration_name FROM schema_migrations WHERE migration_name = :name",
        {"name": migration_name},
    ).first()
    return row is not None


def _mark_applied(conn, migration_name: str) -> None:
    conn.exec_driver_sql(
        "INSERT INTO schema_migrations (migration_name) VALUES (:name)",
        {"name": migration_name},
    )


def execute_statements(statements: Iterable[str], database_url: str) -> int:
    engine = create_engine(database_url, echo=False, future=True)
    count = 0
    with engine.begin() as conn:
        for count, statement in enumerate(statements, start=1):
            conn.exec_driver_sql(statement)
    engine.dispose()
    return count


def execute_linear_migration_plan(file_plans: list[MigrationFilePlan], database_url: str) -> tuple[int, int]:
    engine = create_engine(database_url, echo=False, future=True)
    applied_files = 0
    executed_statements = 0
    with engine.begin() as conn:
        _ensure_schema_migrations_table(conn)
        for file_plan in file_plans:
            migration_name = file_plan.file_path.name
            if _already_applied(conn, migration_name):
                continue
            for statement in file_plan.statements:
                executed_statements += 1
                conn.exec_driver_sql(statement)
            _mark_applied(conn, migration_name)
            applied_files += 1
    engine.dispose()
    return applied_files, executed_statements


def _resolve_database_url(explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url
    from rpg.infrastructure.db.mysql.connection import DATABASE_URL

    env_url = os.getenv("RPG_DATABASE_URL")
    return env_url or DATABASE_URL


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SQL schema/migrations using SQLAlchemy")
    parser.add_argument(
        "--script",
        type=str,
        default=None,
        help="Optional legacy root SQL script path. If omitted, uses strict linear migration mode.",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL override (defaults to RPG_DATABASE_URL / mysql connection config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only parse/resolve scripts and print migration plan",
    )
    args = parser.parse_args()

    if args.script:
        plan = build_migration_plan(args.script)
        print(f"Resolved {len(plan.files)} SQL file(s) and {len(plan.statements)} statement(s).")
        for file_path in plan.files:
            print(f"  - {file_path}")

        if args.dry_run:
            print("Dry run complete. No SQL executed.")
            return

        database_url = _resolve_database_url(args.database_url)
        try:
            executed = execute_statements(plan.statements, database_url)
        except SQLAlchemyError as exc:
            raise SystemExit(
                "Migration execution failed. Verify RPG_DATABASE_URL points to a reachable database instance. "
                f"Details: {exc}"
            ) from exc
        print(f"Executed {executed} statement(s) successfully.")
        return

    linear_plan = build_linear_migration_plan()
    total_statements = sum(len(item.statements) for item in linear_plan)
    print(f"Resolved strict linear plan: {len(linear_plan)} file(s), {total_statements} statement(s).")
    for item in linear_plan:
        print(f"  - {item.file_path}")

    if args.dry_run:
        print("Dry run complete. No SQL executed.")
        return

    database_url = _resolve_database_url(args.database_url)
    try:
        applied_files, executed_statements = execute_linear_migration_plan(linear_plan, database_url)
    except SQLAlchemyError as exc:
        raise SystemExit(
            "Migration execution failed. Verify RPG_DATABASE_URL points to a reachable database instance. "
            f"Details: {exc}"
        ) from exc
    print(f"Applied {applied_files} migration file(s); executed {executed_statements} statement(s).")


if __name__ == "__main__":
    main()
