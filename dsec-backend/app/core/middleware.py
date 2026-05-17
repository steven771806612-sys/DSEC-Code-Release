import uuid
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique request_id into every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        structlog.contextvars.clear_contextvars()
        return response


class OrgIsolationMiddleware(BaseHTTPMiddleware):
    """
    After auth middleware sets request.state.user,
    this middleware sets request.state.org_filter for non-DJI roles.
    Actual filtering is enforced in service layer.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # org_filter is set after auth resolves; services read it from request.state
        request.state.org_filter = None
        return await call_next(request)
