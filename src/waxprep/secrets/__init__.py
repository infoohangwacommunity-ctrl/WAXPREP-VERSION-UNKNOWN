"""Secret safety primitives (Stage 12).

Pure package: standard library only, no vendor SDKs. Vendor secret stores are
wired in outer layers; this package only guarantees that values which do reach
logs, traces, or responses have already been scrubbed.
"""

from waxprep.secrets.redaction import (
    REDACTED,
    SENSITIVE_KEYS,
    is_sensitive_key,
    redact,
    redact_text,
)

__all__ = [
    "REDACTED",
    "SENSITIVE_KEYS",
    "is_sensitive_key",
    "redact",
    "redact_text",
]
