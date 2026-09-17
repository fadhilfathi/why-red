# Labeling criteria

Written and committed before any fixture is hand-labeled (docs/ROADMAP.md P2).
A label is `fixtures/cases/<slug>/label.json`:

```json
{
  "failure_class": "TEST_FAILURE",
  "evidence_lines": [754, 774],
  "job_id": 104401099719,
  "notes": "pytest summary line + the FAILED line above it",
  "ambiguous_with": null
}
```

`evidence_lines` are the real line numbers in `<job_id>.log` a human read to
assign the class — the same contract `Classification.evidence` carries at
runtime. `ambiguous_with` is null unless the log fits more than one class
(see Tie-breaks), in which case it names the runner-up and points here.

A label is assigned by reading the raw log, never by asking the harvest tool
or a model. Labeling is the ground truth the classifier is measured against
in P3; it must not be produced by anything the classifier could also produce.

## Per-class criteria

Each entry: what must be visible in the log, and what similar-looking thing
it is NOT.

| Class | Assign when the log shows | Not this when |
|---|---|---|
| `DEPENDENCY_RESOLUTION` | A package manager (pip/uv/npm/yarn/cargo/go mod/maven/gradle) exits non-zero while resolving or installing, before the project's own build/test tooling ever runs. | The manager succeeds and a later compile or test step fails; that is `COMPILATION_ERROR` or `TEST_FAILURE` even if the root cause is a bad dependency. |
| `COMPILATION_ERROR` | A compiler or type checker (rustc, tsc, javac, go build, mypy, gcc) reports an error and exits non-zero, before any test runs in that step. | The compiler succeeds and a test then fails at runtime due to a type issue caught only at runtime (e.g. Python) — that is `TEST_FAILURE`. |
| `TEST_FAILURE` | A test runner reports one or more failing tests with an assertion, exception, or diff, and exits non-zero. | The failure is explicitly attributed by the runner or a rerun to flakiness (see `FLAKY_TEST`), or the process was killed rather than the test failing on its own (see `OOM_KILLED`, `TIMEOUT`). |
| `FLAKY_TEST` | Direct evidence the SAME test passed on a retry within this run (a rerun plugin's output, `flaky`, `retry 1/3`, or the workflow's own re-run-failed-jobs mechanism producing a different result for that test) OR the test framework itself labels the test flaky/quarantined. | No retry evidence exists. A test that merely looks like it "could be flaky" (timing, network) without a logged retry is `TEST_FAILURE`; guessing flakiness from vibes is exactly the invented-cause the tool must not do. |
| `OOM_KILLED` | Exit code 137, the literal word `Killed`, `OutOfMemoryError`, `oom-kill`, `heap out of memory`, or the kernel OOM-killer log line. | A test's own assertion message happens to contain the word "memory" — that is `TEST_FAILURE`. |
| `TIMEOUT` | The runner, a step's `timeout-minutes`, or a tool explicitly reports a timeout (`The operation was canceled`, `Error: The action 'X' timed out`, a test framework's own timeout wrapper). | A step fails because of a slow network call that errors out on its own (connection reset, DNS) rather than being killed for taking too long — that is `NETWORK_FAILURE`. |
| `DISK_FULL` | `No space left on device`, `ENOSPC`, or a package manager reporting it cannot write because the disk is full. | — |
| `AUTH_FAILURE` | HTTP 401/403, `Permission denied (publickey)`, `bad credentials`, `Authentication failed`, against a registry, cloud provider, or Git remote, where the request was correctly formed but rejected for identity/permission reasons. | HTTP 429 against the same kind of endpoint is `RATE_LIMITED`, not `AUTH_FAILURE`, even though both are "the request was refused" — the fix differs (wait/authenticate vs. fix credentials). |
| `RATE_LIMITED` | HTTP 429, `rate limit exceeded`, `You have exceeded a secondary rate limit`, Docker Hub's `toomanyrequests`. | — |
| `NETWORK_FAILURE` | DNS failure, connection reset/refused, TLS handshake failure, `Could not resolve host`, generic `network is unreachable`, where no timeout wrapper or explicit rate-limit response is present. | The same symptom after a `timeout-minutes` boundary is `TIMEOUT` (something hung, then the runner enforced its limit) rather than `NETWORK_FAILURE` (something errored immediately). |
| `CACHE_MISS` | An `actions/cache` (or tool-native cache) restore step reports no match found, AND a later step fails in a way that depends on that cache being present (e.g. a build step that assumed a restored `node_modules`/`target`). The absence alone is not a failure; the causal link to the later failure must be visible. | A cache miss that is merely logged but the build still succeeds (slower, not broken) is not a failure at all — nothing to classify. |
| `LINT_FAILURE` | A linter or formatter (ruff, eslint, gofmt -l, clippy with `-D warnings`, prettier --check) exits non-zero and the log's own tool name identifies it as style/lint, not a compiler. | `clippy` without `-D warnings` reporting only warnings but exiting 0 elsewhere in the log is not a failure at all — check the actual exit that failed. |
| `MISSING_SECRET` | A step fails because an expected secret or env var is empty, unset, or the literal string used by GitHub for an unavailable fork-PR secret (often surfaces as an auth failure to a service using an empty token, or a tool's own "X is not set" message). | Indistinguishable from `AUTH_FAILURE` when the log only shows "401" with no evidence the credential was empty vs. wrong — see Tie-breaks. |
| `CONFIG_ERROR` | The workflow YAML, an action's `with:` inputs, or a tool's own config file (pyproject.toml, tsconfig.json, Dockerfile syntax) is rejected before any project code runs — a parse error, unknown key, or schema violation reported by GitHub Actions itself or the tool reading the config. | A config file that parses fine but expresses something semantically wrong that only manifests as a later compile/test/lint failure is classified by where it manifests, not by config being the root cause — root-cause archaeology is not this tool's job, only what actually failed. |
| `INFRASTRUCTURE` | Runner-side and outside the repo's control: `startup_failure`, "The runner has received a shutdown signal", "This request has been automatically failed because it uses a deprecated version", GitHub Actions service incident language, an action itself failing to download. | Never inferred from silence or an unclear log; only from explicit runner/job-level metadata or an explicit infra message. If unsure, `UNCLASSIFIED` is correct. |
| `UNCLASSIFIED` | No rule's evidence pattern matched anything in the failing step's region. | This is the default, not a last resort to avoid — assign it whenever no other row's criteria are clearly met by real evidence lines. |

## Tie-breaks (written before labeling, per the brief)

A log can legitimately present evidence for more than one class. These are
the specific overlaps named in the brief plus the ones the criteria above
create, decided now so no label encodes an in-the-moment guess.

1. **OOM that surfaces as a test failure.**
   A test process is OOM-killed; the test runner then reports the test as
   "failed" or "errored" because its subprocess died, without ever printing
   an assertion diff.
   **Winner: `OOM_KILLED`.**
   Why: the test did not fail on its own terms — nothing about the test's
   logic is implicated, and a developer told "test failure" would go read
   the test and find nothing wrong. The evidence line is the OOM signal
   (exit 137 / `Killed` / OOM message), not the runner's summary line.
   `ambiguous_with: "TEST_FAILURE"` in the label.

2. **Timeout that looks like a network error.**
   A request hangs, then is torn down when a `timeout-minutes` or explicit
   timeout wrapper fires, producing a generic connection-reset-looking
   message at the moment of teardown.
   **Winner: `TIMEOUT`** if a timeout boundary (step `timeout-minutes`, a
   named timeout wrapper, or "The operation was canceled" from the runner)
   is visible anywhere in the step's region. **Winner: `NETWORK_FAILURE`**
   only if no such boundary appears and the error is immediate (DNS/refused
   within seconds, not after minutes of hanging).
   Why: the fix differs — raise/adjust a timeout and investigate why it's
   slow, vs. investigate why the network refused outright. The timeout
   wrapper's existence is the deciding evidence, not the surface symptom.
   `ambiguous_with: "NETWORK_FAILURE"` in the label when both patterns
   appear.

3. **Dependency failure that presents as a compilation error.**
   A missing or version-mismatched dependency causes the compiler/type
   checker to report "module not found" / "cannot find crate" / unresolved
   import errors, rather than the package manager itself failing.
   **Winner: `DEPENDENCY_RESOLUTION`** if the package-manager step (install/
   sync/restore) is visibly where things went wrong (non-zero exit, or a
   resolution error) even if a later step's error message is what a human
   would first notice. **Winner: `COMPILATION_ERROR`** if the package
   manager step exited 0 and the compiler is the first and only tool to
   report anything wrong.
   Why: `Location` already picked the step; if the located step IS the
   install step, classify what that step actually said. If the located step
   is the build step, the resolution stage genuinely succeeded and the
   compiler's complaint (however dependency-shaped) is what should be
   fixed there — reclassifying past the located step would contradict
   Stage 2's own contract. `ambiguous_with: "COMPILATION_ERROR"` or
   `"DEPENDENCY_RESOLUTION"` respectively.

4. **MISSING_SECRET vs. AUTH_FAILURE.**
   Both can produce an identical "401 Unauthorized" line.
   **Winner: `MISSING_SECRET`** only if the log itself shows the credential
   was empty/unset (a tool printing `token=` with nothing after it, GitHub's
   own "Secret X is not available to this workflow" note on fork PRs, or an
   explicit "environment variable X is required" message). **Winner:
   `AUTH_FAILURE`** for a bare 401/403 with no evidence about why.
   Why: never invent the "why" behind a rejection; MISSING_SECRET is a
   claim about cause that needs its own evidence, not an inference from the
   symptom alone.

5. **CACHE_MISS vs. the failure it causes.**
   A cache miss log line is almost always present (cold caches are normal);
   it is only evidence when the later failure is visibly caused by the
   absence (e.g. "module not found" for something the cache would have
   restored, immediately after a logged cache miss for that exact path).
   **Winner: whatever the later failure actually is** (e.g.
   `DEPENDENCY_RESOLUTION`) **unless** the causal link is explicit, in which
   case **`CACHE_MISS`** wins because it is the more actionable, fixable-
   at-the-source class.
   Why: a cache miss is the normal, common case and must not become the
   default explanation for every failure that follows one in the log.

6. **Runner shutdown after real test failures in the same step region.**
   (Found labeling `deno-runner-shutdown-during-tests`.) A step's log shows
   genuine `FAILED` test lines, then minutes later an explicit runner
   shutdown message (`The runner has received a shutdown signal...`) and the
   step exits on a signal (128+N, e.g. 143 for SIGTERM) rather than the
   test runner's own exit code.
   **Winner: `INFRASTRUCTURE`.**
   Why: the step's actual exit is attributed to the signal, not to the test
   runner completing and reporting failure — the test run never finished.
   The earlier `FAILED` lines are real but were not what ended the step;
   telling a developer "test failure" would send them to chase tests that
   may well have kept running had the runner survived. The explicit
   shutdown message is more specific evidence than a bare non-zero exit,
   so it wins per the `INFRASTRUCTURE` criteria's own "never inferred from
   silence" rule read the other way: here it is not silence, it is stated.
   `ambiguous_with: "TEST_FAILURE"` in the label.

Any overlap not listed here that comes up during labeling gets added to this
section, with the same reasoning-then-decision shape, before the fixture
that raised it is labeled — not after.

## Per-class fixture count (P2, as of 2026-09-17)

12 real, redacted, hand-labeled fixtures. Two is the minimum to ship in P3,
not a comfortable number — rows at exactly 2 are flagged. Rows at 0 or 1 ship
as `UNCLASSIFIED` in P3, with the sourcing difficulty stated in the README.

| Class | Fixtures | Ships in P3? |
|---|---|---|
| TEST_FAILURE | 2 (min) | yes |
| LINT_FAILURE | 2 (min, weak — see note) | yes |
| NETWORK_FAILURE | 2 (min) | yes |
| DEPENDENCY_RESOLUTION | 1 | no — one short |
| COMPILATION_ERROR | 1 | no — one short |
| TIMEOUT | 1 | no — one short |
| MISSING_SECRET | 1 | no — one short |
| CONFIG_ERROR | 1 | no — one short |
| INFRASTRUCTURE | 1 | no — one short |
| FLAKY_TEST | 0 | no |
| OOM_KILLED | 0 | no |
| DISK_FULL | 0 | no |
| AUTH_FAILURE | 0 | no |
| RATE_LIMITED | 0 | no |
| CACHE_MISS | 0 | no |

Corpus is 12 of the 25-fixture target, 3 of 15 classes at the 2-fixture ship
minimum. Growing it is ongoing work per the roadmap, not a P2 gate; P3 ships
classification for the 3 rows above the line and reports the other 12 as
`UNCLASSIFIED` honestly, which is the outcome this document was written to
make acceptable rather than something to paper over.

**LINT_FAILURE's count is softer than it looks.** Both fixtures
(`vite-eslint-failure`, `vite-eslint-failure-2`) are the same eslint rule set
failing on the same repo two days apart — the fixture-selection priority of
"failure-mode diversity over count" was not met for this class the way it was
for TEST_FAILURE (pytest vs. a different pytest-based repo) or NETWORK_FAILURE
(the same signature, but at least two independent runs of a different repo).
Kept both anyway: dropping either one puts LINT_FAILURE below ship minimum,
and each still genuinely exercises the pipeline on real output. Replace
`vite-eslint-failure-2` with a differently-shaped lint failure (a different
tool or language) when one turns up.

Why each 0-count class was hard to source publicly in this pass:

- `AUTH_FAILURE` / `RATE_LIMITED`: every "401"/"403"/"429"-shaped hit found
  during harvesting was a false positive — text inside a bot's event payload,
  a `retry-exempt-status-codes` config value, or a warning that resolved
  itself mid-build (see `moby-vendoring-mismatch`'s label, which explains
  rejecting an early rate-limit warning as the root cause). A real, harvested
  case where a rejected request is the actual, sole reason the step failed
  did not turn up in this pass.
- `OOM_KILLED` / `DISK_FULL`: GitHub-hosted runners have generous default
  memory and disk; both are more common on self-hosted runners or resource-
  constrained matrix legs, neither of which this pass's repo list happened
  to hit.
- `FLAKY_TEST`: needs direct in-log evidence of a retry (a rerun plugin, or
  the same test both failing and passing within one run/attempt). A run with
  `run_attempt > 1` was found (a human clicked "re-run failed jobs"), but per
  its own second attempt also failing, or the retry's outcome differing
  between attempts, was not confirmed for any candidate in this pass —
  and per the criteria, guessing flakiness from a failure that merely looks
  timing-sensitive is exactly the invented cause the tool must not produce.
- `CACHE_MISS`: cache-miss log lines are common, but a later failure with an
  explicit causal link to that specific miss (tie-break #5) was not found;
  every candidate's real failure traced to something else, as with
  `moby-vendoring-mismatch`.

## Fixture selection priorities (this phase)

1. Failure-mode coverage over language coverage: a class with zero or one
   fixture is a bigger gap than a language with only one fixture.
2. At least one fixture from a small/low-star repo per few classes — large,
   flagship repos have unusually clean CI and are not representative of
   what a stranger will point this tool at.
3. Real, harvested logs only. A hand-written fixture is not evidence a rule
   works on real output and is never created to hit a count.
4. A class that cannot reach 2 real fixtures ships as UNCLASSIFIED in P3,
   not as a rule tuned to one example. The README states this plainly, with
   the actual sourcing difficulty named (e.g. `MISSING_SECRET` fails
   silently on fork PRs and rarely produces a public log that shows it;
   `DISK_FULL` is rare on GitHub-hosted runners' generous disk).
