"""
ai_query_service.py
Owns the "ask the AI, validate, execute, self-correct on error" loop for
AI-assisted SQL. Kept separate from the ai.py router so this logic can be
unit tested and reused without touching FastAPI request/response plumbing.

Flow per chat turn:
  1. Build full grounding context (server version/edition/DB name, schema,
     PKs, FKs, indexes, template catalog).
  2. Ask Qwen. It must respond with EITHER:
       ```template   {"id": "...", "params": {...}}
     OR (only for things no template covers):
       ```sql   SELECT ...
  3. Resolve that directive into SQL (template lookup + identifier
     validation, or sql_validator for raw SQL). This never executes yet.
  4. Execute inside try/except.
  5. On failure: send the failing SQL + the real DB error back to Qwen,
     ask for a corrected query, and repeat. Up to MAX_RETRIES attempts
     total.
  6. Return the final result plus a full attempt log for transparency.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field

from sqlalchemy import text

from .db_connection import connection_manager, model_provider
from .schema_context import SchemaMetadata, load_schema_metadata, render_prompt_context
from .sql_templates import TemplateError, render_prompt_catalog, resolve_template
from .sql_validator import validate_select_only, enforce_row_limit

logger = logging.getLogger("ai_query_service")

MAX_RETRIES = 3
MAX_RESULT_ROWS = 200

SQL_BLOCK_RE = re.compile(r"```sql\s*(.*?)```", re.DOTALL | re.IGNORECASE)
TEMPLATE_BLOCK_RE = re.compile(r"```template\s*(.*?)```", re.DOTALL | re.IGNORECASE)

SYSTEM_PROMPT_TEMPLATE = """You are a SQL Server database analyst assistant running on the qwen3:8b model.

STRICT RULES:
- You may ONLY ever produce SELECT statements. NEVER INSERT, UPDATE, DELETE, DROP,
  ALTER, CREATE, TRUNCATE, EXEC, or MERGE, under any circumstances.
- For any task covered by AVAILABLE SQL TEMPLATES below, you MUST use a template
  instead of writing raw SQL. Respond with a ```template fenced block containing
  JSON: {{"id": "<template_id>", "params": {{...}}}}.
- Only write raw SQL (in a ```sql fenced block) for questions NOT covered by any
  template. Base every table/column name ONLY on the schema context below - never
  invent objects, and never reference DMV columns that are not explicitly listed.
- Be concise; prefer bullet points and a single final query/template call over
  long prose.

{schema_context}

{template_catalog}
"""

CORRECTION_PROMPT_TEMPLATE = """Your previous SQL failed when executed against the real SQL Server instance.

FAILED SQL:
{sql}

DATABASE ERROR:
{error}

