from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def uuid_col():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class AppUser(Base):
    """Local-mode-only stand-in for Supabase's auth.users. Not created / not
    used when DATABASE_MODE=supabase — Supabase Auth owns this table there."""
    __tablename__ = "app_users"
    id = uuid_col()
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(UUID(as_uuid=True), primary_key=True)
    role = Column(String, nullable=False)  # operator | reviewer | consumer
    name = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    id = uuid_col()
    filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, nullable=False)
    source_type = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    row_count = Column(Integer)
    status = Column(String, default="processing")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class RawLoanRow(Base):
    __tablename__ = "raw_loan_rows"
    id = uuid_col()
    batch_id = Column(UUID(as_uuid=True), ForeignKey("upload_batches.id"))
    row_number = Column(Integer, nullable=False)
    raw_json = Column(JSONB, nullable=False)
    parse_error = Column(Text)


class LoanRecord(Base):
    __tablename__ = "loan_records"
    id = uuid_col()
    loan_id = Column(String, nullable=False, index=True)
    borrower_id = Column(String)
    loan_type = Column(String)
    origination_date = Column(Date)
    maturity_date = Column(Date)
    original_principal = Column(Numeric)
    current_balance = Column(Numeric)
    interest_rate = Column(Numeric)
    term_months = Column(Integer)
    borrower_state = Column(String)
    loan_purpose = Column(String)
    credit_grade = Column(String)
    employment_length = Column(String)
    income_band = Column(String)
    payment_status = Column(String)
    days_past_due = Column(Integer)
    servicer_name = Column(String)
    last_payment_date = Column(Date)
    last_updated_at = Column(DateTime(timezone=True))
    document_status = Column(String)
    source_system = Column(String)
    source_batch_id = Column(UUID(as_uuid=True), ForeignKey("upload_batches.id"))
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ValidationRule(Base):
    __tablename__ = "validation_rules"
    id = uuid_col()
    rule_key = Column(String, unique=True, nullable=False)
    field = Column(String)
    rule_type = Column(String, nullable=False)
    params = Column(JSONB, nullable=False, default=dict)
    severity = Column(String, nullable=False)
    message_template = Column(String, nullable=False)
    source = Column(String, default="seed")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    id = uuid_col()
    loan_record_id = Column(UUID(as_uuid=True), ForeignKey("loan_records.id"))
    rule_key = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, default="open")
    field = Column(String)
    detail = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ExceptionComment(Base):
    __tablename__ = "exception_comments"
    id = uuid_col()
    exception_id = Column(UUID(as_uuid=True), ForeignKey("exceptions.id"))
    author_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    body = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    id = uuid_col()
    exception_id = Column(UUID(as_uuid=True), ForeignKey("exceptions.id"))
    prompt = Column(Text, nullable=False)
    model = Column(String, nullable=False)
    response_json = Column(JSONB, nullable=False)
    confidence = Column(Numeric)
    latency_ms = Column(Integer)
    accepted = Column(Boolean)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ReviewerAction(Base):
    __tablename__ = "reviewer_actions"
    id = uuid_col()
    exception_id = Column(UUID(as_uuid=True), ForeignKey("exceptions.id"))
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    action = Column(String, nullable=False)
    field_changed = Column(String)
    old_value = Column(Text)
    new_value = Column(Text)
    ai_recommendation_id = Column(UUID(as_uuid=True), ForeignKey("ai_recommendations.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class VerifiedLoanRecord(Base):
    __tablename__ = "verified_loan_records"
    id = uuid_col()
    loan_record_id = Column(UUID(as_uuid=True), ForeignKey("loan_records.id"))
    canonical_data = Column(JSONB, nullable=False)
    validation_result = Column(JSONB, nullable=False)
    reviewer_decision = Column(JSONB)
    ai_recommendation_id = Column(UUID(as_uuid=True), ForeignKey("ai_recommendations.id"))
    record_hash = Column(String, nullable=False)
    prev_hash = Column(String)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    verified_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = uuid_col()
    event_type = Column(String, nullable=False)
    loan_record_id = Column(UUID(as_uuid=True), ForeignKey("loan_records.id"))
    actor_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    detail = Column(JSONB)
    record_hash = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
