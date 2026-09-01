"""Durable source-file storage for Supabase deployments."""
from __future__ import annotations

from pathlib import Path

import httpx

from app.config import get_settings
from app.errors import AppError

settings = get_settings()
BUCKET = "loan-uploads"


def store_upload(filename: str, content_hash: str, content: bytes) -> str:
    """Persist raw source material outside Vercel's ephemeral filesystem."""
    if settings.database_mode != "supabase":
        storage_dir = Path(settings.local_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        path = storage_dir / f"{content_hash}_{filename}"
        path.write_bytes(content)
        return str(path)

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise AppError(500, "SUPABASE_STORAGE_CONFIG_MISSING", "Supabase Storage requires URL and service-role key")
    object_path = f"{content_hash}_{filename}"
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{BUCKET}/{object_path}",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "x-upsert": "false",
            "Content-Type": "text/csv",
        },
        content=content,
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise AppError(502, "SUPABASE_STORAGE_FAILED", "Could not persist the uploaded source file")
    return f"supabase://{BUCKET}/{object_path}"
