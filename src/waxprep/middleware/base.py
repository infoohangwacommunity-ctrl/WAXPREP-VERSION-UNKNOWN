"""
Base Middleware Patterns - Stage 02
Reference implementations for common middleware patterns.

These are skeletons - real implementations go in separate modules.
Uncomment and customize when needed.
"""

from typing import Callable, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import structlog

logger = structlog.get_logger()


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Skeleton: Request timing middleware.
    
    Measures request duration for observability.
    Uncomment and customize when needed.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # import time
        # start = time.perf_counter()
        # response = await call_next(request)
        # duration = time.perf_counter() - start
        # response.headers["X-Response-Time"] = str(duration)
        # logger.info("request_completed", duration=duration, path=request.url.path)
        return await call_next(request)


class HeaderSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Skeleton: Header sanitization middleware.
    
    Remove sensitive headers from responses.
    Uncomment and customize when needed.
    """

    # Headers to strip from responses
    SENSITIVE_HEADERS = frozenset({"X-Internal-Token", "X-Debug-Info"})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # response = await call_next(request)
        # for header in self.SENSITIVE_HEADERS:
        #     response.headers.pop(header, None)
        # return response
        return await call_next(request)
