"""Wires fetch + cache + locate. Later stages plug in here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from why_red.classify.engine import classify
from why_red.fetch.cache import RunCache
from why_red.fetch.github import (
    LogUnavailableError,
    build_run,
    fetch_job_log,
    fetch_jobs_payload,
    fetch_run_payload,
)
from why_red.locate import failed_jobs, locate, step_line_range
from why_red.models.failure import Classification, FailureClass
from why_red.models.run import Location, Run


@dataclass
class Loaded:
    run: Run
    logs: dict[int, str] = field(default_factory=dict)  # job id -> raw log text
    log_errors: dict[int, str] = field(default_factory=dict)  # job id -> why no log


def load_run(repo: str, run_id: int, cache_root: Path | None) -> Loaded:
    """Two metadata requests always (run, jobs); the log of the located job comes
    from cache when the run's `updated_at` has not changed. Only that one log is
    fetched: a 22-leg matrix at ~3 s per log is not worth waiting for up front."""
    run = build_run(repo, fetch_run_payload(repo, run_id), fetch_jobs_payload(repo, run_id))
    cache = RunCache(cache_root, run) if cache_root else None
    if cache:
        cache.put_run(run)
    loaded = Loaded(run=run)
    loc = locate(run)
    for job in [j for j in failed_jobs(run) if loc and j.id == loc.job_id]:
        text = cache.get_log(job.id) if cache else None
        if text is None:
            try:
                text = fetch_job_log(repo, job.id)
            except LogUnavailableError as exc:
                loaded.log_errors[job.id] = str(exc)
                continue
            if cache:
                cache.put_log(job.id, text)
        loaded.logs[job.id] = text
    return loaded


def load_dir(directory: Path) -> Loaded:
    """Load a cache entry or a fixture: run.json plus <job_id>.log files."""
    run = Run.model_validate_json((directory / "run.json").read_text(encoding="utf-8"))
    loaded = Loaded(run=run)
    for path in directory.glob("*.log"):
        with path.open(encoding="utf-8", newline="") as fh:
            loaded.logs[int(path.stem)] = fh.read()
    return loaded


def locate_in(loaded: Loaded) -> Location | None:
    """Locate the failing step and, when the log exists, its line span."""
    loc = locate(loaded.run)
    if loc is None:
        return None
    text = loaded.logs.get(loc.job_id)
    if text is None:
        return loc
    job = next(j for j in loaded.run.jobs if j.id == loc.job_id)
    step = next((s for s in job.steps if s.number == loc.step_number), None)
    if step is None:
        return loc
    span = step_line_range(text.split("\n"), step)
    return loc.model_copy(update={"line_range": span})


def classify_in(loaded: Loaded, location: Location | None) -> Classification:
    """UNCLASSIFIED, honestly, when there is no location or no log to read --
    never a guess made without evidence in hand."""
    if location is None:
        return Classification(failure_class=FailureClass.UNCLASSIFIED, confidence=0.0)
    text = loaded.logs.get(location.job_id)
    if text is None:
        return Classification(failure_class=FailureClass.UNCLASSIFIED, confidence=0.0)
    return classify(text, location)
