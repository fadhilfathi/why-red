# Architecture

`why-red <run-id>` answers one question: why did this GitHub Actions run fail?
The answer is a failure class, the real log lines that prove it, and what to
check next. Every stage before the optional AI layer is deterministic and runs
offline against committed fixtures.

## Data flow

```
run id
  |
  v
[1 fetch]   gh api  -> Run (jobs, steps, conclusions) + raw log text per job
  |           cache: <cache>/<owner>__<name>/<run-id>/<updated_at>/ (run.json, <job-id>.log)
  v
[2 locate]  Run -> Location (failing job + step + reason)
  |
  v
[3 classify] log lines -> Classification (FailureClass, confidence, evidence)
  |
  v
[4 extract]  log lines + evidence -> Excerpt (real line numbers, compression)
  |
  v
[5 render]   Report -> terminal | --json | --markdown
  |
  v
[6 ai]       Excerpt only -> AiSummary   (only with --ai; never in tests)
```

Every stage consumes and produces the Pydantic models in `src/why_red/models/`.
Stages never talk to each other except through those models, so each stage is
testable in isolation with a fixture on disk.

### Invariants enforced by the schemas

| Invariant | Where enforced |
|---|---|
| A class other than UNCLASSIFIED carries at least one evidence line | `Classification` validator |
| UNCLASSIFIED has confidence 0.0 | `Classification` validator |
| Every excerpt line has a 1-based line number that exists in the raw log | `ExcerptLine.line_no >= 1`, `Excerpt` validator against `total_lines` |
| Excerpt lines are strictly ascending (no reordering, no duplicates) | `Excerpt` validator |
| Log text is verbatim (ANSI stripped, never paraphrased) | Contract on `Evidence.text` / `ExcerptLine.text`; tested in P4 by comparing to the fixture |
| Unknown GitHub API fields do not break parsing | `extra="ignore"` on run models |
| Models are immutable once built | `frozen=True` everywhere |

## Stage contracts

### 1. Fetch (`fetch/github.py`, `fetch/cache.py`)

- Uses the `gh` CLI (`gh api`) so authentication is the user's problem, not ours.
- Endpoints, all GET:
  `GET /repos/{owner}/{repo}/actions/runs/{run_id}`,
  `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100`,
  `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs` (302 to a zip/plain log).
- Read-only. There is no code path that issues POST/PATCH/DELETE. A test greps
  the fetch module for those verbs.
- Cache keyed by run id AND the run's `updated_at`, under the platform cache
  directory (`%LOCALAPPDATA%\why-red` on Windows, `$XDG_CACHE_HOME/why-red` or
  `~/.cache/why-red` elsewhere). `--cache-dir` overrides, `--no-cache` bypasses.
  Every invocation makes the two metadata calls (run, jobs); the job log is
  served from disk when `updated_at` is unchanged, so a re-run never reads a
  stale log. Only the located job's log is fetched: a 22-leg matrix at ~3 s per
  log is not worth waiting for up front. Tested with a fake `gh` on PATH.
- Repo is resolved from `--repo`, else from `git remote get-url origin` in cwd.
  The run id alone is not globally routable in the REST API.
- `--fixture DIR` reads a cache entry or a committed fixture instead of GitHub.
  Fixtures and cache entries have the same layout on purpose.
- What the API really does (BOM, CRLF on Windows runners, 200-with-XML for
  in-progress jobs, 410 for expired logs, non-contiguous step numbers) is
  recorded with measurements in docs/API_NOTES.md.

### 2. Locate (`locate/`)

Input: `Run`. Output: `Location | None`.

Selection rule, in order (the `reason` field names which rule fired):

1. Jobs with `conclusion == failure`; if a matrix, each leg is its own job.
2. Within the job, candidate steps are those with `conclusion == failure`.
3. The API does not expose `continue-on-error`. The only signal is what
   happened next: a real failure skips the steps after it, a
   continue-on-error failure does not. With several failed steps, the first
   one followed by a skipped step (or by nothing but post steps) wins.
4. Post steps (`Post <name>`, `Complete job`) and steps whose name matches a
   cleanup pattern (`cleanup`, `upload artifact/report/coverage`, `stop
   containers`) are dropped when any other failed step exists. They are
   recorded in `other_failed_steps`. If only such steps failed, they are the
   failure.
