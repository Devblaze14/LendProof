"""
Groq integration service.

Resilience rules (Production Readiness Playbook, Hat 4 / Antigravity Build
Package Section 1) implemented here:
  - 10s hard timeout
  - exponential backoff, max 2 retries, only on 5xx/timeout, never on 4xx
  - on exhausted retries: raise AIUnavailableError so the caller can show
    the "AI unavailable, continue manually" state — the reviewer's approve/
    reject workflow must never be blocked by this.

GROQ_MOCK=true (the default in this repo, and in .env.example) runs every
call against a local fixture instead of the network, so the entire AI
panel is demonstrable offline. Flip it to false and set GROQ_API_KEY to
call the real model — no other code changes needed, the interface is
identical either way.

Model choice: openai/gpt-oss-120b for reasoning calls, openai/gpt-oss-20b
for high-volume/summary calls. Do NOT use llama-3.3-70b-versatile or
llama-3.1-8b-instant — both are being retired by Groq.
"""
from __future__ import annotations

import json
import time

import httpx

from app.config import get_settings

settings = get_settings()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class AIUnavailableError(Exception):
    pass


def _call_groq(model: str, system_prompt: str, user_prompt: str) -> tuple[dict, int]:
    """Returns (parsed_json_response, latency_ms). Raises AIUnavailableError
    if all retries are exhausted."""
    if settings.groq_mock:
        return _mock_response(user_prompt), 40

    headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    last_error: Exception | None = None
    for attempt in range(3):  # 1 initial + 2 retries
        start = time.monotonic()
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(GROQ_ENDPOINT, headers=headers, json=payload)
            latency_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError("Groq 5xx", request=resp.request, response=resp)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content), latency_ms
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code < 500:
                raise AIUnavailableError(f"Groq request rejected: {e}") from e
            last_error = e
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_error = e
        time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s
    raise AIUnavailableError(f"Groq unavailable after retries: {last_error}")


def _mock_response(user_prompt: str) -> dict:
    """Deterministic offline fixture so the AI panel is fully demonstrable
    without a Groq key. Shape matches what the real model is prompted to
    return for each call type."""
    if "SUMMARIZE_BATCH" in user_prompt:
        return {"summary": "Most exceptions in this batch are missing/invalid dates and "
                            "duplicate loan IDs; a smaller cluster involves cross-file "
                            "balance conflicts with the servicer update file.",
                "top_severity": "high", "recommended_focus": "duplicate_loan_id"}
    if "GENERATE_RULE" in user_prompt:
        return {"rule_key": "ai_generated_placeholder", "field": "interest_rate",
                "rule_type": "range", "params": {"min": 1.0, "max": 20.0}, "severity": "medium",
                "message_template": "interest_rate outside AI-suggested range",
                "confidence": 0.62}
    return {
        "explanation": "This record failed because the recorded value violates the "
                        "configured rule for this field.",
        "likely_cause": "Manual data entry error or a stale export from the source system.",
        "suggested_value": None,
        "severity_classification": "medium",
        "confidence": 0.71,
    }


def explain_exception(rule_message: str, row_context: dict) -> tuple[dict, str, int]:
    system = ("You are a loan-data quality assistant. Given a validation failure and the "
              "surrounding record fields, explain the likely cause and suggest a correction. "
              "Respond ONLY as JSON: {explanation, likely_cause, suggested_value, "
              "severity_classification, confidence}.")
    user = f"EXPLAIN_EXCEPTION\nRule failure: {rule_message}\nRecord: {json.dumps(row_context, default=str)}"
    response, latency = _call_groq(settings.groq_model_primary, system, user)
    return response, settings.groq_model_primary, latency


def summarize_batch(exceptions: list[dict]) -> tuple[dict, str, int]:
    system = ("You summarize a batch of loan data-quality exceptions for a human reviewer. "
              "Respond ONLY as JSON: {summary, top_severity, recommended_focus}.")
    user = f"SUMMARIZE_BATCH\n{json.dumps(exceptions, default=str)}"
    response, latency = _call_groq(settings.groq_model_fast, system, user)
    return response, settings.groq_model_fast, latency


def generate_rule_from_text(instruction: str) -> tuple[dict, str, int]:
    system = ("You translate a natural-language data-quality instruction into one "
              "validation_rules row. Respond ONLY as JSON: {rule_key, field, rule_type "
              "(one of required|range|regex|date_order|cross_field|duplicate|staleness|"
              "cross_file), params, severity, message_template, confidence}.")
    user = f"GENERATE_RULE\n{instruction}"
    response, latency = _call_groq(settings.groq_model_primary, system, user)
    return response, settings.groq_model_primary, latency
