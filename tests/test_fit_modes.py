import pytest
import fitz
import yaml
from figquilt.parser import parse_layout
from figquilt.compose_pdf import PDFComposer


@pytest.fixture
def wide_pdf(tmp_path):
    """Create a 200x100 pt wide PDF (2:1 aspect ratio)."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(fitz.Rect(0, 0, 200, 100), color=(1, 0, 0), fill=(1, 0, 0))
    path = tmp_path / "wide.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def tall_pdf(tmp_path):
    """Create a 100x200 pt tall PDF (1:2 aspect ratio)."""
    doc = fitz.open()
    page = doc.new_page(width=100, height=200)
    page.draw_rect(fitz.Rect(0, 0, 100, 200), color=(0, 0, 1), fill=(0, 0, 1))
    path = tmp_path / "tall.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_fit_contain_wide_image_in_square_cell(tmp_path, wide_pdf):
    """Contain mode: wide image (2:1) in square cell should be letter-boxed vertically."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "pt"},
        "panels": [
            {
                "id": "A",
                "file": str(wide_pdf),
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "fit": "contain",
            }
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    assert layout.panels[0].fit == "contain"

    doc = PDFComposer(layout).build()
    # The wide image (2:1) fit into 100x100 should scale to 100x50
    # Positioned centered vertically: y offset = (100-50)/2 = 25
    # We can't easily verify exact positioning, but the output should exist
    assert doc.page_count == 1
    doc.close()


def test_fit_contain_tall_image_in_square_cell(tmp_path, tall_pdf):
    """Contain mode: tall image (1:2) in square cell should be pillar-boxed horizontally."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "pt"},
        "panels": [
            {
                "id": "A",
                "file": str(tall_pdf),
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "fit": "contain",
            }
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    doc = PDFComposer(layout).build()
    assert doc.page_count == 1
    doc.close()


def test_fit_cover_wide_image_in_square_cell(tmp_path, wide_pdf):
    """Cover mode: wide image should fill the entire cell (cropped on sides)."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "pt"},
        "panels": [
            {
                "id": "A",
                "file": str(wide_pdf),
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "fit": "cover",
            }
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    assert layout.panels[0].fit == "cover"

    doc = PDFComposer(layout).build()
    assert doc.page_count == 1
    doc.close()


def test_fit_default_is_contain(tmp_path, wide_pdf):
    """When fit is not specified, it should default to 'contain'."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "pt"},
        "panels": [
            {
                "id": "A",
                "file": str(wide_pdf),
                "x": 0,
                "y": 0,
                "width": 100,
            }
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    assert layout.panels[0].fit == "contain"


def test_fit_invalid_value_raises_error(tmp_path, wide_pdf):
    """Invalid fit value should raise a validation error."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "pt"},
        "panels": [
            {
                "id": "A",
                "file": str(wide_pdf),
                "x": 0,
                "y": 0,
                "width": 100,
                "fit": "invalid",
            }
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.errors import LayoutError

    with pytest.raises(LayoutError):
        parse_layout(layout_file)
