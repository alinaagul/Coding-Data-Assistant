import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from ..db_connection import connection_manager, model_provider

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _run(sql: str) -> list[dict]:
    engine = connection_manager.get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = result.keys()
        return [dict(zip(cols, row)) for row in result.fetchall()]


def _require_connection():
    if not connection_manager.is_connected:
        raise HTTPException(status_code=400, detail="Connect to a database first.")


@router.get("/missing-indexes")
def missing_indexes():
    _require_connection()
    sql = """
    SELECT TOP 25
        d.statement AS table_name,
        d.equality_columns, d.inequality_columns, d.included_columns,
        s.avg_total_user_cost * s.avg_user_impact * (s.user_seeks + s.user_scans) AS improvement_measure,
        s.user_seeks, s.user_scans, s.avg_user_impact
    FROM sys.dm_db_missing_index_details d
    JOIN sys.dm_db_missing_index_groups g ON d.index_handle = g.index_handle
    JOIN sys.dm_db_missing_index_group_stats s ON g.index_group_handle = s.group_handle
    ORDER BY improvement_measure DESC
    """
    try:
        return _run(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/redundant-indexes")
def redundant_indexes():
    _require_connection()
    sql = """
    SELECT
        s.name AS schema_name, t.name AS table_name,
        i1.name AS index_a, i2.name AS index_b,
        STRING_AGG(c1.name, ',') WITHIN GROUP (ORDER BY ic1.key_ordinal) AS index_a_columns
    FROM sys.indexes i1
    JOIN sys.indexes i2 ON i1.object_id = i2.object_id AND i1.index_id < i2.index_id
    JOIN sys.tables t ON i1.object_id = t.object_id
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    JOIN sys.index_columns ic1 ON ic1.object_id = i1.object_id AND ic1.index_id = i1.index_id AND ic1.key_ordinal = 1
    JOIN sys.index_columns ic2 ON ic2.object_id = i2.object_id AND ic2.index_id = i2.index_id AND ic2.key_ordinal = 1
    JOIN sys.columns c1 ON c1.object_id = ic1.object_id AND c1.column_id = ic1.column_id
    JOIN sys.columns c2 ON c2.object_id = ic2.object_id AND c2.column_id = ic2.column_id
    WHERE ic1.column_id = ic2.column_id
    GROUP BY s.name, t.name, i1.name, i2.name
    """
    try:
        return _run(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/null-heavy-columns")
def null_heavy_columns(threshold_pct: float = 50.0):
    """
    Scans nullable columns table-by-table and reports those above the NULL
    percentage threshold. Capped to keep this fast on large schemas.
    """
    _require_connection()
    tables = _run(
        """
        SELECT TOP 30 s.name AS schema_name, t.name AS table_name
        FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id
        """
    )
    findings = []
    for t in tables:
        cols = _run(
            f"""
            SELECT c.name AS column_name
            FROM sys.columns c
            JOIN sys.tables tb ON c.object_id = tb.object_id
            JOIN sys.schemas s ON tb.schema_id = s.schema_id
            WHERE s.name = '{t['schema_name']}' AND tb.name = '{t['table_name']}' AND c.is_nullable = 1
            """
        )
        if not cols:
            continue
        total_row = _run(f"SELECT COUNT(*) AS n FROM [{t['schema_name']}].[{t['table_name']}]")
        total = total_row[0]["n"] if total_row else 0
        if total == 0:
            continue
        for c in cols[:15]:
            col = c["column_name"]
            null_row = _run(
                f"SELECT COUNT(*) AS n FROM [{t['schema_name']}].[{t['table_name']}] WHERE [{col}] IS NULL"
            )
            null_count = null_row[0]["n"] if null_row else 0
            pct = round(100.0 * null_count / total, 1)
            if pct >= threshold_pct:
                findings.append({
                    "schema": t["schema_name"], "table": t["table_name"], "column": col,
                    "null_percent": pct, "total_rows": total,
                })
    return findings


@router.get("/health")
def health_report():
    _require_connection()
    table_stats = _run(
        """
        SELECT COUNT(DISTINCT t.object_id) AS total_tables, SUM(p.rows) AS total_rows
        FROM sys.tables t
        JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
        """
    )
    index_stats = _run("SELECT COUNT(*) AS total_indexes FROM sys.indexes WHERE name IS NOT NULL")
    size_stats = _run(
        """
        SELECT CAST(ROUND(SUM(a.total_pages) * 8 / 1024.0, 2) AS FLOAT) AS size_mb
        FROM sys.tables t
        JOIN sys.indexes i ON t.object_id = i.object_id
        JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        JOIN sys.allocation_units a ON p.partition_id = a.container_id
        """
    )
    missing = missing_indexes()
    nulls = null_heavy_columns()

    # Simple composite score: starts at 100, deducted for issues found.
    score = 100
    score -= min(len(missing) * 3, 30)
    score -= min(len(nulls) * 2, 20)
    score = max(score, 0)

    return {
        "total_tables": table_stats[0]["total_tables"] if table_stats else 0,
        "total_rows": table_stats[0]["total_rows"] if table_stats else 0,
        "total_indexes": index_stats[0]["total_indexes"] if index_stats else 0,
        "database_size_mb": size_stats[0]["size_mb"] if size_stats else 0,
        "health_score": score,
        "missing_index_count": len(missing),
        "null_heavy_column_count": len(nulls),
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


@router.get("/performance")
def performance_report(top_n: int = 15):
    _require_connection()
    sql = f"""
    SELECT TOP {top_n}
        SUBSTRING(qt.text, (qs.statement_start_offset/2)+1,
            ((CASE qs.statement_end_offset WHEN -1 THEN DATALENGTH(qt.text)
              ELSE qs.statement_end_offset END - qs.statement_start_offset)/2)+1) AS query_text,
        qs.execution_count,
        qs.total_elapsed_time / 1000.0 AS total_elapsed_ms,
        (qs.total_elapsed_time / qs.execution_count) / 1000.0 AS avg_elapsed_ms,
        qs.total_logical_reads,
        qs.last_execution_time
    FROM sys.dm_exec_query_stats qs
    CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
    WHERE qt.dbid = DB_ID()
    ORDER BY avg_elapsed_ms DESC
    """
    try:
        return _run(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find-duplicates")
def find_duplicates(schema: str, table: str, columns: str):
    """`columns` is a comma-separated list of column names to group by."""
    _require_connection()
    col_list = ", ".join(f"[{c.strip()}]" for c in columns.split(","))
    sql = f"""
    SELECT {col_list}, COUNT(*) AS duplicate_count
    FROM [{schema}].[{table}]
    GROUP BY {col_list}
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC
    """
    try:
        return _run(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orphan-records")
def orphan_records():
    """Uses the FK graph to find child rows whose parent key no longer exists."""
    _require_connection()
    fks = _run(
        """
        SELECT
            fk.name AS constraint_name,
            sp.name AS parent_schema, tp.name AS parent_table, cp.name AS parent_column,
            sr.name AS ref_schema, tr.name AS ref_table, cr.name AS ref_column
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
        JOIN sys.schemas sp ON tp.schema_id = sp.schema_id
        JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
        JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
        JOIN sys.schemas sr ON tr.schema_id = sr.schema_id
        JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
        WHERE fk.is_not_trusted = 1 OR fk.is_disabled = 0
        """
    )
    findings = []
    for fk in fks[:20]:
        sql = f"""
        SELECT COUNT(*) AS orphan_count
        FROM [{fk['parent_schema']}].[{fk['parent_table']}] p
        WHERE p.[{fk['parent_column']}] IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM [{fk['ref_schema']}].[{fk['ref_table']}] r
            WHERE r.[{fk['ref_column']}] = p.[{fk['parent_column']}]
        )
        """
        try:
            count = _run(sql)[0]["orphan_count"]
        except Exception:
            continue
        if count > 0:
            findings.append({**fk, "orphan_count": count})
    return findings


@router.get("/data-quality")
def data_quality_report():
    _require_connection()
    return {
        "null_heavy_columns": null_heavy_columns(),
        "orphan_records": orphan_records(),
        "redundant_indexes": redundant_indexes(),
    }


@router.get("/ai-summary")
def ai_summary_report(kind: str = "health"):
    """
    Runs the requested structured report, then asks qwen3:8b to turn the raw
    numbers into a short narrative summary for the Reports page.
    """
    _require_connection()
    if kind == "health":
        data = health_report()
    elif kind == "performance":
        data = {"slow_queries": performance_report()}
    elif kind == "data-quality":
        data = data_quality_report()
    else:
        raise HTTPException(status_code=400, detail="Unknown report kind.")

    prompt = f"Write a short (5-8 bullet points) plain-English report from this JSON data:\n\n{data}"
    resp = model_provider.chat(
        [{"role": "system", "content": "You are a database analyst summarizing metrics for a non-technical stakeholder."},
         {"role": "user", "content": prompt}],
        think=False, temperature=0.3,
    )
    return {"raw_data": data, "narrative": resp["message"].get("content", "")}
