from pathlib import Path
import base64
from lxml import etree
from .layout import Layout, Panel
from .units import to_pt
from .errors import FigQuiltError
import fitz


class SVGComposer:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.units = layout.page.units
        self.width_pt = to_pt(layout.page.width, self.units)
        self.height_pt = to_pt(layout.page.height, self.units)
        self.margin_pt = to_pt(layout.page.margin, self.units)

    def compose(self, output_path: Path):
        # Create root SVG element
        nsmap = {
            None: "http://www.w3.org/2000/svg",
            "xlink": "http://www.w3.org/1999/xlink",
        }
        root = etree.Element("svg", nsmap=nsmap)
        # SVG uses "in" for inches, "pt" for points, "mm" for millimeters
        svg_unit = "in" if self.units == "inches" else self.units
        root.set("width", f"{self.layout.page.width}{svg_unit}")
        root.set("height", f"{self.layout.page.height}{svg_unit}")
        root.set("viewBox", f"0 0 {self.width_pt} {self.height_pt}")
        root.set("version", "1.1")

        if self.layout.page.background:
            # Draw background
            bg = etree.SubElement(root, "rect")
            bg.set("width", "100%")
            bg.set("height", "100%")
            bg.set("fill", self.layout.page.background)

        # Get panels (resolves grid layout if needed)
        from .grid import resolve_layout

        panels = resolve_layout(self.layout)
        for i, panel in enumerate(panels):
            self._place_panel(root, panel, i)

        # Write to file
        tree = etree.ElementTree(root)
        with open(output_path, "wb") as f:
            tree.write(f, pretty_print=True, xml_declaration=True, encoding="utf-8")

    def _place_panel(self, root: etree.Element, panel: Panel, index: int):
        # Offset by page margin
        x = to_pt(panel.x, self.units) + self.margin_pt
        y = to_pt(panel.y, self.units) + self.margin_pt
        w = to_pt(panel.width, self.units)

        # Determine content sizing
        # For simplicity in V0, relying on fitz for aspect ratio of all inputs (robust)
        try:
            src_doc = fitz.open(panel.file)
        except Exception as e:
            raise FigQuiltError(f"Failed to inspect panel {panel.file}: {e}")

        try:
            src_page = src_doc[0]
            src_rect = src_page.rect
            src_aspect = src_rect.height / src_rect.width

            if panel.height is not None:
                h = to_pt(panel.height, self.units)
            else:
                h = w * src_aspect

            # Calculate content dimensions using fit mode and alignment
            from .units import calculate_fit

            content_w, content_h, offset_x, offset_y = calculate_fit(
                src_aspect, w, h, panel.fit, panel.align
            )

            # Group for the panel
            g = etree.SubElement(root, "g")
            g.set("transform", f"translate({x}, {y})")

            # For cover mode, add a clip path to crop the overflow
            if panel.fit == "cover":
                clip_id = f"clip-{panel.id}"
                defs = etree.SubElement(g, "defs")
                clip_path = etree.SubElement(defs, "clipPath")
                clip_path.set("id", clip_id)
                clip_rect = etree.SubElement(clip_path, "rect")
                clip_rect.set("x", "0")
                clip_rect.set("y", "0")
                clip_rect.set("width", str(w))
                clip_rect.set("height", str(h))

            # Insert content
            # Check if SVG
            suffix = panel.file.suffix.lower()
            if suffix == ".svg":
                # Embed SVG by creating an <image> tag with data URI to avoid DOM conflicts
                data_uri = self._get_data_uri(panel.file, "image/svg+xml")
                img = etree.SubElement(g, "image")
                img.set("x", str(offset_x))
                img.set("y", str(offset_y))
                img.set("width", str(content_w))
                img.set("height", str(content_h))
                img.set("{http://www.w3.org/1999/xlink}href", data_uri)
                if panel.fit == "cover":
                    img.set("clip-path", f"url(#{clip_id})")
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
                img.set("x", str(offset_x))
                img.set("y", str(offset_y))
                img.set("width", str(content_w))
                img.set("height", str(content_h))
                img.set("{http://www.w3.org/1999/xlink}href", data_uri)
                if panel.fit == "cover":
                    img.set("clip-path", f"url(#{clip_id})")

            # Label (positioned relative to content, not cell)
            self._draw_label(g, panel, content_w, content_h, offset_x, offset_y, index)
        finally:
            src_doc.close()

    def _get_data_uri(self, path: Path, mime: str) -> str:
        with open(path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _draw_label(
        self,
        parent: etree.Element,
        panel: Panel,
        content_w: float,
        content_h: float,
        offset_x: float,
        offset_y: float,
        index: int,
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

        # Offset relative to the content position
        x = offset_x + to_pt(style.offset_x, self.units)
        y = offset_y + to_pt(style.offset_y, self.units)

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
