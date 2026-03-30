"""Tests for the CLI application."""

from typer.testing import CliRunner

from modelarr.cli import app

runner = CliRunner()


def test_cli_help() -> None:
    """Test that --help works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "modelarr" in result.stdout
    assert "Radarr/Sonarr" in result.stdout


def test_cli_version() -> None:
    """Test that --version shows the version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.stdout
