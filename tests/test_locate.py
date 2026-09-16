"""Locate rules, one synthetic job per awkward case from the brief, plus the real
harvested fixture."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from why_red.locate import failed_jobs, locate, step_line_range
from why_red.models.run import Conclusion, Job, Run, Step
from why_red.pipeline import load_dir, locate_in

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cases"

S, F, K, U = Conclusion.SUCCESS, Conclusion.FAILURE, Conclusion.SKIPPED, Conclusion.UNKNOWN


def _job(*steps: tuple[int, str, Conclusion], conclusion: Conclusion = F, jid: int = 1) -> Job:
    return Job(
        id=jid,
        name=f"job{jid}",
        conclusion=conclusion,
        steps=[Step(number=n, name=name, conclusion=c) for n, name, c in steps],
    )


def _run(*jobs: Job) -> Run:
    return Run(
        id=1,
        repo="o/r",
        workflow_name="CI",
        run_number=1,
        event="push",
        head_sha="0" * 40,
        conclusion=F,
        jobs=list(jobs),
    )


def test_single_failure() -> None:
    loc = locate(_run(_job((1, "Set up job", S), (2, "Test", F), (3, "Post Set up", S))))
    assert loc is not None
    assert (loc.step_number, loc.reason) == (2, "only failed step in job")
    assert loc.other_failed_steps == []


def test_cleanup_step_after_real_failure_is_not_chosen() -> None:
    job = _job((1, "Build", S), (2, "Test", F), (3, "Upload coverage", F), (9, "Post Build", F))
    loc = locate(_run(job))
    assert loc is not None
    assert loc.step_number == 2
    assert loc.other_failed_steps == [3, 9]
    assert "post/cleanup" in loc.reason


def test_only_post_step_failed() -> None:
    loc = locate(_run(_job((1, "Build", S), (2, "Test", S), (9, "Post Build", F))))
    assert loc is not None
    assert (loc.step_number, loc.reason) == (9, "only post/cleanup steps failed")


def test_continue_on_error_failure_is_skipped_in_favour_of_real_one() -> None:
    # Step 2 failed but step 3 still ran: continue-on-error. Step 4 failed and 5 was skipped.
    job = _job(
        (1, "Setup", S), (2, "Flaky lint", F), (3, "Build", S), (4, "Test", F), (5, "Pub", K)
    )
    loc = locate(_run(job))
    assert loc is not None
    assert loc.step_number == 4
    assert loc.other_failed_steps == [2]
    assert "continue-on-error" in loc.reason


def test_multiple_red_steps_earliest_wins_when_nothing_skipped_after() -> None:
    job = _job((1, "A", F), (2, "B", F), (3, "C", S))
    loc = locate(_run(job))
    assert loc is not None
    assert loc.step_number == 1
    assert loc.reason == "earliest failed step; later failures are downstream"


def test_matrix_leg_first_failed_job_wins() -> None:
    ok = _job((1, "Test", S), conclusion=S, jid=1)
    red = _job((1, "Test", F), jid=2)
    run = _run(ok, red, _job((1, "Test", F), jid=3))
    assert [j.id for j in failed_jobs(run)] == [2, 3]
    loc = locate(run)
    assert loc is not None
    assert loc.job_id == 2


def test_job_failed_without_failing_step_uses_last_started() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    job = Job(
        id=5,
        name="build",
        conclusion=Conclusion.TIMED_OUT,
        steps=[
            Step(number=1, name="Setup", conclusion=S, started_at=t0),
            Step(number=2, name="Long test", conclusion=Conclusion.CANCELLED, started_at=t0),
            Step(number=3, name="Never ran", conclusion=K),
        ],
    )
    loc = locate(_run(job))
    assert loc is not None
    assert loc.step_number == 2
    assert loc.reason.startswith("job timed_out without a failing step")


def test_zero_steps_job() -> None:
    loc = locate(_run(Job(id=7, name="x", conclusion=Conclusion.STARTUP_FAILURE)))
    assert loc is not None
    assert loc.step_number == 1
    assert loc.reason == "job startup_failure with zero steps"


def test_nothing_failed_returns_none() -> None:
    assert locate(_run(_job((1, "Test", S), conclusion=S))) is None


def test_step_line_range_by_timestamp() -> None:
    lines = [
        "2026-01-01T00:00:00.1Z setup",
        "2026-01-01T00:00:05.0Z test start",
        "no timestamp, belongs to previous line",
        "2026-01-01T00:00:09.9Z test end",
        "2026-01-01T00:00:10.5Z post",
    ]
    step = Step(
        number=2,
        name="Test",
        conclusion=F,
        started_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 0, 0, 9, tzinfo=UTC),
    )
    assert step_line_range(lines, step) == (2, 4)
    assert step_line_range(lines, Step(number=9, name="x", conclusion=F)) is None


def test_real_fixture_locates_test_step_and_line_span() -> None:
    loaded = load_dir(FIXTURES / "pytest-test-failure-matrix")
    loc = locate_in(loaded)
    assert loc is not None
    assert loc.step_name == "Test without coverage"
    assert loc.line_range is not None
    lines = loaded.logs[loc.job_id].split("\n")
    first, last = loc.line_range
    span = "\n".join(lines[first - 1 : last])
    assert "##[error]Process completed with exit code 1." in span
    assert lines[first - 1].split("Z ", 1)[1].startswith("##[group]Run tox")
    assert "Post job cleanup." not in span
    assert lines[last].split("Z ", 1)[1].rstrip() == "Post job cleanup."
