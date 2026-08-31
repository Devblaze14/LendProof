import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.validation.engine import run_batch, run_row_rules, run_duplicate_rules  # noqa: E402

RULES = json.loads((Path(__file__).resolve().parents[2] / "data" / "validation_rules.json").read_text())


def clean_row(**overrides):
    row = {
        "loan_id": "LN-00000001", "borrower_id": "BR-000001", "loan_type": "conventional",
        "origination_date": "2022-01-01", "maturity_date": "2032-01-01",
        "original_principal": "200000", "current_balance": "150000", "interest_rate": "5.5",
        "term_months": "120", "borrower_state": "CA", "loan_purpose": "purchase",
        "credit_grade": "A", "employment_length": "5", "income_band": "75k-120k",
        "payment_status": "current", "days_past_due": "0", "servicer_name": "Meridian",
        "last_payment_date": "2026-08-01", "last_updated_at": "2026-08-01",
        "document_status": "complete", "source_system": "origination_sys_a",
    }
    row.update(overrides)
    return row


def test_clean_row_produces_no_exceptions():
    findings = run_row_rules(clean_row(), RULES)
    assert findings == []


def test_missing_loan_id():
    findings = run_row_rules(clean_row(loan_id=""), RULES)
    assert any(f.rule_key == "required_loan_id" for f in findings)


def test_maturity_before_origination():
    findings = run_row_rules(
        clean_row(origination_date="2022-01-01", maturity_date="2020-01-01"), RULES
    )
    assert any(f.rule_key == "maturity_after_origination" for f in findings)


def test_negative_principal():
    findings = run_row_rules(clean_row(original_principal="-5000"), RULES)
    assert any(f.rule_key == "no_negative_principal" for f in findings)


def test_balance_exceeds_principal():
    findings = run_row_rules(
        clean_row(original_principal="100000", current_balance="150000"), RULES
    )
    assert any(f.rule_key == "balance_not_exceeding_principal" for f in findings)


def test_interest_rate_out_of_range():
    findings = run_row_rules(clean_row(interest_rate="99"), RULES)
    assert any(f.rule_key == "interest_rate_range" for f in findings)


def test_status_dpd_mismatch():
    findings = run_row_rules(
        clean_row(payment_status="current", days_past_due="60"), RULES
    )
    assert any(f.rule_key == "status_dpd_consistency" for f in findings)


def test_missing_document_status():
    findings = run_row_rules(clean_row(document_status=""), RULES)
    assert any(f.rule_key == "required_document_status" for f in findings)


def test_stale_record():
    findings = run_row_rules(clean_row(last_updated_at="2023-01-01"), RULES)
    assert any(f.rule_key == "stale_record" for f in findings)


def test_invalid_state_code():
    findings = run_row_rules(clean_row(borrower_state="ZZ"), RULES)
    assert any(f.rule_key == "valid_state_code" for f in findings)


def test_closed_but_positive_balance():
    findings = run_row_rules(
        clean_row(payment_status="closed", current_balance="5000"), RULES
    )
    assert any(f.rule_key == "closed_positive_balance" for f in findings)


def test_duplicate_loan_id_detected():
    rows = [clean_row(loan_id="LN-DUP"), clean_row(loan_id="LN-DUP", borrower_id="BR-999999")]
    findings = run_duplicate_rules(rows, RULES)
    assert any(f.rule_key == "duplicate_loan_id" for f in findings)
    # only the second occurrence is flagged, not the first
    assert len([f for f in findings if f.rule_key == "duplicate_loan_id"]) == 1


def test_duplicate_borrower_amount_origination_combo():
    rows = [
        clean_row(loan_id="LN-A", borrower_id="BR-X", original_principal="100000", origination_date="2021-05-01"),
        clean_row(loan_id="LN-B", borrower_id="BR-X", original_principal="100000", origination_date="2021-05-01"),
    ]
    findings = run_duplicate_rules(rows, RULES)
    assert any(f.rule_key == "duplicate_borrower_amount_origination" for f in findings)


def test_full_batch_run_on_generated_dataset():
    import csv
    data_dir = Path(__file__).resolve().parents[2] / "data"
    with (data_dir / "loan_tape.csv").open() as f:
        rows = list(csv.DictReader(f))
    with (data_dir / "servicer_update.csv").open() as f:
        servicer_rows = list(csv.DictReader(f))
    findings = run_batch(rows, RULES, servicer_rows)
    assert len(findings) > 0
    # sanity: every issue type seeded by the generator should show up somewhere
    fired_keys = {f.rule_key for f in findings}
    assert "required_loan_id" in fired_keys
    assert "maturity_after_origination" in fired_keys
    assert "no_negative_principal" in fired_keys
    assert "duplicate_loan_id" in fired_keys
