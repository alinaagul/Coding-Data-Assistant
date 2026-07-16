"""
sql_templates.py
Trusted, backend-owned SQL for common DBA/analysis tasks (largest tables,
missing indexes, database size, index usage, fragmentation, row counts,
foreign keys, duplicate records, orphan records, data quality reports).

The AI never writes raw SQL for these - it only picks a template id (and,
for the parameterized ones, a table/columns/constraint name that must
already exist in the real schema). This removes an entire class of
hallucinated-DMV-column bugs, because every static template here is
hand-verified against SQL Server's actual DMVs, and every parameterized
template validates identifiers against `SchemaMetadata` before building
any SQL string.
"""

import re
from dataclasses import dataclass

from .schema_context import SchemaMetadata

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TemplateError(Exception):
    """Raised when a template id/params can't be resolved into safe SQL."""


def _quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise TemplateError(f"'{name}' is not a valid SQL Server identifier.")
    return f"[{name}]"


@dataclass
class TemplateSpec:
    id: str
    name: str
    description: str
    requires_params: list[str]


# ---------------------------------------------------------------------------
# Static templates: fixed SQL, no AI-supplied identifiers, safe to run as-is.
# Verified against SQL Server 2016+ DMVs.
# ---------------------------------------------------------------------------
STATIC_TEMPLATES: dict[str, dict] = {
    "largest_tables": {
        "name": "Largest tables",
        "description": "Top tables by used space (MB), largest first.",
        "sql": """
            SELECT TOP 50
                s.name AS schema_name,
                t.name AS table_name,
                SUM(a.used_pages) * 8.0 / 1024 AS used_size_mb,
                SUM(a.total_pages) * 8.0 / 1024 AS allocated_size_mb,
                SUM(p.rows) AS row_count_estimate
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.indexes i ON t.object_id = i.object_id AND i.index_id IN (0, 1)
            JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
            JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE t.is_ms_shipped = 0
            GROUP BY s.name, t.name
            ORDER BY used_size_mb DESC
        """,
    },
    "database_size": {
        "name": "Database size",
        "description": "Total database size, data file(s) and log file(s), in MB.",
        "sql": """
            SELECT
                DB_NAME() AS database_name,
                type_desc,
                name AS logical_name,
                CAST(size * 8.0 / 1024 AS DECIMAL(12,2)) AS size_mb
            FROM sys.database_files
            ORDER BY type_desc
        """,
    },
    "missing_indexes": {
        "name": "Missing indexes",
        "description": "SQL Server's missing-index DMV recommendations, ranked by estimated impact.",
        "sql": """
            SELECT TOP 50
                d.statement AS table_name,
                d.equality_columns,
                d.inequality_columns,
                d.included_columns,
                gs.user_seeks,
                gs.avg_total_user_cost,
                gs.avg_user_impact,
                (gs.avg_total_user_cost * gs.avg_user_impact * (gs.user_seeks + gs.user_scans)) AS impact_score
            FROM sys.dm_db_missing_index_details d
            JOIN sys.dm_db_missing_index_groups g ON d.index_handle = g.index_handle
            JOIN sys.dm_db_missing_index_group_stats gs ON g.index_group_handle = gs.group_handle
            WHERE d.database_id = DB_ID()
            ORDER BY impact_score DESC
        """,
    },
    "index_usage_stats": {
        "name": "Index usage",
        "description": "Seeks/scans/lookups/updates per index, to spot unused or over-written indexes.",
        "sql": """
            SELECT
                s.name AS schema_name,
                t.name AS table_name,
                i.name AS index_name,
                us.user_seeks,
                us.user_scans,
                us.user_lookups,
                us.user_updates,
                us.last_user_seek,
                us.last_user_scan
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.dm_db_index_usage_stats us
                ON us.object_id = i.object_id AND us.index_id = i.index_id AND us.database_id = DB_ID()
            WHERE t.is_ms_shipped = 0 AND i.name IS NOT NULL
            ORDER BY ISNULL(us.user_seeks, 0) + ISNULL(us.user_scans, 0) ASC
        """,
    },
    "index_fragmentation": {
        "name": "Index fragmentation",
        "description": "Average fragmentation percent per index (LIMITED scan mode for speed).",
        "sql": """
            SELECT
                s.name AS schema_name,
                t.name AS table_name,
                i.name AS index_name,
                ips.avg_fragmentation_in_percent,
                ips.page_count
            FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') ips
            JOIN sys.indexes i ON ips.object_id = i.object_id AND ips.index_id = i.index_id
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE ips.page_count > 100
            ORDER BY ips.avg_fragmentation_in_percent DESC
        """,
    },
    "row_counts": {
        "name": "Row counts per table",
        "description": "Estimated row count for every table.",
        "sql": """
            SELECT
                s.name AS schema_name,
                t.name AS table_name,
                SUM(p.rows) AS row_count_estimate
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.partitions p ON t.object_id = p.object_id
            WHERE p.index_id IN (0, 1) AND t.is_ms_shipped = 0
            GROUP BY s.name, t.name
            ORDER BY row_count_estimate DESC
        """,
    },
    "foreign_keys": {
        "name": "Foreign keys",
        "description": "All foreign key relationships in the database.",
        "sql": """
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
        """,
    },
}


