"""Runs the real classification engine against the full real corpus. This is
the test the P3 brief specifically asked for: every fixture outside the 3
shipped classes MUST come back UNCLASSIFIED, because a rule firing on a class
it was never built for is a confidently wrong answer -- worse than not
knowing. Reported on its own, not folded into the precision numbers."""

from __future__ import annotations

from fixtures.measure import measure

from why_red.classify.rules import SHIPPED_CLASSES
from why_red.models.failure import FailureClass


def test_shipped_classes_are_exactly_the_three_with_two_fixtures() -> None:
    assert {
        FailureClass.TEST_FAILURE,
        FailureClass.LINT_FAILURE,
        FailureClass.NETWORK_FAILURE,
    } == SHIPPED_CLASSES


def test_every_fixture_outside_the_shipped_classes_is_unclassified() -> None:
    rows = measure()
    unshipped = [r for r in rows if r.expected not in SHIPPED_CLASSES]
    assert unshipped, "corpus has no fixtures outside the shipped classes to check"
    leaked = [r for r in unshipped if r.predicted is not FailureClass.UNCLASSIFIED]
    assert leaked == [], (
        f"{len(leaked)}/{len(unshipped)} unshipped fixtures were misclassified "
        "instead of UNCLASSIFIED: " + ", ".join(f"{r.slug} -> {r.predicted.value}" for r in leaked)
    )


def test_every_shipped_class_fixture_is_correctly_classified() -> None:
    """The corpus is tiny (2 fixtures per shipped class), so precision and
    recall are expected to be 1.00 right now -- this pins that number so a
    future rule change that regresses it is caught immediately."""
    rows = measure()
    shipped = [r for r in rows if r.expected in SHIPPED_CLASSES]
    assert len(shipped) == 6
    wrong = [r for r in shipped if r.predicted != r.expected]
    assert wrong == [], [(r.slug, r.expected.value, r.predicted.value) for r in wrong]
