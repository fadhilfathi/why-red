# Contributing

## Setup

```bash
uv sync --all-groups
pre-commit install
```

Run `make gate` (ruff, ruff format --check, mypy, pytest) before every push.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `ci:`, `test:`, `build:`, `chore:`. The body explains why, not what.

## Tests must have teeth

A test that can't fail proves nothing. Verify new tests by mutation: break the code the test is supposed to catch and confirm the test fails, then revert.

## Fixture contributions

- Harvest logs from public repositories only.
- Redact tokens, emails, internal hostnames, and org names before committing.
- Hand-label the `FailureClass` per the criteria in `docs/LABELING.md`.
- One fixture = one `.log` file + one entry in the labels file.
- Never tune classifier rules against fixtures that have already been used for measurement (`docs/ACCURACY.md`). Add new fixtures first, then adjust rules.

## PR checklist

- [ ] `make gate` is green
- [ ] Commit title follows Conventional Commits
- [ ] New/changed logic has a test, and that test was verified by mutation
- [ ] Any new fixtures are redacted
- [ ] No metric claims (accuracy, compression, speed) without a measurement backing them
