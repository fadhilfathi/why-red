"""Typer entry point. Stages are wired in P1+; P0 only exposes --version."""

from __future__ import annotations

import typer

from why_red import __version__

app = typer.Typer(add_completion=False, no_args_is_help=True, rich_markup_mode=None)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"why-red {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version, is_eager=True, help="Show version."
    ),
) -> None:
    """Explain why a GitHub Actions run failed."""
