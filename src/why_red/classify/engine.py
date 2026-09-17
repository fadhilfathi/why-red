"""Stage 3: assign a FailureClass from the log. See docs/ARCHITECTURE.md."""

from __future__ import annotations

from why_red.classify.rules import RULES, Rule
from why_red.models.failure import Classification, Evidence, FailureClass
from why_red.models.run import Location
from why_red.text import strip_ansi, strip_timestamp


def classify(log_text: str, location: Location | None = None) -> Classification:
    """Scan every line of the job log for each rule's pattern. UNCLASSIFIED,
    confidence 0.0, no evidence, when no rule fires -- never a guess.

    A rule matches against the line with the GitHub Actions timestamp AND
    ANSI codes stripped -- every real line otherwise starts with a timestamp
    (`2026-09-16T10:00:00.1234567Z `), so an anchored pattern like pytest's
    own `^FAILED ...` would never match the raw line at all. `Evidence.text`
    itself keeps the model's contract of ANSI-stripped only (timestamp
    stripping is extract's job in P4, on the excerpt shown to a person).
    """
    display_lines = [strip_ansi(raw).rstrip("\r") for raw in log_text.split("\n")]
    match_lines = [strip_timestamp(line) for line in display_lines]
    hits: dict[str, list[Evidence]] = {}
    for rule in RULES:
        matches = [
            Evidence(line_no=idx, text=display_lines[idx - 1])
            for idx, line in enumerate(match_lines, start=1)
            if rule.pattern.search(line)
        ]
        if matches:
            hits[rule.rule_id] = matches

    if not hits:
        return Classification(failure_class=FailureClass.UNCLASSIFIED, confidence=0.0)

    step_end = location.line_range[1] if location and location.line_range else None
    best = max((r for r in RULES if r.rule_id in hits), key=lambda r: _rank(r, hits, step_end))
    evidence = hits[best.rule_id]
    return Classification(
        failure_class=best.failure_class,
        confidence=best.confidence,
        rule_id=best.rule_id,
        evidence=evidence,
        next_checks=list(best.next_checks),
    )


def _rank(rule: Rule, hits: dict[str, list[Evidence]], step_end: int | None) -> tuple[float, int]:
    """Highest confidence wins; a confidence tie is broken by the evidence line
    closest to the end of the failing step (the last error is usually the real
    one -- see docs/ARCHITECTURE.md stage 3)."""
    evidence = hits[rule.rule_id]
    if step_end is None:
        closeness = max(e.line_no for e in evidence)
    else:
        closeness = -min(abs(e.line_no - step_end) for e in evidence)
    return (rule.confidence, closeness)
