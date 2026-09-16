"""Typer entry point. P1 wires fetch + cache + locate; classify/extract/render follow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from why_red import __version__
from why_red.fetch.cache import default_cache_dir
from why_red.fetch.github import GhError
from why_red.pipeline import Loaded, load_dir, load_run, locate_in

app = typer.Typer(add_completion=False, rich_markup_mode=None)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"why-red {__version__}")
        raise typer.Exit


def repo_from_git(cwd: Path | None = None) -> str | None:
    """`owner/name` from the origin remote, or None when not in a GitHub checkout."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=cwd
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip().removesuffix(".git")
    for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/"):
        if url.startswith(prefix):
            return url.removeprefix(prefix)
    return None


@app.command()
def main(
    run_id: Annotated[int | None, typer.Argument(help="GitHub Actions run id.")] = None,
    repo: Annotated[
        str | None, typer.Option("--repo", "-R", help="owner/name; default: origin remote.")
    ] = None,
    fixture: Annotated[
        Path | None, typer.Option(help="Read a fixture/cache directory instead of GitHub.")
    ] = None,
    cache_dir: Annotated[Path | None, typer.Option(help="Override the cache directory.")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Bypass the cache.")] = False,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=_version, is_eager=True)
    ] = False,
) -> None:
    """Explain why a GitHub Actions run failed."""
    if fixture is not None:
        loaded = load_dir(fixture)
    else:
        if run_id is None:
            typer.echo("error: a run id is required (or --fixture DIR)", err=True)
            raise typer.Exit(2)
        repo = repo or repo_from_git()
        if repo is None:
            typer.echo("error: --repo owner/name required (no GitHub origin remote)", err=True)
            raise typer.Exit(2)
        root = None if no_cache else (cache_dir or default_cache_dir())
        try:
            loaded = load_run(repo, run_id, root)
        except GhError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(1) from exc
    _print_location(loaded)


def _print_location(loaded: Loaded) -> None:
    run = loaded.run
    typer.echo(f"run {run.id} {run.repo} {run.workflow_name!r} {run.status}/{run.conclusion.value}")
    loc = locate_in(loaded)
    if loc is None:
        typer.echo("no failed job in this run")
        return
    typer.echo(f"job  {loc.job_id} {loc.job_name}")
    typer.echo(f"step {loc.step_number} {loc.step_name}")
    typer.echo(f"why  {loc.reason}")
    if loc.other_failed_steps:
        typer.echo(f"also failed: steps {loc.other_failed_steps}")
    if loc.line_range:
        typer.echo(f"log lines {loc.line_range[0]}-{loc.line_range[1]}")
    for err in loaded.log_errors.values():
        typer.echo(f"warning: {err}", err=True)
