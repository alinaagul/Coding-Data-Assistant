"""
schema_context.py
Builds grounding context for the AI model: SQL Server version/edition,
database name, and a structured schema summary (tables, columns, primary
keys, foreign keys, indexes).

Two outputs come from the same fetch:
  1. `SchemaMetadata` - structured data used by sql_templates.py to
     VALIDATE that a table/column the AI (or a template param) refers to
     actually exists, before it's ever interpolated into SQL.
  2. `render_prompt_context()` - a compact text block injected into the
     AI's system prompt, so it knows exactly which SQL Server version,
     edition, tables, columns, PKs, FKs and indexes it's working with.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import text

from .db_connection import connection_manager

logger = logging.getLogger("schema_context")


def _run(sql: str, params: dict | None = None) -> list[dict]:
    engine = connection_manager.get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = result.keys()
        return [dict(zip(cols, row)) for row in result.fetchall()]


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False


@dataclass
class TableInfo:
    schema_name: str
    table_name: str
    columns: list[ColumnInfo] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"[{self.schema_name}].[{self.table_name}]"

    @property
    def column_names(self) -> set[str]:
        return {c.name for c in self.columns}

    @property
    def primary_key_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.is_primary_key]


@dataclass
class ForeignKeyInfo:
    constraint_name: str
    parent_table: str
    parent_column: str
    ref_table: str
    ref_column: str


@dataclass
class IndexInfo:
    table: str
    index_name: str
    type_desc: str
    is_unique: bool
    columns: str


@dataclass
class SchemaMetadata:
    server_version: str = ""
    edition: str = ""
    database_name: str = ""
    tables: dict[str, TableInfo] = field(default_factory=dict)  # key: "schema.table" lowercase
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)

    def get_table(self, schema: str, table: str) -> "TableInfo | None":
        return self.tables.get(f"{schema}.{table}".lower())

    def find_table_by_name(self, table: str) -> "TableInfo | None":
        """Best-effort lookup when only a bare table name is given (no schema)."""
        matches = [t for t in self.tables.values() if t.table_name.lower() == table.lower()]
        return matches[0] if len(matches) == 1 else None


def get_server_info() -> dict:
    rows = _run(
        """
        SELECT
            CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128)) AS product_version,
            CAST(SERVERPROPERTY('ProductLevel') AS NVARCHAR(128)) AS product_level,
            CAST(SERVERPROPERTY('Edition') AS NVARCHAR(128)) AS edition,
            DB_NAME() AS database_name
        """
    )
    return rows[0] if rows else {}


def load_schema_metadata(max_tables: int = 60, max_cols_per_table: int = 40) -> SchemaMetadata:
    """
    Single source of truth for "what does this database actually look
    like". Fetch once per chat turn and reuse for both prompt grounding
    and identifier validation.
    """
    meta = SchemaMetadata()

    try:
        info = get_server_info()
        meta.server_version = info.get("product_version", "unknown")
        meta.edition = info.get("edition", "unknown")
        meta.database_name = info.get("database_name", "unknown")
    except Exception:
        logger.exception("Failed to read server info")

    try:
        table_rows = _run(
            f"""
            SELECT TOP {max_tables} s.name AS schema_name, t.name AS table_name
            FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE t.is_ms_shipped = 0
            ORDER BY s.name, t.name
            """
        )
    except Exception:
        logger.exception("Failed to list tables")
        table_rows = []

    for t in table_rows:
        schema_name, table_name = t["schema_name"], t["table_name"]
        try:
            col_rows = _run(
                f"""
                SELECT TOP {max_cols_per_table}
                    c.name AS column_name, ty.name AS data_type, c.is_nullable,
                    CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
                FROM sys.columns c
                JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                JOIN sys.tables tb ON c.object_id = tb.object_id
                JOIN sys.schemas s ON tb.schema_id = s.schema_id
                LEFT JOIN (
                    SELECT ic.object_id, ic.column_id
                    FROM sys.index_columns ic
                    JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                    WHERE i.is_primary_key = 1
                ) pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id
                WHERE s.name = :schema AND tb.name = :table
                ORDER BY c.column_id
                """,
                {"schema": schema_name, "table": table_name},
            )
        except Exception:
            logger.exception("Failed to read columns for %s.%s", schema_name, table_name)
            col_rows = []

        table_info = TableInfo(schema_name=schema_name, table_name=table_name)
        for c in col_rows:
            table_info.columns.append(
                ColumnInfo(
                    name=c["column_name"],
                    data_type=c["data_type"],
                    is_nullable=bool(c["is_nullable"]),
                    is_primary_key=bool(c["is_primary_key"]),
                )
            )
        meta.tables[f"{schema_name}.{table_name}".lower()] = table_info

    try:
        fk_rows = _run(
            """
            SELECT fk.name AS constraint_name,
                   tp.name AS parent_table, cp.name AS parent_column,
                   tr.name AS ref_table, cr.name AS ref_column
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
            JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
            JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
            JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
            """
        )
        meta.foreign_keys = [ForeignKeyInfo(**row) for row in fk_rows]
    except Exception:
        logger.exception("Failed to read foreign keys")

    try:
        idx_rows = _run(
            """
            SELECT t.name AS tbl, i.name AS index_name, i.type_desc, i.is_unique,
                   STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS cols
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE i.name IS NOT NULL AND t.is_ms_shipped = 0
            GROUP BY t.name, i.name, i.type_desc, i.is_unique
            """
        )
        meta.indexes = [
            IndexInfo(
                table=row["tbl"],
                index_name=row["index_name"],
                type_desc=row["type_desc"],
                is_unique=bool(row["is_unique"]),
                columns=row["cols"] or "",
            )
            for row in idx_rows
        ]
    except Exception:
        logger.exception("Failed to read indexes")

    return meta


def render_prompt_context(meta: SchemaMetadata) -> str:
    """Turns SchemaMetadata into the compact text block injected into the AI prompt."""
    lines = [
        f"SQL SERVER VERSION: {meta.server_version}",
        f"EDITION: {meta.edition}",
        f"DATABASE: {meta.database_name}",
        "",
        "TABLES:",
    ]
    for t in meta.tables.values():
        col_desc = ", ".join(
            f"{c.name} {c.data_type}{' [PK]' if c.is_primary_key else ''}" for c in t.columns
        )
        lines.append(f"{t.full_name}({col_desc})")

    if meta.foreign_keys:
        lines.append("\nFOREIGN KEYS:")
        for fk in meta.foreign_keys:
            lines.append(f"{fk.parent_table}.{fk.parent_column} -> {fk.ref_table}.{fk.ref_column}")

    if meta.indexes:
        lines.append("\nINDEXES:")
        for idx in meta.indexes:
            uniq = "UNIQUE " if idx.is_unique else ""
            lines.append(f"{idx.table}.{idx.index_name} ({uniq}{idx.type_desc}): {idx.columns}")

    return "\n".join(lines)


# Kept for backwards compatibility with any existing callers.
def build_schema_summary(max_tables: int = 40, max_cols_per_table: int = 25) -> str:
    meta = load_schema_metadata(max_tables=max_tables, max_cols_per_table=max_cols_per_table)
    return render_prompt_context(meta)