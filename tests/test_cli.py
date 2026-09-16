from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import FakeGh
from why_red import __version__
from why_red.cli import app, repo_from_git

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cases" / "pytest-test-failure-matrix"
runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"why-red {__version__}"


def test_help_is_cp1252_safe() -> None:
    result = runner.invoke(app, ["--help"])
    assert "Explain why a GitHub Actions run failed" in result.output
    result.output.encode("cp1252")


def test_missing_run_id_is_usage_error() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "run id is required" in result.output


def test_fixture_mode_is_offline_and_locates() -> None:
    result = runner.invoke(app, ["--fixture", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    assert "step 6 Test without coverage" in result.output
    assert "why  only failed step in job" in result.output
    assert "log lines " in result.output
    result.output.encode("cp1252")


def test_repo_from_git_parses_common_remotes(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for url in (
        "https://github.com/o/r.git",
        "git@github.com:o/r.git",
        "ssh://git@github.com/o/r",
    ):
        subprocess.run(["git", "-C", str(tmp_path), "remote", "rm", "origin"], check=False)
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", url], check=True)
        assert repo_from_git(tmp_path) == "o/r", url
    assert repo_from_git(tmp_path / "nope") is None


def test_network_path_uses_gh_and_cache(fake_gh: FakeGh, tmp_path: Path) -> None:
    from tests.test_fetch import _arm

    _arm(fake_gh)
    args = ["42", "-R", "o/r", "--cache-dir", str(tmp_path / "c")]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "step 2 Test" in first.output
    second = runner.invoke(app, args)
    assert second.output == first.output
    assert sum(c[1].endswith("/logs") for c in fake_gh.calls) == 1
    assert (tmp_path / "c" / "o__r" / "42").is_dir()


def test_gh_error_exits_one(fake_gh: FakeGh) -> None:
    result = runner.invoke(app, ["99", "-R", "o/r", "--no-cache"])
    assert result.exit_code == 1
    assert "HTTP 404" in result.output
