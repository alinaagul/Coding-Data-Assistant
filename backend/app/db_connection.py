"""
db_connection.py

Single source of truth for:
  1. SQL Server connection management (test / save / connect / disconnect)
  2. AI model selection (always qwen3:8b via Ollama - no other model is
     wired up anywhere in this app)

Every router imports `connection_manager` and `model_provider` from this
file instead of building its own engine or Ollama client. That keeps
"how we reach the database" and "which model we talk to" defined in
exactly one place, per the project requirements.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional

import pyodbc
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

import ollama

from .config import get_settings

logger = logging.getLogger("db_connection")

settings = get_settings()


# ============================================================================
# 1. SQL Server connection management
# ============================================================================

@dataclass
class SqlServerConnectionInfo:
    server: str
    port: int
    database: str
    username: str
    password: str
    driver: str = settings.mssql_driver
    encrypt: bool = settings.mssql_encrypt
    trust_server_certificate: bool = settings.mssql_trust_server_certificate

    def odbc_connection_string(self) -> str:
        encrypt = "yes" if self.encrypt else "no"
        trust = "yes" if self.trust_server_certificate else "no"
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust};"
        )

    def sqlalchemy_url(self) -> str:
        # SQLAlchemy + pyodbc, credentials URL-encoded defensively.
        from urllib.parse import quote_plus

        odbc_str = quote_plus(self.odbc_connection_string())
        return f"mssql+pyodbc:///?odbc_connect={odbc_str}"

    def safe_dict(self) -> dict:
        """Connection info without the password, safe to send to the UI."""
        d = asdict(self)
        d["password"] = "•" * 8 if self.password else ""
        return d


class ConnectionManager:
    """
    Owns the SQLAlchemy engine for the single SQL Server connection
    configured via environment variables (see config.py / backend/.env).
    There is no UI or API to change this at runtime - edit .env and
    restart the backend.
    """

    def __init__(self) -> None:
        self._info = SqlServerConnectionInfo(
            server=settings.mssql_server,
            port=settings.mssql_port,
            database=settings.mssql_database,
            username=settings.mssql_username,
            password=settings.mssql_password,
        )
        self._engine: Optional[Engine] = None

    def test_connection(self) -> dict:
        """Attempt a real connection + trivial query against the configured server."""
        start = time.time()
        try:
            conn = pyodbc.connect(self._info.odbc_connection_string(), timeout=8)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version_row = cursor.fetchone()
            cursor.execute(
                "SELECT IS_MEMBER('db_owner') AS is_owner, "
                "HAS_PERMS_BY_NAME(NULL, NULL, 'INSERT') AS can_insert"
            )
            perm_row = cursor.fetchone()
            conn.close()
            elapsed = round(time.time() - start, 3)
            warnings = []
            if perm_row and perm_row.can_insert:
                warnings.append(
                    "This login can INSERT rows. Use a read-only login for production."
                )
            return {
                "success": True,
                "elapsed_s": elapsed,
                "server_version": str(version_row[0]).splitlines()[0] if version_row else None,
                "warnings": warnings,
            }
        except pyodbc.Error as e:
            return {"success": False, "elapsed_s": round(time.time() - start, 3), "error": str(e)}

    @property
    def is_connected(self) -> bool:
        if not self._info.server:
            return False
        return self.test_connection().get("success", False)

    @property
    def info(self) -> Optional[SqlServerConnectionInfo]:
        return self._info if self._info.server else None

    def get_engine(self) -> Engine:
        if not self._info.server:
            raise RuntimeError(
                "No database configured. Set MSSQL_* variables in backend/.env and restart the backend."
            )
        if self._engine is None:
            self._engine = create_engine(
                self._info.sqlalchemy_url(), poolclass=NullPool, pool_pre_ping=True
            )
        return self._engine

    def raw_connection(self):
        """A plain pyodbc connection, used where SQLAlchemy adds no value."""
        if not self._info.server:
            raise RuntimeError(
                "No database configured. Set MSSQL_* variables in backend/.env and restart the backend."
            )
        return pyodbc.connect(self._info.odbc_connection_string(), timeout=15)


# Module-level singleton used by every router.
connection_manager = ConnectionManager()


# ============================================================================
# 2. AI model selection - qwen3:8b via Ollama, and nothing else
# ============================================================================

class ModelProvider:
    """
    Deliberately narrow: this app supports exactly one local model. There is
    no model-switching UI and no code path that accepts an arbitrary model
    name from the client - MODEL_NAME is the only value ever sent to Ollama.
    """

    MODEL_NAME = settings.ollama_model  # "qwen3:8b"

    def __init__(self, host: str = settings.ollama_host) -> None:
        self._client = ollama.Client(host=host)

    def is_server_running(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def is_model_pulled(self) -> bool:
        try:
            models = self._client.list().get("models", [])
            names = [m.get("model", m.get("name", "")) for m in models]
            return any(n.startswith(self.MODEL_NAME.split(":")[0]) for n in names)
        except Exception:
            return False

    def status(self) -> dict:
        running = self.is_server_running()
        return {
            "model": self.MODEL_NAME,
            "ollama_running": running,
            "model_pulled": self.is_model_pulled() if running else False,
        }

    def chat(self, messages, think: bool = True, temperature: float = None, tools=None):
        kwargs = dict(
            model=self.MODEL_NAME,
            messages=messages,
            options={"temperature": temperature if temperature is not None else settings.ollama_temperature},
        )
        if tools:
            kwargs["tools"] = tools
        try:
            kwargs["think"] = think
            return self._client.chat(**kwargs)
        except TypeError:
            kwargs.pop("think", None)
            if messages and messages[-1]["role"] == "user":
                prefix = "/think " if think else "/no_think "
                messages[-1]["content"] = prefix + messages[-1]["content"]
            return self._client.chat(**kwargs)


# Module-level singleton used by every router. Always qwen3:8b.
model_provider = ModelProvider()
