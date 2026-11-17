"""
Test Middleware Skeletons - Stage 02
Prove skeleton middleware classes can be instantiated and have correct signatures.
"""

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from waxprep.middleware.base import HeaderSanitizationMiddleware, TimingMiddleware


class TestTimingMiddleware:
    """Prove TimingMiddleware skeleton is properly structured."""

    def test_can_be_instantiated(self):
        """Prove TimingMiddleware can be instantiated without errors."""
        middleware = TimingMiddleware(app=None)
        assert middleware is not None

    def test_is_base_http_middleware_subclass(self):
        """Prove TimingMiddleware inherits from BaseHTTPMiddleware."""
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(TimingMiddleware, BaseHTTPMiddleware)

    def test_dispatch_method_exists(self):
        """Prove TimingMiddleware has a dispatch method."""
        assert hasattr(TimingMiddleware, "dispatch")
        assert callable(TimingMiddleware.dispatch)

    def test_dispatch_signature_accepts_request_and_call_next(self):
        """Prove dispatch method accepts request and call_next parameters."""
        sig = inspect.signature(TimingMiddleware.dispatch)
        params = list(sig.parameters.keys())

        # Should have 'self', 'request', 'call_next'
        assert "self" in params
        assert "request" in params
        assert "call_next" in params

    def test_dispatch_returns_response(self):
        """Prove dispatch method return annotation is Response."""
        sig = inspect.signature(TimingMiddleware.dispatch)
        return_annotation = sig.return_annotation

        # Should be Response or a Union containing Response
        assert return_annotation is not inspect.Parameter.empty
        # Check it's Response type (may be typing.Any in some cases)
        if hasattr(return_annotation, "__origin__"):
            # It's a generic like Union[Response, ...]
            args = return_annotation.__args__
            assert Response in args or Any in args
        else:
            assert return_annotation is Response

    @pytest.mark.asyncio
    async def test_dispatch_calls_call_next_and_returns_response(self):
        """Prove dispatch delegates to call_next and returns its response."""
        middleware = TimingMiddleware(app=None)

        mock_request = MagicMock(spec=Request)
        mock_response = MagicMock(spec=Response)
        mock_call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, mock_call_next)

        assert result is mock_response
        mock_call_next.assert_called_once_with(mock_request)


class TestHeaderSanitizationMiddleware:
    """Prove HeaderSanitizationMiddleware skeleton is properly structured."""

    def test_can_be_instantiated(self):
        """Prove HeaderSanitizationMiddleware can be instantiated without errors."""
        middleware = HeaderSanitizationMiddleware(app=None)
        assert middleware is not None

    def test_is_base_http_middleware_subclass(self):
        """Prove HeaderSanitizationMiddleware inherits from BaseHTTPMiddleware."""
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(HeaderSanitizationMiddleware, BaseHTTPMiddleware)

    def test_dispatch_method_exists(self):
        """Prove HeaderSanitizationMiddleware has a dispatch method."""
        assert hasattr(HeaderSanitizationMiddleware, "dispatch")
        assert callable(HeaderSanitizationMiddleware.dispatch)

    def test_dispatch_signature_accepts_request_and_call_next(self):
        """Prove dispatch method accepts request and call_next parameters."""
        sig = inspect.signature(HeaderSanitizationMiddleware.dispatch)
        params = list(sig.parameters.keys())

        # Should have 'self', 'request', 'call_next'
        assert "self" in params
        assert "request" in params
        assert "call_next" in params

    def test_dispatch_returns_response(self):
        """Prove dispatch method return annotation is Response."""
        sig = inspect.signature(HeaderSanitizationMiddleware.dispatch)
        return_annotation = sig.return_annotation

        # Should be Response or a Union containing Response
        assert return_annotation is not inspect.Parameter.empty
        if hasattr(return_annotation, "__origin__"):
            args = return_annotation.__args__
            assert Response in args or Any in args
        else:
            assert return_annotation is Response

    def test_sensitive_headers_class_attribute_exists(self):
        """Prove SENSITIVE_HEADERS class attribute exists."""
        assert hasattr(HeaderSanitizationMiddleware, "SENSITIVE_HEADERS")
        assert isinstance(HeaderSanitizationMiddleware.SENSITIVE_HEADERS, frozenset)

    def test_sensitive_headers_contains_expected_values(self):
        """Prove SENSITIVE_HEADERS contains the expected sensitive header names."""
        expected = frozenset({"X-Internal-Token", "X-Debug-Info"})
        assert HeaderSanitizationMiddleware.SENSITIVE_HEADERS == expected

    def test_sensitive_headers_is_not_empty(self):
        """Prove SENSITIVE_HEADERS is not empty."""
        assert len(HeaderSanitizationMiddleware.SENSITIVE_HEADERS) > 0

    def test_sensitive_headers_can_be_accessed_on_instance(self):
        """Prove SENSITIVE_HEADERS accessible from instance via self."""
        middleware = HeaderSanitizationMiddleware(app=None)
        assert hasattr(middleware, "SENSITIVE_HEADERS")
        assert middleware.SENSITIVE_HEADERS == HeaderSanitizationMiddleware.SENSITIVE_HEADERS

    @pytest.mark.asyncio
    async def test_dispatch_calls_call_next_and_returns_response(self):
        """Prove dispatch delegates to call_next and returns its response."""
        middleware = HeaderSanitizationMiddleware(app=None)

        mock_request = MagicMock(spec=Request)
        mock_response = MagicMock(spec=Response)
        mock_call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, mock_call_next)

        assert result is mock_response
        mock_call_next.assert_called_once_with(mock_request)
