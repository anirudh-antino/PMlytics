"""
SQL adapter (Postgres + MySQL) on top of SQLAlchemy.

Honors the read-only guardrail in `sql_guard.py`. SQLite is supported under
the hood for local dev, but it is not advertised in the connection UI.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from adapters.base import (
    Adapter,
    AdapterError,
    ConnectionConfig,
    SchemaTree,
    TableInfo,
)


def build_sql_url(config: ConnectionConfig) -> str:
    """Construct a SQLAlchemy URL from typed fields, or pass through raw_url."""
    if config.raw_url and config.raw_url.strip():
        return config.raw_url.strip()

    t = (config.type or "").lower()
    if t in ("postgresql", "postgres"):
        scheme = "postgresql+psycopg2"
        default_port = 5432
    elif t == "mysql":
        scheme = "mysql+pymysql"
        default_port = 3306
    else:
        raise AdapterError(f"Unsupported SQL type: {config.type!r}")

    if not config.database:
        raise AdapterError("Database name is required.")
    if not config.host:
        raise AdapterError("Host is required.")

    user = quote_plus(config.user or "")
    pwd = quote_plus(config.password or "")
    auth = f"{user}:{pwd}@" if user else ""
    port = config.port or default_port
    url = f"{scheme}://{auth}{config.host}:{port}/{quote_plus(config.database)}"

    qs: list[str] = []
    if config.ssl:
        qs.append("sslmode=require" if t in ("postgresql", "postgres") else "ssl=true")
    for k, v in (config.options or {}).items():
        if k and v:
            qs.append(f"{quote_plus(k)}={quote_plus(str(v))}")
    if qs:
        url += "?" + "&".join(qs)
    return url


def _dialect_from_type(t: str) -> str:
    t = (t or "").lower()
    if t in ("postgresql", "postgres"):
        return "postgresql"
    if t == "mysql":
        return "mysql"
    if t == "sqlite":
        return "sqlite"
    return "generic"


class SqlAdapter(Adapter):
    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config
        self._engine: Engine | None = None
        self._url = build_sql_url(config)

    @property
    def dialect(self) -> str:
        return _dialect_from_type(self.config.type)

    def _engine_safe(self) -> Engine:
        if self._engine is not None:
            return self._engine
        kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 3600}
        if self._url.lower().startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        try:
            self._engine = create_engine(self._url, **kwargs)
        except Exception as exc:
            raise AdapterError(str(exc)) from exc
        return self._engine

    def test(self) -> None:
        try:
            with self._engine_safe().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise AdapterError(str(exc)) from exc

    def schema(self) -> SchemaTree:
        eng = self._engine_safe()
        try:
            insp = inspect(eng)
            names = insp.get_table_names()
        except Exception as exc:
            raise AdapterError(str(exc)) from exc

        objects: list[TableInfo] = []
        for tname in names:
            try:
                cols = insp.get_columns(tname)
            except Exception:
                continue
            objects.append(
                TableInfo(
                    name=tname,
                    columns=[{"name": c["name"], "type": str(c["type"])} for c in cols],
                    kind="table",
                )
            )
        return SchemaTree(objects=objects)

    def schema_text(self, max_objects: int = 64, max_cols: int = 40) -> str:
        eng = self._engine_safe()
        insp = inspect(eng)
        try:
            names = insp.get_table_names()
        except Exception as exc:
            return f"(Could not list tables: {exc})"

        lines: list[str] = []
        for tname in names[:max_objects]:
            try:
                cols = insp.get_columns(tname)
            except Exception:
                continue
            bits = [f"{c['name']}:{str(c['type'])}" for c in cols[:max_cols]]
            lines.append(f"{tname}: " + ", ".join(bits))
            if len(cols) > max_cols:
                lines.append(f"  … +{len(cols) - max_cols} more columns")
        if len(names) > max_objects:
            lines.append(f"… +{len(names) - max_objects} more tables")
        return "\n".join(lines) if lines else "(No tables found.)"

    def sample(
        self, object_name: str, limit: int = 5
    ) -> tuple[list[str], list[dict[str, Any]]]:
        ident = self._quote_ident(object_name)
        sql = f"SELECT * FROM {ident} LIMIT {int(limit)}"
        eng = self._engine_safe()
        with eng.connect() as conn:
            result = conn.execute(text(sql))
            cols = list(result.keys())
            raw = result.fetchmany(limit)
            rows = [dict(zip(cols, r)) for r in raw]
        return cols, rows

    def _quote_ident(self, name: str) -> str:
        if any(c in name for c in (";", "`", '"', "'", " ")):
            raise AdapterError(f"Invalid object name: {name!r}")
        if self.dialect == "mysql":
            return f"`{name}`"
        return f'"{name}"'

    def run(
        self, query: Any, *, max_rows: int
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if not isinstance(query, str):
            raise AdapterError("SQL adapter expects a string query.")
        from sql_guard import enforce_limit, validate_select_only

        ok, msg = validate_select_only(query)
        if not ok:
            raise AdapterError(msg)
        bounded = enforce_limit(msg, self.dialect, max_rows)

        eng = self._engine_safe()
        try:
            with eng.connect() as conn:
                result = conn.execute(text(bounded))
                cols = list(result.keys())
                raw = result.fetchmany(max_rows + 1)
                if len(raw) > max_rows:
                    raw = raw[:max_rows]
                rows = [dict(zip(cols, r)) for r in raw]
        except Exception as exc:
            raise AdapterError(str(exc)) from exc
        return cols, rows

    def dispose(self) -> None:
        if self._engine is not None:
            try:
                self._engine.dispose()
            except Exception:
                pass
            self._engine = None
