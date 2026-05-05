"""
Phase 1: decompose a PM question into N read-only sub-queries.

Output shape:
{
  "steps": [
    {
      "id": "step1",
      "intent": "Total signups in last 30 days",
      "query": "SELECT ..." | { "op": "aggregate", "collection": "users", ... }
    },
    ...
  ],
  "synthesis_hint": "free-text reminder for the synthesizer"
}
"""

from __future__ import annotations

import json
from typing import Any, Optional

from analysts.llm import llm_json


def _coerce_query(query: Any, dialect: str) -> Any:
    """LLMs occasionally return Mongo queries as JSON-encoded strings or wrap
    them in code fences. Try to recover before handing to the executor."""
    if query is None:
        return None
    if dialect != "mongodb":
        return query
    if isinstance(query, dict):
        return query
    if isinstance(query, str):
        s = query.strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s.lower().startswith("json"):
                s = s[4:].lstrip()
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return query

PLANNER_SYSTEM_SQL = """You are an elite product analytics planner working with a live SQL warehouse.

You receive a PM's question, the SQL dialect, and a compact schema of real tables/columns. You decompose the question into between 1 and {step_cap} ordered read-only sub-queries that, together, answer the question well enough for a sectioned PM report (executive summary, KPIs, charts, findings, hypotheses, actions).

Return ONLY valid JSON (no markdown fences) with keys:
- steps: array of objects, each with:
    - id: short slug like "step1"
    - intent: one-sentence description of what this query computes
    - query: ONE read-only SELECT or WITH ... SELECT statement, dialect-aware, single statement only
- synthesis_hint: free-text guidance for the report writer (what to emphasize, what to compare)

Rules:
- Each query must be strictly read-only (SELECT / WITH only). Runtime blocks writes.
- Use only tables/columns present in the schema. If something is missing, design queries that adapt (e.g. compute approximations from available columns).
- Prefer step queries that produce small, chart-friendly result sets (aggregations, group-bys, time series).
- Do NOT hard-code LIMIT; runtime will append a safe cap.
- Never invent metrics — if numbers matter, queries must compute them.
"""

PLANNER_SYSTEM_MONGO = """You are an elite product analytics planner working with a live MongoDB database.

You receive a PM's question and an inferred schema (collection: field:type pairs sampled from documents). You decompose the question into between 1 and {step_cap} ordered read-only sub-queries that, together, answer the question well enough for a sectioned PM report.

Return ONLY valid JSON (no markdown fences) with keys:
- steps: array of objects, each with:
    - id: short slug like "step1"
    - intent: one-sentence description
    - query: object with shape:
        {{ "op": "aggregate", "collection": "<name>", "pipeline": [ ...stages... ] }}
        OR
        {{ "op": "find", "collection": "<name>", "filter": {{...}}, "projection": {{...}}, "sort": {{...}}, "limit": <int> }}
        OR
        {{ "op": "countDocuments", "collection": "<name>", "filter": {{...}} }}
        OR
        {{ "op": "distinct", "collection": "<name>", "field": "<field>", "filter": {{...}} }}
- synthesis_hint: free-text guidance for the report writer

Rules:
- Read-only only. Never use $out, $merge, $function, $where, $accumulator.
- Use only collections/fields visible in the schema; treat the schema as a sample (some fields may be missing in some docs).
- Prefer aggregate pipelines that produce small, chart-friendly result sets.
- Do NOT include $limit yourself for capping; runtime appends a safe cap. (You MAY include $limit when the analysis logically requires top-N.)
"""


async def plan_steps(
    *,
    question: str,
    dialect: str,
    schema_text: str,
    template_intent: Optional[str] = None,
    template_synthesis_hint: Optional[str] = None,
    template_params: Optional[dict[str, Any]] = None,
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    anthropic_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    llm_provider: str = "auto",
    step_cap: int = 5,
) -> dict[str, Any]:
    is_mongo = dialect == "mongodb"
    system = (PLANNER_SYSTEM_MONGO if is_mongo else PLANNER_SYSTEM_SQL).format(
        step_cap=step_cap
    )

    parts: list[str] = []
    if template_intent:
        parts.append(f"Template focus:\n{template_intent}")
    if template_params:
        parts.append("Template parameters:\n" + "\n".join(
            f"- {k}: {v}" for k, v in template_params.items() if v
        ))
    if template_synthesis_hint:
        parts.append(f"Synthesis hint from template:\n{template_synthesis_hint}")

    parts.append(f"Dialect: {dialect}")
    parts.append(f"Schema snapshot:\n{schema_text}")
    parts.append(f"PM question:\n{question.strip()}")

    user = "\n\n".join(parts)

    plan = await llm_json(
        system,
        user,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
        gemini_key=gemini_key,
        anthropic_model=anthropic_model,
        openai_model=openai_model,
        gemini_model=gemini_model,
        llm_provider=llm_provider,
    )

    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Planner did not return any steps.")

    cleaned: list[dict[str, Any]] = []
    for i, s in enumerate(steps[:step_cap]):
        if not isinstance(s, dict):
            continue
        cleaned.append(
            {
                "id": str(s.get("id") or f"step{i + 1}"),
                "intent": str(s.get("intent") or "").strip(),
                "query": _coerce_query(s.get("query"), dialect),
            }
        )
    if not cleaned:
        raise ValueError("Planner returned no usable steps.")

    return {
        "steps": cleaned,
        "synthesis_hint": str(plan.get("synthesis_hint") or "").strip(),
    }
