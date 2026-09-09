from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def error_response(request: Request, status: int, code: str, message: str, headers=None):
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message,
                 "requestId": getattr(request.state, "request_id", str(uuid4()))},
        headers=headers,
    )


def register_errors(app: FastAPI):
    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = {404: "NOT_FOUND", 409: "IDEMPOTENCY_CONFLICT", 501: "NOT_IMPLEMENTED"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return error_response(request, exc.status_code, code, str(exc.detail), exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(request, 422, "VALIDATION_ERROR", "请求参数不符合接口约定")

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return error_response(request, 500, "INTERNAL_ERROR", "服务暂时无法处理请求")
