from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
engine_options = {"pool_pre_ping": True, "future": True}
if settings.database_mode == "supabase":
    engine_options.update({"pool_size": 1, "max_overflow": 0, "pool_recycle": 300})
engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
