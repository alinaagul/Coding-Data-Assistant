"""
config.py
Central application settings, loaded from environment variables / .env file.

Nothing in this file talks to SQL Server or Ollama directly - it only
describes *what* to connect to. The actual connection objects live in
`db_connection.py`, which imports this module.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App -----------------------------------------------------------
    app_name: str = "AI Database Analyst"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ---- AI model selection --------------------------------------------
    # Only one model is supported by design: qwen3:8b via a local Ollama
    # server. This is intentionally NOT a list/dropdown of models.
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_temperature: float = 0.2
    ollama_request_timeout_s: int = 120

    # ---- SQL Server connection ------------------------------------------
    # The only source of DB connection info - set these in backend/.env and
    # restart the backend. There is no UI or API to change them at runtime.
    # Credentials should belong to a READ-ONLY SQL Server login - the backend
    # does not enforce that at the DB-permission level, only at the
    # SQL-statement level (see sql_validator.py); a true read-only login is
    # a required deployment step (see README).
    mssql_server: str = ""
    mssql_port: int = 1433
    mssql_database: str = ""
    mssql_username: str = ""
    mssql_password: str = ""
    mssql_driver: str = "ODBC Driver 18 for SQL Server"
    mssql_encrypt: bool = True
    mssql_trust_server_certificate: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> "Settings":
    return Settings()
