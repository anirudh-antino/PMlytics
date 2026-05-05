"""
In-memory registry of active database connections.

Connections live for the lifetime of the FastAPI process; nothing persists.
Exactly one connection can be marked active at a time, and PM analyses run
against the active connection's adapter.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from adapters import Adapter, ConnectionConfig, create_adapter


@dataclass
class ConnectionRecord:
    id: str
    name: str
    type: str  # "postgresql" | "mysql" | "mongodb"
    host: Optional[str]
    port: Optional[int]
    database: Optional[str]
    user: Optional[str]
    ssl: bool
    has_raw_url: bool
    created_at: str
    is_active: bool
    adapter: Adapter = field(repr=False)

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "ssl": self.ssl,
            "has_raw_url": self.has_raw_url,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "dialect": self.adapter.dialect,
        }


class ConnectionRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, ConnectionRecord] = {}
        self._active_id: Optional[str] = None

    def list(self) -> list[ConnectionRecord]:
        with self._lock:
            return list(self._records.values())

    def get(self, conn_id: str) -> Optional[ConnectionRecord]:
        with self._lock:
            return self._records.get(conn_id)

    def active(self) -> Optional[ConnectionRecord]:
        with self._lock:
            if self._active_id is None:
                return None
            return self._records.get(self._active_id)

    def add(self, config: ConnectionConfig) -> ConnectionRecord:
        adapter = create_adapter(config)
        adapter.test()

        rec = ConnectionRecord(
            id=str(uuid.uuid4()),
            name=config.name.strip() or f"{config.type} connection",
            type=config.type,
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            ssl=bool(config.ssl),
            has_raw_url=bool(config.raw_url and config.raw_url.strip()),
            created_at=datetime.now(timezone.utc).isoformat(),
            is_active=False,
            adapter=adapter,
        )
        with self._lock:
            self._records[rec.id] = rec
            if self._active_id is None:
                self._active_id = rec.id
                rec.is_active = True
        return rec

    def activate(self, conn_id: str) -> ConnectionRecord:
        with self._lock:
            if conn_id not in self._records:
                raise KeyError(conn_id)
            for r in self._records.values():
                r.is_active = False
            self._active_id = conn_id
            self._records[conn_id].is_active = True
            return self._records[conn_id]

    def remove(self, conn_id: str) -> None:
        with self._lock:
            rec = self._records.pop(conn_id, None)
            if rec is not None:
                try:
                    rec.adapter.dispose()
                except Exception:
                    pass
            if self._active_id == conn_id:
                self._active_id = None
                if self._records:
                    next_id = next(iter(self._records))
                    self._active_id = next_id
                    self._records[next_id].is_active = True

    def clear(self) -> None:
        with self._lock:
            for r in list(self._records.values()):
                try:
                    r.adapter.dispose()
                except Exception:
                    pass
            self._records.clear()
            self._active_id = None
