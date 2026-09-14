"""
Local-mode seed script: creates the 3 test users referenced in
TEST_CREDENTIALS.md, loads validation_rules.json, and optionally loads
loan_tape.csv for demo data. Run once after applying migrations/001_init_local.sql.

    python -m app.seed.seed_db
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from app.db import SessionLocal
from app.config import get_settings
from app.models import (
    AppUser, Profile, ValidationRule, UploadBatch, RawLoanRow, LoanRecord, ExceptionRecord
)
from app.security import hash_password

DATA_DIR = Path(__file__).resolve().parents[2].parent / "data"

DEMO_PASSWORD = get_settings().demo_password

USERS = [
    {"email": "operator@testmail.dev", "role": "operator", "name": "Dana Operator"},
    {"email": "reviewer@testmail.dev", "role": "reviewer", "name": "Rae Reviewer"},
    {"email": "consumer@testmail.dev", "role": "consumer", "name": "Cam Consumer"},
]


def seed():
    db = SessionLocal()
    try:
        # Seed users
        for u in USERS:
            existing = db.query(AppUser).filter(AppUser.email == u["email"]).first()
            if existing:
                continue
            user = AppUser(email=u["email"], password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)
            db.flush()
            db.add(Profile(id=user.id, role=u["role"], name=u["name"]))
        db.commit()

        # Seed validation rules
        rules_path = DATA_DIR / "validation_rules.json"
        if rules_path.exists():
            rules = json.loads(rules_path.read_text())
            for r in rules:
                if db.query(ValidationRule).filter(ValidationRule.rule_key == r["rule_key"]).first():
                    continue
                db.add(ValidationRule(
                    rule_key=r["rule_key"], field=r.get("field"), rule_type=r["rule_type"],
                    params=r.get("params", {}), severity=r["severity"],
                    message_template=r["message_template"], source="seed", active=True,
                ))
            db.commit()

        # Auto-load loan_tape.csv for demo data
        loan_tape_path = DATA_DIR / "loan_tape.csv"
        if loan_tape_path.exists():
            # Check if data already exists
            existing_batch = db.query(UploadBatch).filter(
                UploadBatch.source_type == "loan_tape"
            ).first()
            
            if not existing_batch:
                print("Loading loan_tape.csv for demo data...")
                load_loan_data(db, loan_tape_path)
            else:
                print("Demo loan data already exists, skipping upload.")
        
        print(f"Seeded {len(USERS)} users (password: {DEMO_PASSWORD}) and validation rules.")
    finally:
        db.close()


def load_loan_data(db, csv_path):
    """Load loan_tape.csv and create exceptions automatically"""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        file_hash = hashlib.sha256(content.encode()).hexdigest()
    
    # Create upload batch
    operator_profile = db.query(Profile).filter(Profile.role == "operator").first()
    batch = UploadBatch(
        filename="loan_tape.csv",
        file_hash=file_hash,
        source_type="loan_tape",
        storage_path="seeded_data",
        uploaded_by=operator_profile.id,
        status="processing",
    )
    db.add(batch)
    db.flush()
    
    # Inline normalization function to avoid circular imports
    NUMERIC_FIELDS = {"original_principal", "current_balance", "interest_rate"}
    INT_FIELDS = {"term_months", "days_past_due"}
    DATE_FIELDS = {"origination_date", "maturity_date", "last_payment_date"}
    
    def normalize_row_inline(raw):
        try:
            normalized = dict(raw)
            for f in DATE_FIELDS:
                if raw.get(f):
                    try:
                        normalized[f] = datetime.strptime(raw[f], "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        normalized[f] = None
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
        except Exception as e:
            return raw, str(e)
    
    # Parse and load data
    reader = csv.DictReader(content.splitlines())
    normalized_rows = []
    
    for i, raw_row in enumerate(reader):
        normalized, parse_error = normalize_row_inline(raw_row)
        db.add(RawLoanRow(
            batch_id=batch.id,
            row_number=i,
            raw_json=raw_row,
            parse_error=parse_error
        ))
        
        if parse_error is None and normalized.get("loan_id"):
            loan = LoanRecord(
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
                source_batch_id=batch.id,
            )
            db.add(loan)
            normalized_rows.append(normalized)
    
    batch.row_count = len(normalized_rows)
    batch.status = "validating"
    db.commit()
    
    # Run validation
    rules = [
        {"rule_key": r.rule_key, "field": r.field, "rule_type": r.rule_type, "params": r.params,
         "severity": r.severity, "message_template": r.message_template, "active": r.active}
        for r in db.query(ValidationRule).filter(ValidationRule.active.is_(True)).all()
    ]
    
    # Convert database rows to dict format for validation engine
    rows_for_engine = []
    for row in normalized_rows:
        rows_for_engine.append({
            "loan_id": row.get("loan_id"),
            "borrower_id": row.get("borrower_id"),
            "origination_date": row.get("origination_date").isoformat() if row.get("origination_date") and hasattr(row.get("origination_date"), 'isoformat') else str(row.get("origination_date", "")),
            "maturity_date": row.get("maturity_date").isoformat() if row.get("maturity_date") and hasattr(row.get("maturity_date"), 'isoformat') else str(row.get("maturity_date", "")),
            "original_principal": row.get("original_principal"),
            "current_balance": row.get("current_balance"),
            "interest_rate": row.get("interest_rate"),
            "payment_status": row.get("payment_status"),
            "days_past_due": row.get("days_past_due"),
            "document_status": row.get("document_status"),
            "borrower_state": row.get("borrower_state"),
            "last_updated_at": str(datetime.utcnow())[:10],
        })
    
    # Simple inline validation to avoid circular imports
    findings = []
    for row in rows_for_engine:
        for rule in rules:
            if not rule.get("active", True):
                continue
            # Simple required field check
            if rule["rule_type"] == "required":
                field = rule["field"]
                value = row.get(field)
                if value is None or str(value).strip() == "":
                    findings.append({
                        "rule_key": rule["rule_key"],
                        "field": rule.get("field"),
                        "severity": rule["severity"],
                        "message": rule["message_template"],
                        "row_ref": row.get("loan_id"),
                    })
            # Simple range check
            elif rule["rule_type"] == "range":
                field = rule["field"]
                raw = row.get(field)
                if raw is None or str(raw).strip() == "":
                    continue
                try:
                    value = float(raw)
                except (ValueError, TypeError):
                    continue
                params = rule["params"]
                if "min" in params and value < params["min"]:
                    findings.append({
                        "rule_key": rule["rule_key"],
                        "field": rule.get("field"),
                        "severity": rule["severity"],
                        "message": rule["message_template"],
                        "row_ref": row.get("loan_id"),
                    })
                if "max" in params and value > params["max"]:
                    findings.append({
                        "rule_key": rule["rule_key"],
                        "field": rule.get("field"),
                        "severity": rule["severity"],
                        "message": rule["message_template"],
                        "row_ref": row.get("loan_id"),
                    })
    
    # Map loan IDs to database IDs
    loan_records = db.query(LoanRecord).filter(LoanRecord.source_batch_id == batch.id).all()
    id_by_loan_id = {r.loan_id: r.id for r in loan_records}
    
    # Create exception records
    for finding in findings:
        loan_record_id = id_by_loan_id.get(finding["row_ref"])
        if loan_record_id:
            db.add(ExceptionRecord(
                loan_record_id=loan_record_id,
                rule_key=finding["rule_key"],
                severity=finding["severity"],
                field=finding["field"],
                detail={"message": finding["message"]},
            ))
    
    batch.status = "complete"
    db.commit()
    
    # Write audit events
    from app.services.audit import write_audit_event
    write_audit_event(db, event_type="file.uploaded", actor_id=operator_profile.id,
                      detail={"batch_id": str(batch.id), "filename": "loan_tape.csv"})
    write_audit_event(db, event_type="loan_record.imported", actor_id=operator_profile.id,
                      detail={"batch_id": str(batch.id), "row_count": len(normalized_rows)})
    write_audit_event(db, event_type="validation.executed", actor_id=operator_profile.id,
                      detail={"batch_id": str(batch.id), "exception_count": len(findings)})
    
    print(f"Loaded {len(normalized_rows)} loan records and created {len(findings)} exceptions.")


if __name__ == "__main__":
    seed()
