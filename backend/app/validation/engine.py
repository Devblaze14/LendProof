"""
Config-driven validation rule engine.

Design intent (see docs/Requirements_SRS_and_AI_Build_Prompt.md, FR-VAL-2):
rules are DATA (rows in `validation_rules`, or the seed JSON before a DB
exists), not hardcoded per-field `if` statements. Disabling a rule stops it
from firing without a code change. Adding a new rule_type is the only case
that needs a code change — everything else is configuration.

This module has zero external dependencies (no DB, no HTTP) so it can be
unit tested in complete isolation, and so an AI-generated rule (brief
Module D: "generate validation rules from natural language") is just
another row this same interpreter already knows how to run, provided it
uses one of the existing rule_type values.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable


@dataclass
class Exception_:
    """One validation failure. Named Exception_ to avoid shadowing builtins.Exception."""
    rule_key: str
    field: str | None
    severity: str
    message: str
    row_ref: Any = None  # loan_id or row index, whatever the caller wants to trace by


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _rule_required(row: dict, rule: dict) -> list[str]:
    field = rule["field"]
    value = row.get(field)
    if value is None or str(value).strip() == "":
        return [rule["message_template"]]
    return []


def _rule_regex(row: dict, rule: dict) -> list[str]:
    field = rule["field"]
    value = row.get(field)
    if value is None or str(value).strip() == "":
        return []  # let the `required` rule own emptiness; regex only checks format
    pattern = rule["params"]["pattern"]
    if not re.match(pattern, str(value)):
        return [rule["message_template"]]
    return []


def _rule_range(row: dict, rule: dict) -> list[str]:
    field = rule["field"]
    raw = row.get(field)
    if raw is None or str(raw).strip() == "":
        return []
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return [f"{field} is not numeric"]
    params = rule["params"]
    if "min" in params and value < params["min"]:
        return [rule["message_template"]]
    if "max" in params and value > params["max"]:
        return [rule["message_template"]]
    return []


def _rule_date_order(row: dict, rule: dict) -> list[str]:
    field = rule["field"]
    other_field = rule["params"]["after"]
    d1, d2 = _parse_date(row.get(field)), _parse_date(row.get(other_field))
    if d1 is None or d2 is None:
        return []  # malformed dates are caught by their own regex/required rules
    if d1 <= d2:
        return [rule["message_template"]]
    return []


def _rule_cross_field(row: dict, rule: dict) -> list[str]:
    check = rule["params"].get("check")
    if check == "status_dpd_consistency":
        status, dpd = row.get("payment_status"), row.get("days_past_due")
        try:
            dpd = int(dpd)
        except (ValueError, TypeError):
            return []
        if status == "current" and dpd > 0:
            return [rule["message_template"]]
        if status in ("delinquent_30", "delinquent_60", "delinquent_90") and dpd == 0:
            return [rule["message_template"]]
        return []
    if check == "closed_zero_balance":
        status, balance = row.get("payment_status"), row.get("current_balance")
        try:
            balance = float(balance)
        except (ValueError, TypeError):
            return []
        if status == "closed" and balance > 0:
            return [rule["message_template"]]
        return []
    # must_not_exceed style (e.g. current_balance vs original_principal)
    cap_field = rule["params"].get("must_not_exceed")
    if cap_field:
        field = rule["field"]
        try:
            value, cap = float(row.get(field)), float(row.get(cap_field))
        except (ValueError, TypeError):
            return []
        if value > cap:
            return [rule["message_template"]]
    return []


def _rule_staleness(row: dict, rule: dict) -> list[str]:
    field = rule["field"]
    last_updated = row.get(field)
    try:
        # accept both date and datetime-ish strings
        d = _parse_date(str(last_updated)[:10])
    except Exception:
        d = None
    if d is None:
        return []
    max_days = rule["params"]["max_days"]
    reference_today = date(2026, 8, 29)
    if (reference_today - d).days > max_days:
        return [rule["message_template"]]
    return []


# duplicate and cross_file rules operate on the WHOLE batch, not a single row —
# handled separately in `run_batch_rules` below.

_ROW_RULE_DISPATCH: dict[str, Callable[[dict, dict], list[str]]] = {
    "required": _rule_required,
    "regex": _rule_regex,
    "range": _rule_range,
    "date_order": _rule_date_order,
    "cross_field": _rule_cross_field,
    "staleness": _rule_staleness,
}


def run_row_rules(row: dict, rules: list[dict]) -> list[Exception_]:
    """Applies every active, single-row rule_type to one normalized loan row."""
    findings: list[Exception_] = []
    for rule in rules:
        if not rule.get("active", True):
            continue
        handler = _ROW_RULE_DISPATCH.get(rule["rule_type"])
        if handler is None:
            continue  # duplicate/cross_file handled at batch level
        for message in handler(row, rule):
            findings.append(Exception_(
                rule_key=rule["rule_key"], field=rule.get("field"),
                severity=rule["severity"], message=message,
                row_ref=row.get("loan_id"),
            ))
    return findings


def run_duplicate_rules(rows: list[dict], rules: list[dict]) -> list[Exception_]:
    """Batch-level duplicate detection, keyed per rule's `params.keys`."""
    findings: list[Exception_] = []
    for rule in rules:
        if not rule.get("active", True) or rule["rule_type"] != "duplicate":
            continue
        keys = rule["params"]["keys"]
        seen: dict[tuple, list[int]] = defaultdict(list)
        for idx, row in enumerate(rows):
            key = tuple(str(row.get(k, "")).strip() for k in keys)
            if any(k == "" for k in key):
                continue  # blank keys are a `required` violation, not a duplicate
            seen[key].append(idx)
        for key, indices in seen.items():
            if len(indices) > 1:
                for idx in indices[1:]:  # first occurrence is the "original"
                    findings.append(Exception_(
                        rule_key=rule["rule_key"], field=rule.get("field"),
                        severity=rule["severity"], message=rule["message_template"],
                        row_ref=rows[idx].get("loan_id"),
                    ))
    return findings


def run_cross_file_rules(
    rows: list[dict], other_source_rows: list[dict], rules: list[dict]
) -> list[Exception_]:
    """Compares loan_tape rows against servicer_update rows for conflicting fields."""
    findings: list[Exception_] = []
    active_cross_file = [r for r in rules if r.get("active", True) and r["rule_type"] == "cross_file"]
    if not active_cross_file:
        return findings
    other_by_id = {r["loan_id"]: r for r in other_source_rows if r.get("loan_id")}
    compare_fields = ["current_balance", "payment_status", "days_past_due", "servicer_name"]
    for row in rows:
        other = other_by_id.get(row.get("loan_id"))
        if not other:
            continue
        for field in compare_fields:
            if field in other and str(row.get(field)) != str(other.get(field)):
                findings.append(Exception_(
                    rule_key=active_cross_file[0]["rule_key"], field=field,
                    severity=active_cross_file[0]["severity"],
                    message=f"{field}: loan_tape={row.get(field)!r} vs servicer_update={other.get(field)!r}",
                    row_ref=row.get("loan_id"),
                ))
    return findings


def run_batch(
    rows: list[dict], rules: list[dict], servicer_rows: list[dict] | None = None
) -> list[Exception_]:
    """Full validation pass over a batch: per-row rules + duplicate + cross-file."""
    findings: list[Exception_] = []
    for row in rows:
        findings.extend(run_row_rules(row, rules))
    findings.extend(run_duplicate_rules(rows, rules))
    if servicer_rows is not None:
        findings.extend(run_cross_file_rules(rows, servicer_rows, rules))
    return findings
