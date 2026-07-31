from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def success(data: Any = None, message: str = "") -> dict[str, Any]:
    return {
        "code": 200,
        "data": data if data is not None else {},
        "message": message,
    }


def error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "data": data if data is not None else {},
        "message": message,
    }


def _format_validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "参数错误"

    first = errors[0]
    msg = first.get("msg", "参数错误")
    if msg.startswith("Value error, "):
        return msg.removeprefix("Value error, ")
    return msg


async def validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=error(400, _format_validation_message(exc)),
    )


async def http_exception_handler(
    _: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
    elif isinstance(detail, list) and detail:
        message = str(detail[0])
    else:
        message = "请求失败"

    return JSONResponse(
        status_code=200,
        content=error(exc.status_code, message),
    )
