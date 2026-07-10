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

    # ---- Default / fallback SQL Server connection ----------------------
    # These act as defaults that pre-fill the "Settings" screen the first
    # time the app runs. The connection actually used at runtime is
    # whatever was last saved via POST /api/connection/save (see
    # db_connection.py: ConnectionManager). Credentials should belong to a
    # READ-ONLY SQL Server login - the backend does not enforce that at
    # the DB-permission level, only at the SQL-statement level (see
    # sql_validator.py); a true read-only login is a required deployment
    # step (see README).
    mssql_server: str = ""
    mssql_port: int = 1433
    mssql_database: str = ""
    mssql_username: str = ""
    mssql_password: str = ""
    mssql_driver: str = "ODBC Driver 18 for SQL Server"
    mssql_encrypt: bool = True
    mssql_trust_server_certificate: bool = True

    # Where saved connection profiles are persisted between restarts.
    # A local JSON file is enough for this app; swap for a secrets manager
    # in a real production deployment.
    connection_store_path: str = "connections.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> "Settings":
    return Settings()
