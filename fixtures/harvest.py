"""Harvest one failed public run into fixtures/cases/<slug>/ and pin it in MANIFEST.json.

    uv run python fixtures/harvest.py <slug> <owner/name> <run-id> [--replace OLD=NEW ...]

Writes run.json (Run model) and <job_id>.log for the located failing job, both
redacted. Re-running with the same slug overwrites. Labels are added by hand in
label.json afterwards (see docs/LABELING.md, P2).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from why_red.pipeline import load_run
from why_red.redact import redact

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
MANIFEST = ROOT / "MANIFEST.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("repo")
    ap.add_argument("run_id", type=int)
    ap.add_argument("--replace", action="append", default=[], metavar="OLD=NEW")
    args = ap.parse_args(argv)
    replacements = dict(item.split("=", 1) for item in args.replace)

    loaded = load_run(args.repo, args.run_id, cache_root=None)
    if not loaded.logs:
        print(f"no log fetched: {loaded.log_errors or 'no failed job'}", file=sys.stderr)
        return 1

    out = CASES / args.slug
    out.mkdir(parents=True, exist_ok=True)
    run_json = redact(loaded.run.model_dump_json(indent=2), replacements)
    (out / "run.json").write_text(run_json, encoding="utf-8")
    for job_id, text in loaded.logs.items():
        with (out / f"{job_id}.log").open("w", encoding="utf-8", newline="") as fh:
            fh.write(redact(text, replacements))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    manifest[args.slug] = {
        "repo": args.repo,
        "run_id": args.run_id,
        "head_sha": loaded.run.head_sha,
        "run_attempt": loaded.run.run_attempt,
        "jobs": sorted(loaded.logs),
        "harvested_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": loaded.run.html_url,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sizes = ", ".join(f"{j}: {len(t.splitlines())} lines" for j, t in loaded.logs.items())
    print(f"wrote {out} ({sizes})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
