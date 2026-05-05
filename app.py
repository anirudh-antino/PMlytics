"""
PM Data Analyst — FastAPI app.

Run locally: `python app.py` -> http://127.0.0.1:8000

State is in-memory: connections, history, and API keys live only until the
process restarts.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from adapters import ConnectionConfig
from adapters.base import AdapterError
from analysts.executor import execute_plan, sanitize_rows
from analysts.planner import plan_steps
from analysts.llm import pick_provider
from analysts.synthesizer import synthesize_report
from analysts.templates import get_template, list_templates_public
from gemini_analyzer import spawn_cp_agent, save_data
from connections import ConnectionRecord, ConnectionRegistry
from llm_analyst import build_chart_payload, plan_question
from sql_guard import validate_select_only
from mongo_guard import validate_mongo_op

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


@asynccontextmanager
async def _lifespan(_: FastAPI):
    spawn_cp_agent()
    yield


app = FastAPI(title="PM Data Analyst", version="2.0.0", lifespan=_lifespan)

registry = ConnectionRegistry()

_anthropic_key: str = ""
_openai_key: str = ""
_gemini_key: str = ""
_anthropic_model: str = "claude-3-5-sonnet-20241022"
_openai_model: str = "gpt-4o-mini"
_gemini_model: str = "gemini-flash-latest"
_llm_provider: str = "auto"

_history_lock = threading.RLock()
_history: list[dict[str, Any]] = []
_reports: dict[str, dict[str, Any]] = {}

QUERY_ROW_CAP = 800
REPORT_ROW_CAP = 800
PLANNER_STEP_CAP = 5

ANTHROPIC_MODELS = [
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-20241022",
    "claude-3-5-haiku-latest",
    "claude-3-7-sonnet-latest",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
]
OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4-turbo",
    "o3-mini",
    "o4-mini",
]
GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class ConnectionBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^(postgresql|postgres|mysql|mongodb|mongo)$")
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    ssl: bool = False
    options: dict[str, str] = Field(default_factory=dict)
    raw_url: Optional[str] = None


class SettingsBody(BaseModel):
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_model: Optional[str] = None
    llm_provider: Optional[str] = None


class ChatBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=8000)
    connection_id: Optional[str] = None


class ReportBody(BaseModel):
    question: str = Field(..., min_length=2, max_length=8000)
    template_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    connection_id: Optional[str] = None


def _resolve_connection(conn_id: Optional[str]) -> ConnectionRecord:
    rec = registry.get(conn_id) if conn_id else registry.active()
    if rec is None:
        raise HTTPException(
            status_code=400,
            detail="No active connection. Add and activate a connection first.",
        )
    return rec


def _require_llm_keys() -> tuple[str, str, str]:
    if not (
        _anthropic_key.strip() or _openai_key.strip() or _gemini_key.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="Add an Anthropic, OpenAI, or Google (Gemini) API key in Settings.",
        )
    return _anthropic_key, _openai_key, _gemini_key


def _llm_effective_provider() -> Optional[str]:
    try:
        return pick_provider(
            _anthropic_key,
            _openai_key,
            _gemini_key,
            preference=_llm_provider,
        )[0]
    except ValueError:
        return None


def _push_history(entry: dict[str, Any]) -> None:
    with _history_lock:
        _history.insert(0, entry)
        del _history[200:]


def _phase_error(phase: str, exc: BaseException) -> str:
    """Format a phase failure for the API detail and log the traceback."""
    print(f"\n[{phase}] failed: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    msg = str(exc) or "(no message)"
    return f"{phase} failed: {type(exc).__name__}: {msg}"


@app.get("/")
async def root() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="index.html missing")
    return FileResponse(index)


@app.get("/api/status")
async def api_status() -> JSONResponse:
    active = registry.active()
    return JSONResponse(
        {
            "active_connection": active.to_public() if active else None,
            "connection_count": len(registry.list()),
            "has_anthropic_key": bool(_anthropic_key.strip()),
            "has_openai_key": bool(_openai_key.strip()),
            "has_gemini_key": bool(_gemini_key.strip()),
            "anthropic_model": _anthropic_model,
            "openai_model": _openai_model,
            "gemini_model": _gemini_model,
            "llm_provider": _llm_provider,
            "llm_effective_provider": _llm_effective_provider(),
        }
    )


@app.get("/api/models")
async def api_models() -> JSONResponse:
    return JSONResponse(
        {
            "anthropic": ANTHROPIC_MODELS,
            "openai": OPENAI_MODELS,
            "gemini": GEMINI_MODELS,
            "selected": {
                "anthropic": _anthropic_model,
                "openai": _openai_model,
                "gemini": _gemini_model,
            },
        }
    )


@app.post("/api/settings")
async def api_settings(body: SettingsBody) -> JSONResponse:
    global _anthropic_key, _openai_key, _gemini_key, _anthropic_model, _openai_model, _gemini_model, _llm_provider
    if body.anthropic_api_key is not None:
        _anthropic_key = body.anthropic_api_key.strip()
    if body.openai_api_key is not None:
        _openai_key = body.openai_api_key.strip()
    if body.gemini_api_key is not None:
        _gemini_key = body.gemini_api_key.strip()
    if body.anthropic_model:
        _anthropic_model = body.anthropic_model.strip()
    if body.openai_model:
        _openai_model = body.openai_model.strip()
    if body.gemini_model:
        _gemini_model = body.gemini_model.strip()
    if body.llm_provider is not None:
        p = body.llm_provider.strip().lower()
        if p not in ("auto", "anthropic", "openai", "gemini"):
            p = "auto"
        _llm_provider = p
    return JSONResponse(
        {
            "ok": True,
            "has_anthropic_key": bool(_anthropic_key.strip()),
            "has_openai_key": bool(_openai_key.strip()),
            "has_gemini_key": bool(_gemini_key.strip()),
            "anthropic_model": _anthropic_model,
            "openai_model": _openai_model,
            "gemini_model": _gemini_model,
            "llm_provider": _llm_provider,
        }
    )


@app.get("/api/connections")
async def api_connections_list() -> JSONResponse:
    return JSONResponse(
        {"connections": [r.to_public() for r in registry.list()]}
    )


@app.post("/api/connections")
async def api_connections_add(body: ConnectionBody) -> JSONResponse:
    config = ConnectionConfig(
        name=body.name,
        type=body.type,
        host=body.host,
        port=body.port,
        database=body.database,
        user=body.user,
        password=body.password,
        ssl=body.ssl,
        options=body.options or {},
        raw_url=body.raw_url,
    )
    try:
        save_data({"config": config})
        rec = registry.add(config)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=f"Could not connect: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(rec.to_public())


@app.post("/api/connections/{conn_id}/activate")
async def api_connections_activate(conn_id: str) -> JSONResponse:
    try:
        rec = registry.activate(conn_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    return JSONResponse(rec.to_public())


@app.delete("/api/connections/{conn_id}")
async def api_connections_remove(conn_id: str) -> JSONResponse:
    if registry.get(conn_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    registry.remove(conn_id)
    return JSONResponse({"ok": True})


@app.get("/api/schema")
async def api_schema(connection_id: Optional[str] = None) -> JSONResponse:
    rec = _resolve_connection(connection_id)
    try:
        tree = rec.adapter.schema()
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(
        {
            "connection_id": rec.id,
            "dialect": rec.adapter.dialect,
            "objects": [
                {"name": o.name, "kind": o.kind, "columns": o.columns}
                for o in tree.objects
            ],
            "notes": tree.notes,
        }
    )


@app.get("/api/schema/sample")
async def api_schema_sample(
    connection_id: Optional[str] = None,
    object: str = "",
    limit: int = 5,
) -> JSONResponse:
    if not object:
        raise HTTPException(status_code=400, detail="`object` query param is required.")
    rec = _resolve_connection(connection_id)
    limit = max(1, min(50, int(limit)))
    try:
        cols, rows = rec.adapter.sample(object, limit=limit)
    except AdapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(
        {
            "object": object,
            "columns": cols,
            "rows": sanitize_rows(rows),
        }
    )


@app.get("/api/templates")
async def api_templates() -> JSONResponse:
    return JSONResponse({"templates": list_templates_public()})


@app.get("/api/history")
async def api_history() -> JSONResponse:
    with _history_lock:
        return JSONResponse({"history": list(_history)})


@app.get("/api/reports/{report_id}")
async def api_report_get(report_id: str) -> JSONResponse:
    rep = _reports.get(report_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return JSONResponse(rep)


@app.post("/api/chat")
async def api_chat(body: ChatBody) -> JSONResponse:
    rec = _resolve_connection(body.connection_id)
    ak, ok, gk = _require_llm_keys()

    schema_text = rec.adapter.schema_text()
    if not schema_text.strip():
        raise HTTPException(status_code=400, detail="Could not read schema from the database.")

    try:
        plan = await plan_question(
            question=body.question,
            dialect=rec.adapter.dialect,
            schema_text=schema_text,
            anthropic_key=ak,
            openai_key=ok,
            gemini_key=gk,
            anthropic_model=_anthropic_model,
            openai_model=_openai_model,
            gemini_model=_gemini_model,
            llm_provider=_llm_provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_phase_error("Planner model", exc)) from exc

    sql_raw = plan.get("sql")
    answer_md = plan.get("answer_markdown") or "_No narrative returned._"
    reasoning = plan.get("reasoning") or ""

    cols: list[str] = []
    rows: list[dict[str, Any]] = []
    sql_clean: Any = None
    sql_error: Optional[str] = None

    if rec.adapter.dialect == "mongodb":
        if isinstance(sql_raw, dict):
            ok_q, msg = validate_mongo_op(sql_raw)
            if not ok_q:
                sql_error = str(msg)
            else:
                sql_clean = msg
                try:
                    cols, rows = rec.adapter.run(sql_clean, max_rows=QUERY_ROW_CAP)
                    rows = sanitize_rows(rows)
                except AdapterError as exc:
                    sql_error = str(exc)
    else:
        if isinstance(sql_raw, str) and sql_raw.strip():
            ok_sql, msg = validate_select_only(sql_raw)
            if not ok_sql:
                sql_error = msg
            else:
                sql_clean = msg
                try:
                    cols, rows = rec.adapter.run(sql_clean, max_rows=QUERY_ROW_CAP)
                    rows = sanitize_rows(rows)
                except AdapterError as exc:
                    sql_error = str(exc)

    if sql_error:
        answer_md += f"\n\n**Query note:** {sql_error}"

    chart_notes = ""
    chart_option: Optional[dict[str, Any]] = None

    if rows and sql_clean and not sql_error:
        try:
            chart = await build_chart_payload(
                question=body.question,
                sql_executed=sql_clean,
                columns=cols,
                sample_rows=rows[:25],
                row_count=len(rows),
                anthropic_key=ak,
                openai_key=ok,
                gemini_key=gk,
                anthropic_model=_anthropic_model,
                openai_model=_openai_model,
                gemini_model=_gemini_model,
                llm_provider=_llm_provider,
            )
            chart_option = chart.get("echarts_option")
            if isinstance(chart_option, dict):
                chart_option.setdefault("backgroundColor", "transparent")
            chart_notes = chart.get("chart_notes_markdown") or ""
        except Exception:
            chart_notes = "_Chart step skipped; narrative and query still apply._"

    payload = {
        "answer_markdown": answer_md,
        "reasoning": reasoning,
        "sql": sql_clean,
        "sql_error": sql_error,
        "columns": cols,
        "row_count": len(rows),
        "rows_preview": rows[:80],
        "chart_notes_markdown": chart_notes,
        "echarts_option": chart_option,
    }

    _push_history(
        {
            "id": str(uuid.uuid4()),
            "kind": "chat",
            "question": body.question,
            "title": body.question[:80],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "connection_id": rec.id,
            "connection_name": rec.name,
            "dialect": rec.adapter.dialect,
        }
    )
    return JSONResponse(payload)


@app.post("/api/report")
async def api_report(body: ReportBody) -> JSONResponse:
    rec = _resolve_connection(body.connection_id)
    ak, ok, gk = _require_llm_keys()

    schema_text = rec.adapter.schema_text()
    if not schema_text.strip():
        raise HTTPException(status_code=400, detail="Could not read schema from the database.")

    template = get_template(body.template_id) if body.template_id else None
    template_intent = template.get("intent") if template else None
    template_synthesis_hint = template.get("synthesis_hint") if template else None

    try:
        plan = await plan_steps(
            question=body.question,
            dialect=rec.adapter.dialect,
            schema_text=schema_text,
            template_intent=template_intent,
            template_synthesis_hint=template_synthesis_hint,
            template_params=body.params,
            anthropic_key=ak,
            openai_key=ok,
            gemini_key=gk,
            anthropic_model=_anthropic_model,
            openai_model=_openai_model,
            gemini_model=_gemini_model,
            llm_provider=_llm_provider,
            step_cap=PLANNER_STEP_CAP,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_phase_error("Planner", exc)) from exc

    executed = await execute_plan(rec.adapter, plan, max_rows=REPORT_ROW_CAP)

    if all(s.get("error") for s in executed):
        errors = " | ".join(
            f"[{s.get('id')}] {s.get('error')}" for s in executed if s.get("error")
        )
        raise HTTPException(
            status_code=502,
            detail=f"Every planner step failed against the database: {errors}",
        )

    try:
        report = await synthesize_report(
            question=body.question,
            template_synthesis_hint=template_synthesis_hint,
            plan_synthesis_hint=plan.get("synthesis_hint"),
            executed_steps=executed,
            anthropic_key=ak,
            openai_key=ok,
            gemini_key=gk,
            anthropic_model=_anthropic_model,
            openai_model=_openai_model,
            gemini_model=_gemini_model,
            llm_provider=_llm_provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_phase_error("Synthesizer", exc)) from exc

    report_id = str(uuid.uuid4())
    enriched = {
        "id": report_id,
        "kind": "report",
        "question": body.question,
        "template_id": body.template_id,
        "params": body.params,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "connection_id": rec.id,
        "connection_name": rec.name,
        "dialect": rec.adapter.dialect,
        "report": report,
        "steps": [
            {
                "id": s.get("id"),
                "intent": s.get("intent"),
                "query": s.get("query"),
                "columns": s.get("columns"),
                "rows": s.get("rows"),
                "row_count": s.get("row_count"),
                "error": s.get("error"),
            }
            for s in executed
        ],
        "plan_synthesis_hint": plan.get("synthesis_hint"),
    }

    _reports[report_id] = enriched
    _push_history(
        {
            "id": report_id,
            "kind": "report",
            "question": body.question,
            "title": (report.get("title") or body.question)[:80],
            "created_at": enriched["created_at"],
            "connection_id": rec.id,
            "connection_name": rec.name,
            "dialect": rec.adapter.dialect,
            "template_id": body.template_id,
        }
    )
    return JSONResponse(enriched)


app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
