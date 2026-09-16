# why-red

Tells you why a GitHub Actions run failed: failure class, the log lines that prove it, and what to check next.

[![CI](https://img.shields.io/github/actions/workflow/status/fadhilfathi/why-red/ci.yml?branch=main)](https://github.com/fadhilfathi/why-red/actions)
[![PyPI](https://img.shields.io/pypi/v/why-red)](https://pypi.org/project/why-red/)
[![Python versions](https://img.shields.io/pypi/pyversions/why-red)](https://pypi.org/project/why-red/)
[![License](https://img.shields.io/github/license/fadhilfathi/why-red)](LICENSE)

<!-- demo: before/after terminal screenshot goes here (P5) -->

## Quickstart

```bash
uv tool install why-red
# or: pipx install why-red
```

Requires the `gh` CLI, authenticated (`gh auth status`).

```bash
why-red <run-id>
why-red <run-id> --json
```

Read-only: never comments, reruns, or cancels.

## What it does

1. Fetch — pulls the run, its jobs, and logs via `gh api`.
2. Locate — finds the failing job and step.
3. Classify — deterministically assigns one failure class.
4. Extract — pulls the smallest log excerpt that explains the failure, with real line numbers.
5. Render — prints to terminal, or emits `--json` / `--markdown`.
6. Optional AI — `--ai` adds prose on top of the deterministic result.

## Failure classes

| Class | Meaning |
|---|---|
| DEPENDENCY_RESOLUTION | Package manager could not resolve or install dependencies. |
| COMPILATION_ERROR | Source failed to compile or build. |
| TEST_FAILURE | A test assertion failed. |
| FLAKY_TEST | Test failed but shows signs of non-determinism (retry/pass pattern). |
| OOM_KILLED | Process was killed for exceeding memory limits. |
| TIMEOUT | A step or job exceeded its time limit. |
| DISK_FULL | Runner ran out of disk space. |
| AUTH_FAILURE | Authentication or authorization to a service failed. |
| RATE_LIMITED | A request was rejected for exceeding a rate limit. |
| NETWORK_FAILURE | A network request failed (DNS, connection reset, unreachable). |
| CACHE_MISS | A required cache was missing or invalid. |
| LINT_FAILURE | A linter or formatter check failed. |
| MISSING_SECRET | A required secret or environment variable was absent. |
| CONFIG_ERROR | Workflow or tool configuration was invalid. |
| INFRASTRUCTURE | Failure originated in GitHub's infrastructure, not the job itself. |
| UNCLASSIFIED | An honest answer: no rule matched. Shown with the best candidate excerpt. |

## Accuracy

Per-class precision, recall, and UNCLASSIFIED rate are measured against the committed fixture corpus. Current numbers: not yet measured (fixture corpus lands in P2, measurement in P3).

## Optional AI layer

`--ai` adds a prose explanation on top of the deterministic classification. Off by default. Bring your own key via an OpenAI-compatible base URL:

- `WHY_RED_AI_BASE_URL`
- `WHY_RED_AI_API_KEY`
- `WHY_RED_AI_MODEL`

Only the extracted excerpt is sent, never the full log. Never required — the tool is fully functional without it.

## Limitations

- GitHub Actions only.
- Requires `gh` CLI authentication.
- Subject to GitHub's log retention limits (logs are deleted after 90 days by default).
- Classification is rule-based; reports UNCLASSIFIED when unsure.
- Not yet released.

## Development

```bash
uv sync --all-groups
make gate
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ROADMAP.md](docs/ROADMAP.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
