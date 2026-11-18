"""Qt stylesheet loading."""

from pathlib import Path


def load_stylesheet():
    stylesheet_path = Path(__file__).with_name("theme.qss")
    return stylesheet_path.read_text(encoding="utf-8")
