"""
Generates a synthetic loan tape + servicer update file + document manifest,
deliberately seeded with every data-quality issue listed in the challenge
brief (section 7, "Intentional Data Issues"), plus an expected-exceptions
reference file for orientation.

Run:
    python -m app.seed.generate_synthetic_dataset --rows 1500 --out ../data

No network access required — this is pure synthetic generation.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import string
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # deterministic output for reproducible demos

US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY",
]
INVALID_STATE_CODES = ["ZZ", "XX", "QQ", "00"]
LOAN_TYPES = ["conventional", "fha", "va", "jumbo"]
LOAN_PURPOSES = ["purchase", "refinance", "cash_out_refinance"]
CREDIT_GRADES = ["A", "B", "C", "D"]
INCOME_BANDS = ["<40k", "40k-75k", "75k-120k", "120k+"]
PAYMENT_STATUSES = ["current", "delinquent_30", "delinquent_60", "delinquent_90", "closed"]
SERVICERS = ["Meridian Loan Servicing", "Highline Capital Servicing", "Coastal Trust Servicing"]
SOURCE_SYSTEMS = ["origination_sys_a", "origination_sys_b", "manual_spreadsheet"]
DOC_STATUSES = ["complete", "partial", "missing"]

EXPECTED_ROWS = []  # populated as we generate, written to expected_exception_sample.csv


def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def new_loan_id() -> str:
    return "LN-" + "".join(random.choices(string.digits, k=8))


def new_borrower_id() -> str:
    return "BR-" + "".join(random.choices(string.digits, k=6))


@dataclass
class Loan:
    loan_id: str
    borrower_id: str
    loan_type: str
    origination_date: str
    maturity_date: str
    original_principal: float
    current_balance: float
    interest_rate: float
    term_months: int
    borrower_state: str
    loan_purpose: str
    credit_grade: str
    employment_length: int
    income_band: str
    payment_status: str
    days_past_due: int
    servicer_name: str
    last_payment_date: str
    last_updated_at: str
    document_status: str
    source_system: str


def make_clean_loan() -> Loan:
    origination = rand_date(date(2019, 1, 1), date(2024, 6, 30))
    term = random.choice([120, 180, 240, 360])
    maturity = origination + timedelta(days=term * 30)
    principal = round(random.uniform(80_000, 650_000), 2)
    paid_down_ratio = random.uniform(0.05, 0.9)
    balance = round(principal * (1 - paid_down_ratio), 2)
    status = random.choices(PAYMENT_STATUSES, weights=[70, 12, 8, 5, 5])[0]
    dpd = {"current": 0, "delinquent_30": random.randint(30, 44),
           "delinquent_60": random.randint(45, 74), "delinquent_90": random.randint(75, 120),
           "closed": 0}[status]
    last_updated = rand_date(date(2025, 6, 1), date(2026, 8, 1))
    return Loan(
        loan_id=new_loan_id(),
        borrower_id=new_borrower_id(),
        loan_type=random.choice(LOAN_TYPES),
        origination_date=origination.isoformat(),
        maturity_date=maturity.isoformat(),
        original_principal=principal,
        current_balance=balance,
        interest_rate=round(random.uniform(3.5, 8.5), 3),
        term_months=term,
        borrower_state=random.choice(US_STATES),
        loan_purpose=random.choice(LOAN_PURPOSES),
        credit_grade=random.choice(CREDIT_GRADES),
        employment_length=random.randint(0, 30),
        income_band=random.choice(INCOME_BANDS),
        payment_status=status,
        days_past_due=dpd,
        servicer_name=random.choice(SERVICERS),
        last_payment_date=rand_date(origination, date(2026, 8, 1)).isoformat(),
        last_updated_at=last_updated.isoformat(),
        document_status=random.choice(DOC_STATUSES),
        source_system=random.choice(SOURCE_SYSTEMS),
    )


def apply_issue(loan: Loan, issue: str) -> Loan:
    """Mutates a clean loan to deliberately trigger one named validation issue."""
    if issue == "missing_loan_id":
        loan.loan_id = ""
    elif issue == "invalid_date_format":
        loan.origination_date = "31/02/2021"  # not ISO, not even a real date
    elif issue == "maturity_before_origination":
        loan.maturity_date = (date.fromisoformat(loan.origination_date) - timedelta(days=400)).isoformat()
    elif issue == "negative_principal":
        loan.original_principal = -round(random.uniform(10_000, 50_000), 2)
    elif issue == "balance_exceeds_principal":
        loan.current_balance = loan.original_principal + round(random.uniform(5_000, 20_000), 2)
    elif issue == "interest_rate_out_of_range":
        loan.interest_rate = round(random.choice([0.01, 45.0]), 3)
    elif issue == "status_dpd_mismatch":
        loan.payment_status = "current"
        loan.days_past_due = random.randint(60, 120)
    elif issue == "missing_document_status":
        loan.document_status = ""
    elif issue == "stale_record":
        loan.last_updated_at = (date(2026, 8, 1) - timedelta(days=random.randint(400, 900))).isoformat()
    elif issue == "invalid_state_code":
        loan.borrower_state = random.choice(INVALID_STATE_CODES)
    elif issue == "closed_but_positive_balance":
        loan.payment_status = "closed"
        loan.current_balance = round(random.uniform(5_000, 40_000), 2)
    return loan


def generate(rows: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    loans: list[Loan] = []
    expected: list[dict] = []

    issue_pool = [
        "missing_loan_id", "invalid_date_format", "maturity_before_origination",
        "negative_principal", "balance_exceeds_principal", "interest_rate_out_of_range",
        "status_dpd_mismatch", "missing_document_status", "stale_record",
        "invalid_state_code", "closed_but_positive_balance",
    ]
    n_issue_rows = max(int(rows * 0.18), len(issue_pool))  # ~18% of rows carry an issue

    for i in range(rows):
        loan = make_clean_loan()
        loans.append(loan)

    # Apply one issue type per selected row, cycling through the pool so every
    # issue type is represented at least a few times regardless of dataset size.
    issue_targets = random.sample(range(rows), k=min(n_issue_rows, rows))
    for idx, target in enumerate(issue_targets):
        issue = issue_pool[idx % len(issue_pool)]
        loans[target] = apply_issue(loans[target], issue)
        expected.append({"loan_id": loans[target].loan_id or f"(blank-row-{target})",
                          "row_index": target, "expected_issue": issue})

    # Duplicate loan IDs: clone two existing clean rows with a shared loan_id
    dup_targets = random.sample([i for i in range(rows) if i not in issue_targets], k=2)
    loans[dup_targets[1]].loan_id = loans[dup_targets[0]].loan_id
    expected.append({"loan_id": loans[dup_targets[0]].loan_id, "row_index": dup_targets[1],
                      "expected_issue": "duplicate_loan_id"})

    # Duplicate borrower+amount+origination-date combination
    combo_targets = random.sample(
        [i for i in range(rows) if i not in issue_targets and i not in dup_targets], k=2
    )
    loans[combo_targets[1]].borrower_id = loans[combo_targets[0]].borrower_id
    loans[combo_targets[1]].original_principal = loans[combo_targets[0]].original_principal
    loans[combo_targets[1]].origination_date = loans[combo_targets[0]].origination_date
    expected.append({"loan_id": loans[combo_targets[1]].loan_id, "row_index": combo_targets[1],
                      "expected_issue": "duplicate_borrower_amount_origination_combo"})

    # Suspiciously repeated borrower (same borrower id on many rows)
    repeat_borrower = new_borrower_id()
    repeat_targets = random.sample(
        [i for i in range(rows) if i not in issue_targets], k=min(6, rows // 20 + 6)
    )
    for t in repeat_targets:
        loans[t].borrower_id = repeat_borrower
    expected.append({"loan_id": "(multiple)", "row_index": str(repeat_targets),
                      "expected_issue": "suspiciously_repeated_borrower"})

    fieldnames = list(asdict(loans[0]).keys())
    loan_tape_path = out_dir / "loan_tape.csv"
    with loan_tape_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for loan in loans:
            writer.writerow(asdict(loan))

    # Servicer update file: a subset of loans, some with conflicting values
    servicer_rows = []
    conflict_sample = random.sample(
        [i for i in range(rows) if i not in issue_targets], k=max(int(rows * 0.06), 5)
    )
    for idx in conflict_sample:
        loan = loans[idx]
        servicer_rows.append({
            "loan_id": loan.loan_id,
            "current_balance": round(loan.current_balance * random.uniform(0.85, 1.15), 2),
            "payment_status": random.choice(PAYMENT_STATUSES),
            "days_past_due": random.randint(0, 120),
            "servicer_name": random.choice(SERVICERS),
            "last_updated_at": rand_date(date(2025, 6, 1), date(2026, 8, 1)).isoformat(),
        })
        expected.append({"loan_id": loan.loan_id, "row_index": idx,
                          "expected_issue": "conflicting_values_between_sources"})

    with (out_dir / "servicer_update.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(servicer_rows[0].keys()))
        writer.writeheader()
        writer.writerows(servicer_rows)

    # Document manifest
    with (out_dir / "document_manifest.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["loan_id", "document_status"])
        writer.writeheader()
        for loan in random.sample(loans, k=int(rows * 0.9)):
            writer.writerow({"loan_id": loan.loan_id, "document_status": loan.document_status or "missing"})

    # Validation rules seed
    validation_rules = [
        {"rule_key": "required_loan_id", "field": "loan_id", "rule_type": "required",
         "params": {}, "severity": "critical", "message_template": "loan_id is required"},
        {"rule_key": "required_borrower_id", "field": "borrower_id", "rule_type": "required",
         "params": {}, "severity": "high", "message_template": "borrower_id is required"},
        {"rule_key": "valid_origination_date", "field": "origination_date", "rule_type": "regex",
         "params": {"pattern": r"^\d{4}-\d{2}-\d{2}$"}, "severity": "high",
         "message_template": "origination_date is not a valid ISO date"},
        {"rule_key": "maturity_after_origination", "field": "maturity_date", "rule_type": "date_order",
         "params": {"after": "origination_date"}, "severity": "critical",
         "message_template": "maturity_date must be after origination_date"},
        {"rule_key": "no_negative_principal", "field": "original_principal", "rule_type": "range",
         "params": {"min": 0}, "severity": "critical",
         "message_template": "original_principal cannot be negative"},
        {"rule_key": "balance_not_exceeding_principal", "field": "current_balance", "rule_type": "cross_field",
         "params": {"must_not_exceed": "original_principal"}, "severity": "high",
         "message_template": "current_balance exceeds original_principal"},
        {"rule_key": "interest_rate_range", "field": "interest_rate", "rule_type": "range",
         "params": {"min": 0.5, "max": 25.0}, "severity": "high",
         "message_template": "interest_rate is outside the expected range"},
        {"rule_key": "status_dpd_consistency", "field": "payment_status", "rule_type": "cross_field",
         "params": {"check": "status_dpd_consistency"}, "severity": "medium",
         "message_template": "payment_status is inconsistent with days_past_due"},
        {"rule_key": "required_document_status", "field": "document_status", "rule_type": "required",
         "params": {}, "severity": "medium", "message_template": "document_status is missing"},
        {"rule_key": "stale_record", "field": "last_updated_at", "rule_type": "staleness",
         "params": {"max_days": 365}, "severity": "low",
         "message_template": "record has not been updated in over a year"},
        {"rule_key": "valid_state_code", "field": "borrower_state", "rule_type": "regex",
         "params": {"pattern": "^(" + "|".join(US_STATES) + ")$"}, "severity": "medium",
         "message_template": "borrower_state is not a recognized US state code"},
        {"rule_key": "duplicate_loan_id", "field": "loan_id", "rule_type": "duplicate",
         "params": {"keys": ["loan_id"]}, "severity": "critical",
         "message_template": "loan_id appears more than once in this batch"},
        {"rule_key": "duplicate_borrower_amount_origination", "field": "borrower_id", "rule_type": "duplicate",
         "params": {"keys": ["borrower_id", "original_principal", "origination_date"]}, "severity": "high",
         "message_template": "borrower_id + original_principal + origination_date combination repeats"},
        {"rule_key": "closed_positive_balance", "field": "payment_status", "rule_type": "cross_field",
         "params": {"check": "closed_zero_balance"}, "severity": "high",
         "message_template": "loan is marked closed but still shows a positive balance"},
        {"rule_key": "cross_file_conflict", "field": None, "rule_type": "cross_file",
         "params": {"source": "servicer_update"}, "severity": "medium",
         "message_template": "value conflicts with servicer_update.csv"},
    ]
    with (out_dir / "validation_rules.json").open("w") as f:
        json.dump(validation_rules, f, indent=2)

    # Test users
    users = [
        {"email": "operator@testmail.dev", "role": "operator", "name": "Dana Operator"},
        {"email": "reviewer@testmail.dev", "role": "reviewer", "name": "Rae Reviewer"},
        {"email": "consumer@testmail.dev", "role": "consumer", "name": "Cam Consumer"},
    ]
    with (out_dir / "users.json").open("w") as f:
        json.dump(users, f, indent=2)

    with (out_dir / "expected_exception_sample.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["loan_id", "row_index", "expected_issue"])
        writer.writeheader()
        writer.writerows(expected)

    print(f"Generated {rows} loan rows -> {loan_tape_path}")
    print(f"Seeded {len(expected)} deliberate exception scenarios -> expected_exception_sample.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1500)
    parser.add_argument("--out", type=str, default="../data")
    args = parser.parse_args()
    generate(args.rows, Path(args.out))
