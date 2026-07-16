import time

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from ..db_connection import connection_manager
from ..schemas import QueryPayload, ExplainQueryPayload
from ..sql_validator import validate_select_only, enforce_row_limit

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("/execute")
def execute_query(payload: QueryPayload):
    validation = validate_select_only(payload.sql)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.reason)

    safe_sql = enforce_row_limit(validation.cleaned_sql, max_rows=payload.max_rows)

    start = time.time()
    try:
        engine = connection_manager.get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(safe_sql))
            cols = list(result.keys())
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    elapsed = round(time.time() - start, 3)
    return {
        "columns": cols,
        "rows": rows,
        "row_count": len(rows),
        "elapsed_s": elapsed,
        "executed_sql": safe_sql,
    }


@router.post("/validate")
def validate_query(payload: ExplainQueryPayload):
    result = validate_select_only(payload.sql)
    return {"is_valid": result.is_valid, "reason": result.reason}


@router.post("/plan")
def query_plan(payload: ExplainQueryPayload):
    """Returns SQL Server's estimated execution plan (SET SHOWPLAN) as XML."""
    validation = validate_select_only(payload.sql)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.reason)
    try:
        raw_conn = connection_manager.raw_connection()
        cursor = raw_conn.cursor()
        cursor.execute("SET SHOWPLAN_XML ON")
        cursor.execute(validation.cleaned_sql)
        plan_xml = cursor.fetchone()[0]
        cursor.execute("SET SHOWPLAN_XML OFF")
        raw_conn.close()
        return {"plan_xml": plan_xml}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
