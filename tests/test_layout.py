import pytest
from figquilt.layout import Layout
from figquilt.parser import parse_layout
from figquilt.errors import LayoutError, AssetMissingError
import yaml


@pytest.fixture
def valid_layout_data(tmp_path):
    panel_file = tmp_path / "panel.pdf"
    panel_file.touch()

    data = {
        "page": {"width": 100, "height": 100, "units": "mm"},
        "panels": [
            {"id": "A", "file": str(panel_file.name), "x": 0, "y": 0, "width": 50}
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(data, f)
    return layout_file


def test_parse_valid_layout(valid_layout_data):
    layout = parse_layout(valid_layout_data)
    assert isinstance(layout, Layout)
    assert layout.page.width == 100
    assert layout.panels[0].id == "A"
    assert layout.panels[0].width == 50


def test_missing_file_raises_error(tmp_path):
    data = {
        "page": {"width": 100, "height": 100},
        "panels": [
            {"id": "A", "file": "non_existent.pdf", "x": 0, "y": 0, "width": 50}
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(data, f)

    with pytest.raises(AssetMissingError):
        parse_layout(layout_file)


def test_invalid_yaml(tmp_path):
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        f.write("page: { invalid yaml")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_pydantic_validation_error(tmp_path):
    data = {"page": "not a dict", "panels": []}
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(data, f)

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_error_message_includes_line_number(tmp_path):
    """Error messages should include line numbers for easier debugging."""
    layout_file = tmp_path / "layout.yaml"
    # Write raw YAML so we know exact line numbers
    layout_file.write_text("""\
page:
  width: 100
  height: 100
panels:
  - id: A
    file: panel.pdf
    x: 0
    y: not_a_number
    width: 50
""")

    with pytest.raises(LayoutError) as exc_info:
        parse_layout(layout_file)

    # Error message should mention line 8 where the invalid 'y' value is
    assert "line 8" in str(exc_info.value)


# Grid layout tests


def test_parse_simple_row_layout(tmp_path):
    """A simple row layout with two panels."""
    panel_a = tmp_path / "a.pdf"
    panel_b = tmp_path / "b.pdf"
    panel_a.touch()
    panel_b.touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(f"""\
page:
  width: 180
  height: 100
  units: mm

layout:
  type: row
  ratios: [3, 2]
  gap: 5
  children:
    - id: A
      file: {panel_a.name}
    - id: B
      file: {panel_b.name}
""")

    layout = parse_layout(layout_file)
    assert layout.layout is not None
    assert layout.panels is None
    assert layout.layout.type == "row"
    assert layout.layout.ratios == [3, 2]
    assert layout.layout.gap == 5
    assert len(layout.layout.children) == 2
    assert layout.layout.children[0].id == "A"
    assert layout.layout.children[1].id == "B"


def test_parse_nested_layout(tmp_path):
    """A nested layout: column containing a leaf and a row."""
    for name in ["header.pdf", "left.pdf", "right.pdf"]:
        (tmp_path / name).touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text("""\
page:
  width: 180
  height: 200
  units: mm

layout:
  type: col
  ratios: [1, 2]
  children:
    - id: A
      file: header.pdf
    - type: row
      ratios: [1, 1]
      gap: 5
      children:
        - id: B
          file: left.pdf
        - id: C
          file: right.pdf
""")

    layout = parse_layout(layout_file)
    assert layout.layout.type == "col"
    assert len(layout.layout.children) == 2

    # First child is a leaf
    first = layout.layout.children[0]
    assert first.id == "A"
    assert not first.is_container()

    # Second child is a row container
    second = layout.layout.children[1]
    assert second.is_container()
    assert second.type == "row"
    assert len(second.children) == 2


def test_layout_must_have_panels_or_layout(tmp_path):
    """Layouts without panels or layout should fail."""
    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text("""\
page:
  width: 100
  height: 100
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_layout_cannot_have_both(tmp_path):
    """Layouts with both panels and layout should fail."""
    panel = tmp_path / "panel.pdf"
    panel.touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(f"""\
page:
  width: 100
  height: 100

panels:
  - id: A
    file: {panel.name}
    x: 0
    y: 0
    width: 50

layout:
  type: row
  children:
    - id: B
      file: {panel.name}
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_container_must_have_children(tmp_path):
    """Container nodes must have children."""
    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text("""\
page:
  width: 100
  height: 100

layout:
  type: row
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_ratios_must_match_children_count(tmp_path):
    """Ratios length must match children count."""
    for name in ["a.pdf", "b.pdf"]:
        (tmp_path / name).touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text("""\
page:
  width: 100
  height: 100

layout:
  type: row
  ratios: [1, 2, 3]
  children:
    - id: A
      file: a.pdf
    - id: B
      file: b.pdf
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_ratios_must_be_positive(tmp_path):
    """Ratios must be > 0."""
    for name in ["a.pdf", "b.pdf"]:
        (tmp_path / name).touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text("""\
page:
  width: 100
  height: 100

layout:
  type: row
  ratios: [1, 0]
  children:
    - id: A
      file: a.pdf
    - id: B
      file: b.pdf
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_page_margin_must_not_consume_page(tmp_path):
    """Page margin must leave positive content area."""
    panel = tmp_path / "panel.pdf"
    panel.touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(f"""\
page:
  width: 100
  height: 80
  margin: 40

panels:
  - id: A
    file: {panel.name}
    x: 0
    y: 0
    width: 10
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_duplicate_panel_ids_raise_error(tmp_path):
    """Panel IDs must be unique in explicit panel mode."""
    panel = tmp_path / "panel.pdf"
    panel.touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(f"""\
page:
  width: 100
  height: 100

panels:
  - id: A
    file: {panel.name}
    x: 0
    y: 0
    width: 40
  - id: A
    file: {panel.name}
    x: 50
    y: 0
    width: 40
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)


def test_duplicate_grid_leaf_ids_raise_error(tmp_path):
    """Panel IDs must be unique in grid layout mode."""
    panel = tmp_path / "panel.pdf"
    panel.touch()

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(f"""\
page:
  width: 100
  height: 100

layout:
  type: row
  children:
    - id: A
      file: {panel.name}
    - id: A
      file: {panel.name}
""")

    with pytest.raises(LayoutError):
        parse_layout(layout_file)
