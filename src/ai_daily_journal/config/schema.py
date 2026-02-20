from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerConfig(StrictModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    public_base_url: str


class ApiUIConfig(StrictModel):
    cors_origins: list[str] = Field(default_factory=list)
    session_cookie_name: str = "aijournal_session"
    session_ttl_seconds: int = Field(default=86400, ge=60)


class DatabaseConfig(StrictModel):
    url_env: str = "AI_DAILY_JOURNAL_DB_URL"
    pool_size: int = Field(default=10, ge=1)
    max_overflow: int = Field(default=20, ge=0)
    echo_sql: bool = False


class ProjectionConfig(StrictModel):
    root_path: str = "./projections"
    atomic_write_mode: bool = True


class SingleModelRoleConfig(StrictModel):
    model_name: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_retries: int = Field(default=2, ge=0, le=5)
    base_url: str
    api_key_env: str


class EmbeddingsConfig(StrictModel):
    enabled: bool = True
    model_name: str
    dimensions: int = Field(default=1536, ge=64)
    base_url: str
    api_key_env: str


class ModelsConfig(StrictModel):
    provider: str = "openai_compatible"
    coordinator: SingleModelRoleConfig
    editor: SingleModelRoleConfig
    embeddings: EmbeddingsConfig


class DecisionConfig(StrictModel):
    dedup_similarity_threshold: float = Field(default=0.88, ge=0.0, le=1.0)
    candidate_limit: int = Field(default=10, ge=1, le=100)


class LoggingConfig(StrictModel):
    level: str = "INFO"
    format: str = "json"
    log_dir: str = "./logs"
    log_file_name: str = "ai-daily-journal.log"
    max_bytes: int = Field(default=5_242_880, ge=10_000)
    backup_count: int = Field(default=5, ge=1)


class DiagnosticsConfig(StrictModel):
    health_timeout_seconds: int = Field(default=2, ge=1)
    readiness_timeout_seconds: int = Field(default=5, ge=1)


class RuntimeConfig(StrictModel):
    timezone: str = "Europe/Ljubljana"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value


class AppConfig(StrictModel):
    server: ServerConfig
    api_ui: ApiUIConfig
    database: DatabaseConfig
    ai_daily_journal_projection: ProjectionConfig
    models: ModelsConfig
    decision: DecisionConfig
    logging: LoggingConfig
    diagnostics: DiagnosticsConfig
    runtime: RuntimeConfig
