import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ApiError(BaseModel):
    code: str
    message: str
    field_errors: dict[str, list[str]] | None = None


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        self.status, self.code, self.message, self.retry_after = status, code, message, retry_after


def error_response(status: int, code: str, message: str, fields=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ApiError(code=code, message=message, field_errors=fields).model_dump(
            exclude_none=True
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        response = error_response(exc.status, exc.code, exc.message)
        if exc.retry_after is not None:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed"}
        return error_response(
            exc.status_code,
            codes.get(exc.status_code, "request_error"),
            "Nie można wykonać żądania.",
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, list[str]] = {}
        for error in exc.errors():
            key = ".".join(str(part) for part in error["loc"])
            fields.setdefault(key, []).append("Nieprawidłowa wartość.")
        return error_response(422, "validation_error", "Sprawdź podane dane.", fields)

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        # Details may contain driver URLs or credentials; report only the exception type.
        logging.getLogger(__name__).error("Unhandled API exception: %s", type(exc).__name__)
        return error_response(500, "internal_error", "Wystąpił błąd usługi.")