5. Otherwise the earliest remaining failed step. Earlier failures cause
   later ones.
6. If no step failed but the job did (`failure`, `timed_out`,
   `startup_failure`, `cancelled` at job level): the last step that started,
   or step 1 named `(no steps reported)` for a job with zero steps, with a
   reason that says so.
7. If nothing failed at all (all green): `None`.

Step-to-line mapping (`Location.line_range`): lines are assigned by comparing
their timestamp, truncated to the second, with the step's `started_at` and
`completed_at`. Inside the shared start second the last `##[group]Run` /
`Post job cleanup.` marker opens the step; inside the shared end second the
first such marker closes it. Measured reason: one shared second held 48 lines
of the previous step. The run-level logs zip no longer carries per-step files,
so there is no exact source (see API_NOTES.md).

### 3. Classify (`classify/engine.py`, `classify/rules/`)

Input: raw log lines of the located job (all of them, not just the step;
`Location.line_range`, when known, is passed as a tie-break hint, not a
search boundary). Output: `Classification`.

- Rules are data (`classify/rules/Rule`): `rule_id`, `FailureClass`, a
  compiled regex, a fixed `confidence`, and `next_checks`. A rule fires on a
  line; every matching line becomes `Evidence` (not just the first).
- A rule only exists for a class with >=2 real fixtures in the corpus
  (`SHIPPED_CLASSES`, derived from `RULES` itself, never hand-maintained).
  A class below that bar has no rule and can only ever come back
  UNCLASSIFIED — this is enforced by construction, not by a check someone
  could forget. As of P3: TEST_FAILURE, LINT_FAILURE, NETWORK_FAILURE.
- Matching happens against each line with ANSI codes AND the GitHub
  timestamp stripped (`classify/engine.py`'s `match_lines`) -- every real
  line starts with a timestamp, so an anchored pattern like pytest's own
  `^FAILED ...` never matches the raw line. `Evidence.text` itself keeps
  only ANSI stripped, per the schema's contract; timestamp stripping for
  *display* is extract's job in P4. This was a real P3 bug (measure.py
  showed 0.00 recall for two classes before the fix; see docs/ACCURACY.md's
  history in git log).
- The engine evaluates all rules, collects every hit, and picks the class
  with the highest confidence. A confidence tie is broken by the evidence
  line closest to the end of the failing step's region when one is known
  (the last error is usually the real one).
- No hit: `UNCLASSIFIED`, confidence 0.0, empty evidence, `rule_id` is
  `None`. The extract stage still produces a best-candidate excerpt (P4).
- Confidence is a fixed number per rule, decided when the rule is written
  and documented next to it. It is not learned and not tuned against the
  corpus. `docs/ACCURACY.md`'s numbers are the check that it wasn't.
- Rules must not be tuned against fixtures that were already used for
  measurement. New rules need new fixtures first (see CONTRIBUTING.md).

### 4. Extract (`extract/`)

Input: raw log lines, `Classification`, `Location`. Output: `Excerpt`.

- Strip ANSI escape sequences and the leading GitHub timestamp
  (`2026-09-16T10:00:00.1234567Z `) for display; line numbers still refer to
  the raw log.
- Drop noise lines by pattern: progress bars (`\r`, `[=====>  ]`), dependency
  download chatter (`Downloading`, `Collecting`, `Resolved N packages`),
  `##[group]`/`##[endgroup]` markers, blank runs.
- Window: evidence lines plus context (default 3 lines before, 8 after,
  merged when overlapping). Consecutive kept lines that are repeats of the
  same stack-frame pattern collapse to the first occurrence; the collapse is
  shown as a separate marker line in the renderer, never as an `ExcerptLine`.
- UNCLASSIFIED: the window is centred on the last line matching a generic
  error pattern (`error|Error|ERROR|FAIL|fatal|panic|Traceback|exit code`)
  inside the failing step's region, or the last 20 lines of the step if none.
- `compression_ratio = total_lines / len(lines)` is the number the README
  reports. It is measured per fixture in P4 and never hand-written.

### 5. Render (`render/terminal.py`, `render/json.py`, `render/markdown.py`)

- Terminal: rich panel. Header line: class, confidence, run link. Then the
  excerpt with right-aligned line numbers, evidence lines highlighted. Then
  `next_checks`. Footer: `N lines -> M lines`. Colors are optional; output must
  encode under cp1252 (Windows CI job) and look right at 80 columns.
- `--json`: `Report.model_dump_json(indent=2)`. `schema_version` is bumped on
  any breaking change.
- `--markdown`: the same content as a fenced block plus a two-row table,
  meant to be pasted into an issue.

### 6. AI (`ai/provider.py`)

- Off unless `--ai`. Reads `WHY_RED_AI_BASE_URL`, `WHY_RED_AI_API_KEY`,
  `WHY_RED_AI_MODEL`. Talks to any OpenAI-compatible chat endpoint using the
  stdlib `urllib`; no SDK dependency.
- Payload is the rendered excerpt plus the classification, never the full
  log. A test asserts the payload size is bounded by the excerpt.
- Any failure in this stage degrades to `ai = None`; it can never make the
  deterministic output worse.

## FailureClass

| Class | Meaning | Why it is its own class |
|---|---|---|
| `DEPENDENCY_RESOLUTION` | A package manager could not resolve or install dependencies (pip/uv/npm/cargo/go mod/maven). | Fix is in the lockfile or registry, not in the code. Very common and easy to spot by tool-specific markers. |
| `COMPILATION_ERROR` | Compiler or type checker rejected the code (rustc, tsc, javac, go build, mypy). | Fix is a source change at a file:line the log names. Distinct from tests, which compiled fine. |
| `TEST_FAILURE` | The test runner reported failures. | The most common class; the excerpt should be the failing test's assertion, not the summary line. |
| `FLAKY_TEST` | A test failure where the same test passed on retry within the run, or the runner labels it flaky/rerun. | Tells the developer not to chase a bug that is not there. Only emitted with direct evidence of a retry; otherwise it is TEST_FAILURE. |
| `OOM_KILLED` | Process killed for memory (exit 137, `Killed`, `OutOfMemoryError`, `heap out of memory`). | Fix is memory limits or parallelism, not code. Often masquerades as a test failure. |
| `TIMEOUT` | Step or job exceeded its time limit, or a tool reported a timeout. | Distinct root cause (slowness or hang) and distinct fix (`timeout-minutes`). |
| `DISK_FULL` | `No space left on device` and equivalents. | Runner-side, fixable by cleanup steps; nothing to do with the diff. |
| `AUTH_FAILURE` | 401/403, bad credentials, permission denied against a registry, cloud, or Git. | Fix is in secrets or permissions, usually the `permissions:` block. |
| `RATE_LIMITED` | 429, `rate limit exceeded`, Docker Hub pull limits. | Transient; the correct action is wait or authenticate, not debug. Kept apart from AUTH_FAILURE because the fix differs. |
| `NETWORK_FAILURE` | DNS, connection reset, TLS handshake, `ECONNREFUSED`, `Could not resolve host`. | Transient and external; a rerun is the right first move. |
| `CACHE_MISS` | A cache restore step failed or the build failed because an expected cached artifact was absent. | Usually a key mismatch after a lockfile change; the developer is looking in the wrong place otherwise. |
| `LINT_FAILURE` | Linter or formatter exited non-zero (ruff, eslint, gofmt, clippy, prettier). | Fix is mechanical (`--fix`) and should not be confused with a real bug. |
| `MISSING_SECRET` | An expected secret or env var is empty or undefined. | Extremely common on fork PRs where secrets are unavailable by design. |
| `CONFIG_ERROR` | The workflow or a tool config file is invalid (YAML error, unknown key, action input error). | The failure happens before any code runs; the excerpt is usually the first lines of the log, not the last. |
| `INFRASTRUCTURE` | Runner lost, `startup_failure`, GitHub-side outage, action download failure. | Nothing in the repo caused it. Emitted only from run/job metadata or explicit runner messages, never inferred from silence. |
| `UNCLASSIFIED` | No rule fired with evidence. | The honest answer. Shown with the best candidate excerpt so the user still saves time. The rate of this class is a published metric. |

