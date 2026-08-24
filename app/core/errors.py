"""One error shape for the whole API.

Everything a client sees is `{"error": {"code", "message", "details"}}`. `code`
is stable and machine-readable; `message` is written for a person, surfaces
directly in the admin UI, and follows the voice rules — say what failed and what
to do about it, never "Something went wrong".
"""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for every error this API raises deliberately."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class BadRequestError(ApiError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"


class UnauthorizedError(ApiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class NotFoundError(ApiError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(ApiError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class RateLimitedError(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class ServiceUnavailableError(ApiError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(code, message, details))


# Status codes Starlette raises on its own, mapped to stable codes so a 405 from
# the router and a 405 from a handler read identically to a client.
_STATUS_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_413_CONTENT_TOO_LARGE: "payload_too_large",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_failed",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
}


# Starlette types every handler as taking a bare `Exception`, so each one
# narrows to the class it was registered for.
async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    error = cast(ApiError, exc)
    return error_response(error.status_code, error.code, error.message, error.details)


async def http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    code = _STATUS_CODES.get(error.status_code, "http_error")
    detail = (
        error.detail if isinstance(error.detail, str) else "The request could not be completed."
    )
    response = error_response(error.status_code, code, detail)
    # Preserve WWW-Authenticate and friends; a 401 without it is not a 401.
    for key, value in (error.headers or {}).items():
        response.headers[key] = value
    return response


async def validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    details = [
        {
            "field": ".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in validation_error.errors()
    ]
    fields = ", ".join(item["field"] for item in details) or "the request body"
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_failed",
        f"Check {fields} — {len(details)} field(s) did not pass validation.",
        details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the traceback, return nothing internal. Request bodies are never
    # logged: some of them carry credentials.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "The API could not complete this request. Try again, and report it if it repeats.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
