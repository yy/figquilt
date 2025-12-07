import pytest
from pathlib import Path
from figquilt.layout import Layout, Page, Panel
from figquilt.parser import parse_layout
from figquilt.errors import LayoutError, AssetMissingError
import yaml

@pytest.fixture
def valid_layout_data(tmp_path):
    panel_file = tmp_path / "panel.pdf"
    panel_file.touch()
    
    data = {
        "page": {
            "width": 100,
            "height": 100,
            "units": "mm"
        },
        "panels": [
            {
                "id": "A",
                "file": str(panel_file.name),
                "x": 0,
                "y": 0,
                "width": 50
            }
        ]
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
        "panels": [{"id": "A", "file": "non_existent.pdf", "x": 0, "y": 0, "width": 50}]
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
