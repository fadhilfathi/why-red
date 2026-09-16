"""Filesystem cache for run metadata and job logs.

Layout: <cache_dir>/<owner>__<name>/<run_id>/<updated_at>/{run.json, <job_id>.log}

`updated_at` is part of the key so a re-run of the same run id (which keeps the
id and bumps `updated_at`) never serves stale logs. The cost of that guarantee is
one small metadata request per invocation; job logs, the expensive part, are
served from disk on every repeat.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from why_red.models.run import Run


def default_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "why-red"


class RunCache:
    def __init__(self, root: Path, run: Run) -> None:
        stamp = run.updated_at.strftime("%Y%m%dT%H%M%SZ") if run.updated_at else "unknown"
        self.dir = root / run.repo.replace("/", "__") / str(run.id) / stamp

    def _log_path(self, job_id: int) -> Path:
        return self.dir / f"{job_id}.log"

    def get_log(self, job_id: int) -> str | None:
        path = self._log_path(job_id)
        if not path.is_file():
            return None
        with path.open(encoding="utf-8", newline="") as fh:
            return fh.read()

    def put_log(self, job_id: int, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        # newline="" keeps the log byte-for-byte so line numbers stay honest.
        with self._log_path(job_id).open("w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def put_run(self, run: Run) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
