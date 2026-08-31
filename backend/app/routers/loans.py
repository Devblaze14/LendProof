from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import LoanRecord, Profile
from app.schemas import LoanRecordOut
from app.security import require_role

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])


@router.get("", response_model=list[LoanRecordOut])
def list_loans(
    q: str | None = Query(None, description="search by loan_id or borrower_id"),
    limit: int = 50, offset: int = 0,
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_role("operator", "reviewer", "consumer")),
):
    query = db.query(LoanRecord)
    if q:
        query = query.filter(
            (LoanRecord.loan_id.ilike(f"%{q}%")) | (LoanRecord.borrower_id.ilike(f"%{q}%"))
        )
    return query.order_by(LoanRecord.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{loan_record_id}", response_model=LoanRecordOut)
def get_loan(loan_record_id: UUID, db: Session = Depends(get_db),
             profile: Profile = Depends(require_role("operator", "reviewer", "consumer"))):
    loan = db.get(LoanRecord, loan_record_id)
    if not loan:
        raise AppError(404, "NOT_FOUND", "Loan record not found")
    return loan
