from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LoanRecord, RawLoanRow, UploadBatch, ValidationRule
from app.validation.engine import run_batch
from app.services.audit import write_audit_event

logger = logging.getLogger("ingestion")

NUMERIC_FIELDS = {"original_principal", "current_balance", "interest_rate"}
INT_FIELDS = {"term_months", "days_past_due"}
DATE_FIELDS = {"origination_date", "maturity_date", "last_payment_date"}


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None  # malformed dates are surfaced by the validation engine, not swallowed


def normalize_row(raw: dict) -> tuple[dict, str | None]:
    """Best-effort normalization. Returns (normalized_dict, parse_error|None).
    Deliberately permissive: a row with a malformed date still gets stored
    and later flagged by the validation engine (FR-ING-3) rather than
    silently dropped here."""
    try:
        normalized = dict(raw)
        for f in DATE_FIELDS:
            if raw.get(f):
                normalized[f] = _parse_date(raw[f])
        for f in NUMERIC_FIELDS:
            try:
                normalized[f] = float(raw[f]) if raw.get(f) not in (None, "") else None
            except ValueError:
                normalized[f] = None
        for f in INT_FIELDS:
            try:
                normalized[f] = int(float(raw[f])) if raw.get(f) not in (None, "") else None
            except ValueError:
                normalized[f] = None
        return normalized, None
    except Exception as e:  # last-resort safety net; row is still preserved raw
        return raw, str(e)


def process_upload(db: Session, batch_id: UUID, csv_bytes: bytes) -> None:
    """Runs as a FastAPI BackgroundTask. Parses -> normalizes -> stores raw
    rows -> upserts loan_records -> runs validation -> writes exceptions."""
    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        logger.error("process_upload: batch %s not found", batch_id)
        return

    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    normalized_rows: list[dict] = []

    for i, raw_row in enumerate(reader):
        normalized, parse_error = normalize_row(raw_row)
        db.add(RawLoanRow(batch_id=batch_id, row_number=i, raw_json=raw_row, parse_error=parse_error))
        if parse_error is None:
            normalized_rows.append(normalized)

        if not parse_error and normalized.get("loan_id"):
            db.add(LoanRecord(
                loan_id=normalized.get("loan_id") or "",
                borrower_id=normalized.get("borrower_id"),
                loan_type=normalized.get("loan_type"),
                origination_date=normalized.get("origination_date"),
                maturity_date=normalized.get("maturity_date"),
                original_principal=normalized.get("original_principal"),
                current_balance=normalized.get("current_balance"),
                interest_rate=normalized.get("interest_rate"),
                term_months=normalized.get("term_months"),
                borrower_state=normalized.get("borrower_state"),
                loan_purpose=normalized.get("loan_purpose"),
                credit_grade=normalized.get("credit_grade"),
                employment_length=normalized.get("employment_length"),
                income_band=normalized.get("income_band"),
                payment_status=normalized.get("payment_status"),
                days_past_due=normalized.get("days_past_due"),
                servicer_name=normalized.get("servicer_name"),
                last_payment_date=normalized.get("last_payment_date"),
                document_status=normalized.get("document_status"),
                source_system=normalized.get("source_system"),
                source_batch_id=batch_id,
            ))

    batch.row_count = len(normalized_rows)
    batch.status = "validating"
    db.commit()
    write_audit_event(db, event_type="loan_record.imported", actor_id=batch.uploaded_by,
                       detail={"batch_id": str(batch_id), "row_count": len(normalized_rows)})

    # Run the validation engine over rows that made it into loan_records
    rules = [
        {"rule_key": r.rule_key, "field": r.field, "rule_type": r.rule_type, "params": r.params,
         "severity": r.severity, "message_template": r.message_template, "active": r.active}
        for r in db.query(ValidationRule).filter(ValidationRule.active.is_(True)).all()
    ]
    stored_rows = db.query(LoanRecord).filter(LoanRecord.source_batch_id == batch_id).all()
    rows_for_engine = [
        {
            "loan_id": r.loan_id, "borrower_id": r.borrower_id,
            "origination_date": r.origination_date.isoformat() if r.origination_date else "",
            "maturity_date": r.maturity_date.isoformat() if r.maturity_date else "",
            "original_principal": r.original_principal, "current_balance": r.current_balance,
            "interest_rate": r.interest_rate, "payment_status": r.payment_status,
            "days_past_due": r.days_past_due, "document_status": r.document_status,
            "borrower_state": r.borrower_state, "last_updated_at": str(r.created_at)[:10],
        }
        for r in stored_rows
    ]
    from app.validation.engine import Exception_  # local import to avoid cycle in type hints
    findings: list[Exception_] = run_batch(rows_for_engine, rules)

    id_by_loan_id = {r.loan_id: r.id for r in stored_rows}
    from app.models import ExceptionRecord
    for finding in findings:
        loan_record_id = id_by_loan_id.get(finding.row_ref)
        db.add(ExceptionRecord(
            loan_record_id=loan_record_id, rule_key=finding.rule_key, severity=finding.severity,
            field=finding.field, detail={"message": finding.message},
        ))
    db.commit()
    write_audit_event(db, event_type="validation.executed", actor_id=batch.uploaded_by,
                       detail={"batch_id": str(batch_id), "exception_count": len(findings)})
    if findings:
        write_audit_event(db, event_type="exception.created", actor_id=batch.uploaded_by,
                           detail={"batch_id": str(batch_id), "count": len(findings)})

    batch.status = "complete"
    db.commit()
