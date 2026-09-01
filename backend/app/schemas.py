from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    role: str
    name: str | None = None


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    role: str
    name: str | None = None


class UploadBatchOut(BaseModel):
    id: UUID
    filename: str
    source_type: str
    row_count: int | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class LoanRecordOut(BaseModel):
    id: UUID
    loan_id: str
    borrower_id: str | None
    payment_status: str | None
    current_balance: float | None
    original_principal: float | None
    document_status: str | None

    class Config:
        from_attributes = True


class ExceptionOut(BaseModel):
    id: UUID
    loan_record_id: UUID | None
    rule_key: str
    severity: str
    status: str
    field: str | None
    detail: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True


class ExceptionCommentIn(BaseModel):
    body: str


class ExceptionCommentOut(BaseModel):
    id: UUID
    exception_id: UUID | None
    author_id: UUID | None
    body: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ExceptionDecisionIn(BaseModel):
    action: str  # approve | reject | edit | request_correction
    field_changed: str | None = None
    new_value: str | None = None
    ai_recommendation_id: UUID | None = None


class AIReviewOut(BaseModel):
    id: UUID
    exception_id: UUID
    model: str
    response_json: dict[str, Any]
    confidence: float | None
    latency_ms: int | None
    accepted: bool | None

    class Config:
        from_attributes = True


class GenerateRuleIn(BaseModel):
    instruction: str


class VerifiedLoanOut(BaseModel):
    id: UUID
    loan_record_id: UUID | None
    canonical_data: dict[str, Any]
    record_hash: str
    prev_hash: str | None
    verified_at: datetime

    class Config:
        from_attributes = True


class AuditEventOut(BaseModel):
    id: UUID
    event_type: str
    actor_id: UUID | None
    detail: dict[str, Any] | None
    record_hash: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SummaryOut(BaseModel):
    total_loans: int
    open_exceptions: int
    resolved_exceptions: int
    verified_records: int
    data_quality_score: float
