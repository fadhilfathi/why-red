# Roadmap

## P0 — Scaffolding (in progress)

- [ ] Repo is public.
- [ ] CI green on Python 3.11, 3.12, 3.13.
- [ ] Security workflow (gitleaks full history + pinned-action check) green.
- [ ] PyPI package name `why-red` reserved.
- [ ] Pydantic schemas (run, classification, excerpt, report) documented in `docs/ARCHITECTURE.md`.
- [ ] No tags cut yet.

## P1 — Fetch + cache + locate (not started)

- [ ] `gh api` fetch of run, jobs, and logs implemented.
- [ ] Filesystem cache keyed by run ID; a second invocation makes zero network calls, proven by a test using a fake `gh`.
- [ ] Locates the failing job + step correctly on fixtures covering: single failure, multiple red steps, continue-on-error step, cleanup-step-after-real-failure, matrix leg.
- [ ] Harvest script committed, with pinned run IDs and repo SHAs.

## P2 — Fixture corpus (not started)

- [ ] Labeling criteria doc (`docs/LABELING.md`) committed before any label is assigned.
- [ ] At least 40 redacted fixtures spanning Python, Node, Go, Rust, Java, Docker.
- [ ] Every fixture hand-labeled.
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

## P5 — JSON + markdown + Action wrapper + v1.0.0 (not started)

- [ ] `--json` output validated against a committed schema.
- [ ] `--markdown` output is directly pasteable.
- [ ] `action.yml` composite action added.
- [ ] README has a before/after asset and measured numbers.
- [ ] Tag `v1.0.0`; release workflow publishes to PyPI.

## P6 — Optional AI layer (not started)

- [ ] `--ai` flag, off by default.
- [ ] Provider configured via an OpenAI-compatible base URL.
- [ ] Sends only the excerpt, not the full log; a test asserts payload size is bounded by excerpt + prompt.
- [ ] No test requires an API key.
- [ ] Tool is fully functional with `--no-ai`.
