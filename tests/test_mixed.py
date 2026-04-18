import pytest
import fitz
from lxml import etree
from figquilt.compose_pdf import PDFComposer
from figquilt.compose_svg import SVGComposer
from figquilt.parser import parse_layout
import yaml
from PIL import Image, ImageDraw


@pytest.fixture
def dummy_assets(tmp_path):
    # PDF
    path_pdf = tmp_path / "panel.pdf"
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(fitz.Rect(0, 0, 100, 100), color=(0, 0, 1))
    doc.save(str(path_pdf))
    doc.close()

    # PNG
    path_png = tmp_path / "panel.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(path_png)

    # SVG
    path_svg = tmp_path / "panel.svg"
    with open(path_svg, "w") as f:
        f.write(
            '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100" fill="green"/></svg>'
        )

    return path_pdf, path_png, path_svg


def test_compose_mixed_to_pdf(tmp_path, dummy_assets):
    pdf, png, svg = dummy_assets
    layout_data = {
        "page": {"width": 150, "height": 50},
        "panels": [
            {"id": "A", "file": str(pdf), "x": 0, "y": 0, "width": 50},
            {"id": "B", "file": str(png), "x": 50, "y": 0, "width": 50},
            {"id": "C", "file": str(svg), "x": 100, "y": 0, "width": 50},
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)

    # PDF Output
    out_pdf = tmp_path / "fig.pdf"
    composer = PDFComposer(layout)
    composer.compose(out_pdf)
    assert out_pdf.exists()

    # Verify content roughly
    doc = fitz.open(out_pdf)
    assert doc.page_count == 1
    doc.close()


def test_compose_mixed_to_svg(tmp_path, dummy_assets):
    pdf, png, svg = dummy_assets
    layout_data = {
        "page": {"width": 150, "height": 50},
        "panels": [
            {"id": "A", "file": str(pdf), "x": 0, "y": 0, "width": 50},
            {"id": "B", "file": str(png), "x": 50, "y": 0, "width": 50},
            {"id": "C", "file": str(svg), "x": 100, "y": 0, "width": 50},
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)

    out_svg = tmp_path / "fig.svg"
    composer = SVGComposer(layout)
    composer.compose(out_svg)
    assert out_svg.exists()

    # Check for <image> tags
    content = out_svg.read_text()
    assert content.count("<image") >= 3
    assert "data:image/svg+xml" in content  # The SVG panel
    assert "data:image/png" in content  # The PDF (rasterized) and PNG panel


def test_compose_to_png(tmp_path, dummy_assets):
    pdf, _, _ = dummy_assets
    layout_data = {
        "page": {"width": 100, "height": 100},
        "panels": [
            {"id": "A", "file": str(pdf), "x": 0, "y": 0, "width": 50},
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)

    # Mock CLI logic manually
    composer = PDFComposer(layout)
    doc = composer.build()
    pix = doc[0].get_pixmap(dpi=72)
    out_png = tmp_path / "fig.png"
    pix.save(str(out_png))
    doc.close()

    assert out_png.exists()


def test_svg_pdf_rasterization_uses_page_dpi(tmp_path, dummy_assets, monkeypatch):
    """SVG output should use page.dpi when rasterizing PDF panels."""
    pdf, _, _ = dummy_assets
    layout_data = {
        "page": {"width": 100, "height": 100, "dpi": 123},
        "panels": [{"id": "A", "file": str(pdf), "x": 0, "y": 0, "width": 50}],
    }
    layout_file = tmp_path / "layout_dpi.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)

    seen_dpi = []
    original_get_pixmap = fitz.Page.get_pixmap

    def wrapped_get_pixmap(self, *args, **kwargs):
        if "dpi" in kwargs:
            seen_dpi.append(kwargs["dpi"])
        return original_get_pixmap(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_pixmap", wrapped_get_pixmap)

    out_svg = tmp_path / "fig_dpi.svg"
    SVGComposer(layout).compose(out_svg)
    assert out_svg.exists()
    assert 123 in seen_dpi


def test_compose_jpeg_to_svg_uses_jpeg_data_uri(tmp_path):
    jpeg = tmp_path / "panel.jpeg"
    Image.new("RGB", (100, 100), color="purple").save(jpeg, format="JPEG")

    layout_data = {
        "page": {"width": 50, "height": 50},
        "panels": [{"id": "A", "file": str(jpeg), "x": 0, "y": 0, "width": 50}],
    }
    layout_file = tmp_path / "layout_jpeg.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)

    out_svg = tmp_path / "fig_jpeg.svg"
    SVGComposer(layout).compose(out_svg)

    assert "data:image/jpeg" in out_svg.read_text()


def test_svg_cover_mode_keeps_label_inside_panel_cell(tmp_path):
    """SVG cover-mode labels should anchor to the panel cell, not cropped content."""
    wide_pdf = tmp_path / "wide.pdf"
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(page.rect, color=(1, 0, 0), fill=(1, 0, 0))
    doc.save(str(wide_pdf))
    doc.close()

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
    layout_file = tmp_path / "layout_cover_label.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    out_svg = tmp_path / "cover_label.svg"
    SVGComposer(layout).compose(out_svg)

    root = etree.fromstring(out_svg.read_bytes())
    text = root.find(".//{http://www.w3.org/2000/svg}text")
    assert text is not None
    assert text.text == "A"
    assert float(text.get("x")) == pytest.approx(2.0)
    assert float(text.get("y")) == pytest.approx(2.0)


def test_svg_cover_mode_wraps_image_in_clipping_viewport(tmp_path):
    """SVG cover mode should wrap the image in a nested <svg> viewport
    sized to the panel cell, so proper SVG renderers clip overflow.

    Note: fitz/MuPDF does not honor SVG clipping when rendering SVG input,
    so this test verifies the structural contract only. Browsers, Inkscape,
    rsvg, and cairosvg all honor nested-<svg> viewport clipping per the
    SVG spec.
    """
    wide_png = tmp_path / "wide.png"
    img = Image.new("RGB", (200, 100), color="white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 99, 99], fill="red")
    draw.rectangle([100, 0, 199, 99], fill="blue")
    img.save(wide_png)

    layout_data = {
        "page": {"width": 100, "height": 60, "units": "pt", "background": "white"},
        "panels": [
            {
                "id": "A B",
                "file": str(wide_png),
                "x": 20,
                "y": 5,
                "width": 20,
                "height": 40,
                "fit": "cover",
            }
        ],
    }
    layout_file = tmp_path / "layout_cover_clip.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    out_svg = tmp_path / "cover_clip.svg"
    SVGComposer(layout).compose(out_svg)

    root = etree.fromstring(out_svg.read_bytes())
    ns = "{http://www.w3.org/2000/svg}"

    # The panel group should contain a nested <svg> viewport sized to the cell.
    panel_group = root.find(f".//{ns}g")
    assert panel_group is not None
    nested_svg = panel_group.find(f"./{ns}svg")
    assert nested_svg is not None, "cover mode must wrap image in nested <svg> viewport"
    assert float(nested_svg.get("width")) == pytest.approx(20.0)
    assert float(nested_svg.get("height")) == pytest.approx(40.0)

    # The <image> must be a child of the nested viewport, with cover-mode
    # dimensions (wider than the viewport so clipping is required).
    image = nested_svg.find(f"./{ns}image")
    assert image is not None, "image must be inside the clipping viewport"
    assert float(image.get("width")) > 20.0

    # Label stays on the outer group so it isn't clipped.
    label = panel_group.find(f"./{ns}text")
    assert label is not None


def test_svg_contain_mode_keeps_label_inside_panel_cell(tmp_path):
    """SVG contain-mode labels should anchor to the panel cell, not letterboxed content."""
    wide_pdf = tmp_path / "wide.pdf"
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(page.rect, color=(1, 0, 0), fill=(1, 0, 0))
    doc.save(str(wide_pdf))
    doc.close()

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
                "align": "center",
            }
        ],
    }
    layout_file = tmp_path / "layout_contain_label.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    out_svg = tmp_path / "contain_label.svg"
    SVGComposer(layout).compose(out_svg)

    root = etree.fromstring(out_svg.read_bytes())
    text = root.find(".//{http://www.w3.org/2000/svg}text")
    assert text is not None
    assert text.text == "A"
    assert float(text.get("x")) == pytest.approx(2.0)
    assert float(text.get("y")) == pytest.approx(2.0)


def test_pdf_contain_mode_keeps_label_inside_panel_cell(tmp_path):
    """PDF contain-mode labels should anchor to the panel cell, not letterboxed content."""
    wide_pdf = tmp_path / "wide.pdf"
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    page.draw_rect(page.rect, color=(1, 0, 0), fill=(1, 0, 0))
    doc.save(str(wide_pdf))
    doc.close()

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
                "align": "center",
            }
        ],
    }
    layout_file = tmp_path / "layout_contain_label.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(layout_data, f)

    layout = parse_layout(layout_file)
    out_pdf = tmp_path / "contain_label.pdf"
    PDFComposer(layout).compose(out_pdf)

    doc = fitz.open(out_pdf)
    try:
        blocks = doc[0].get_text("dict")["blocks"]
        label_bbox = None
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text") == "A":
                        label_bbox = span["bbox"]
                        break
                if label_bbox is not None:
                    break
            if label_bbox is not None:
                break
        assert label_bbox is not None
        assert label_bbox[0] == pytest.approx(2.0, abs=0.1)
        assert label_bbox[1] < 10.0
    finally:
        doc.close()
