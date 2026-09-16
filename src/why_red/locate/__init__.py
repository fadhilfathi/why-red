"""Stage 2: find the failing job and step. Rules are numbered as in docs/ARCHITECTURE.md
and the chosen rule is written into `Location.reason`."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from why_red.models.run import Conclusion, Job, Location, Run, Step

_POST_RE = re.compile(r"^(Post |Complete job$)")
_CLEANUP_RE = re.compile(
    r"(?i)\b(cleanup|clean up|upload (test )?(artifact|report|coverage)|stop containers)\b"
)
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+Z ")

_JOB_LEVEL_FAILURES = frozenset(
    {Conclusion.FAILURE, Conclusion.TIMED_OUT, Conclusion.STARTUP_FAILURE, Conclusion.CANCELLED}
)


def failed_jobs(run: Run) -> list[Job]:
    """Rule 1: jobs that failed, in API order (matrix legs are separate jobs)."""
    return [j for j in run.jobs if j.conclusion in _JOB_LEVEL_FAILURES]


def locate(run: Run, job: Job | None = None) -> Location | None:
    """Pick the step that explains why `job` (default: first failed job) went red."""
    if job is None:
        jobs = failed_jobs(run)
        if not jobs:
            return None  # Rule 7
        job = jobs[0]

    failed = [s for s in job.steps if s.conclusion == Conclusion.FAILURE]
    if not failed:
        return _job_level_failure(job)  # Rule 6

    primary = [s for s in failed if not _is_post(s)]  # Rule 4a
    real = [s for s in primary if not _CLEANUP_RE.search(s.name)] or primary  # Rule 4b
    if not real:
        real = failed  # only post/cleanup steps failed: they are the failure

    chosen = _first_followed_by_skip(job, real) or real[0]  # Rule 3 / Rule 5
    reason = _reason(job, failed, chosen)
    others = [s.number for s in failed if s.number != chosen.number]
    return Location(
        job_id=job.id,
        job_name=job.name,
        step_number=chosen.number,
        step_name=chosen.name,
        reason=reason,
        other_failed_steps=others,
    )


def _is_post(step: Step) -> bool:
    return bool(_POST_RE.match(step.name))


def _first_followed_by_skip(job: Job, candidates: list[Step]) -> Step | None:
    """Rule 3: a real failure skips what comes after it; a continue-on-error failure does
    not. The API does not expose continue-on-error, so the skip is the only signal."""
    if len(candidates) < 2:
        return None
    by_number = sorted(job.steps, key=lambda s: s.number)
    for cand in candidates:
        idx = next(i for i, s in enumerate(by_number) if s.number == cand.number)
        nxt = by_number[idx + 1] if idx + 1 < len(by_number) else None
        if nxt is None or nxt.conclusion == Conclusion.SKIPPED or _is_post(nxt):
            return cand
    return None


def _reason(job: Job, failed: list[Step], chosen: Step) -> str:
    if _is_post(chosen) or _CLEANUP_RE.search(chosen.name):
        return "only post/cleanup steps failed"
    if len(failed) == 1:
        return "only failed step in job"
    others = [s for s in failed if s.number != chosen.number]
    if all(_is_post(s) or _CLEANUP_RE.search(s.name) for s in others):
        return "earliest failed step; later failures are post/cleanup steps"
    if chosen.number == min(s.number for s in failed):
        return "earliest failed step; later failures are downstream"
    return "first failed step followed by skipped steps (earlier failures look continue-on-error)"


def _job_level_failure(job: Job) -> Location | None:
    started = [s for s in job.steps if s.started_at is not None]
    if not started:
        if not job.steps:
            return Location(
                job_id=job.id,
                job_name=job.name,
                step_number=1,
                step_name="(no steps reported)",
                reason=f"job {job.conclusion.value} with zero steps",
            )
        last = job.steps[-1]
    else:
        last = max(started, key=lambda s: (s.started_at or datetime.min, s.number))
    return Location(
        job_id=job.id,
        job_name=job.name,
        step_number=last.number,
        step_name=last.name,
        reason=f"job {job.conclusion.value} without a failing step; last step that started",
    )


_STEP_START_RE = re.compile(r"^\S+Z (##\[group\]Run |Post job cleanup\.\s*$)")


def step_line_range(log_lines: list[str], step: Step) -> tuple[int, int] | None:
    """Map a step to a 1-based inclusive line span.

    Step times have whole-second precision, log lines have 100 ns precision, and
    neighbouring steps share their boundary second. Measured on a real log, the
    shared start second held 48 lines of the previous step's tail (cache-restore
    chatter) and one nested `##[group]Run` of that step's composite action. So:
    inside the start second the LAST step-opening marker (`##[group]Run ...` or
    `Post job cleanup.`) wins; inside the end second the FIRST such marker after
    the start closes the span. Elsewhere the timestamp alone decides. Lines
    without a timestamp belong to the preceding stamped line.
    """
    # ponytail: the run-level logs zip no longer ships per-step files (measured
    # 2026-09-16), so there is no exact source to upgrade to.
    if step.started_at is None or step.completed_at is None:
        return None
    start = step.started_at.astimezone(UTC).replace(microsecond=0)
    end = step.completed_at.astimezone(UTC).replace(microsecond=0)
    stamped = _seconds(log_lines)
    inside = [i for i, t in enumerate(stamped, start=1) if t is not None and start <= t <= end]
    if not inside:
        return None
    first, last = inside[0], inside[-1]
    for i in inside:
        if stamped[i - 1] == start and _STEP_START_RE.match(log_lines[i - 1]):
            first = i
    for i in inside:
        if i > first and stamped[i - 1] == end and _STEP_START_RE.match(log_lines[i - 1]):
            last = i - 1
            break
    return (first, last) if first <= last else None


def _seconds(log_lines: list[str]) -> list[datetime | None]:
    out: list[datetime | None] = []
    current: datetime | None = None
    for line in log_lines:
        m = _TS_RE.match(line)
        if m:
            current = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
        out.append(current)
    return out
