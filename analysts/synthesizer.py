"""
Phase 3: turn executed step results into a sectioned PM report.

Output JSON shape (rendered directly by the frontend Report view):

{
  "title": "Onboarding drop-off, last 30 days",
  "summary": "2-3 sentence executive summary with **bold** numbers.",
  "kpis": [
    {"label": "Sign-ups", "value": "12,430", "delta": "+8.2% vs prior", "trend": "up"|"down"|"flat"},
    ...
  ],
  "charts": [
    {
      "title": "Funnel: sign-up -> activation",
      "step_id": "step2",
      "how_to_read": "Each bar is...",
      "echarts_option": { ... ECharts option JSON ... }
    },
    ...
  ],
  "findings": [
    {"text": "...", "evidence_step_id": "step3"},
    ...
  ],
  "hypotheses": [
    {"text": "...", "confidence": "high"|"medium"|"low", "evidence_step_id": "step1"},
    ...
  ],
  "actions": [
    {"text": "Run an A/B on ...", "owner_hint": "Growth"},
    ...
  ],
  "methodology": [
    {"step_id": "step1", "intent": "...", "query_preview": "...", "row_count": 30}
  ]
}
"""

from __future__ import annotations

import json
from typing import Any, Optional

from analysts.llm import llm_json


SYNTH_SYSTEM = """You are a senior product analytics partner writing a sectioned report for a PM.

You receive: the original PM question, an optional template synthesis hint, and the executed sub-query results (intent, columns, sample rows, row counts, errors). Some steps may have failed; tolerate that.

Return ONLY valid JSON (no markdown fences) with these keys:
- title: short headline for the report (<= 80 chars).
- summary: 2-3 sentence executive summary in markdown. Bold key numbers using **value**.
- kpis: array of 3-6 objects { label, value, delta (string or empty), trend (one of "up"|"down"|"flat") }. Pick metrics actually present in the step results.
- charts: array of 1-3 chart objects, each with:
    - title (string)
    - step_id (string referring to the step whose rows feed the chart)
    - how_to_read (1-2 sentences)
    - echarts_option (valid Apache ECharts option JSON tuned for a WHITE/light dashboard: transparent backgroundColor, axis labels #6b7280, titles #111, single accent color #4338ca, neutral grid)
- findings: array of 3-7 objects { text, evidence_step_id }. Cite the step that supports each finding.
- hypotheses: array of 2-5 ranked objects { text, confidence, evidence_step_id } explaining WHY (especially for drop-off / churn questions).
- actions: array of 3-5 objects { text, owner_hint } — concrete experiments or fixes a PM could ship.
- methodology: array of objects { step_id, intent, query_preview (string truncated to ~300 chars), row_count }.

Rules:
- Only cite numbers that appear in the provided rows.
- Categories in echarts must match actual values returned (truncate long labels).
- Keep series.data numeric where appropriate.
- If a step errored, still produce a useful report from the others and mention the gap in the summary.
- If essential data is missing, say so plainly and propose what to collect.
"""


def _truncate_query(q: Any, max_len: int = 300) -> str:
    if isinstance(q, str):
        s = q
    else:
        try:
            s = json.dumps(q, ensure_ascii=False, default=str)
        except Exception:
            s = str(q)
    if len(s) > max_len:
        s = s[:max_len] + " ..."
    return s


def _step_for_prompt(step: dict[str, Any], max_sample_rows: int) -> dict[str, Any]:
    rows = step.get("rows") or []
    return {
        "id": step.get("id"),
        "intent": step.get("intent"),
        "query_preview": _truncate_query(step.get("query")),
        "columns": step.get("columns") or [],
        "row_count": step.get("row_count") or 0,
        "sample_rows": rows[:max_sample_rows],
        "error": step.get("error"),
    }


async def synthesize_report(
    *,
    question: str,
    template_synthesis_hint: Optional[str],
    plan_synthesis_hint: Optional[str],
    executed_steps: list[dict[str, Any]],
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    anthropic_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    llm_provider: str = "auto",
    max_sample_rows_per_step: int = 25,
) -> dict[str, Any]:
    payload = {
        "question": question.strip(),
        "template_synthesis_hint": template_synthesis_hint or "",
        "plan_synthesis_hint": plan_synthesis_hint or "",
        "steps": [_step_for_prompt(s, max_sample_rows_per_step) for s in executed_steps],
    }
    user = json.dumps(payload, ensure_ascii=False, default=str)[:60_000]

    report = await llm_json(
        SYNTH_SYSTEM,
        user,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
        gemini_key=gemini_key,
        anthropic_model=anthropic_model,
        openai_model=openai_model,
        gemini_model=gemini_model,
        llm_provider=llm_provider,
    )

    report.setdefault("title", question.strip()[:80] or "Analysis")
    report.setdefault("summary", "")
    report.setdefault("kpis", [])
    report.setdefault("charts", [])
    report.setdefault("findings", [])
    report.setdefault("hypotheses", [])
    report.setdefault("actions", [])

    if not report.get("methodology"):
        report["methodology"] = [
            {
                "step_id": s.get("id"),
                "intent": s.get("intent"),
                "query_preview": _truncate_query(s.get("query")),
                "row_count": s.get("row_count") or 0,
                "error": s.get("error"),
            }
            for s in executed_steps
        ]

    for chart in report.get("charts") or []:
        opt = chart.get("echarts_option")
        if isinstance(opt, dict):
            opt.setdefault("backgroundColor", "transparent")

    return report
