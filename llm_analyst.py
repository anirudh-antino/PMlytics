"""
Single-shot Q&A used by /api/chat (the "Quick answer" mode).

This is the lighter, original two-phase flow: (1) plan one query and a narrative,
(2) build a chart from the rows. The multi-step report flow lives in
`analysts/{planner,executor,synthesizer}.py`.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from analysts.llm import llm_json


PHASE1_SYSTEM_SQL = """You are an elite product analytics partner for a PM with live warehouse access.

The schema lists real tables and columns. The PM may ask for cross-table analysis, cohorts, funnels built from events, retention proxies, revenue joins—anything answerable with read-only SQL.

Return ONLY valid JSON (no markdown fences) with keys:
- answer_markdown (string): executive narrative with bullets and **bold** KPIs when you have numbers from SQL.
- sql (string|null): ONE read-only SELECT or WITH … SELECT using only tables/columns that appear in the schema. Match the SQL dialect exactly (Postgres vs MySQL quirks).
- reasoning (string): assumptions, missing dimensions, or what you would validate next.

Rules:
- Use JOINs, subqueries, window functions, CTEs when helpful—still one statement only.
- Never invent metrics; if numbers matter, sql must fetch them.
- sql must be strictly read-only (SELECT/WITH only). Runtime blocks writes.
- If the question is purely methodological or schema lacks needed entities, set sql null.
- Prefer aggregates/filters that behave well with an automatic row LIMIT (runtime adds LIMIT if absent).
"""


PHASE1_SYSTEM_MONGO = """You are an elite product analytics partner for a PM with live MongoDB access.

The schema lists collections with sampled fields and inferred types. The PM may ask for cross-collection analysis, cohorts, funnels, etc.—anything answerable with read-only Mongo queries.

Return ONLY valid JSON (no markdown fences) with keys:
- answer_markdown (string): executive narrative with bullets and **bold** KPIs when you have numbers from the query.
- sql (object|null): a Mongo op spec — one of:
    {"op": "aggregate", "collection": "<name>", "pipeline": [...]}
    {"op": "find", "collection": "<name>", "filter": {...}, "projection": {...}, "sort": {...}, "limit": <int>}
    {"op": "countDocuments", "collection": "<name>", "filter": {...}}
    {"op": "distinct", "collection": "<name>", "field": "<field>", "filter": {...}}
- reasoning (string): assumptions or what you would validate next.

Rules:
- Read-only only. Never use $out, $merge, $function, $where, $accumulator.
- Use only collections/fields visible in the schema (treat schema as a sample).
- If the question is purely methodological or the data is missing, set sql null.
"""


PHASE2_SYSTEM = """You visualize analytics for product managers.

Return ONLY JSON with keys:
- echarts_option (object): valid Apache ECharts option with transparent background and axes/tooltip/text colors suited for a WHITE/light dashboard (#6b7280 axis labels, #111 titles).
- chart_notes_markdown (string): how to read the chart + caveats.

Constraints:
- Categories must match the actual column values provided (truncate long labels).
- Keep series.data numeric where appropriate.
"""


async def plan_question(
    *,
    question: str,
    dialect: str,
    schema_text: str,
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    anthropic_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    llm_provider: str = "auto",
) -> dict[str, Any]:
    is_mongo = dialect == "mongodb"
    system = PHASE1_SYSTEM_MONGO if is_mongo else PHASE1_SYSTEM_SQL
    user = (
        f"Dialect: {dialect}\n\n"
        f"Schema snapshot:\n{schema_text}\n\n"
        f"PM question:\n{question.strip()}"
    )
    return await llm_json(
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


async def build_chart_payload(
    *,
    question: str,
    sql_executed: Any,
    columns: list[str],
    sample_rows: list[dict[str, Any]],
    row_count: int,
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    anthropic_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    llm_provider: str = "auto",
) -> dict[str, Any]:
    if isinstance(sql_executed, str):
        executed_text = sql_executed
    else:
        try:
            executed_text = json.dumps(sql_executed, ensure_ascii=False, default=str)
        except Exception:
            executed_text = str(sql_executed)

    preview = json.dumps(sample_rows, ensure_ascii=False, default=str)[:12000]
    user = (
        f"Original question:\n{question}\n\n"
        f"Executed query:\n{executed_text}\n\n"
        f"Columns: {columns}\n"
        f"Row count returned (<=limit): {row_count}\n"
        f"Sample rows JSON:\n{preview}"
    )
    return await llm_json(
        PHASE2_SYSTEM,
        user,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
        gemini_key=gemini_key,
        anthropic_model=anthropic_model,
        openai_model=openai_model,
        gemini_model=gemini_model,
        llm_provider=llm_provider,
    )
