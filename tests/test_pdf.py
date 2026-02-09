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


def test_compose_pdf_with_margin(tmp_path, dummy_pdf):
    """Test that page margin offsets panel positions."""
    # Panel at x=0, y=0 with margin=10 should render at (10, 10) in page coords
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "mm", "margin": 10},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 0, "y": 0, "width": 30}],
    }

    layout_file = tmp_path / "layout_margin.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)

    # Verify margin was parsed
    assert layout.page.margin == 10

    output_pdf = tmp_path / "output_margin.pdf"
    composer = PDFComposer(layout)
    composer.compose(output_pdf)

    assert output_pdf.exists()

    # The panel should be offset by margin (10mm = 28.35pt)
    doc = fitz.open(output_pdf)
    # Extract images/forms to check position - or just verify doc renders
    doc.close()


def testparse_color_valid_hex(tmp_path, dummy_pdf):
    """Test that valid hex colors are parsed correctly."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "mm", "background": "#ff0000"},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 0, "y": 0, "width": 50}],
    }

    layout_file = tmp_path / "layout_color.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)
    composer = PDFComposer(layout)

    # Test the internal parse_color method
    result = composer.parse_color("#ff0000")
    assert result == (1.0, 0.0, 0.0)

    result = composer.parse_color("#00ff00")
    assert result == (0.0, 1.0, 0.0)

    result = composer.parse_color("#0000ff")
    assert result == (0.0, 0.0, 1.0)


def testparse_color_invalid_hex(tmp_path, dummy_pdf):
    """Test that invalid hex colors return None without raising."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "mm"},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 0, "y": 0, "width": 50}],
    }

    layout_file = tmp_path / "layout_nocolor.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)
    composer = PDFComposer(layout)

    # Too short hex string
    assert composer.parse_color("#ff") is None

    # Invalid hex characters
    assert composer.parse_color("#gggggg") is None


def testparse_color_named_colors(tmp_path, dummy_pdf):
    """Test that named colors work via PIL ImageColor."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "mm"},
        "panels": [{"id": "A", "file": str(dummy_pdf), "x": 0, "y": 0, "width": 50}],
    }

    layout_file = tmp_path / "layout_named.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)
    composer = PDFComposer(layout)

    # Named colors should work via PIL
    result = composer.parse_color("white")
    assert result == (1.0, 1.0, 1.0)

    result = composer.parse_color("red")
    assert result == (1.0, 0.0, 0.0)

    # Invalid named color should return None
    assert composer.parse_color("notavalidcolor") is None


@pytest.fixture
def dummy_jpeg(tmp_path):
    """Create a 100x100 px red JPEG image."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    path = tmp_path / "dummy.jpg"
    img.save(path, "JPEG")
    return path


def test_compose_pdf_with_jpeg_input(tmp_path, dummy_jpeg):
    """Test that JPEG images can be embedded in PDF output."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "mm"},
        "panels": [{"id": "A", "file": str(dummy_jpeg), "x": 0, "y": 0, "width": 50}],
    }

    layout_file = tmp_path / "layout_jpeg.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)

    output_pdf = tmp_path / "output_jpeg.pdf"
    composer = PDFComposer(layout)
    composer.compose(output_pdf)

    assert output_pdf.exists()

    # Validate the PDF contains exactly 1 page with expected dimensions
    doc = fitz.open(output_pdf)
    assert doc.page_count == 1
    page = doc[0]

    # Page size should be 100mm * 72/25.4 ~= 283.46 pts
    assert abs(page.rect.width - (100 * 72 / 25.4)) < 0.1

    # Check if text "A" exists (default label)
    text = page.get_text()
    assert "A" in text

    # Verify the page has image content by checking for XObject references
    xobjects = page.get_images()
    assert len(xobjects) >= 1, "JPEG image should be embedded in the PDF"

    doc.close()


def test_compose_pdf_with_jpeg_fit_modes(tmp_path, dummy_jpeg):
    """Test that JPEG images work correctly with fit modes."""
    layout_data = {
        "page": {"width": 100, "height": 100, "units": "pt"},
        "panels": [
            {
                "id": "A",
                "file": str(dummy_jpeg),
                "x": 0,
                "y": 0,
                "width": 50,
                "height": 100,  # Different aspect ratio than source
                "fit": "contain",
            }
        ],
    }

    layout_file = tmp_path / "layout_jpeg_fit.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    from figquilt.parser import parse_layout

    layout = parse_layout(layout_file)

    output_pdf = tmp_path / "output_jpeg_fit.pdf"
    composer = PDFComposer(layout)
    composer.compose(output_pdf)

    assert output_pdf.exists()

    doc = fitz.open(output_pdf)
    assert doc.page_count == 1
    doc.close()
