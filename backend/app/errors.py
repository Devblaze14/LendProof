"""
Standard error envelope (see Production Readiness Playbook, Hat 4):
every error response, no exceptions:
    {"error": {"code": ..., "message": ..., "field": ..., "request_id": ...}}
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, field: str | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.field = field


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.detail,
                                "field": exc.field, "request_id": str(uuid.uuid4())[:8]}},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": exc.detail,
                                "field": None, "request_id": str(uuid.uuid4())[:8]}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:]) or None
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_FAILED", "message": first.get("msg", "Invalid request"),
                                "field": field, "request_id": str(uuid.uuid4())[:8]}},
        )
