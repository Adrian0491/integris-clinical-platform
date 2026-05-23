"""
Application configuration via Pydantic Settings.

Values are loaded from environment variables and / or a .env file at the
project root.  The Settings object is a module-level singleton obtained via
get_settings().
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME:    str = "CDTool API"
    APP_VERSION: str = "0.1.0"
    DEBUG:       bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL:           str = "postgresql://cdtool:cdtool_dev@localhost:5432/cdtool"
    TEST_DATABASE_URL:      str = "postgresql://cdtool:cdtool_dev@localhost:5432/cdtool_test"
    DATABASE_POOL_SIZE:     int = 10
    DATABASE_MAX_OVERFLOW:  int = 20

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Elasticsearch ─────────────────────────────────────────────────────
    ELASTICSEARCH_URL:            str = "http://localhost:9200"
    ELASTICSEARCH_INDEX_FINDINGS: str = "cdtool_findings"

    # ── JWT RS256 ─────────────────────────────────────────────────────────
    # PEM keys stored in .env with literal \n for newlines.
    # If empty in development, keys are auto-generated at startup.
    JWT_ALGORITHM:                    str = "RS256"
    JWT_PRIVATE_KEY:                  str = ""
    JWT_PUBLIC_KEY:                   str = ""
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES:  int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS:    int = 7

    # ── Security ──────────────────────────────────────────────────────────
    # Used for HMAC-based electronic signatures (21 CFR Part 11).
    SECRET_KEY: str = "change-me-in-production-minimum-256-bits"

    # ── Storage ───────────────────────────────────────────────────────────
    STORAGE_BACKEND:    str = "local"   # local | gcs
    STORAGE_LOCAL_PATH: str = "./storage"
    GCS_BUCKET_NAME:    str = ""
    GCS_PROJECT_ID:     str = ""

    # ── CORS ──────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:4200", "http://localhost:3000"]

    # ── Feature flags ─────────────────────────────────────────────────────
    ENABLE_ES_INDEXING: bool = True   # set False to skip ES writes in tests

    def get_private_key(self) -> str:
        """Return the RSA private key PEM, expanding \\n literals."""
        return self.JWT_PRIVATE_KEY.replace("\\n", "\n")

    def get_public_key(self) -> str:
        """Return the RSA public key PEM, expanding \\n literals."""
        return self.JWT_PUBLIC_KEY.replace("\\n", "\n")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
