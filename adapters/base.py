"""
Common adapter interface for SQL + MongoDB.

A single API the planner/executor uses regardless of underlying engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class AdapterError(Exception):
    """Raised for connection / validation / execution problems."""


@dataclass
class ConnectionConfig:
    """User-provided connection inputs.

    Either `raw_url` is set (advanced tab), or the typed fields are set and
    the adapter builds the URL itself.
    """

    name: str
    type: str  # "postgresql" | "mysql" | "mongodb"
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    ssl: bool = False
    options: dict[str, str] = field(default_factory=dict)
    raw_url: Optional[str] = None


@dataclass
class TableInfo:
    name: str
    columns: list[dict[str, str]]  # [{"name", "type"}]
    kind: str = "table"  # "table" | "collection"


@dataclass
class SchemaTree:
    objects: list[TableInfo]
    notes: str = ""


class Adapter(ABC):
    """One adapter per active connection."""

    config: ConnectionConfig

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Returns 'postgresql' | 'mysql' | 'mongodb'."""

    @property
    def is_sql(self) -> bool:
        return self.dialect in ("postgresql", "mysql")

    @abstractmethod
    def test(self) -> None:
        """Connect + ping; raise AdapterError on failure."""

    @abstractmethod
    def schema(self) -> SchemaTree:
        """Structured schema for the explorer UI."""

    @abstractmethod
    def schema_text(self, max_objects: int = 64, max_cols: int = 40) -> str:
        """Compact text summary fed into the planner LLM."""

    @abstractmethod
    def sample(
        self, object_name: str, limit: int = 5
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Return (columns, rows) preview for one table/collection."""

    @abstractmethod
    def run(
        self, query: Any, *, max_rows: int
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Execute a validated read-only query.

        For SQL adapters, `query` is a SQL string.
        For Mongo, `query` is a dict like
            {"op": "aggregate" | "find" | "countDocuments" | "distinct",
             "collection": "...",
             "pipeline" | "filter" | "field": ...,
             "limit"?: int, "sort"?: {...}, "projection"?: {...}}
        """

    @abstractmethod
    def dispose(self) -> None:
        """Release the underlying connection / pool."""
