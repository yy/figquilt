import pytest
import fitz
from figquilt.compose_pdf import PDFComposer
from figquilt.compose_svg import SVGComposer
from figquilt.parser import parse_layout
import yaml
from PIL import Image

@pytest.fixture
def dummy_assets(tmp_path):
    # PDF
    path_pdf = tmp_path / "panel.pdf"
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(fitz.Rect(0,0,100,100), color=(0,0,1))
    doc.save(str(path_pdf))
    doc.close()

    # PNG
    path_png = tmp_path / "panel.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(path_png)
    
    # SVG
    path_svg = tmp_path / "panel.svg"
    with open(path_svg, "w") as f:
        f.write('<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100" fill="green"/></svg>')
        
    return path_pdf, path_png, path_svg

def test_compose_mixed_to_pdf(tmp_path, dummy_assets):
    pdf, png, svg = dummy_assets
    layout_data = {
        "page": {"width": 150, "height": 50},
        "panels": [
            {"id": "A", "file": str(pdf), "x": 0, "y": 0, "width": 50},
            {"id": "B", "file": str(png), "x": 50, "y": 0, "width": 50},
            {"id": "C", "file": str(svg), "x": 100, "y": 0, "width": 50},
        ]
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
        ]
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
    assert "data:image/svg+xml" in content # The SVG panel
    assert "data:image/png" in content # The PDF (rasterized) and PNG panel

def test_compose_to_png(tmp_path, dummy_assets):
    pdf, _, _ = dummy_assets
    layout_data = {
        "page": {"width": 100, "height": 100},
        "panels": [
            {"id": "A", "file": str(pdf), "x": 0, "y": 0, "width": 50},
        ]
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
