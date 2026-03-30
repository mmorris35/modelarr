"""Tests for the serve CLI command."""

from typer.testing import CliRunner

from modelarr.cli import app

runner = CliRunner()


def test_serve_help():
    """Test that modelarr serve --help works."""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "Start the web UI" in result.stdout
    assert "--interval" in result.stdout
    assert "8585" in result.stdout
