# GitHub Actions API: measured behaviour

What the API actually did when probed, not what the docs imply. Each entry names
the date and the run used so it can be re-checked. Probed with `gh` 2.95.0 via
`gh api`, which follows redirects and handles content-encoding itself.

Probe run: `pytest-dev/pytest` run 34964800998 (32 jobs, 22 failed, 2026-09-15).
In-progress probe: `python/cpython` run 35107063204 (2026-09-16).

## Run and jobs

| Observation | Measured |
|---|---|
| `GET /actions/runs/{id}` has no jobs; a separate `/jobs?per_page=100` call is needed, and it is paginated. | 32 jobs came back in one page; the fetch code still passes `--paginate --slurp` and merges pages. |
| `conclusion` is `null` while the run or job is in progress. | Run `status: in_progress`, `conclusion: null`; 28 of 45 jobs `in_progress` with `conclusion: null`. Mapped to `Conclusion.UNKNOWN`. |
| Step numbers are not contiguous. | Failed job had steps 1-9, then 16, 17, 18, 19. `Post ...` steps are numbered from the end. Never index steps by position. |
| Step `started_at`/`completed_at` have whole-second precision. | `2026-09-15T14:49:31Z`. Log lines have 100 ns precision. Adjacent steps share a boundary second. |
| Skipped jobs still report steps. | `minsteps` across the run: 3 (a `check` job), no zero-step job was observed. The locate stage handles zero steps anyway (synthetic test). |
| `updated_at` on the run changes on re-run. | Not yet measured on a real re-run; the cache key includes it on the strength of the API docs. Flagged in ROADMAP P2 to verify with a harvested re-run. |

## Job logs (`GET /actions/jobs/{id}/logs`)

| Observation | Measured |
|---|---|
| Response is a 302 to Azure Blob storage; `gh api` follows it and returns the body. | Final response `200`, `Content-Type: text/plain`, `Content-Length: 115095`, served by `Windows-Azure-Blob`. |
| Body starts with a UTF-8 BOM. | `EF BB BF` as the first three bytes. Stripped in `fetch_job_log`. |
| Line endings differ by runner OS. | ubuntu job: LF only, 0 CR bytes. windows job: CRLF. The cache and fixture writers use `newline=""` so line numbers survive round trips. |
| ANSI colour codes are present in the body. | pytest summary lines contain `\x1b[31m` etc. Stripped only for display (P4), never in the stored log. |
| Every step's log region starts with `##[group]Run ...`; post steps start with `Post job cleanup.`. | Both markers observed on ubuntu and windows runners. Composite actions nest further `##[group]Run` lines inside a step. |
| A shared boundary second is not "a few lines". | Between step 5 (`Set up tox`) and step 6 (`Test without coverage`), second `14:25:31` held 64 lines: 48 of step 5's tail (cache restore output), then step 6's `##[group]Run tox`. Locate uses the last opening marker in the start second and the first in the end second. |
| In-progress job: HTTP 200 with an XML error body, not a 4xx. | `<?xml ...><Error><Code>BlobNotFound</Code>...`, preceded by a BOM. `gh` exits 0. Detected by content and reported as `LogUnavailableError`. |
| Expired logs: HTTP 410. | Run 25104921521 (older than retention): `{"message":"Server Error","status":"410"}`, `gh` exit 1. |
| Unknown job id: HTTP 404. | `gh: Not Found (HTTP 404)`, `gh` exit 1. |
| Size and time of one log fetch. | 115 KB / 797 lines (ubuntu leg), 973 lines (windows leg); 2.9 s wall for one `gh api` call on this machine. |
| Truncation of very large logs. | Not yet measured. No fixture over 1 MB harvested yet. |
| gzip. | Not observed; `gh` negotiates and decodes transparently, so the tool never sees it. |

## Run-level logs (`GET /actions/runs/{id}/logs`)

| Observation | Measured |
|---|---|
| It is a zip of the whole run. | 748 KB for the 32-job run, 4.3 s. |
| It does NOT contain per-step files any more. | 64 entries: `N_<job name>.txt` (full job log) and `<job name>/system.txt` (8 lines of runner scheduling). Older docs and blog posts describe `<job>/<n>_<step>.txt`; that layout was not present on 2026-09-16. So there is no exact step-to-line source; timestamps plus markers are the only option. |

## `gh` CLI

| Observation | Measured |
|---|---|
| `subprocess.run(["gh", ...])` on Windows does not find a `gh.cmd` earlier on PATH; it finds `gh.exe` anywhere on PATH. | Test suite's fake `gh.cmd` was bypassed and the real `gh` was called. Fixed by resolving with `shutil.which("gh")`, which honours `PATHEXT`. |
| Cold vs warm invocation, real network. | Cold (run + jobs + one log): 6.3 s. Warm (run + jobs, log from cache): 2.6 s. About 1.2 s of each `gh api` call is process start-up on this Windows machine. |
