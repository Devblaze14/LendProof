from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.hashing import compute_record_hash
from app.models import (
    AIRecommendation, ExceptionComment, ExceptionRecord, LoanRecord, Profile,
    ReviewerAction, VerifiedLoanRecord,
)
from app.schemas import (
    AIReviewOut, ExceptionCommentIn, ExceptionCommentOut, ExceptionDecisionIn, ExceptionOut,
)
from app.security import require_role
from app.services import ai_service
from app.services.ai_service import AIUnavailableError
from app.services.audit import write_audit_event

router = APIRouter(prefix="/api/v1/exceptions", tags=["exceptions"])


@router.get("", response_model=list[ExceptionOut])
def list_exceptions(
    status: str | None = None, severity: str | None = None, q: str | None = None,
    limit: int = 50, offset: int = 0,
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_role("reviewer", "operator")),
):
    query = db.query(ExceptionRecord)
    if status:
        query = query.filter(ExceptionRecord.status == status)
    if severity:
        query = query.filter(ExceptionRecord.severity == severity)
    if q:
        query = query.join(LoanRecord, ExceptionRecord.loan_record_id == LoanRecord.id).filter(or_(
            LoanRecord.loan_id.ilike(f"%{q}%"), LoanRecord.borrower_id.ilike(f"%{q}%")
        ))
    return query.order_by(ExceptionRecord.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{exception_id}", response_model=ExceptionOut)
def get_exception(exception_id: UUID, db: Session = Depends(get_db),
                   profile: Profile = Depends(require_role("reviewer", "operator"))):
    exc = db.get(ExceptionRecord, exception_id)
    if not exc:
        raise AppError(404, "NOT_FOUND", "Exception not found")
    return exc


@router.post("/{exception_id}/comments", status_code=201)
def add_comment(exception_id: UUID, payload: ExceptionCommentIn, db: Session = Depends(get_db),
                 profile: Profile = Depends(require_role("reviewer"))):
    exc = db.get(ExceptionRecord, exception_id)
    if not exc:
        raise AppError(404, "NOT_FOUND", "Exception not found")
    comment = ExceptionComment(exception_id=exception_id, author_id=profile.id, body=payload.body)
    db.add(comment)
    db.commit()
    write_audit_event(db, event_type="reviewer.comment_added", actor_id=profile.id,
                       loan_record_id=exc.loan_record_id, detail={"exception_id": str(exception_id)})
    return {"status": "ok"}


@router.get("/{exception_id}/comments", response_model=list[ExceptionCommentOut])
def list_comments(exception_id: UUID, db: Session = Depends(get_db),
                  profile: Profile = Depends(require_role("reviewer", "operator"))):
    exc = db.get(ExceptionRecord, exception_id)
    if not exc:
        raise AppError(404, "NOT_FOUND", "Exception not found")
    return (db.query(ExceptionComment).filter(ExceptionComment.exception_id == exception_id)
            .order_by(ExceptionComment.created_at.asc()).all())


@router.post("/{exception_id}/ai-review", response_model=AIReviewOut)
def request_ai_review(exception_id: UUID, db: Session = Depends(get_db),
                       profile: Profile = Depends(require_role("reviewer"))):
    exc = db.get(ExceptionRecord, exception_id)
    if not exc:
        raise AppError(404, "NOT_FOUND", "Exception not found")
    loan = db.get(LoanRecord, exc.loan_record_id) if exc.loan_record_id else None
    row_context = {c.name: getattr(loan, c.name) for c in loan.__table__.columns} if loan else {}
    rule_message = (exc.detail or {}).get("message", exc.rule_key)

    try:
        response_json, model, latency_ms = ai_service.explain_exception(rule_message, row_context)
    except AIUnavailableError as e:
        # Design rule: AI being down must never block the human workflow.
        # The reviewer sees a clear "AI unavailable" state and can still
        # approve/reject manually.
        raise AppError(503, "AI_UNAVAILABLE",
                        "The AI assistant is temporarily unavailable. You can still review and "
                        "decide on this exception manually.") from e

    rec = AIRecommendation(
        exception_id=exception_id, prompt=f"explain_exception::{rule_message}", model=model,
        response_json=response_json, confidence=response_json.get("confidence"), latency_ms=latency_ms,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    write_audit_event(db, event_type="ai.recommendation_generated", actor_id=profile.id,
                       loan_record_id=exc.loan_record_id,
                       detail={"exception_id": str(exception_id), "ai_recommendation_id": str(rec.id)})
    return rec


@router.post("/{exception_id}/decision")
def submit_decision(exception_id: UUID, payload: ExceptionDecisionIn, db: Session = Depends(get_db),
                     profile: Profile = Depends(require_role("reviewer"))):
    """The ONLY endpoint that may move an exception to 'resolved' or create
    a verified_loan_records row. AI recommendations are informational input
    here, never an alternate write path — see the non-negotiable design
    rules in docs/Antigravity_Build_Package.md Section 1."""
    exc = db.get(ExceptionRecord, exception_id)
    if not exc:
        raise AppError(404, "NOT_FOUND", "Exception not found")
    if payload.action not in ("approve", "reject", "edit", "request_correction"):
        raise AppError(400, "INVALID_ACTION", "action must be approve, reject, edit, or request_correction")

    if payload.ai_recommendation_id:
        rec = db.get(AIRecommendation, payload.ai_recommendation_id)
        if rec:
            rec.accepted = payload.action == "approve"
            rec.reviewed_by = profile.id

    reviewer_action = ReviewerAction(
        exception_id=exception_id, reviewer_id=profile.id, action=payload.action,
        field_changed=payload.field_changed, new_value=payload.new_value,
        ai_recommendation_id=payload.ai_recommendation_id,
    )
    db.add(reviewer_action)

    if payload.action == "edit" and payload.field_changed and exc.loan_record_id:
        loan = db.get(LoanRecord, exc.loan_record_id)
        if loan and hasattr(loan, payload.field_changed):
            setattr(loan, payload.field_changed, payload.new_value)
            write_audit_event(db, event_type="field.edited", actor_id=profile.id,
                               loan_record_id=exc.loan_record_id,
                               detail={"field": payload.field_changed, "new_value": payload.new_value})

    if payload.action in ("approve", "reject"):
        exc.status = "resolved"
        write_audit_event(
            db, event_type="loan.approved" if payload.action == "approve" else "loan.rejected",
            actor_id=profile.id, loan_record_id=exc.loan_record_id,
            detail={"exception_id": str(exception_id)},
        )
    elif payload.action == "request_correction":
        exc.status = "in_review"
        write_audit_event(
            db, event_type="loan.correction_requested", actor_id=profile.id,
            loan_record_id=exc.loan_record_id,
            detail={"exception_id": str(exception_id), "field": exc.field},
        )

    db.commit()

    if payload.action == "approve" and exc.loan_record_id:
        remaining_open = db.query(ExceptionRecord).filter(
            ExceptionRecord.loan_record_id == exc.loan_record_id,
            ExceptionRecord.status.in_(("open", "in_review")),
        ).count()
        if remaining_open == 0:
            _create_verified_record(db, exc.loan_record_id, profile.id, payload.ai_recommendation_id)

    return {"status": "ok"}


def _create_verified_record(db: Session, loan_record_id: UUID, verified_by: UUID,
                             ai_recommendation_id: UUID | None) -> VerifiedLoanRecord:
    loan = db.get(LoanRecord, loan_record_id)
    canonical_data = {c.name: str(getattr(loan, c.name)) for c in loan.__table__.columns}

    prior = (
        db.query(VerifiedLoanRecord)
        .filter(VerifiedLoanRecord.loan_record_id == loan_record_id)
        .order_by(VerifiedLoanRecord.verified_at.desc())
        .first()
    )
    prev_hash = prior.record_hash if prior else None
    record_hash = compute_record_hash(canonical_data, prev_hash)

    remaining_open = db.query(ExceptionRecord).filter(
        ExceptionRecord.loan_record_id == loan_record_id, ExceptionRecord.status == "open"
    ).count()

    verified = VerifiedLoanRecord(
        loan_record_id=loan_record_id, canonical_data=canonical_data,
        validation_result={"open_exceptions_remaining": remaining_open},
        ai_recommendation_id=ai_recommendation_id, record_hash=record_hash, prev_hash=prev_hash,
        verified_by=verified_by,
    )
    db.add(verified)
    db.commit()
    db.refresh(verified)
    write_audit_event(db, event_type="verified_record.created", actor_id=verified_by,
                       loan_record_id=loan_record_id, record_hash=record_hash,
                       detail={"verified_record_id": str(verified.id)})
    return verified
