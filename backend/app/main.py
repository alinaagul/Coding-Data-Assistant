import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import connection, schema, query, ai, reports

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")

app = FastAPI(
    title=settings.app_name,
    description="Read-only AI-assisted analysis for Microsoft SQL Server, powered by qwen3:8b via Ollama.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connection.router)
app.include_router(schema.router)
app.include_router(query.router)
app.include_router(ai.router)
app.include_router(reports.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.on_event("startup")
def on_startup():
    logger.info("%s starting up (model=%s)", settings.app_name, settings.ollama_model)