# ---------------------------------------------------------------------------
# Parameterized templates: SQL is built dynamically, but every identifier is
# checked against real SchemaMetadata before it is ever interpolated into a
# query string. This stands in for parameter binding when the "parameter"
# is itself a table/column/constraint name.
# ---------------------------------------------------------------------------
PARAMETERIZED_TEMPLATE_SPECS: list[TemplateSpec] = [
    TemplateSpec(
        id="duplicate_records",
        name="Duplicate records",
        description="Find rows in a table that duplicate on a given set of columns.",
        requires_params=["schema", "table", "columns"],
    ),
    TemplateSpec(
        id="orphan_records",
        name="Orphan records",
        description="Find child rows whose foreign key doesn't match any parent row.",
        requires_params=["foreign_key_constraint_name"],
    ),
    TemplateSpec(
        id="data_quality_report",
        name="Data quality report",
        description="NULL counts for every column of a table.",
        requires_params=["schema", "table"],
    ),
]


def _get_table(meta: SchemaMetadata, schema: str, table: str):
    t = meta.get_table(schema, table)
    if t is None:
        raise TemplateError(f"Table [{schema}].[{table}] was not found in the connected database.")
    return t


def render_duplicate_records(meta: SchemaMetadata, schema: str, table: str, columns: list[str]) -> str:
    t = _get_table(meta, schema, table)
    if not columns:
        raise TemplateError("At least one column is required to check duplicates.")
    for c in columns:
        if c not in t.column_names:
            raise TemplateError(f"Column '{c}' does not exist on {t.full_name}.")
    col_list = ", ".join(_quote_ident(c) for c in columns)
    return f"""
        SELECT TOP 200 {col_list}, COUNT(*) AS duplicate_count
        FROM {t.full_name}
        GROUP BY {col_list}
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC
    """


def render_orphan_records(meta: SchemaMetadata, foreign_key_constraint_name: str) -> str:
    fk = next((f for f in meta.foreign_keys if f.constraint_name == foreign_key_constraint_name), None)
    if fk is None:
        available = ", ".join(f.constraint_name for f in meta.foreign_keys) or "(none)"
        raise TemplateError(f"Unknown foreign key '{foreign_key_constraint_name}'. Available: {available}")
    parent_col = _quote_ident(fk.parent_column)
    parent_tbl = _quote_ident(fk.parent_table)
    ref_col = _quote_ident(fk.ref_column)
    ref_tbl = _quote_ident(fk.ref_table)
    return f"""
        SELECT TOP 200 c.*
        FROM {parent_tbl} c
        LEFT JOIN {ref_tbl} p ON c.{parent_col} = p.{ref_col}
        WHERE c.{parent_col} IS NOT NULL AND p.{ref_col} IS NULL
    """


def render_data_quality(meta: SchemaMetadata, schema: str, table: str) -> str:
    t = _get_table(meta, schema, table)
    if not t.columns:
        raise TemplateError(f"No columns found for {t.full_name}.")
    parts = []
    for c in t.columns:
        col = _quote_ident(c.name)
        parts.append(f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS [{c.name}_nulls]")
    select_list = ",\n            ".join(parts)
    return f"""
        SELECT
            COUNT(*) AS total_rows,
            {select_list}
        FROM {t.full_name}
    """


def get_template_catalog() -> list[TemplateSpec]:
    catalog = [
        TemplateSpec(id=tid, name=tpl["name"], description=tpl["description"], requires_params=[])
        for tid, tpl in STATIC_TEMPLATES.items()
    ]
    catalog += PARAMETERIZED_TEMPLATE_SPECS
    return catalog


def render_prompt_catalog(meta: SchemaMetadata) -> str:
    """Text block describing available templates, injected into the AI prompt."""
    lines = ["AVAILABLE SQL TEMPLATES (prefer these over writing raw SQL):"]
    for tpl in get_template_catalog():
        params = f" [params: {', '.join(tpl.requires_params)}]" if tpl.requires_params else ""
        lines.append(f"- {tpl.id}: {tpl.description}{params}")
    if meta.foreign_keys:
        lines.append("\nForeign key constraint names available for 'orphan_records':")
        lines.append(", ".join(f.constraint_name for f in meta.foreign_keys[:30]))
    return "\n".join(lines)


def resolve_template(template_id: str, params: dict, meta: SchemaMetadata) -> str:
    """Returns SQL for a template id + params, or raises TemplateError/KeyError."""
    if template_id in STATIC_TEMPLATES:
        return STATIC_TEMPLATES[template_id]["sql"]

    if template_id == "duplicate_records":
        return render_duplicate_records(meta, params.get("schema", "dbo"), params["table"], params["columns"])
    if template_id == "orphan_records":
        return render_orphan_records(meta, params["foreign_key_constraint_name"])
    if template_id == "data_quality_report":
        return render_data_quality(meta, params.get("schema", "dbo"), params["table"])

    raise TemplateError(f"Unknown template id: {template_id}")