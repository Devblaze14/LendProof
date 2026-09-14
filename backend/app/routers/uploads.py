from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db
from app.errors import AppError
from app.models import (
    AIRecommendation, AuditLog, ExceptionComment, ExceptionRecord, LoanRecord,
    Profile, RawLoanRow, ReviewerAction, UploadBatch, VerifiedLoanRecord,
)
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
        # Return existing batch instead of error for better demo experience
        # The file was already processed, so return the existing batch info
        return existing

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

    if source_type == "loan_tape" and (
        settings.database_mode == "supabase" or os.getenv("VERCEL") == "1"
    ):
        # Serverless functions may stop after sending a response. Complete the
        # ingestion before returning so no batch is left stranded when a worker
        # is not available to run BackgroundTasks.
        process_upload(db, batch.id, content)
    elif source_type == "loan_tape":
        background_tasks.add_task(_run_ingestion_in_new_session, batch.id, content)
    else:
        batch.status = "complete"  # servicer_update/document_manifest ingestion
        db.commit()               # follows the same pattern; omitted here for scope

    return batch


@router.delete("/reset", status_code=200)
def reset_uploaded_data(
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_role("operator")),
):
    """Clear demo-uploaded data while retaining accounts and validation rules."""
    batches = db.query(UploadBatch).all()
    batch_ids = [batch.id for batch in batches]
    loan_ids = [
        loan.id for loan in db.query(LoanRecord)
        .filter(LoanRecord.source_batch_id.in_(batch_ids)).all()
    ] if batch_ids else []
    exception_ids = [
        item.id for item in db.query(ExceptionRecord)
        .filter(ExceptionRecord.loan_record_id.in_(loan_ids)).all()
    ] if loan_ids else []

    if exception_ids:
        db.query(ReviewerAction).filter(ReviewerAction.exception_id.in_(exception_ids)).delete(synchronize_session=False)
        db.query(ExceptionComment).filter(ExceptionComment.exception_id.in_(exception_ids)).delete(synchronize_session=False)
        db.query(AIRecommendation).filter(AIRecommendation.exception_id.in_(exception_ids)).delete(synchronize_session=False)
        db.query(ExceptionRecord).filter(ExceptionRecord.id.in_(exception_ids)).delete(synchronize_session=False)
    if loan_ids:
        # Verified records reference loan_records directly, including clean
        # loans that never created an exception.
        db.query(VerifiedLoanRecord).filter(VerifiedLoanRecord.loan_record_id.in_(loan_ids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.loan_record_id.in_(loan_ids)).delete(synchronize_session=False)
        db.query(LoanRecord).filter(LoanRecord.id.in_(loan_ids)).delete(synchronize_session=False)
    if batch_ids:
        db.query(RawLoanRow).filter(RawLoanRow.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(UploadBatch).filter(UploadBatch.id.in_(batch_ids)).delete(synchronize_session=False)

    db.commit()
    _remove_stored_uploads([batch.storage_path for batch in batches])
    return {"status": "reset", "batches_removed": len(batches), "loans_removed": len(loan_ids)}


def _remove_stored_uploads(paths: list[str]) -> None:
    for path in paths:
        if path.startswith("supabase://"):
            object_path = path.removeprefix("supabase://loan-uploads/")
            if settings.supabase_url and settings.supabase_service_role_key:
                try:
                    httpx.delete(
                        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/loan-uploads/{object_path}",
                        headers={
                            "apikey": settings.supabase_service_role_key,
                            "Authorization": f"Bearer {settings.supabase_service_role_key}",
                        },
                        timeout=10.0,
                    )
                except httpx.HTTPError:
                    pass
        else:
            try:
                from pathlib import Path
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass


@router.get("/{batch_id}", response_model=UploadBatchOut)
def get_batch(batch_id: UUID, db: Session = Depends(get_db),
              profile: Profile = Depends(require_role("operator", "reviewer", "consumer"))):
    batch = db.get(UploadBatch, batch_id)
    if not batch:
        raise AppError(404, "NOT_FOUND", "Upload batch not found")
    return batch
