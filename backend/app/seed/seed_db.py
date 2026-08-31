"""
Local-mode seed script: creates the 3 test users referenced in
TEST_CREDENTIALS.md and loads validation_rules.json into the DB.
Run once after applying migrations/001_init_local.sql.

    python -m app.seed.seed_db
"""
from __future__ import annotations

import json
from pathlib import Path

from app.db import SessionLocal
from app.models import AppUser, Profile, ValidationRule
from app.security import hash_password

DATA_DIR = Path(__file__).resolve().parents[2].parent / "data"

DEMO_PASSWORD = "DemoPass123!"

USERS = [
    {"email": "operator@testmail.dev", "role": "operator", "name": "Dana Operator"},
    {"email": "reviewer@testmail.dev", "role": "reviewer", "name": "Rae Reviewer"},
    {"email": "consumer@testmail.dev", "role": "consumer", "name": "Cam Consumer"},
]


def seed():
    db = SessionLocal()
    try:
        for u in USERS:
            existing = db.query(AppUser).filter(AppUser.email == u["email"]).first()
            if existing:
                continue
            user = AppUser(email=u["email"], password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)
            db.flush()
            db.add(Profile(id=user.id, role=u["role"], name=u["name"]))
        db.commit()

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
        print(f"Seeded {len(USERS)} users (password: {DEMO_PASSWORD}) and validation rules.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
