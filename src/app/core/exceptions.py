"""Custom application exceptions and FastAPI exception handlers."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# ============================================
# Base exception
# ============================================


class AppException(Exception):
    """Base class for all application exceptions.

    Subclasses define `code`, `message` and `status_code`.
    """

    code: str = "INTERNAL_ERROR"
    message: str = "Внутренняя ошибка сервера"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


# ============================================
# Domain exceptions
# ============================================


class NotFoundError(AppException):
    """Resource not found."""

    code = "NOT_FOUND"
    message = "Ресурс не найден"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppException):
    """Conflict with current state (e.g. slot already booked)."""

    code = "CONFLICT"
    message = "Конфликт с текущим состоянием"
    status_code = status.HTTP_409_CONFLICT


class ForbiddenError(AppException):
    """Authenticated but not allowed to perform the action."""

    code = "FORBIDDEN"
    message = "Доступ запрещён"
    status_code = status.HTTP_403_FORBIDDEN


class UnauthorizedError(AppException):
    """Not authenticated or invalid credentials."""

    code = "UNAUTHORIZED"
    message = "Требуется авторизация"
    status_code = status.HTTP_401_UNAUTHORIZED


class BadRequestError(AppException):
    """Bad request (business logic violation)."""

    code = "BAD_REQUEST"
    message = "Некорректный запрос"
    status_code = status.HTTP_400_BAD_REQUEST


class RateLimitError(AppException):
    """Too many requests."""

    code = "RATE_LIMIT_EXCEEDED"
    message = "Слишком много запросов, попробуйте позже"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


# ============================================
# Helpers
# ============================================


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: Any | None = None,
) -> JSONResponse:
    """Build unified JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )


# ============================================
# Handlers
# ============================================


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """Handle all AppException subclasses."""
    return _error_response(exc.code, exc.message, exc.status_code, exc.details)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette/FastAPI HTTPException in unified format."""
    code_map: dict[int, str] = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return _error_response(code, str(exc.detail), exc.status_code)


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors in unified format."""
    return _error_response(
        code="VALIDATION_ERROR",
        message="Ошибка валидации данных",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        details=exc.errors(),
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected exceptions."""
    return _error_response(
        code="INTERNAL_ERROR",
        message="Внутренняя ошибка сервера",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=str(exc) if str(exc) else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
