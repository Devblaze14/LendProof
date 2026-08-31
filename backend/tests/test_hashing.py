import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.hashing import GENESIS, compute_record_hash, verify_chain  # noqa: E402


def test_first_record_uses_genesis():
    h = compute_record_hash({"loan_id": "LN-1", "balance": 100}, prev_hash=None)
    h_explicit = compute_record_hash({"loan_id": "LN-1", "balance": 100}, prev_hash=GENESIS)
    assert h == h_explicit


def test_hash_changes_if_fields_change():
    h1 = compute_record_hash({"loan_id": "LN-1", "balance": 100}, prev_hash=None)
    h2 = compute_record_hash({"loan_id": "LN-1", "balance": 101}, prev_hash=None)
    assert h1 != h2


def test_hash_is_order_independent_on_dict_keys():
    h1 = compute_record_hash({"a": 1, "b": 2}, prev_hash=None)
    h2 = compute_record_hash({"b": 2, "a": 1}, prev_hash=None)
    assert h1 == h2


def test_chain_of_three_verifies():
    r1_data = {"loan_id": "LN-1", "balance": 100}
    r1_hash = compute_record_hash(r1_data, None)
    r2_data = {"loan_id": "LN-1", "balance": 90}
    r2_hash = compute_record_hash(r2_data, r1_hash)
    r3_data = {"loan_id": "LN-1", "balance": 80}
    r3_hash = compute_record_hash(r3_data, r2_hash)

    chain = [
        {"canonical_data": r1_data, "record_hash": r1_hash, "prev_hash": None},
        {"canonical_data": r2_data, "record_hash": r2_hash, "prev_hash": r1_hash},
        {"canonical_data": r3_data, "record_hash": r3_hash, "prev_hash": r2_hash},
    ]
    valid, broken_at = verify_chain(chain)
    assert valid is True
    assert broken_at is None


def test_tampered_record_is_detected():
    r1_data = {"loan_id": "LN-1", "balance": 100}
    r1_hash = compute_record_hash(r1_data, None)
    r2_data = {"loan_id": "LN-1", "balance": 90}
    r2_hash = compute_record_hash(r2_data, r1_hash)

    chain = [
        {"canonical_data": r1_data, "record_hash": r1_hash, "prev_hash": None},
        {"canonical_data": r2_data, "record_hash": r2_hash, "prev_hash": r1_hash},
    ]
    # tamper: someone edits the first record's data after the fact without
    # recomputing hashes downstream
    chain[0]["canonical_data"] = {"loan_id": "LN-1", "balance": 999999}

    valid, broken_at = verify_chain(chain)
    assert valid is False
    assert broken_at == 0