Fix the query. Respond with ONLY a corrected ```sql fenced code block (or a
```template block if a template now fits better), no other prose. Do not repeat
the same mistake - base every identifier strictly on the schema context you were
given.
"""


@dataclass
class QueryAttempt:
    attempt: int
    sql: str
    source: str  # "template" | "ai_sql" | "ai_corrected"
    success: bool
    error: str | None = None


@dataclass
class ChatResult:
    answer: str
    used_template: str | None
    final_sql: str | None
    execution: dict | None
    execution_error: str | None
    attempts: list[QueryAttempt] = field(default_factory=list)
    elapsed_s: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _extract_directive(raw: str) -> tuple[str | None, str | None]:
    """Returns (kind, payload) where kind is 'template' or 'sql'."""
    tmpl_match = TEMPLATE_BLOCK_RE.search(raw)
    if tmpl_match:
        return "template", tmpl_match.group(1).strip()
    sql_match = SQL_BLOCK_RE.search(raw)
    if sql_match:
        return "sql", sql_match.group(1).strip()
    return None, None


def _sql_from_directive(
    kind: str | None, payload: str, meta: SchemaMetadata
) -> tuple[str | None, str | None, str | None]:
    """
    Returns (sql, used_template_id, error). Never raises - a bad directive
    is a normal, expected retry case handled via the error string, not an
    exception.
    """
    if kind == "template":
        try:
            spec = json.loads(payload)
            template_id = spec["id"]
            params = spec.get("params", {})
        except Exception as e:
            return None, None, f"Could not parse template directive as JSON: {e}"
        try:
            sql = resolve_template(template_id, params, meta)
            return sql, template_id, None
        except TemplateError as e:
            return None, None, str(e)
        except KeyError as e:
            return None, None, f"Missing required template parameter: {e}"

    if kind == "sql":
        return payload, None, None

    return None, None, "Response did not contain a ```sql or ```template code block."


def _execute_sql(sql: str, max_rows: int = MAX_RESULT_ROWS) -> tuple[dict | None, str | None, str | None]:
    """
    Validates + executes a SELECT. Returns (execution_result, safe_sql, error).
    Always wrapped in try/except - a DB error here is fed back to the model,
    never surfaced to the user as a raw 500.
    """
    validation = validate_select_only(sql)
    if not validation.is_valid:
        return None, None, validation.reason

    safe_sql = enforce_row_limit(validation.cleaned_sql, max_rows=max_rows)
    try:
        engine = connection_manager.get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(safe_sql))
            cols = list(result.keys())
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
        return {"columns": cols, "rows": rows, "row_count": len(rows), "executed_sql": safe_sql}, safe_sql, None
    except Exception as e:
        logger.warning("SQL execution failed: %s | SQL: %s", e, safe_sql)
        return None, safe_sql, str(e)


def run_ai_chat(message: str, history: list[dict], think: bool = True) -> ChatResult:
    start = time.time()

    if not model_provider.is_server_running():
        raise RuntimeError("Ollama server is not reachable.")

    meta = SchemaMetadata()
    schema_ctx_text = "(not connected to a database)"
    template_catalog_text = ""
    if connection_manager.is_connected:
        try:
            meta = load_schema_metadata()
            schema_ctx_text = render_prompt_context(meta)
            template_catalog_text = render_prompt_catalog(meta)
        except Exception:
            logger.exception("Failed to load schema metadata")
            schema_ctx_text = "(schema metadata unavailable)"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        schema_context=schema_ctx_text, template_catalog=template_catalog_text
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": message})

    resp = model_provider.chat(messages, think=think, temperature=0.2)
    raw = resp["message"].get("content", "")
    prompt_tokens = resp.get("prompt_eval_count")
    completion_tokens = resp.get("eval_count")

    attempts: list[QueryAttempt] = []
    final_sql: str | None = None
    used_template: str | None = None
    execution: dict | None = None
    execution_error: str | None = None

    if connection_manager.is_connected:
        current_kind, current_payload = _extract_directive(raw)
        source = "template" if current_kind == "template" else "ai_sql"

        for attempt_num in range(1, MAX_RETRIES + 1):
            sql, template_id, directive_error = _sql_from_directive(current_kind, current_payload or "", meta)

            if directive_error:
                attempts.append(
                    QueryAttempt(attempt=attempt_num, sql=current_payload or "", source=source,
                                 success=False, error=directive_error)
                )
                execution_error = directive_error
                correction = CORRECTION_PROMPT_TEMPLATE.format(sql=current_payload or "(none)", error=directive_error)
            else:
                exec_result, safe_sql, exec_err = _execute_sql(sql)
                attempts.append(
                    QueryAttempt(attempt=attempt_num, sql=safe_sql or sql, source=source,
                                 success=exec_err is None, error=exec_err)
                )
                if exec_err is None:
                    execution = exec_result
                    execution_error = None
                    final_sql = safe_sql
                    used_template = template_id
                    break
                execution_error = exec_err
                final_sql = safe_sql or sql
                used_template = template_id
                correction = CORRECTION_PROMPT_TEMPLATE.format(sql=safe_sql or sql, error=exec_err)

            if attempt_num == MAX_RETRIES:
                break

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": correction})
            resp = model_provider.chat(messages, think=False, temperature=0.1)
            raw = resp["message"].get("content", "")
            prompt_tokens = resp.get("prompt_eval_count", prompt_tokens)
            completion_tokens = resp.get("eval_count", completion_tokens)
            current_kind, current_payload = _extract_directive(raw)
            source = "ai_corrected"

    elapsed = round(time.time() - start, 3)
    return ChatResult(
        answer=raw,
        used_template=used_template,
        final_sql=final_sql,
        execution=execution,
        execution_error=execution_error,
        attempts=attempts,
        elapsed_s=elapsed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )