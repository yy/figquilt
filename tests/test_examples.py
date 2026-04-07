from pathlib import Path

import pytest

from figquilt.grid import resolve_layout
from figquilt.parser import parse_layout


EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize(
    "layout_path",
    sorted(EXAMPLES_DIR.glob("*.yaml")) + sorted(EXAMPLES_DIR.glob("*.json")),
    ids=lambda path: path.name,
)
def test_example_layouts_are_runnable(layout_path: Path):
    """Checked-in example layouts should resolve against checked-in example assets."""
    layout = parse_layout(layout_path)
    panels = resolve_layout(layout)

    assert panels
