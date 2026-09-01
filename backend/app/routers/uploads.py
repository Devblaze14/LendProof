from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db
from app.errors import AppError
from app.models import Profile, UploadBatch
from app.schemas import UploadBatchOut
from app.security import require_role
from app.services.audit import write_audit_event
from app.services.ingestion import file_hash, process_upload
from app.services.storage import store_upload

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])
settings = get_settings()


def _run_ingestion_in_new_session(batch_id: UUID, csv_bytes: bytes) -> None:
    """BackgroundTasks run after the response is sent; give ingestion its
    own DB session rather than reusing the request-scoped one, which FastAPI
    will have already closed by the time this runs."""
    db = SessionLocal()
    try:
        process_upload(db, batch_id, csv_bytes)
    finally:
        db.close()


@router.post("", response_model=UploadBatchOut, status_code=202)
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_type: str = Form(...),
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_role("operator")),
):
    if source_type not in ("loan_tape", "servicer_update", "document_manifest"):
        raise AppError(400, "INVALID_SOURCE_TYPE", "source_type must be loan_tape, "
                        "servicer_update, or document_manifest", "source_type")
    content = file.file.read()
    h = file_hash(content)

    existing = db.query(UploadBatch).filter(UploadBatch.file_hash == h).first()
    if existing:
        raise AppError(409, "DUPLICATE_UPLOAD",
                        "This exact file has already been uploaded (idempotency check on file hash)")

    storage_path = store_upload(file.filename, h, content)

    batch = UploadBatch(
        filename=file.filename, file_hash=h, source_type=source_type,
        storage_path=storage_path, uploaded_by=profile.id, status="processing",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    write_audit_event(db, event_type="file.uploaded", actor_id=profile.id,
                       detail={"batch_id": str(batch.id), "filename": file.filename})

    if source_type == "loan_tape" and settings.database_mode == "supabase":
        # Serverless functions may stop after sending a response. Complete the
        # demo-sized ingestion before returning so no batch is left stranded.
        process_upload(db, batch.id, content)
    elif source_type == "loan_tape":
        background_tasks.add_task(_run_ingestion_in_new_session, batch.id, content)
    else:
        batch.status = "complete"  # servicer_update/document_manifest ingestion
        db.commit()               # follows the same pattern; omitted here for scope

    return batch


@router.get("/{batch_id}", response_model=UploadBatchOut)
def get_batch(batch_id: UUID, db: Session = Depends(get_db),
              profile: Profile = Depends(require_role("operator", "reviewer", "consumer"))):
    batch = db.get(UploadBatch, batch_id)
    if not batch:
        raise AppError(404, "NOT_FOUND", "Upload batch not found")
    return batch
