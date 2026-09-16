# Roadmap

## P0 — Scaffolding (done 2026-09-16)

- [x] Repo is public.
- [x] CI green on Python 3.11, 3.12, 3.13.
- [x] Security workflow (gitleaks full history + pinned-action check) green.
- [ ] PyPI package name `why-red` reserved (owner-side step; name confirmed free 2026-09-16).
- [x] Pydantic schemas (run, classification, excerpt, report) documented in `docs/ARCHITECTURE.md`.
- [x] No tags cut yet.

## P1 — Fetch + cache + locate (done 2026-09-16)

- [x] `gh api` fetch of run, jobs, and logs implemented; in-progress (200 + XML), expired (410) and missing (404) logs handled explicitly. Measurements in `docs/API_NOTES.md`.
- [x] Filesystem cache keyed by run ID + `updated_at`; a second invocation makes zero log calls (the two metadata calls always run so a re-run is never served stale), proven by a test using a fake `gh`. `--cache-dir` and `--no-cache` added.
- [x] Locates the failing job + step on synthetic cases: single failure, multiple red steps, continue-on-error step, cleanup-step-after-real-failure, matrix leg, job-level timeout, zero-step job; and on one real harvested fixture with a verified step line span.
- [x] Harvest script committed (`fixtures/harvest.py`), pins in `fixtures/MANIFEST.json`, redaction with tests.

## P2 — Fixture corpus (not started)

- [ ] Labeling criteria doc (`docs/LABELING.md`) committed before any label is assigned.
- [ ] 25 redacted fixtures spanning Python, Node, Go, Rust, Java, Docker. Composition over count: every class P3 intends to ship has at least 2 fixtures; at least 5 of the 25 are awkward cases (cleanup-masked failure, matrix leg, continue-on-error, stack trace with exit 0, multiple red steps).
- [ ] A class with fewer than 2 fixtures does not ship in P3; it stays UNCLASSIFIED until the corpus supports it.
- [ ] Per-class fixture count table in the P2 handoff and in `docs/LABELING.md`.
- [ ] Every fixture hand-labeled.
- [ ] Verify `updated_at` changes on a real re-run (harvest one re-run attempt).
- [ ] Growing past 25 is ongoing work, not a phase gate.
- [ ] Redaction test proves tokens and emails are caught.
- [ ] gitleaks green on full history.

## P3 — Classification (not started)

- [ ] Classification engine + rule set implemented.
- [ ] Per-class precision/recall/UNCLASSIFIED-rate script (`make measure`) with output committed to `docs/ACCURACY.md`.
- [ ] Every classification carries evidence line numbers.
- [ ] No rule tuned against already-measured fixtures; new fixtures are added first.

## P4 — Extraction + terminal render (not started)

- [ ] Every excerpt line maps to a real log line number, asserted by test.
- [ ] Compression ratio measured and printed.
- [ ] ANSI codes, progress-bar noise, and other log noise stripped, with tests.
- [ ] Renders correctly under cp1252 (Windows CI job).
- [ ] Under 5 seconds on the largest fixture, timed in a test.
- [ ] Widen the `rich` pin past 14 once the renderer can be checked visually (dependabot PR #1 was closed for this reason).

## P5 — JSON + markdown + Action wrapper + v1.0.0 (not started)

- [ ] `--json` output validated against a committed schema.
- [ ] `--markdown` output is directly pasteable.
- [ ] `action.yml` composite action added.
- [ ] README has a before/after asset and measured numbers.
- [ ] Switch `main` to PR-only with required checks (gate 3.11/3.12/3.13, windows-smoke, gitleaks, pinned-actions) before tagging. Direct pushes were kept through P4 because `make gate` before push covers a solo project.
- [ ] Tag `v1.0.0`; release workflow publishes to PyPI.

## P6 — Optional AI layer (not started)

- [ ] `--ai` flag, off by default.
- [ ] Provider configured via an OpenAI-compatible base URL.
- [ ] Sends only the excerpt, not the full log; a test asserts payload size is bounded by excerpt + prompt.
- [ ] No test requires an API key.
- [ ] Tool is fully functional with `--no-ai`.
