"""Capture CLI output as SVG screenshots for README."""
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.text import Text

ASSETS_DIR = Path(__file__).parent.parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)


def capture(name: str, command: list[str]) -> None:
    """Run a command and save its output as SVG."""
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "COLUMNS": "100", "FORCE_COLOR": "1", "TERM": "xterm-256color"},
    )
    output = result.stdout + result.stderr

    console = Console(record=True, width=100, force_terminal=True)
    console.print(Text.from_ansi(output))
    svg = console.export_svg(title=f"modelarr {' '.join(command[2:])}")

    svg_path = ASSETS_DIR / f"{name}.svg"
    svg_path.write_text(svg)
    print(f"  Saved {svg_path}")


if __name__ == "__main__":
    print("Capturing screenshots...")
    capture("help", ["uv", "run", "modelarr", "--help"])
    capture("watch-list", ["uv", "run", "modelarr", "watch", "list"])
    capture("config-show", ["uv", "run", "modelarr", "config", "show"])
    capture("watch-help", ["uv", "run", "modelarr", "watch", "--help"])
    capture("library-help", ["uv", "run", "modelarr", "library", "--help"])
    capture("monitor-help", ["uv", "run", "modelarr", "monitor", "--help"])
    print("Done!")
