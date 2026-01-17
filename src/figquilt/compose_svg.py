from pathlib import Path
import base64
from lxml import etree
from .layout import Layout, Panel
from .units import mm_to_pt
from .errors import FigQuiltError
import fitz


class SVGComposer:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.width_pt = mm_to_pt(layout.page.width)
        self.height_pt = mm_to_pt(layout.page.height)

    def compose(self, output_path: Path):
        # Create root SVG element
        nsmap = {
            None: "http://www.w3.org/2000/svg",
            "xlink": "http://www.w3.org/1999/xlink",
        }
        root = etree.Element("svg", nsmap=nsmap)
        root.set("width", f"{self.layout.page.width}mm")
        root.set("height", f"{self.layout.page.height}mm")
        root.set("viewBox", f"0 0 {self.width_pt} {self.height_pt}")
        root.set("version", "1.1")

        if self.layout.page.background:
            # Draw background
            bg = etree.SubElement(root, "rect")
            bg.set("width", "100%")
            bg.set("height", "100%")
            bg.set("fill", self.layout.page.background)

        # Draw panels
        for i, panel in enumerate(self.layout.panels):
            self._place_panel(root, panel, i)

        # Write to file
        tree = etree.ElementTree(root)
        with open(output_path, "wb") as f:
            tree.write(f, pretty_print=True, xml_declaration=True, encoding="utf-8")

    def _place_panel(self, root: etree.Element, panel: Panel, index: int):
        x = mm_to_pt(panel.x)
        y = mm_to_pt(panel.y)
        w = mm_to_pt(panel.width)

        # Determine content sizing
        # For simplicity in V0, relying on fitz for aspect ratio of all inputs (robust)
        try:
            src_doc = fitz.open(panel.file)
        except Exception as e:
            raise FigQuiltError(f"Failed to inspect panel {panel.file}: {e}")

        try:
            src_page = src_doc[0]
            src_rect = src_page.rect
            aspect = src_rect.height / src_rect.width

            if panel.height is not None:
                h = mm_to_pt(panel.height)
            else:
                h = w * aspect

            # Group for the panel
            g = etree.SubElement(root, "g")
            g.set("transform", f"translate({x}, {y})")

            # Insert content
            # Check if SVG
            suffix = panel.file.suffix.lower()
            if suffix == ".svg":
                # Embed SVG by creating an <image> tag with data URI to avoid DOM conflicts
                # This is safer than merging trees for V0.
                # Merging trees requires stripping root, handling viewbox/transform matching.
                # <image> handles scaling automatically.
                data_uri = self._get_data_uri(panel.file, "image/svg+xml")
                img = etree.SubElement(g, "image")
                img.set("width", str(w))
                img.set("height", str(h))
                img.set("{http://www.w3.org/1999/xlink}href", data_uri)
            else:
                # PDF or Raster Image
                # For PDF, we rasterize to PNG (easiest for SVG compatibility without huge libs)
                # Browsers don't support image/pdf in SVG.
                # If PNG/JPG, embed directly.

                mime = "image/png"
                if suffix in [".jpg", ".jpeg"]:
                    mime = "image/jpeg"
                    data_path = panel.file
                elif suffix == ".png":
                    mime = "image/png"
                    data_path = panel.file
                elif suffix == ".pdf":
                    # Rasterize page to PNG
                    pix = src_page.get_pixmap(dpi=300)
                    data = pix.tobytes("png")
                    b64 = base64.b64encode(data).decode("utf-8")
                    data_uri = f"data:image/png;base64,{b64}"
                    data_path = None  # signal that we have URI
                else:
                    # Fallback
                    mime = "application/octet-stream"
                    data_path = panel.file

                if data_path:
                    data_uri = self._get_data_uri(data_path, mime)

                img = etree.SubElement(g, "image")
                img.set("width", str(w))
                img.set("height", str(h))
                img.set("{http://www.w3.org/1999/xlink}href", data_uri)

            # Label
            self._draw_label(g, panel, w, h, index)
        finally:
            src_doc.close()

    def _get_data_uri(self, path: Path, mime: str) -> str:
        with open(path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _draw_label(
        self, parent: etree.Element, panel: Panel, w: float, h: float, index: int
    ):
        style = panel.label_style if panel.label_style else self.layout.page.label
        if not style.enabled:
            return

        text_str = panel.label
        if text_str is None and style.auto_sequence:
            text_str = chr(65 + index)
        if not text_str:
            return
        if style.uppercase:
            text_str = text_str.upper()

        # Offset (relative to panel top-left, which is 0,0 inside the group)
        x = mm_to_pt(style.offset_x_mm)
        y = mm_to_pt(style.offset_y_mm)

        # Create text element
        txt = etree.SubElement(parent, "text")
        txt.text = text_str
        txt.set("x", str(x))
        txt.set("y", str(y))

        # Style
        # Font family is tricky in SVG (system fonts).
        txt.set("font-family", style.font_family)
        txt.set("font-size", f"{style.font_size_pt}pt")
        if style.bold:
            txt.set("font-weight", "bold")

        # Baseline alignment? SVG text y is usually baseline.
        # If we want top-left of text at (x,y), we should adjust or use dominant-baseline.
        txt.set("dominant-baseline", "hanging")  # Matches top-down coordinate logic
