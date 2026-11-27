"""
Redaction - Stage 12

Defence-in-depth scrubbing for anything that leaves the process: logs, trace
attributes, metric labels, error payloads, and diagnostics.

Layer order (each layer catches what the previous one missed):
1. Sensitive *key* names are replaced wholesale (``password``, ``api_key``...).
2. Structural secrets inside strings are replaced by shape:
   bearer tokens, ``user:pass@`` URL segments, ``KEY=value`` assignments,
   PEM blocks, and well-known provider token prefixes.
3. Containers are walked recursively with a depth and size budget, so a
   pathological payload cannot hang the process or blow the stack.

Deliberate non-goals:
- This is not a secret *policy*. It must never be the only control; callers are
  still expected not to put secrets into events in the first place.
- Replacement is by marker, never by a partially masked value. A partial mask of
  a short secret can still leak most of it.
"""

from __future__ import annotations

import re
from typing import Any, Final

REDACTED: Final[str] = "[REDACTED]"

# Exact key names (lowercased) whose values are always replaced.
SENSITIVE_KEYS: Final[frozenset[str]] = frozenset({
    "password",
    "passwd",
    "passphrase",
    "secret",
    "client_secret",
    "secret_key",
    "private_key",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "auth_token",
    "token",
    "authorization",
    "cookie",
    "set-cookie",
    "session",
    "session_id",
    "credential",
    "credentials",
    "dsn",
    "database_url",
    "connection_string",
})

# Substrings that mark a key as sensitive (e.g. ``x-api-key``, ``db_password``).
_SENSITIVE_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
)

# Bounded traversal so adversarial payloads cannot hang or overflow the stack.
MAX_DEPTH: Final[int] = 6
MAX_ITEMS: Final[int] = 100
_MAX_STRING: Final[int] = 8192

_PEM_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._\-+/=]{8,}")
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)[^/\s:@]+:[^/\s@]+@")
_KEY_VALUE = re.compile(
    r"(?i)\b([a-z0-9_.\-]*(?:password|passwd|secret|token|api[_\-]?key|private[_\-]?key)"
    r"[a-z0-9_.\-]*)\s*[:=]\s*(\"[^\"]*\"|'[^']*'|[^\s,;&\"']+)"
)
# Well-known provider token shapes. Matched by prefix, not by full validation.
_PROVIDER_TOKENS = re.compile(
    r"\b(?:"
    r"gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9]{20,}"
    r"|xox[abposr]-[A-Za-z0-9\-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z\-_]{35}"
    r"|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    r")\b"
)


def is_sensitive_key(key: object) -> bool:
    """Return True when ``key`` names a value that must never be emitted.

    Separators are normalised so ``x-api-key``, ``x_api_key`` and ``X Api Key``
    are all recognised. Header names use hyphens while config uses underscores,
    and missing one spelling silently leaks the value.
    """
    if not isinstance(key, str):
        return False
    lowered = key.strip().lower()
    if lowered in SENSITIVE_KEYS:
        return True
    normalized = lowered.replace("-", "_").replace(" ", "_")
    if normalized in SENSITIVE_KEYS:
        return True
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def redact_text(value: str) -> str:
    """Replace structural secrets inside a single string.

    Order matters: PEM blocks are removed before key/value matching so that a
    multiline key body is not partially rewritten.
    """
    if not value:
        return value
    text = value[:_MAX_STRING]
    text = _PEM_BLOCK.sub(REDACTED, text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = _URL_CREDENTIALS.sub(lambda m: f"{m.group('scheme')}{REDACTED}@", text)
    text = _KEY_VALUE.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    return _PROVIDER_TOKENS.sub(REDACTED, text)


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Recursively return a copy of ``value`` with secrets replaced.

    Mapping keys are preserved (they are field names, not secrets) but their
    values are replaced when the key looks sensitive. Sequences are truncated to
    ``MAX_ITEMS`` and traversal stops at ``MAX_DEPTH``.
    """
    if _depth > MAX_DEPTH:
        return REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return REDACTED
    if isinstance(value, dict):
        scrubbed: dict[Any, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_ITEMS:
                break
            safe_key = redact_text(key) if isinstance(key, str) else key
            scrubbed[safe_key] = (
                REDACTED if is_sensitive_key(key) else redact(item, _depth=_depth + 1)
            )
        return scrubbed
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)[:MAX_ITEMS]
        scrubbed_items = [redact(item, _depth=_depth + 1) for item in items]
        return scrubbed_items if not isinstance(value, tuple) else tuple(scrubbed_items)
    # Unknown object: its repr may embed credentials, so do not leak it.
    return redact_text(repr(value))
