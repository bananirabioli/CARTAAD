from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.guardrails.hard_rules import HardRuleViolation
from app.i18n import t


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str | None = None, details: dict[str, Any] | None = None, **params: Any):
        self.status = status
        self.code = code
        self.message = message or t(f"errors.{code}", **params)
        self.details = details or {}
        super().__init__(self.message)


def not_found() -> AppError:
    return AppError(404, "not_found")


def invalid(detail: str) -> AppError:
    return AppError(422, "invalid_value", detail=detail)


def conflict(detail: str) -> AppError:
    return AppError(409, "conflict", detail=detail)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(HardRuleViolation)
    async def _hard_rule(_: Request, exc: HardRuleViolation) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "hard_rule", "rule_id": exc.rule_id, "message": exc.message, "details": exc.details}},
        )
