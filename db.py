"""
Backwards-compat shim. The SQL helpers now live in `adapters.sql_adapter`;
new code should use the `Adapter` interface in `adapters.base` via the
`ConnectionRegistry` in `connections.py`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


def dialect_from_url(url: str) -> str:
    u = url.strip().lower()
    if u.startswith("postgresql") or u.startswith("postgres"):
        return "postgresql"
    if u.startswith("mysql"):
        return "mysql"
    if u.startswith("sqlite"):
        return "sqlite"
    if u.startswith("mongodb"):
        return "mongodb"
    return "generic"


def create_engine_safe(database_url: str) -> Engine:
    kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 3600}
    if database_url.strip().lower().startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **kwargs)


def test_engine(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def schema_summary(engine: Engine, max_tables: int = 64, max_cols: int = 40) -> str:
    insp = inspect(engine)
    lines: list[str] = []
    try:
        names = insp.get_table_names()
    except Exception as exc:
        return f"(Could not list tables: {exc})"

    for tname in names[:max_tables]:
        try:
            cols = insp.get_columns(tname)
        except Exception:
            continue
        bits = [f"{c['name']}:{str(c['type'])}" for c in cols[:max_cols]]
        lines.append(f"{tname}: " + ", ".join(bits))
        if len(cols) > max_cols:
            lines.append(f"  … +{len(cols) - max_cols} more columns")
    if len(names) > max_tables:
        lines.append(f"… +{len(names) - max_tables} more tables")
    return "\n".join(lines) if lines else "(No tables found.)"


def execute_select(
    engine: Engine,
    sql: str,
    *,
    max_rows: int,
    dialect: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    from sql_guard import enforce_limit

    bounded = enforce_limit(sql, dialect, max_rows)
    with engine.connect() as conn:
        result = conn.execute(text(bounded))
        cols = list(result.keys())
        rows_raw = result.fetchmany(max_rows + 1)
        if len(rows_raw) > max_rows:
            rows_raw = rows_raw[:max_rows]
        rows = [dict(zip(cols, row)) for row in rows_raw]
    return cols, rows
