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
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    storage_url = settings.supabase_url.rstrip("/")
    try:
        bucket_response = httpx.get(
            f"{storage_url}/storage/v1/bucket/{BUCKET}", headers=headers, timeout=20.0
        )
        if bucket_response.status_code == 404:
            bucket_response = httpx.post(
                f"{storage_url}/storage/v1/bucket",
                headers={**headers, "Content-Type": "application/json"},
                json={"id": BUCKET, "name": BUCKET, "public": False},
                timeout=20.0,
            )
    except httpx.HTTPError as exc:
        raise AppError(502, "SUPABASE_STORAGE_UNAVAILABLE", "Supabase Storage is unreachable") from exc
    if bucket_response.status_code not in (200, 201, 409):
        raise AppError(
            502, "SUPABASE_STORAGE_SETUP_FAILED",
            f"Could not access the Supabase Storage bucket ({bucket_response.status_code}). "
            "Check that the bucket exists and SUPABASE_SERVICE_ROLE_KEY is valid.",
        )

    object_path = f"{content_hash}_{filename}"
    try:
        response = httpx.post(
            f"{storage_url}/storage/v1/object/{BUCKET}/{object_path}",
            headers={**headers, "x-upsert": "false", "Content-Type": "text/csv"},
            content=content,
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        raise AppError(502, "SUPABASE_STORAGE_UNAVAILABLE", "Supabase Storage is unreachable") from exc
    if response.status_code >= 400:
        raise AppError(
            502, "SUPABASE_STORAGE_FAILED",
            f"Could not persist the uploaded source file ({response.status_code}). "
            "Check the Storage bucket and service-role key.",
        )
    return f"supabase://{BUCKET}/{object_path}"
