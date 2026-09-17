"""pipeline.classify_in's own branches: it must be honest about UNCLASSIFIED
before it ever touches a rule, for the two cases where there is nothing to
read (locate found nothing; the log for the located job never arrived)."""

from __future__ import annotations

from why_red.models.failure import FailureClass
from why_red.models.run import Location, Run
from why_red.pipeline import Loaded, classify_in


def _run() -> Run:
    return Run(id=1, repo="o/r", workflow_name="CI", run_number=1, event="push", head_sha="0" * 40)


def test_no_location_is_unclassified_without_touching_any_rule() -> None:
    loaded = Loaded(run=_run(), logs={1: "FAILED a::b - x\n"})
    result = classify_in(loaded, None)
    assert result.failure_class is FailureClass.UNCLASSIFIED
    assert result.confidence == 0.0
    assert result.evidence == []


def test_location_without_a_fetched_log_is_unclassified() -> None:
    loaded = Loaded(run=_run(), logs={})  # log for job 1 never arrived (see log_errors)
    loc = Location(job_id=1, job_name="j", step_number=1, step_name="s", reason="r")
    result = classify_in(loaded, loc)
    assert result.failure_class is FailureClass.UNCLASSIFIED
    assert result.confidence == 0.0


def test_location_with_a_fetched_log_runs_the_real_engine() -> None:
    loaded = Loaded(run=_run(), logs={1: "FAILED a::b - x\n"})
    loc = Location(job_id=1, job_name="j", step_number=1, step_name="s", reason="r")
    result = classify_in(loaded, loc)
    assert result.failure_class is FailureClass.TEST_FAILURE
