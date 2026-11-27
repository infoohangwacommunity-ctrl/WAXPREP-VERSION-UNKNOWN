"""
Test Exception Handlers - Stages 01-04, extended in Stage 15

Prove exception handler bodies execute correctly (the module docstring
previously cited only Stages 01-04; the behaviour now also covers the Stage 15
error taxonomy boundary, which preserves this exact public contract):
- validation_exception_handler (RequestValidationError)
- general_exception_handler (unhandled Exception)
- http_exception_handler is already covered by 404 tests in test_foundation.py
"""

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from waxprep.main import get_app


class TestValidationExceptionHandler:
    """Prove validation_exception_handler body (logger + JSONResponse) executes."""

    @pytest.fixture
    def client(self):
        app = get_app()

        # Add a temporary POST route with a Pydantic model to trigger validation errors.
        # This mutates the in-memory app instance only; source files are untouched.

        class TestModel(BaseModel):
            name: str
            count: int

        @app.post("/test-validation")
        async def validate_route(model: TestModel) -> JSONResponse:  # noqa: RUF029
            return JSONResponse(content={"ok": True})

        with TestClient(app) as test_client:
            yield test_client

    @pytest.mark.integration
    def test_validation_error_returns_422(self, client):
        """Prove RequestValidationError returns 422 with sanitized errors."""
        # Send valid JSON but wrong types to trigger Pydantic validation error
        response = client.post(
            "/test-validation",
            json={"name": 123, "count": "not-an-int"},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["detail"] == "Validation error"
        assert "errors" in data
        assert len(data["errors"]) > 0
        # Each error should have loc and msg
        for err in data["errors"]:
            assert "loc" in err
            assert "msg" in err

    @pytest.mark.integration
    def test_validation_error_does_not_leak_traceback(self, client):
        """Prove validation error response contains no traceback or file paths."""
        response = client.post(
            "/test-validation",
            json={"name": 123, "count": "not-an-int"},
        )
        data_str = str(response.json())
        assert "Traceback" not in data_str
        assert "File " not in data_str

    @pytest.mark.integration
    def test_validation_error_includes_correlation_id(self, client):
        """Prove validation error responses include X-Request-ID."""
        response = client.post(
            "/test-validation",
            json={"name": 123, "count": "not-an-int"},
        )
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    @pytest.mark.integration
    def test_malformed_json_triggers_validation_handler(self, client):
        """Prove malformed JSON body triggers RequestValidationError handler."""
        response = client.post(
            "/test-validation",
            content="not valid json{{{",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["detail"] == "Validation error"


class TestGeneralExceptionHandler:
    """Prove general_exception_handler body (logger.exception + JSONResponse) executes."""

    @pytest.fixture
    def client(self):
        app = get_app()

        # Add a temporary route that raises an unhandled exception.
        # This mutates the in-memory app instance only; source files are untouched.

        @app.get("/test-raise")
        async def raise_route() -> JSONResponse:  # noqa: RUF029
            raise ValueError("test unhandled exception")

        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client

    @pytest.mark.integration
    def test_unhandled_exception_returns_500(self, client):
        """Prove unhandled exception returns 500 with sanitized response."""
        response = client.get("/test-raise")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"

    @pytest.mark.integration
    def test_unhandled_exception_does_not_leak_traceback(self, client):
        """Prove 500 response contains no traceback or file paths."""
        response = client.get("/test-raise")
        data_str = str(response.json())
        assert "Traceback" not in data_str
        assert "File " not in data_str
        assert "ValueError" not in data_str
        assert "test unhandled exception" not in data_str

    @pytest.mark.integration
    def test_unhandled_exception_response_structure(self, client):
        """Prove 500 response has correct sanitized structure."""
        response = client.get("/test-raise")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"
        assert data["message"] == "An unexpected error occurred"
        # Verify no internal details leaked
        data_str = str(data)
        assert "Traceback" not in data_str
        assert "File " not in data_str
        assert "ValueError" not in data_str
        assert "test unhandled exception" not in data_str

    @pytest.mark.integration
    def test_different_exception_types_all_return_500(self, client):
        """Prove any Exception subclass is caught and returns 500."""
        # Add another temporary route with a different exception type
        app = get_app()

        @app.get("/test-raise-type")
        async def raise_type_route() -> JSONResponse:  # noqa: RUF029
            raise RuntimeError("different error type")

        response = client.get("/test-raise-type")
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"
