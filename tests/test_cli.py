from typer.testing import CliRunner

from why_red import __version__
from why_red.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"why-red {__version__}"


def test_no_args_shows_help_and_is_ascii() -> None:
    result = runner.invoke(app, [])
    assert "Explain why a GitHub Actions run failed" in result.output
    # Windows cp1252 consoles must never choke on our help text.
    result.output.encode("cp1252")
