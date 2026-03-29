"""Typer CLI application for modelarr."""

import typer

from modelarr import __version__

app = typer.Typer(
    help=(
        "modelarr - Radarr/Sonarr for LLM models. Monitors HuggingFace for "
        "new releases matching a watchlist and auto-downloads them to a "
        "local library."
    )
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"modelarr {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """modelarr - Radarr/Sonarr for LLM models."""
    pass
