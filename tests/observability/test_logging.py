"""Stage 13 — logging contract, correlation, and redaction tests."""

import json

import pytest
import structlog

from waxprep.observability import logging as logging_module
from waxprep.observability.logging import configure_logging, is_configured

pytestmark = pytest.mark.unit

SENTINEL = "SENTINEL-log-secret-4b2e"


@pytest.fixture(autouse=True)
def _restore_logging():
    """Each test configures logging itself; restore defaults afterwards."""
    yield
    structlog.reset_defaults()
    logging_module._configured = False


def _capture(capsys, *, level="INFO", json_output=True):
    configure_logging(level=level, json_output=json_output, environment="test")
    structlog.get_logger().info("probe_event", port=8000)
    return capsys.readouterr().out


class TestLoggingContract:
    def test_emits_valid_json_with_required_fields(self, capsys):
        out = _capture(capsys)
        line = next(line for line in out.splitlines() if "probe_event" in line)
        payload = json.loads(line)
        for field in (
            "timestamp",
            "level",
            "event",
            "service.name",
            "service.version",
            "deployment.environment",
        ):
            assert field in payload, f"missing required field {field}"
        assert payload["event"] == "probe_event"
        assert payload["port"] == 8000

    def test_timestamp_is_utc_iso8601(self, capsys):
        out = _capture(capsys)
        payload = json.loads(next(line for line in out.splitlines() if "probe_event" in line))
        assert payload["timestamp"].endswith("Z")

    def test_level_is_reflected(self, capsys):
        configure_logging(level="DEBUG", json_output=True)
        structlog.get_logger().warning("warn_event", port=1)
        out = capsys.readouterr().out
        payload = json.loads(next(line for line in out.splitlines() if "warn_event" in line))
        assert payload["level"] == "warning"

    def test_level_filtering_suppresses_below_threshold(self, capsys):
        configure_logging(level="ERROR", json_output=True)
        structlog.get_logger().debug("debug_event")
        structlog.get_logger().info("info_event")
        out = capsys.readouterr().out
        assert "debug_event" not in out
        assert "info_event" not in out

    def test_console_renderer_used_when_json_disabled(self, capsys):
        out = _capture(capsys, json_output=False)
        assert "probe_event" in out
        with pytest.raises(json.JSONDecodeError):
            json.loads(next(line for line in out.splitlines() if "probe_event" in line))

    def test_repeated_configure_does_not_duplicate_events(self, capsys):
        """App factories and reloads call configure repeatedly in tests."""
        configure_logging(level="INFO", json_output=True)
        configure_logging(level="INFO", json_output=True)
        configure_logging(level="INFO", json_output=True)
        structlog.get_logger().info("once_only")
        out = capsys.readouterr().out
        assert out.count("once_only") == 1

    def test_is_configured_flag(self):
        assert is_configured() is False
        configure_logging(level="INFO")
        assert is_configured() is True


class TestLoggingRedaction:
    def test_sensitive_field_value_never_reaches_output(self, capsys):
        configure_logging(level="INFO", json_output=True)
        structlog.get_logger().info("auth_probe", password=SENTINEL)
        out = capsys.readouterr().out
        assert SENTINEL not in out
        assert "[REDACTED]" in out

    def test_secret_embedded_in_message_is_scrubbed(self, capsys):
        configure_logging(level="INFO", json_output=True)
        structlog.get_logger().info("call_failed", reason=f"api_key={SENTINEL}")
        assert SENTINEL not in capsys.readouterr().out

    def test_nested_payload_is_scrubbed(self, capsys):
        configure_logging(level="INFO", json_output=True)
        structlog.get_logger().info("nested", config={"client_secret": SENTINEL})
        assert SENTINEL not in capsys.readouterr().out

    def test_exception_traceback_is_scrubbed_but_preserved(self, capsys):
        """Internally useful stack detail survives; the credential does not."""
        configure_logging(level="INFO", json_output=True)
        try:
            raise RuntimeError(f"token={SENTINEL}")
        except RuntimeError:
            structlog.get_logger().exception("boom")
        out = capsys.readouterr().out
        assert SENTINEL not in out
        assert "RuntimeError" in out, "exception type must remain for diagnosis"


class TestCorrelation:
    def test_request_id_binds_into_events(self, capsys):
        configure_logging(level="INFO", json_output=True)
        structlog.contextvars.bind_contextvars(request_id="req-abc")
        try:
            structlog.get_logger().info("in_request")
        finally:
            structlog.contextvars.clear_contextvars()
        payload = json.loads(
            next(line for line in capsys.readouterr().out.splitlines() if "in_request" in line)
        )
        assert payload["request_id"] == "req-abc"

    def test_context_is_cleared_between_requests(self, capsys):
        configure_logging(level="INFO", json_output=True)
        structlog.contextvars.clear_contextvars()
        structlog.get_logger().info("no_context")
        payload = json.loads(
            next(line for line in capsys.readouterr().out.splitlines() if "no_context" in line)
        )
        assert "request_id" not in payload
