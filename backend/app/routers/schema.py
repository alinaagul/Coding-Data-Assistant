from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from ..db_connection import connection_manager

router = APIRouter(prefix="/api/schema", tags=["schema"])


def _run(sql: str, params: dict | None = None) -> list[dict]:
    engine = connection_manager.get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {})
        cols = rows.keys()
        return [dict(zip(cols, row)) for row in rows.fetchall()]


@router.get("/databases")
def list_databases():
    try:
        return _run(
            "SELECT name, database_id, create_date, state_desc "
            "FROM sys.databases WHERE database_id > 4 ORDER BY name"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
def list_tables():
    sql = """
    SELECT
        s.name AS schema_name,
        t.name AS table_name,
        p.rows AS row_count_estimate,
        CAST(ROUND(SUM(a.total_pages) * 8 / 1024.0, 2) AS FLOAT) AS size_mb
    FROM sys.tables t
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    JOIN sys.indexes i ON t.object_id = i.object_id AND i.index_id IN (0, 1)
    JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
    JOIN sys.allocation_units a ON p.partition_id = a.container_id
    GROUP BY s.name, t.name, p.rows
    ORDER BY size_mb DESC
    """
    try:
        return _run(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{schema}/{table}/columns")
def get_columns(schema: str, table: str):
    sql = """
    SELECT
        c.name AS column_name,
        ty.name AS data_type,
        c.max_length,
        c.precision,
        c.scale,
        c.is_nullable,
        c.is_identity,
        CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
        dc.definition AS default_value
    FROM sys.columns c
    JOIN sys.types ty ON c.user_type_id = ty.user_type_id
    JOIN sys.tables t ON c.object_id = t.object_id
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    LEFT JOIN sys.default_constraints dc ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
    LEFT JOIN (
        SELECT ic.object_id, ic.column_id
        FROM sys.index_columns ic
        JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        WHERE i.is_primary_key = 1
    ) pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id
    WHERE s.name = :schema AND t.name = :table
    ORDER BY c.column_id
    """
    try:
        return _run(sql, {"schema": schema, "table": table})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{schema}/{table}/indexes")
def get_indexes(schema: str, table: str):
    sql = """
    SELECT
        i.name AS index_name,
        i.type_desc,
        i.is_unique,
        i.is_primary_key,
        STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns,
        ps.row_count,
        CAST(ROUND(ps.used_page_count * 8 / 1024.0, 2) AS FLOAT) AS size_mb
    FROM sys.indexes i
    JOIN sys.tables t ON i.object_id = t.object_id
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    LEFT JOIN sys.dm_db_partition_stats ps ON ps.object_id = i.object_id AND ps.index_id = i.index_id
    WHERE s.name = :schema AND t.name = :table AND i.name IS NOT NULL
    GROUP BY i.name, i.type_desc, i.is_unique, i.is_primary_key, ps.row_count, ps.used_page_count
    """
    try:
        return _run(sql, {"schema": schema, "table": table})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/foreign-keys")
def get_foreign_keys():
    sql = """
    SELECT
        fk.name AS constraint_name,
        sch1.name AS parent_schema, tp.name AS parent_table, cp.name AS parent_column,
        sch2.name AS ref_schema, tr.name AS ref_table, cr.name AS ref_column
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
    JOIN sys.schemas sch1 ON tp.schema_id = sch1.schema_id
    JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
    JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
    JOIN sys.schemas sch2 ON tr.schema_id = sch2.schema_id
    JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
    ORDER BY parent_table
    """
    try:
        return _run(sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{schema}/{table}/constraints")
def get_constraints(schema: str, table: str):
    sql = """
    SELECT
        con.name AS constraint_name,
        con.type_desc,
        col.name AS column_name
    FROM sys.check_constraints con
    JOIN sys.columns col ON con.parent_object_id = col.object_id AND con.parent_column_id = col.column_id
    JOIN sys.tables t ON con.parent_object_id = t.object_id
    JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = :schema AND t.name = :table
    """
    try:
        return _run(sql, {"schema": schema, "table": table})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{schema}/{table}/sample")
def get_sample_data(schema: str, table: str, limit: int = 20):
    limit = min(max(limit, 1), 200)
    try:
        return _run(f"SELECT TOP {limit} * FROM [{schema}].[{table}]")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{schema}/{table}/row-count")
def get_row_count(schema: str, table: str):
    try:
        rows = _run(
            "SELECT SUM(p.rows) AS row_count FROM sys.partitions p "
            "JOIN sys.tables t ON p.object_id = t.object_id "
            "JOIN sys.schemas s ON t.schema_id = s.schema_id "
            "WHERE s.name = :schema AND t.name = :table AND p.index_id IN (0,1)",
            {"schema": schema, "table": table},
        )
        return rows[0] if rows else {"row_count": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
