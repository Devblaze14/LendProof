from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import csv
import io

from app.db import get_db
from app.errors import AppError
from app.hashing import verify_chain
from app.models import LoanRecord, Profile, VerifiedLoanRecord
from app.schemas import VerifiedLoanOut
from app.security import require_role

router = APIRouter(prefix="/api/v1/verified-loans", tags=["verified"])


@router.get("", response_model=list[VerifiedLoanOut])
def list_verified(limit: int = 50, offset: int = 0, db: Session = Depends(get_db),
                   profile: Profile = Depends(require_role("consumer", "reviewer", "operator"))):
    return (
        db.query(VerifiedLoanRecord)
        .order_by(VerifiedLoanRecord.verified_at.desc())
        .offset(offset).limit(limit).all()
    )


@router.get("/{verified_id}", response_model=VerifiedLoanOut)
def get_verified(verified_id: UUID, db: Session = Depends(get_db),
                  profile: Profile = Depends(require_role("consumer", "reviewer", "operator"))):
    v = db.get(VerifiedLoanRecord, verified_id)
    if not v:
        raise AppError(404, "NOT_FOUND", "Verified record not found")
    return v


@router.get("/{verified_id}/verify-integrity")
def verify_integrity(verified_id: UUID, db: Session = Depends(get_db),
                      profile: Profile = Depends(require_role("consumer", "reviewer", "operator"))):
    v = db.get(VerifiedLoanRecord, verified_id)
    if not v:
        raise AppError(404, "NOT_FOUND", "Verified record not found")
    chain = (
        db.query(VerifiedLoanRecord)
        .filter(VerifiedLoanRecord.loan_record_id == v.loan_record_id)
        .order_by(VerifiedLoanRecord.verified_at.asc())
        .all()
    )
    records = [{"canonical_data": c.canonical_data, "record_hash": c.record_hash,
                "prev_hash": c.prev_hash} for c in chain]
    valid, broken_at = verify_chain(records)
    return {"valid": valid, "broken_at_index": broken_at, "chain_length": len(records)}


export_router = APIRouter(prefix="/api/v1/export", tags=["export"])


@export_router.get("/verified-dataset")
def export_verified_dataset(db: Session = Depends(get_db),
                             profile: Profile = Depends(require_role("consumer"))):
    records = db.query(VerifiedLoanRecord).order_by(VerifiedLoanRecord.verified_at.asc()).all()
    if not records:
        raise AppError(404, "NO_DATA", "No verified records to export yet")
    buffer = io.StringIO()
    fieldnames = ["id", "loan_record_id", "record_hash", "prev_hash", "verified_at"] + list(
        records[0].canonical_data.keys()
    )
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for r in records:
        row = {"id": str(r.id), "loan_record_id": str(r.loan_record_id),
               "record_hash": r.record_hash, "prev_hash": r.prev_hash, "verified_at": str(r.verified_at)}
        row.update(r.canonical_data)
        writer.writerow(row)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=verified_loans_export.csv"},
    )
