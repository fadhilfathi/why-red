"""Fetch + cache behaviour against a scripted `gh` on PATH."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import FakeGh
from why_red.fetch import github
from why_red.fetch.github import GhError, LogUnavailableError, build_run, fetch_job_log
from why_red.pipeline import load_run

RUN = {
    "id": 42,
    "name": "CI",
    "run_number": 3,
    "run_attempt": 1,
    "event": "push",
    "head_branch": "main",
    "head_sha": "f" * 40,
    "status": "completed",
    "conclusion": "failure",
    "updated_at": "2026-09-16T10:00:00Z",
    "html_url": "https://github.com/o/r/actions/runs/42",
    "some_new_field": {"ignored": True},
}
JOBS = {
    "jobs": [
        {"id": 1, "name": "ok", "status": "completed", "conclusion": "success", "steps": []},
        {
            "id": 2,
            "name": "red",
            "status": "completed",
            "conclusion": "failure",
            "steps": [
                {"number": 1, "name": "Setup", "status": "completed", "conclusion": "success"},
                {"number": 2, "name": "Test", "status": "completed", "conclusion": "failure"},
            ],
        },
    ]
}
LOG = "﻿2026-09-16T10:00:00.0000000Z hello\r\n2026-09-16T10:00:01.0000000Z FAIL\n"


def _arm(fake: FakeGh, log: object = LOG, log_status: int = 200) -> None:
    fake.respond("repos/o/r/actions/runs/42/jobs", JOBS)
    fake.respond("repos/o/r/actions/runs/42", RUN)
    fake.respond("repos/o/r/actions/jobs/2/logs", log, status=log_status)


def test_only_get_requests_exist_in_fetch_module() -> None:
    source = Path(github.__file__).read_text(encoding="utf-8")
    assert not re.search(r"(-X|--method|\b(POST|PATCH|PUT|DELETE)\b)", source)


def test_build_run_maps_payload_and_ignores_unknown_fields() -> None:
    run = build_run("o/r", RUN, JOBS["jobs"])
    assert (run.workflow_name, run.repo, run.conclusion.value) == ("CI", "o/r", "failure")
    assert run.updated_at is not None
    assert [j.conclusion.value for j in run.jobs] == ["success", "failure"]
    assert run.jobs[1].steps[1].conclusion.value == "failure"


def test_job_log_strips_bom_and_keeps_line_endings(fake_gh: FakeGh) -> None:
    _arm(fake_gh)
    text = fetch_job_log("o/r", 2)
    assert not text.startswith("﻿")
    assert "hello\r\n" in text


@pytest.mark.parametrize("status", [404, 410])
def test_missing_or_expired_log_is_unavailable(fake_gh: FakeGh, status: int) -> None:
    _arm(fake_gh, log="", log_status=status)
    with pytest.raises(LogUnavailableError) as exc:
        fetch_job_log("o/r", 2)
    assert exc.value.status == status


def test_in_progress_blob_not_found_is_unavailable(fake_gh: FakeGh) -> None:
    xml = '﻿<?xml version="1.0"?><Error><Code>BlobNotFound</Code></Error>'
    _arm(fake_gh, log=xml)
    with pytest.raises(LogUnavailableError, match="still running"):
        fetch_job_log("o/r", 2)


def test_other_gh_failure_propagates(fake_gh: FakeGh) -> None:
    _arm(fake_gh, log="", log_status=500)
    with pytest.raises(GhError) as exc:
        fetch_job_log("o/r", 2)
    assert not isinstance(exc.value, LogUnavailableError)
    assert exc.value.status == 500


def _log_calls(fake: FakeGh) -> list[list[str]]:
    return [c for c in fake.calls if c[1].endswith("/logs")]


def test_second_load_serves_log_from_cache(fake_gh: FakeGh, tmp_path: Path) -> None:
    _arm(fake_gh)
    first = load_run("o/r", 42, tmp_path / "cache")
    assert first.logs[2] == LOG.removeprefix("﻿")
    assert len(_log_calls(fake_gh)) == 1
    second = load_run("o/r", 42, tmp_path / "cache")
    assert second.logs == first.logs
    assert len(_log_calls(fake_gh)) == 1, "log must come from cache"
    assert len(fake_gh.calls) == 5, "metadata (run + jobs) is fetched every time"


def test_rerun_with_new_updated_at_refetches(fake_gh: FakeGh, tmp_path: Path) -> None:
    _arm(fake_gh)
    load_run("o/r", 42, tmp_path / "cache")
    fake_gh.respond("repos/o/r/actions/runs/42", {**RUN, "updated_at": "2026-09-16T11:00:00Z"})
    load_run("o/r", 42, tmp_path / "cache")
    assert len(_log_calls(fake_gh)) == 2


def test_no_cache_always_fetches(fake_gh: FakeGh) -> None:
    _arm(fake_gh)
    load_run("o/r", 42, None)
    load_run("o/r", 42, None)
    assert len(_log_calls(fake_gh)) == 2


def test_unavailable_log_is_reported_not_raised(fake_gh: FakeGh) -> None:
    _arm(fake_gh, log="", log_status=410)
    loaded = load_run("o/r", 42, None)
    assert loaded.logs == {}
    assert "410" in loaded.log_errors[2]
