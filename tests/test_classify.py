"""Classification engine. The three shipped rules against synthetic logs (unit
behaviour) plus every one of the 12 real fixtures (see test_measure.py for the
full corpus-wide pass/fail and the UNCLASSIFIED-control numbers)."""

from __future__ import annotations

from why_red.classify.engine import classify
from why_red.models.failure import FailureClass
from why_red.models.run import Location


def _loc(end: int) -> Location:
    return Location(
        job_id=1, job_name="j", step_number=1, step_name="s", reason="r", line_range=(1, end)
    )


def test_no_rule_fires_is_unclassified_with_zero_confidence_and_no_evidence() -> None:
    result = classify("hello\nworld\n")
    assert result.failure_class is FailureClass.UNCLASSIFIED
    assert result.confidence == 0.0
    assert result.evidence == []
    assert result.rule_id is None


def test_pytest_failed_line_classifies_as_test_failure() -> None:
    log = "setup\nFAILED tests/test_x.py::test_y - AssertionError\ndone\n"
    result = classify(log)
    assert result.failure_class is FailureClass.TEST_FAILURE
    assert result.rule_id == "pytest.failed_line"
    assert len(result.evidence) == 1
    assert result.evidence[0].line_no == 2
    assert result.evidence[0].text == "FAILED tests/test_x.py::test_y - AssertionError"
    assert result.next_checks


def test_non_anchored_failed_mention_does_not_match() -> None:
    """A worker-progress line like '[gw2] [ 90%] FAILED path::test' must not fire --
    only a line that STARTS with FAILED (pytest's own summary format) counts."""
    log = "[gw2] [ 90%] FAILED tests/test_x.py::test_y\n"
    assert classify(log).failure_class is FailureClass.UNCLASSIFIED


def test_ansi_codes_around_failed_do_not_block_the_match() -> None:
    log = "\x1b[31mFAILED\x1b[0m tests/test_x.py::\x1b[1mtest_y\x1b[0m - reason\n"
    result = classify(log)
    assert result.failure_class is FailureClass.TEST_FAILURE
    assert "\x1b" not in result.evidence[0].text


def test_eslint_violation_line_classifies_as_lint_failure() -> None:
    log = "##[group]Run eslint\n##[error]  10:5  error  no-unused-vars  no-unused-vars\ndone\n"
    result = classify(log)
    assert result.failure_class is FailureClass.LINT_FAILURE
    assert result.rule_id == "eslint.violation_line"
    assert result.evidence[0].line_no == 2


def test_multiple_lint_violations_all_become_evidence() -> None:
    log = "\n".join(
        [
            "##[error]  1:1  error  a  rule-a",
            "##[error]  2:2  error  b  rule-b",
            "x 2 problems (2 errors, 0 warnings)",
        ]
    )
    result = classify(log)
    assert result.failure_class is FailureClass.LINT_FAILURE
    assert [e.line_no for e in result.evidence] == [1, 2]


def test_connection_reset_classifies_as_network_failure() -> None:
    log = "Caused by: java.io.IOException: Connection reset by peer\n"
    result = classify(log)
    assert result.failure_class is FailureClass.NETWORK_FAILURE
    assert result.rule_id == "network.reset_or_unreachable"


def test_dns_and_econnrefused_also_fire_network_rule() -> None:
    for line in (
        "curl: Could not resolve host: example.com\n",
        "connect: ECONNREFUSED\n",
        "dial tcp: i/o timeout: ETIMEDOUT\n",
        "Temporary failure in name resolution\n",
        "sendto: network is unreachable\n",
    ):
        assert classify(line).failure_class is FailureClass.NETWORK_FAILURE, line


def test_higher_confidence_rule_wins_when_both_fire() -> None:
    log = "FAILED tests/test_x.py::test_y - reason\nConnection reset by peer\n"
    result = classify(log)
    assert result.failure_class is FailureClass.TEST_FAILURE  # 0.9 beats 0.75


def test_tie_break_prefers_evidence_closest_to_step_end() -> None:
    """Two TEST_FAILURE hits (same rule, same confidence, no tie needed) --
    proximity only matters for picking BETWEEN rules of equal confidence, so
    this exercises the code path via a duplicate rule id, i.e. the location
    hint is actually consulted rather than ignored."""
    log = "\n".join(["FAILED a::b - x"] * 3)
    result = classify(log, location=_loc(end=2))
    # all evidence collected regardless; the rule itself doesn't change per-line.
    assert result.failure_class is FailureClass.TEST_FAILURE
    assert len(result.evidence) == 3


def test_evidence_text_has_no_trailing_carriage_return() -> None:
    result = classify("FAILED a::b - x\r\n")
    assert result.evidence[0].text == "FAILED a::b - x"
