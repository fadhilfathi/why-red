"""Schema invariants. Each test guards a constraint from docs/ARCHITECTURE.md."""

import pytest
from pydantic import ValidationError

from why_red.models import (
    Classification,
    Conclusion,
    Evidence,
    Excerpt,
    ExcerptLine,
    FailureClass,
    Job,
    Location,
    Report,
    Run,
    Step,
)


def _run() -> Run:
    return Run(
        id=1,
        repo="o/r",
        workflow_name="CI",
        run_number=7,
        event="push",
        head_sha="a" * 40,
        conclusion=Conclusion.FAILURE,
        jobs=[Job(id=10, name="gate", steps=[Step(number=1, name="test")])],
    )


def test_failure_class_has_sixteen_members_and_unclassified() -> None:
    assert len(FailureClass) == 16
    assert FailureClass.UNCLASSIFIED in FailureClass


def test_classified_result_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires at least one evidence line"):
        Classification(failure_class=FailureClass.TEST_FAILURE, confidence=0.9)


def test_unclassified_allows_no_evidence_but_forces_zero_confidence() -> None:
    ok = Classification(failure_class=FailureClass.UNCLASSIFIED, confidence=0.0)
    assert ok.evidence == []
    with pytest.raises(ValidationError, match=r"confidence 0.0"):
        Classification(failure_class=FailureClass.UNCLASSIFIED, confidence=0.5)


def test_confidence_bounded() -> None:
    ev = [Evidence(line_no=3, text="FAILED tests/test_x.py::test_y")]
    with pytest.raises(ValidationError):
        Classification(failure_class=FailureClass.TEST_FAILURE, confidence=1.5, evidence=ev)


def test_evidence_line_numbers_are_one_based() -> None:
    with pytest.raises(ValidationError):
        Evidence(line_no=0, text="x")


def test_excerpt_lines_must_ascend_and_fit_log() -> None:
    with pytest.raises(ValidationError, match="strictly ascending"):
        Excerpt(
            job_id=1,
            total_lines=10,
            lines=[ExcerptLine(line_no=5, text="a"), ExcerptLine(line_no=5, text="b")],
        )
    with pytest.raises(ValidationError, match="exceeds total_lines"):
        Excerpt(job_id=1, total_lines=3, lines=[ExcerptLine(line_no=4, text="a")])


def test_excerpt_compression_ratio() -> None:
    ex = Excerpt(
        job_id=1,
        total_lines=4000,
        lines=[ExcerptLine(line_no=n, text="") for n in range(1, 19)],
    )
    assert ex.compression_ratio == pytest.approx(4000 / 18)
    assert Excerpt(job_id=1, total_lines=4000).compression_ratio == 0.0


def test_run_ignores_unknown_api_fields_and_is_frozen() -> None:
    run = Run.model_validate({**_run().model_dump(), "unexpected_field": 1})
    assert run.id == 1
    with pytest.raises(ValidationError):
        run.id = 2  # type: ignore[misc]


def test_report_json_round_trip_preserves_line_numbers() -> None:
    report = Report(
        run=_run(),
        location=Location(
            job_id=10, job_name="gate", step_number=1, step_name="test", reason="only failed step"
        ),
        classification=Classification(
            failure_class=FailureClass.TEST_FAILURE,
            confidence=0.8,
            rule_id="pytest.failed",
            evidence=[Evidence(line_no=1234, text="FAILED tests/test_x.py::test_y")],
        ),
        excerpt=Excerpt(
            job_id=10,
            total_lines=4000,
            lines=[
                ExcerptLine(line_no=1234, text="FAILED tests/test_x.py::test_y", highlight=True)
            ],
        ),
    )
    back = Report.model_validate_json(report.model_dump_json())
    assert back == report
    assert back.excerpt.lines[0].line_no == back.classification.evidence[0].line_no == 1234
    assert back.ai is None
