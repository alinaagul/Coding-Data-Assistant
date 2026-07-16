import logging

from fastapi import APIRouter, HTTPException

from ..ai_query_service import SQL_BLOCK_RE, run_ai_chat
from ..db_connection import connection_manager, model_provider
from ..schema_context import build_schema_summary, load_schema_metadata, render_prompt_context
from ..sql_templates import get_template_catalog
from ..schemas import ChatPayload, ChatResponse, ExplainQueryPayload, NLToSqlPayload, QueryAttempt, TemplateInfo
from ..sql_validator import validate_select_only

logger = logging.getLogger("ai_router")

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def ai_chat(payload: ChatPayload):
    """
    Full validate -> execute -> self-correct pipeline. Never lets a raw
    SQLAlchemy/pyodbc exception reach the user - execution errors are
    handled inside run_ai_chat() and fed back to the model for up to
    MAX_RETRIES attempts before being returned as `execution_error`.
    """
    try:
        result = run_ai_chat(payload.message, payload.history, think=payload.think)
    except RuntimeError as e:
        # e.g. Ollama not reachable - a real infra problem, not a query problem.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in AI chat")
        raise HTTPException(status_code=500, detail="AI chat failed unexpectedly. Check server logs.")

    return ChatResponse(
        answer=result.answer,
        used_template=result.used_template,
        final_sql=result.final_sql,
        execution=result.execution,
        execution_error=result.execution_error,
        attempts=[QueryAttempt(**vars(a)) for a in result.attempts],
        elapsed_s=result.elapsed_s,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


@router.get("/templates", response_model=list[TemplateInfo])
def list_templates():
    """Exposes the trusted SQL template catalog (useful for the frontend / debugging)."""
    return [
        TemplateInfo(id=t.id, name=t.name, description=t.description, requires_params=t.requires_params)
        for t in get_template_catalog()
    ]


@router.post("/explain-query")
def explain_query(payload: ExplainQueryPayload):
    validation = validate_select_only(payload.sql)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.reason)
    messages = [
        {"role": "system", "content": "Explain what the following SQL Server query does, in plain English, step by step."},
        {"role": "user", "content": payload.sql},
    ]
    resp = model_provider.chat(messages, think=False, temperature=0.2)
    return {"explanation": resp["message"].get("content", "")}


@router.post("/optimize-query")
def optimize_query(payload: ExplainQueryPayload):
    validation = validate_select_only(payload.sql)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.reason)
    schema_ctx = build_schema_summary() if connection_manager.is_connected else ""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a SQL Server performance expert. Suggest concrete optimizations for the "
                "given SELECT query (indexes, rewrites, avoiding scans, SARGability). "
                "Give a short bullet list, then an optimized ```sql version if applicable.\n\nSCHEMA:\n" + schema_ctx
            ),
        },
        {"role": "user", "content": payload.sql},
    ]
    resp = model_provider.chat(messages, think=True, temperature=0.2)
    raw = resp["message"].get("content", "")
    m = SQL_BLOCK_RE.search(raw)
    return {"recommendations": raw, "optimized_sql": m.group(1).strip() if m else None}


@router.post("/nl-to-sql")
def nl_to_sql(payload: NLToSqlPayload):
    """
    Returns a proposed SQL statement WITHOUT executing it - for callers
    that want to review a query before running it via /api/query or the
    SQL console. Uses the same rich schema grounding as /chat.
    """
    if not connection_manager.is_connected:
        raise HTTPException(status_code=400, detail="Connect to a database first.")
    meta = load_schema_metadata()
    schema_ctx = render_prompt_context(meta)
    messages = [
        {
            "role": "system",
            "content": (
                "Convert the user's question into a single safe SQL Server SELECT statement. "
                "Reply with ONLY a ```sql fenced code block, no other prose.\n\n" + schema_ctx
            ),
        },
        {"role": "user", "content": payload.question},
    ]
    resp = model_provider.chat(messages, think=False, temperature=0.1)
    raw = resp["message"].get("content", "")
    m = SQL_BLOCK_RE.search(raw)
    sql = m.group(1).strip() if m else raw.strip()
    validation = validate_select_only(sql)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=f"Model produced an unsafe query: {validation.reason}")
    return {"sql": validation.cleaned_sql}