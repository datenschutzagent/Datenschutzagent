"""Request correlation ID middleware and context variable."""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ContextVar is set per-request; accessible anywhere in the call stack
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

HEADER_NAME = "x-request-id"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request.

    Uses the incoming ``x-request-id`` header when present; otherwise generates
    a new UUID4.  The value is stored in a ContextVar so services and logger
    calls deeper in the stack can reference it without threading issues.
    The ID is also echoed back in the response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get(HEADER_NAME) or str(uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[HEADER_NAME] = req_id
        return response


def get_request_id() -> str:
    """Return the current request's correlation ID (or '-' outside a request)."""
    return request_id_var.get()
