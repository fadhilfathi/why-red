"""Text normalisation shared by classify (P3) and extract (P4). Kept separate from
both so neither stage owns a dependency on the other for something this small."""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z ")


def strip_ansi(line: str) -> str:
    """Remove ANSI escape sequences. Evidence.text and ExcerptLine.text are
    contractually ANSI-stripped; nothing else about the line is changed."""
    return _ANSI_RE.sub("", line)


def strip_timestamp(line: str) -> str:
    """Remove the leading GitHub Actions timestamp, if present. Line numbers are
    unaffected -- this only changes what is displayed for a given line."""
    return _TIMESTAMP_RE.sub("", line)
