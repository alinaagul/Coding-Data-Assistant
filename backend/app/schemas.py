from typing import Any, Optional
from pydantic import BaseModel, Field


class QueryPayload(BaseModel):
    sql: str
    max_rows: int = Field(default=1000, le=10000)


class ChatPayload(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)
    think: bool = True


class ExplainQueryPayload(BaseModel):
    sql: str


class NLToSqlPayload(BaseModel):
    question: str


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# AI chat / retry-loop models
# ---------------------------------------------------------------------------

class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    requires_params: list[str] = Field(default_factory=list)


class QueryAttempt(BaseModel):
    attempt: int
    sql: str
    source: str  # "template" | "ai_sql" | "ai_corrected"
    success: bool
    error: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    used_template: Optional[str] = None
    final_sql: Optional[str] = None
    execution: Optional[dict] = None
    execution_error: Optional[str] = None
    attempts: list[QueryAttempt] = Field(default_factory=list)
    elapsed_s: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None