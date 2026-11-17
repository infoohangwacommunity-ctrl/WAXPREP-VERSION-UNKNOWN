"""
Request ID Middleware - Stage 02
Generates and propagates request correlation IDs.
Binds to structlog context for structured logging.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


def _validate_request_id(request_id: str) -> bool:
    """Validate that a request ID is a well-formed UUID.

    Returns True if valid, False otherwise.
    """
    try:
        uuid.UUID(request_id)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a correlation ID.

    - Generates new UUID if X-Request-ID header not present
    - Propagates existing X-Request-ID from upstream
    - Binds ID to structlog context for the request lifetime
    - Adds X-Request-ID to response headers
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Get or generate request ID
        incoming_id = request.headers.get("X-Request-ID")
        if incoming_id and _validate_request_id(incoming_id):
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        # Bind to structlog context
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            # Process request
            response = await call_next(request)

            # Add request ID to response
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Clear context after request
            structlog.contextvars.unbind_contextvars("request_id")
