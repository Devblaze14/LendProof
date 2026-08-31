from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import AIRecommendation, ExceptionRecord, Profile, ValidationRule
from app.schemas import GenerateRuleIn
from app.security import require_role
from app.services import ai_service
from app.services.ai_service import AIUnavailableError
from app.services.audit import write_audit_event

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/summarize-batch")
def summarize_batch(status: str = "open", db: Session = Depends(get_db),
                     profile: Profile = Depends(require_role("reviewer"))):
    exceptions = db.query(ExceptionRecord).filter(ExceptionRecord.status == status).limit(200).all()
    if not exceptions:
        raise AppError(404, "NO_EXCEPTIONS", f"No exceptions with status '{status}' to summarize")
    payload = [{"rule_key": e.rule_key, "severity": e.severity, "detail": e.detail} for e in exceptions]
    try:
        response_json, model, latency_ms = ai_service.summarize_batch(payload)
    except AIUnavailableError as e:
        raise AppError(503, "AI_UNAVAILABLE", "The AI assistant is temporarily unavailable.") from e

    rec = AIRecommendation(exception_id=None, prompt="summarize_batch", model=model,
                            response_json=response_json, latency_ms=latency_ms)
    db.add(rec)
    db.commit()
    write_audit_event(db, event_type="ai.recommendation_generated", actor_id=profile.id,
                       detail={"type": "batch_summary", "count": len(exceptions)})
    return response_json


@router.post("/generate-rule")
def generate_rule(payload: GenerateRuleIn, db: Session = Depends(get_db),
                   profile: Profile = Depends(require_role("reviewer", "operator"))):
    try:
        response_json, model, latency_ms = ai_service.generate_rule_from_text(payload.instruction)
    except AIUnavailableError as e:
        raise AppError(503, "AI_UNAVAILABLE", "The AI assistant is temporarily unavailable.") from e

    rule = ValidationRule(
        rule_key=response_json.get("rule_key", "ai_generated_rule"),
        field=response_json.get("field"), rule_type=response_json.get("rule_type", "range"),
        params=response_json.get("params", {}), severity=response_json.get("severity", "medium"),
        message_template=response_json.get("message_template", "AI-generated rule violation"),
        source="ai_generated", active=False,  # inactive until a human approves it — FR-AI-4
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    write_audit_event(db, event_type="ai.recommendation_generated", actor_id=profile.id,
                       detail={"type": "rule_generation", "rule_id": str(rule.id), "active": False})
    return {"rule_id": str(rule.id), "active": False, "ai_response": response_json}
