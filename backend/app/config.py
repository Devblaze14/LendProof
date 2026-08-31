"""
Central configuration. Two supported modes, switched by DATABASE_MODE:

  local    -> connects to a plain Postgres instance via DATABASE_URL, uses
              app/auth_local.py for auth (own JWT issuance). This is what
              this repo ships tested and runnable against, with zero
              external accounts required.

  supabase -> connects to your Supabase Postgres via DATABASE_URL (the
              Supabase connection string), verifies tokens issued by
              Supabase Auth instead of minting its own, and expects
              SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_JWT_SECRET
              to be set. This is the production path — see
              docs/Antigravity_Build_Package.md Section 0.

Groq is controlled independently by GROQ_MOCK: true runs the AI layer
against local fixture responses (no network call, fully offline-testable);
false calls the real Groq API using GROQ_API_KEY.
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    database_mode: str = os.getenv("DATABASE_MODE", "local")
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://loanapp:loanapp@localhost:5432/loan_copilot"
    )

    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_service_role_key: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str | None = os.getenv("SUPABASE_ANON_KEY")
    supabase_jwt_secret: str | None = os.getenv("SUPABASE_JWT_SECRET")

    groq_mock: bool = os.getenv("GROQ_MOCK", "true").lower() == "true"
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model_primary: str = os.getenv("GROQ_MODEL_PRIMARY", "openai/gpt-oss-120b")
    groq_model_fast: str = os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")

    local_jwt_secret: str = os.getenv("LOCAL_JWT_SECRET", "dev-only-change-me")
    local_storage_dir: str = os.getenv("LOCAL_STORAGE_DIR", "./storage")

    ai_rate_limit_per_minute: int = int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "20"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
