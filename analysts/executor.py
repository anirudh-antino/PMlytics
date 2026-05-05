"""
Phase 2: run each planner step against the active adapter, capture results.

Errors are captured per-step (not raised) so the synthesizer can still build a
useful report from the steps that did succeed.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, AsyncIterator

from adapters import Adapter, AdapterError


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def sanitize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: _json_safe(v) for k, v in row.items()} for row in rows]


def execute_step(
    adapter: Adapter, step: dict[str, Any], *, max_rows: int
) -> dict[str, Any]:
    """Run one step. Returns the step dict augmented with results / error."""
    out = dict(step)
    query = step.get("query")
    if query is None or (isinstance(query, str) and not query.strip()):
        out["error"] = "Step has no query."
        out["columns"] = []
        out["rows"] = []
        out["row_count"] = 0
        return out

    try:
        cols, rows = adapter.run(query, max_rows=max_rows)
        rows = sanitize_rows(rows)
    except AdapterError as exc:
        out["error"] = str(exc)
        out["columns"] = []
        out["rows"] = []
        out["row_count"] = 0
        return out
    except Exception as exc:
        out["error"] = str(exc)
        out["columns"] = []
        out["rows"] = []
        out["row_count"] = 0
        return out

    out["error"] = None
    out["columns"] = cols
    out["rows"] = rows
    out["row_count"] = len(rows)
    return out


async def execute_plan(
    adapter: Adapter,
    plan: dict[str, Any],
    *,
    max_rows: int,
) -> list[dict[str, Any]]:
    """Run every step sequentially and return the executed-step list."""
    results: list[dict[str, Any]] = []
    for step in plan.get("steps", []):
        results.append(execute_step(adapter, step, max_rows=max_rows))
    return results


async def execute_plan_streaming(
    adapter: Adapter,
    plan: dict[str, Any],
    *,
    max_rows: int,
) -> AsyncIterator[dict[str, Any]]:
    """Yield each completed step as it finishes (for SSE progress)."""
    total = len(plan.get("steps", []))
    for i, step in enumerate(plan.get("steps", [])):
        result = execute_step(adapter, step, max_rows=max_rows)
        result["index"] = i + 1
        result["total"] = total
        yield result
