from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit_event(
    db: Session, event_type: str, actor_id: UUID | None = None,
    loan_record_id: UUID | None = None, detail: dict | None = None,
    record_hash: str | None = None,
) -> AuditLog:
    """The ONLY function in this codebase that should ever write to
    audit_log. Never call db.add(AuditLog(...)) directly elsewhere — route
    every audit write through here so the append-only guarantee (Production
    Readiness Playbook, Hat 4: 'never write an UPDATE or DELETE against it')
    stays enforced by convention, not just by policy."""
    entry = AuditLog(
        event_type=event_type, actor_id=actor_id, loan_record_id=loan_record_id,
        detail=detail or {}, record_hash=record_hash,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
