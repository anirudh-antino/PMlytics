"""
MongoDB adapter using PyMongo.

Schema is implicit in Mongo, so `schema()` samples N docs per collection and
infers field types. The adapter accepts JSON op specs (validated via
`mongo_guard`) and returns flattened row dicts so the rest of the pipeline
(charts, tables, synthesizer) treats Mongo and SQL output uniformly.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from adapters.base import (
    Adapter,
    AdapterError,
    ConnectionConfig,
    SchemaTree,
    TableInfo,
)
from mongo_guard import enforce_mongo_limit, validate_mongo_op

SAMPLE_DOCS_FOR_SCHEMA = 25


def build_mongo_url(config: ConnectionConfig) -> str:
    """Construct a Mongo URI from typed fields, or pass through raw_url."""
    if config.raw_url and config.raw_url.strip():
        return config.raw_url.strip()

    if not config.host:
        raise AdapterError("Host is required.")

    from urllib.parse import quote_plus

    user = quote_plus(config.user or "")
    pwd = quote_plus(config.password or "")
    auth = f"{user}:{pwd}@" if user else ""
    port = config.port or 27017
    db = config.database or ""
    base = f"mongodb://{auth}{config.host}:{port}/{quote_plus(db) if db else ''}"

    qs: list[str] = []
    if config.ssl:
        qs.append("tls=true")
    for k, v in (config.options or {}).items():
        if k and v:
            qs.append(f"{quote_plus(k)}={quote_plus(str(v))}")
    if qs:
        base += "?" + "&".join(qs)
    return base


def _infer_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, (datetime, date)):
        return "date"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _flatten(doc: dict, prefix: str = "") -> dict[str, Any]:
    """Light flatten: nested objects become 'a.b'; arrays stay as arrays."""
    out: dict[str, Any] = {}
    for k, v in doc.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def _stringify_id(doc: dict) -> dict:
    if "_id" in doc:
        try:
            doc["_id"] = str(doc["_id"])
        except Exception:
            pass
    return doc


class MongoAdapter(Adapter):
    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config
        self._client = None  # type: ignore[assignment]
        self._db = None  # type: ignore[assignment]
        self._uri = build_mongo_url(config)
        self._db_name: Optional[str] = config.database

    @property
    def dialect(self) -> str:
        return "mongodb"

    def _connect(self):
        if self._client is not None and self._db is not None:
            return self._db
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise AdapterError(
                "pymongo is not installed. Add `pymongo` to requirements.txt."
            ) from exc

        try:
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
        except Exception as exc:
            raise AdapterError(str(exc)) from exc

        if not self._db_name:
            try:
                default = self._client.get_default_database()
                if default is not None:
                    self._db_name = default.name
            except Exception:
                self._db_name = None

        if not self._db_name:
            raise AdapterError(
                "Database name is required (set it in the form or include /dbname in the URL)."
            )

        self._db = self._client[self._db_name]
        return self._db

    def test(self) -> None:
        try:
            db = self._connect()
            db.command("ping")
        except Exception as exc:
            raise AdapterError(str(exc)) from exc

    def schema(self) -> SchemaTree:
        db = self._connect()
        try:
            names = db.list_collection_names()
        except Exception as exc:
            raise AdapterError(str(exc)) from exc

        objects: list[TableInfo] = []
        for cname in names:
            try:
                coll = db[cname]
                docs = list(coll.find({}, limit=SAMPLE_DOCS_FOR_SCHEMA))
            except Exception:
                continue
            field_types: dict[str, set[str]] = {}
            for d in docs:
                flat = _flatten(_stringify_id(dict(d)))
                for k, v in flat.items():
                    field_types.setdefault(k, set()).add(_infer_type(v))
            cols = [
                {"name": k, "type": "|".join(sorted(v))}
                for k, v in sorted(field_types.items())
            ]
            objects.append(TableInfo(name=cname, columns=cols, kind="collection"))
        return SchemaTree(
            objects=objects,
            notes="Schema inferred from a sample of recent documents per collection.",
        )

    def schema_text(self, max_objects: int = 64, max_cols: int = 40) -> str:
        tree = self.schema()
        lines: list[str] = []
        for obj in tree.objects[:max_objects]:
            bits = [f"{c['name']}:{c['type']}" for c in obj.columns[:max_cols]]
            lines.append(f"{obj.name} (collection): " + ", ".join(bits))
            if len(obj.columns) > max_cols:
                lines.append(f"  … +{len(obj.columns) - max_cols} more fields")
        if len(tree.objects) > max_objects:
            lines.append(f"… +{len(tree.objects) - max_objects} more collections")
        if tree.notes:
            lines.append(f"# {tree.notes}")
        return "\n".join(lines) if lines else "(No collections found.)"

    def sample(
        self, object_name: str, limit: int = 5
    ) -> tuple[list[str], list[dict[str, Any]]]:
        db = self._connect()
        try:
            docs = list(db[object_name].find({}, limit=limit))
        except Exception as exc:
            raise AdapterError(str(exc)) from exc
        flat_rows = [_flatten(_stringify_id(dict(d))) for d in docs]
        cols: list[str] = []
        seen = set()
        for r in flat_rows:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        return cols, flat_rows

    def run(
        self, query: Any, *, max_rows: int
    ) -> tuple[list[str], list[dict[str, Any]]]:
        ok, msg = validate_mongo_op(query)
        if not ok:
            raise AdapterError(str(msg))
        spec = enforce_mongo_limit(msg, max_rows)
        db = self._connect()

        op = spec["op"]
        coll = db[spec["collection"]]
        results: list[dict[str, Any]] = []

        try:
            if op == "aggregate":
                cur = coll.aggregate(
                    spec["pipeline"], allowDiskUse=False, maxTimeMS=30_000
                )
                for d in cur:
                    results.append(_flatten(_stringify_id(dict(d))))
            elif op == "find":
                kwargs: dict[str, Any] = {}
                if "projection" in spec:
                    kwargs["projection"] = spec["projection"]
                if "limit" in spec:
                    kwargs["limit"] = int(spec["limit"])
                if "sort" in spec and isinstance(spec["sort"], dict):
                    kwargs["sort"] = list(spec["sort"].items())
                cur = coll.find(spec.get("filter") or {}, **kwargs)
                cur = cur.max_time_ms(30_000)
                for d in cur:
                    results.append(_flatten(_stringify_id(dict(d))))
            elif op == "countDocuments":
                count = coll.count_documents(spec.get("filter") or {}, maxTimeMS=30_000)
                results = [{"count": count}]
            elif op == "distinct":
                vals = coll.distinct(spec["field"], spec.get("filter") or {})
                vals = list(vals)[: int(spec.get("limit") or max_rows)]
                results = [{"value": v} for v in vals]
        except Exception as exc:
            raise AdapterError(str(exc)) from exc

        if len(results) > max_rows:
            results = results[:max_rows]

        cols: list[str] = []
        seen = set()
        for r in results:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        return cols, results

    def dispose(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._db = None
