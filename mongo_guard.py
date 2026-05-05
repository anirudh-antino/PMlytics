"""
Read-only MongoDB query gatekeeper.

The planner LLM emits a JSON op spec like:
    {"op": "aggregate", "collection": "users", "pipeline": [...]}
    {"op": "find", "collection": "events", "filter": {...}, "projection": {...}, "limit": 100, "sort": {...}}
    {"op": "countDocuments", "collection": "users", "filter": {...}}
    {"op": "distinct", "collection": "events", "field": "name", "filter": {...}}

This module validates the spec stays within a safe, read-only subset.
"""

from __future__ import annotations

from typing import Any

ALLOWED_OPS = {"aggregate", "find", "countDocuments", "distinct"}

DENIED_STAGES = {
    "$out",
    "$merge",
    "$function",
    "$where",
    "$accumulator",
    "$listSessions",
    "$listLocalSessions",
    "$currentOp",
    "$collStats",
    "$indexStats",
    "$planCacheStats",
}


def _walk_for_denied_ops(node: Any, denied: set[str]) -> str | None:
    """Walk a nested dict/list and return the first denied operator key found."""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k in denied:
                return k
            r = _walk_for_denied_ops(v, denied)
            if r:
                return r
    elif isinstance(node, list):
        for item in node:
            r = _walk_for_denied_ops(item, denied)
            if r:
                return r
    return None


def validate_mongo_op(spec: Any) -> tuple[bool, Any]:
    """Validate a Mongo op spec. Returns (ok, normalized_spec_or_message)."""
    if not isinstance(spec, dict):
        return False, "Mongo query must be a JSON object."

    op = str(spec.get("op", "")).strip()
    if op not in ALLOWED_OPS:
        return False, f"Operation {op!r} is not allowed (read-only)."

    coll = spec.get("collection")
    if not isinstance(coll, str) or not coll.strip():
        return False, "Mongo query must specify a collection."

    bad = _walk_for_denied_ops(spec, DENIED_STAGES)
    if bad:
        return False, f"Disallowed Mongo operator: {bad}"

    if op == "aggregate":
        pipeline = spec.get("pipeline")
        if not isinstance(pipeline, list) or not pipeline:
            return False, "aggregate requires a non-empty pipeline array."
        for stage in pipeline:
            if not isinstance(stage, dict) or len(stage) != 1:
                return False, "Each pipeline stage must be a single-key object."
            stage_name = next(iter(stage.keys()))
            if stage_name in DENIED_STAGES:
                return False, f"Disallowed pipeline stage: {stage_name}"

    if op == "find":
        if "filter" in spec and not isinstance(spec["filter"], dict):
            return False, "find.filter must be an object."
        if "projection" in spec and not isinstance(spec["projection"], dict):
            return False, "find.projection must be an object."

    if op == "distinct":
        if not isinstance(spec.get("field"), str):
            return False, "distinct.field must be a string."

    return True, spec


def enforce_mongo_limit(spec: dict, max_rows: int) -> dict:
    """Append a $limit / .limit() if the user op didn't include one."""
    op = spec.get("op")
    out = dict(spec)
    if op == "aggregate":
        pipeline = list(out.get("pipeline") or [])
        has_limit = any(
            isinstance(s, dict) and "$limit" in s for s in pipeline
        )
        if not has_limit:
            pipeline.append({"$limit": max_rows})
        out["pipeline"] = pipeline
    elif op == "find":
        lim = out.get("limit")
        if not isinstance(lim, int) or lim <= 0 or lim > max_rows:
            out["limit"] = max_rows
    elif op == "distinct":
        out.setdefault("limit", max_rows)
    return out
