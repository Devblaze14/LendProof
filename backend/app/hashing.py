"""
Hash-chain utility for verified_loan_records.

record_hash = SHA256(canonical_json(fields) + prev_hash)

Each loan's verified-record history forms its own chain. The first record
for a loan uses GENESIS as prev_hash. Recomputing the chain from audit_log
and comparing to the stored hash is the tamper-evidence check exposed as
"verify integrity" in the Consumer dashboard (see Master Plan §5, §9).

Deliberately NOT a real blockchain (out of scope per brief §16) — this is a
single-writer, database-backed hash chain, which gives genuine tamper
evidence without the distributed-consensus machinery the brief explicitly
doesn't ask for.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS = "0" * 64


def canonical_json(fields: dict[str, Any]) -> str:
    """Deterministic JSON serialization so the same logical record always
    hashes the same way regardless of dict ordering."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


def compute_record_hash(fields: dict[str, Any], prev_hash: str | None) -> str:
    prev = prev_hash or GENESIS
    payload = canonical_json(fields) + prev
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(records: list[dict[str, Any]]) -> tuple[bool, int | None]:
    """
    records: ordered oldest-to-newest, each a dict with keys
             'canonical_data', 'record_hash', 'prev_hash'.
    Returns (is_valid, first_broken_index_or_None).
    """
    expected_prev = GENESIS
    for i, record in enumerate(records):
        if (record.get("prev_hash") or GENESIS) != expected_prev:
            return False, i
        recomputed = compute_record_hash(record["canonical_data"], expected_prev)
        if recomputed != record["record_hash"]:
            return False, i
        expected_prev = record["record_hash"]
    return True, None
