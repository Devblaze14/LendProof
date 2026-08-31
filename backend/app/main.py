from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors import register_error_handlers
from app.routers import ai, audit, auth, exceptions, loans, uploads, verified
from app.routers.audit import summary_router
from app.routers.verified import export_router

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="Loan Data Verification Copilot", version="0.1.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
register_error_handlers(app)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(loans.router)
app.include_router(exceptions.router)
app.include_router(ai.router)
app.include_router(verified.router)
app.include_router(export_router)
app.include_router(audit.audit_router)
app.include_router(summary_router)


@app.get("/health")
def health():
    return {"status": "ok"}