Rules for adding a class: it needs at least five real fixtures from at least
two ecosystems, a fix that differs from every existing class, and a
one-line meaning that a stranger understands.

## Schemas

These are the exact Pydantic v2 models in `src/why_red/models/`. The code is
the source of truth; this section is kept in sync by review.

### `models/run.py`

```python
class Conclusion(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    NEUTRAL = "neutral"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    STARTUP_FAILURE = "startup_failure"
    UNKNOWN = "unknown"          # null or any value we do not model

class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

class Step(_Model):
    number: int                  # ge=1, 1-based within the job
    name: str
    conclusion: Conclusion = Conclusion.UNKNOWN
    started_at: datetime | None = None
    completed_at: datetime | None = None

class Job(_Model):
    id: int
    name: str
    status: str = "unknown"      # queued | in_progress | completed
    conclusion: Conclusion = Conclusion.UNKNOWN
    started_at: datetime | None = None
    completed_at: datetime | None = None
    runner_name: str | None = None
    html_url: str | None = None
    steps: list[Step] = []

class Run(_Model):
    id: int
    repo: str                    # "owner/name"
    workflow_name: str
    run_number: int
    run_attempt: int = 1
    event: str
    head_branch: str | None = None
    head_sha: str
    status: str = "unknown"      # queued | in_progress | completed
    conclusion: Conclusion = Conclusion.UNKNOWN
    created_at: datetime | None = None
    updated_at: datetime | None = None   # part of the cache key
    html_url: str | None = None
    jobs: list[Job] = []

class Location(_Model):
    job_id: int
    job_name: str
    step_number: int             # ge=1
    step_name: str
    reason: str                  # min_length=1; names the locate rule that fired
    other_failed_steps: list[int] = []
    line_range: tuple[int, int] | None = None   # 1-based inclusive span in the raw log
```

### `models/failure.py`

```python
class FailureClass(StrEnum):
    DEPENDENCY_RESOLUTION, COMPILATION_ERROR, TEST_FAILURE, FLAKY_TEST,
    OOM_KILLED, TIMEOUT, DISK_FULL, AUTH_FAILURE, RATE_LIMITED,
    NETWORK_FAILURE, CACHE_MISS, LINT_FAILURE, MISSING_SECRET,
    CONFIG_ERROR, INFRASTRUCTURE, UNCLASSIFIED      # values == names

class Evidence(BaseModel):       # frozen
    line_no: int                 # ge=1, 1-based in the raw job log
    text: str                    # verbatim, ANSI stripped, never paraphrased

class Classification(BaseModel): # frozen
    failure_class: FailureClass
    confidence: float            # 0.0 <= x <= 1.0
    rule_id: str | None = None   # None for UNCLASSIFIED
    evidence: list[Evidence] = []
    next_checks: list[str] = []

    # validator: failure_class != UNCLASSIFIED  =>  len(evidence) >= 1
    # validator: failure_class == UNCLASSIFIED  =>  confidence == 0.0
```

### `models/excerpt.py`

```python
class ExcerptLine(BaseModel):    # frozen
    line_no: int                 # ge=1, 1-based in the raw job log
    text: str                    # verbatim, ANSI stripped
    highlight: bool = False      # True if this line is evidence

class Excerpt(BaseModel):        # frozen
    job_id: int
    total_lines: int             # ge=0, line count of the raw job log
    lines: list[ExcerptLine] = []
    compression_ratio: float     # computed: total_lines / len(lines), 0.0 if empty

    # validator: line_no strictly ascending
    # validator: every line_no <= total_lines
```

### `models/report.py`

```python
class AiSummary(BaseModel):      # frozen; present only with --ai
    model: str
    summary: str
    suggested_fix: str | None = None

class Report(BaseModel):         # frozen; this is the --json payload
    schema_version: int = 1
    run: Run
    location: Location | None = None   # None when nothing failed
    classification: Classification
    excerpt: Excerpt
    ai: AiSummary | None = None
```

## Non-goals

- No web UI, no daemon, no database. Filesystem cache only.
- No GitLab/CircleCI/Buildkite in v1. The fetch stage is the only GitHub-
  specific code, so a later port is contained, but it is not planned.
- No automatic reruns, comments, or any write to GitHub, ever.
