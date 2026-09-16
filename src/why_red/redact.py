"""Scrub secrets and identifying strings from log text before it is committed as a
fixture. Replacements keep the line count and, where possible, the line shape, so
line numbers in labels stay valid."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # GitHub tokens: classic, fine-grained, app, oauth, refresh.
    (re.compile(r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}\b"), "<GITHUB_TOKEN>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<AWS_ACCESS_KEY>"),
    (re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test)[-_][A-Za-z0-9]{16,}\b"), "<API_KEY>"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b"), "<SLACK_TOKEN>"),
    (
        re.compile(r"(?i)\b(bearer|token|authorization)([:= ]+)[A-Za-z0-9._~+/=-]{16,}"),
        r"\1\2<REDACTED>",
    ),
    (re.compile(r"https?://[^/\s:@]+:[^@\s]+@"), "https://<CREDENTIALS>@"),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "<PRIVATE_KEY>",
    ),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<EMAIL>"),
    (re.compile(r"\b[a-z0-9.-]+\.(?:local|internal|corp|lan|intranet)\b"), "<INTERNAL_HOST>"),
    (
        re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)(?:\.\d{1,3}){2,3}\b"),
        "<PRIVATE_IP>",
    ),
]


def redact(text: str, replacements: dict[str, str] | None = None) -> str:
    """Apply built-in patterns, then literal `replacements` (e.g. org names)."""
    for pattern, sub in _PATTERNS:
        text = pattern.sub(sub, text)
    for old, new in (replacements or {}).items():
        text = text.replace(old, new)
    return text
