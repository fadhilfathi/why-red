"""Read-only GitHub access through the `gh` CLI.

Only GET requests are ever issued. `gh api` defaults to GET and this module never
passes a method flag; tests grep for that. Measured behaviour this code relies on
is recorded in docs/API_NOTES.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

from why_red.models.run import Job, Run

_STATUS_RE = re.compile(r"HTTP (\d{3})")
_BLOB_NOT_FOUND = b"<Code>BlobNotFound</Code>"
_BOM = "﻿".encode()


class GhError(RuntimeError):
    """`gh` exited non-zero. `status` is the HTTP status when one was reported."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LogUnavailableError(GhError):
    """The job log does not exist (yet): in-progress job, expired run, or bad id."""


def gh_api(path: str, *paginate_key: str) -> bytes:
    """Run `gh api <path>` and return the raw body.

    With `paginate_key`, every page is fetched and the arrays under that key are
    concatenated into one JSON object `{key: [...]}`.
    """
    gh = shutil.which("gh")  # honours PATHEXT on Windows, unlike a bare "gh"
    if gh is None:
        msg = "gh CLI not found on PATH; install it and run `gh auth login`"
        raise GhError(msg)
    cmd = [gh, "api", path]
    if paginate_key:
        cmd += ["--paginate", "--slurp"]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        match = _STATUS_RE.search(stderr)
        status = int(match.group(1)) if match else None
        msg = f"gh api {path} failed: {stderr or proc.stdout[:200]!r}"
        raise GhError(msg, status)
    if not paginate_key:
        return proc.stdout
    key = paginate_key[0]
    pages: list[dict[str, Any]] = json.loads(proc.stdout)
    merged = [item for page in pages for item in page.get(key, [])]
    return json.dumps({key: merged}).encode()


def fetch_run_payload(repo: str, run_id: int) -> dict[str, Any]:
    body = gh_api(f"repos/{repo}/actions/runs/{run_id}")
    data: dict[str, Any] = json.loads(body)
    return data


def fetch_jobs_payload(repo: str, run_id: int) -> list[dict[str, Any]]:
    body = gh_api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", "jobs")
    jobs: list[dict[str, Any]] = json.loads(body)["jobs"]
    return jobs


def fetch_job_log(repo: str, job_id: int) -> str:
    """Return the job log as text with the UTF-8 BOM removed and line endings kept.

    GitHub answers 200 with an Azure `BlobNotFound` XML document while the job is
    still running, so that case is turned into LogUnavailableError here.
    """
    try:
        body = gh_api(f"repos/{repo}/actions/jobs/{job_id}/logs")
    except GhError as exc:
        if exc.status in (404, 410):
            msg = f"log for job {job_id} unavailable (HTTP {exc.status})"
            raise LogUnavailableError(msg, exc.status) from exc
        raise
    if body.removeprefix(_BOM).lstrip().startswith(b"<?xml") and _BLOB_NOT_FOUND in body:
        msg = f"log for job {job_id} not written yet (job still running?)"
        raise LogUnavailableError(msg, 200)
    return body.decode("utf-8", "replace").removeprefix("\ufeff")


def build_run(repo: str, run: dict[str, Any], jobs: list[dict[str, Any]]) -> Run:
    """Map raw API payloads onto the Run model. Unknown fields are dropped by the model."""
    return Run.model_validate(
        {
            **run,
            "repo": repo,
            "workflow_name": run.get("name") or run.get("workflow_name") or "",
            "conclusion": run.get("conclusion") or "unknown",
            "jobs": [_job(j) for j in jobs],
        }
    )


def _job(job: dict[str, Any]) -> Job:
    steps = [
        {**s, "conclusion": s.get("conclusion") or "unknown"} for s in (job.get("steps") or [])
    ]
    return Job.model_validate(
        {**job, "conclusion": job.get("conclusion") or "unknown", "steps": steps}
    )
