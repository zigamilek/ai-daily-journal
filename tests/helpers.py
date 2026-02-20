from __future__ import annotations

from ai_daily_journal.config.schema import AppConfig


def make_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "server": {"host": "127.0.0.1", "port": 8080, "public_base_url": "http://127.0.0.1:8080"},
            "api_ui": {
                "cors_origins": ["http://127.0.0.1:5173"],
                "session_cookie_name": "aijournal_session",
                "session_ttl_seconds": 86400,
            },
            "database": {
                "url_env": "AI_DAILY_JOURNAL_DB_URL",
                "pool_size": 5,
                "max_overflow": 5,
                "echo_sql": False,
            },
            "models": {
                "provider": "openai_compatible",
                "coordinator": {
                    "model_name": "coordinator-test",
                    "temperature": 0.0,
                    "max_retries": 2,
                    "base_url": "http://localhost",
                    "api_key_env": "AI_DAILY_JOURNAL_COORDINATOR_API_KEY",
                },
                "editor": {
                    "model_name": "editor-test",
                    "temperature": 0.0,
                    "max_retries": 2,
                    "base_url": "http://localhost",
                    "api_key_env": "AI_DAILY_JOURNAL_EDITOR_API_KEY",
                },
                "embeddings": {
                    "enabled": False,
                    "model_name": "embedding-test",
                    "dimensions": 64,
                    "base_url": "http://localhost",
                    "api_key_env": "AI_DAILY_JOURNAL_EMBEDDINGS_API_KEY",
                },
            },
            "decision": {"dedup_similarity_threshold": 0.88, "candidate_limit": 10},
            "logging": {
                "level": "INFO",
                "format": "json",
                "log_dir": "./logs",
                "log_file_name": "ai-daily-journal.log",
                "max_bytes": 5242880,
                "backup_count": 5,
            },
            "diagnostics": {"health_timeout_seconds": 2, "readiness_timeout_seconds": 5},
            "runtime": {"timezone": "Europe/Ljubljana"},
        }
    )
