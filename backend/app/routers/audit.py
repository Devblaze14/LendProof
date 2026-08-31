from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, ExceptionRecord, LoanRecord, Profile, VerifiedLoanRecord
from app.schemas import AuditEventOut, SummaryOut
from app.security import require_role

audit_router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
summary_router = APIRouter(prefix="/api/v1", tags=["summary"])


@audit_router.get("/{loan_record_id}", response_model=list[AuditEventOut])
def get_audit_trail(loan_record_id: UUID, db: Session = Depends(get_db),
                     profile: Profile = Depends(require_role("operator", "reviewer", "consumer"))):
    return (
        db.query(AuditLog)
        .filter(AuditLog.loan_record_id == loan_record_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )


@summary_router.get("/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db),
                 profile: Profile = Depends(require_role("operator", "reviewer", "consumer"))):
    total_loans = db.query(LoanRecord).count()
    open_exceptions = db.query(ExceptionRecord).filter(ExceptionRecord.status == "open").count()
    resolved_exceptions = db.query(ExceptionRecord).filter(ExceptionRecord.status == "resolved").count()
    verified_records = db.query(VerifiedLoanRecord).count()

    # Data-quality score formula (documented per FR-DASH-3): the share of
    # loans with zero open exceptions. Simple, defensible, and easy to
    # explain in the demo — revisit if the team wants a severity-weighted
    # version instead (# DECISION: kept unweighted for hackathon scope).
    loans_with_open_exceptions = (
        db.query(ExceptionRecord.loan_record_id)
        .filter(ExceptionRecord.status == "open")
        .distinct()
        .count()
    )
    score = 100.0 if total_loans == 0 else round(
        100.0 * (total_loans - loans_with_open_exceptions) / total_loans, 1
    )

    return SummaryOut(
        total_loans=total_loans, open_exceptions=open_exceptions,
        resolved_exceptions=resolved_exceptions, verified_records=verified_records,
        data_quality_score=score,
    )
