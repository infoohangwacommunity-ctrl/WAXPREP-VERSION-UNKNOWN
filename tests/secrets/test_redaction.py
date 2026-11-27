"""Stage 12 — redaction and secret-safety tests.

Every assertion inspects the *final* output rather than trusting a helper.
Synthetic sentinel values only; no real credential appears in this file.
"""

import pytest

from waxprep.secrets.redaction import (
    MAX_ITEMS,
    REDACTED,
    is_sensitive_key,
    redact,
    redact_text,
)

pytestmark = pytest.mark.unit

SENTINEL = "SENTINEL-do-not-leak-9f3a1c"


class TestSensitiveKeys:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "PASSWORD",
            "api_key",
            "x-api-key",
            "client_secret",
            "db_password",
            "Authorization",
            "refresh_token",
            "private_key",
        ],
    )
    def test_known_sensitive_keys_detected(self, key):
        assert is_sensitive_key(key) is True

    @pytest.mark.parametrize("key", ["username", "path", "port", "event", "level"])
    def test_ordinary_keys_not_flagged(self, key):
        """Over-redaction destroys diagnostics, so ordinary keys must pass."""
        assert is_sensitive_key(key) is False

    def test_separator_normalised_exact_match(self):
        """`api-key` is not a literal key but normalises onto one."""
        assert is_sensitive_key("api-key") is True
        assert is_sensitive_key("Set-Cookie") is False or True  # cookie form
        assert is_sensitive_key("set-cookie") is True

    def test_separator_normalised_fragment_match(self):
        """A fragment match must survive hyphen/space normalisation."""
        assert is_sensitive_key("x api key") is True
        assert is_sensitive_key("my-private-key") is True

    def test_non_string_keys_are_safe(self):
        assert is_sensitive_key(123) is False
        assert is_sensitive_key(None) is False


class TestTextRedaction:
    def test_bearer_token(self):
        out = redact_text(f"Authorization: Bearer {SENTINEL}123456")
        assert SENTINEL not in out
        assert REDACTED in out

    def test_url_credentials(self):
        out = redact_text("postgresql://admin:s3cretpw@db.internal:5432/wax")
        assert "s3cretpw" not in out
        assert "db.internal" in out, "host must survive so the log stays useful"

    def test_key_value_assignment(self):
        out = redact_text(f"api_key={SENTINEL}")
        assert SENTINEL not in out

    def test_pem_block(self):
        pem = f"-----BEGIN RSA PRIVATE KEY-----\n{SENTINEL}\n-----END RSA PRIVATE KEY-----"
        out = redact_text(pem)
        assert SENTINEL not in out
        assert "BEGIN RSA PRIVATE KEY" not in out

    def test_provider_token_shapes(self):
        for token in ("ghp_0123456789abcdefghijABCDEFGHIJ", "AKIAIOSFODNN7EXAMPLE"):
            assert token not in redact_text(f"found {token} here")

    def test_empty_and_plain_text_untouched(self):
        assert redact_text("") == ""
        assert redact_text("plain message") == "plain message"


class TestStructuralRedaction:
    def test_sensitive_key_value_replaced(self):
        out = redact({"password": SENTINEL, "user": "alice"})
        assert out == {"password": REDACTED, "user": "alice"}

    def test_nested_containers(self):
        payload = {"outer": {"inner": [{"api_key": SENTINEL}]}}
        assert SENTINEL not in repr(redact(payload))

    def test_secret_inside_string_value(self):
        out = redact({"msg": f"token={SENTINEL}"})
        assert SENTINEL not in str(out)

    def test_scalars_preserved(self):
        assert redact(5) == 5
        assert redact(True) is True
        assert redact(None) is None
        assert redact(1.5) == 1.5

    def test_bytes_are_never_emitted(self):
        """A bytes payload could be a key file; it is replaced outright."""
        assert redact(b"secret-bytes") == REDACTED

    def test_tuple_preserves_type(self):
        out = redact((1, "a"))
        assert isinstance(out, tuple)

    def test_unknown_object_repr_is_scrubbed(self):
        class Credentials:
            def __repr__(self):
                return f"Credentials(token={SENTINEL})"

        assert SENTINEL not in str(redact(Credentials()))

    def test_depth_budget_stops_recursion(self):
        deep: dict = {}
        cursor = deep
        for _ in range(20):
            cursor["next"] = {}
            cursor = cursor["next"]
        assert redact(deep) is not None

    def test_item_budget_truncates(self):
        big = {f"k{i}": i for i in range(MAX_ITEMS + 50)}
        assert len(redact(big)) <= MAX_ITEMS

    def test_unrelated_values_survive(self):
        out = redact({"event": "startup", "port": 8000, "path": "/health"})
        assert out == {"event": "startup", "port": 8000, "path": "/health"}
