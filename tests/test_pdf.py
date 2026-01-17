import pytest
import fitz
from figquilt.compose_pdf import PDFComposer
import yaml


@pytest.fixture
def dummy_pdf(tmp_path):
    # Create a 100x100 pt red square PDF
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(fitz.Rect(0, 0, 100, 100), color=(1, 0, 0), fill=(1, 0, 0))
    path = tmp_path / "dummy.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_compose_pdf_simple(tmp_path, dummy_pdf):
    # Layout: 100x100mm page, single panel at 0,0, width 50mm
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "mm"},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 0, "y": 0, "width": 50}],
    }

    layout_file = tmp_path / "layout_pdf.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    # We need to load layout objects (usually via parser, but testing composer directly here)
    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)

    output_pdf = tmp_path / "output.pdf"
    composer = PDFComposer(layout)
    composer.compose(output_pdf)

    assert output_pdf.exists()

    # Validation
    doc = fitz.open(output_pdf)
    assert doc.page_count == 1
    page = doc[0]
    # Page size should be 100mm * 72/25.4 ~= 283.46 pts
    assert abs(page.rect.width - (100 * 72 / 25.4)) < 0.1

    # Check if text "A" exists (default label)
    text = page.get_text()
    assert "A" in text
    doc.close()


def test_compose_pdf_inches(tmp_path, dummy_pdf):
    """Test that units: inches works correctly."""
    layout_data = {
        "page": {"width": 8, "height": 6, "units": "inches"},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 0, "y": 0, "width": 4}],
    }

    layout_file = tmp_path / "layout_inches.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)

    output_pdf = tmp_path / "output_inches.pdf"
    composer = PDFComposer(layout)
    composer.compose(output_pdf)

    assert output_pdf.exists()

    doc = fitz.open(output_pdf)
    page = doc[0]
    # 8 inches = 576 pts, 6 inches = 432 pts
    assert abs(page.rect.width - 576) < 0.1
    assert abs(page.rect.height - 432) < 0.1
    doc.close()


def test_compose_pdf_pt(tmp_path, dummy_pdf):
    """Test that units: pt works correctly."""
    layout_data = {
        "page": {"width": 400, "height": 300, "units": "pt"},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 10, "y": 10, "width": 100}],
    }

    layout_file = tmp_path / "layout_pt.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)

    output_pdf = tmp_path / "output_pt.pdf"
    composer = PDFComposer(layout)
    composer.compose(output_pdf)

    assert output_pdf.exists()

    doc = fitz.open(output_pdf)
    page = doc[0]
    # 400 pt, 300 pt directly
    assert abs(page.rect.width - 400) < 0.1
    assert abs(page.rect.height - 300) < 0.1
    doc.close()
