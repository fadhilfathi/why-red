.PHONY: sync lint fmt fmt-check type test gate build clean

sync:
	uv sync --all-groups

lint:
	uv run ruff check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

fmt-check:
	uv run ruff format --check .

type:
	uv run mypy

test:
	uv run pytest --cov=why_red --cov-report=term-missing

gate: lint fmt-check type test

build:
	uv build

clean:
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
