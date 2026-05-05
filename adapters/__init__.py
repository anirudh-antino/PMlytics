"""Database adapter layer (SQL + MongoDB) behind a single Adapter interface."""

from adapters.base import Adapter, AdapterError, ConnectionConfig
from adapters.sql_adapter import SqlAdapter, build_sql_url
from adapters.mongo_adapter import MongoAdapter, build_mongo_url

__all__ = [
    "Adapter",
    "AdapterError",
    "ConnectionConfig",
    "SqlAdapter",
    "MongoAdapter",
    "build_sql_url",
    "build_mongo_url",
    "create_adapter",
]


def create_adapter(config: ConnectionConfig) -> Adapter:
    """Factory: build the right adapter for a connection config."""
    t = (config.type or "").lower()
    if t in ("postgresql", "postgres", "mysql"):
        return SqlAdapter(config)
    if t in ("mongodb", "mongo"):
        return MongoAdapter(config)
    raise AdapterError(f"Unsupported connection type: {config.type!r}")
