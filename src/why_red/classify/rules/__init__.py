"""Rules are data, per docs/ARCHITECTURE.md: one rule per shipped class, each a
compiled pattern plus a fixed confidence decided when the rule was written and
never tuned against the corpus afterward (see docs/CONTRIBUTING.md).

Only classes with >=2 real fixtures in the P2 corpus get a rule (P2 decision,
docs/LABELING.md's per-class count table). A rule for a class below that bar
is exactly the "tuned to one example" the brief forbids.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from why_red.models.failure import FailureClass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    failure_class: FailureClass
    pattern: re.Pattern[str]
    confidence: float
    next_checks: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="pytest.failed_line",
        failure_class=FailureClass.TEST_FAILURE,
        # pytest's own summary format: "FAILED <path>::<test> - <reason>".
        # Confirmed against both TEST_FAILURE fixtures (pytest-dev/pytest,
        # strands-agents/evals); neither fixture's other FAILED-shaped lines
        # (a per-worker progress notice, a per-test debugger label) match this
        # anchored form.
        pattern=re.compile(r"^FAILED \S+::\S+"),
        confidence=0.9,
        next_checks=(
            "Re-run the named test in isolation: pytest <path>::<test>.",
            "Check whether the assertion or fixture it depends on changed recently.",
        ),
    ),
    Rule(
        rule_id="eslint.violation_line",
        failure_class=FailureClass.LINT_FAILURE,
        # GitHub Actions annotates each eslint violation as its own
        # "##[error]  LINE:COL  error  <message>  <rule>" line. Confirmed
        # against both LINT_FAILURE fixtures (vitejs/vite, same rule set on
        # two different runs -- see docs/LABELING.md on why that pair is
        # weaker diversity than it looks).
        pattern=re.compile(r"^##\[error\]\s+\d+:\d+\s+error\s+"),
        confidence=0.9,
        next_checks=(
            "Run the linter locally with --fix for mechanically fixable rules.",
            "Review the remaining reported rule ids for the ones needing a manual fix.",
        ),
    ),
    Rule(
        rule_id="network.reset_or_unreachable",
        failure_class=FailureClass.NETWORK_FAILURE,
        # The exact phrases docs/LABELING.md's NETWORK_FAILURE criteria row
        # names. Only "Connection reset by peer" is confirmed against a real
        # fixture (spring-projects/spring-boot, twice); the others are the
        # documented criteria, not yet backed by a harvested example, so this
        # rule's confidence sits below the other two shipped rules.
        pattern=re.compile(
            r"Connection reset by peer"
            r"|Could not resolve host"
            r"|Temporary failure in name resolution"
            r"|\bECONNREFUSED\b"
            r"|\bETIMEDOUT\b"
            r"|network is unreachable"
        ),
        confidence=0.75,
        next_checks=(
            "Re-run the job: this class of failure is usually transient.",
            "If it recurs, check the target host or service's own status page.",
        ),
    ),
)

SHIPPED_CLASSES: frozenset[FailureClass] = frozenset(r.failure_class for r in RULES)
"""Derived from RULES, not hand-maintained: a class is 'shipped' exactly when a
rule for it exists, so this set can never drift from what the engine does."""
