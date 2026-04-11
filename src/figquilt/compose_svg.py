"""SVG composer using lxml."""

import base64
from pathlib import Path

from lxml import etree

from .base_composer import BaseComposer
from .layout import Panel
from .units import to_pt


class SVGComposer(BaseComposer):
    def compose(self, output_path: Path) -> None:
        nsmap = {
            None: "http://www.w3.org/2000/svg",
            "xlink": "http://www.w3.org/1999/xlink",
        }
        root = etree.Element("svg", nsmap=nsmap)

        # Set SVG dimensions
        svg_unit = "in" if self.units == "inches" else self.units
        root.set("width", f"{self.layout.page.width}{svg_unit}")
        root.set("height", f"{self.layout.page.height}{svg_unit}")
        root.set("viewBox", f"0 0 {self.width_pt} {self.height_pt}")
        root.set("version", "1.1")

        self._draw_background(root)

        panels = self.get_panels()
        for i, panel in enumerate(panels):
            self._place_panel(root, panel, i)

        tree = etree.ElementTree(root)
        with open(output_path, "wb") as f:
            tree.write(f, pretty_print=True, xml_declaration=True, encoding="utf-8")

    def _draw_background(self, root: etree.Element) -> None:
        """Draw background color if specified."""
        if not self.layout.page.background:
            return

        bg = etree.SubElement(root, "rect")
        bg.set("width", "100%")
        bg.set("height", "100%")
        bg.set("fill", self.layout.page.background)

    def _place_panel(self, root: etree.Element, panel: Panel, index: int) -> None:
        """Place a panel on the SVG."""
        source_info = self.open_source(panel)

        try:
            geometry = self.calculate_panel_geometry(panel, source_info.aspect_ratio)
            content_rect = geometry.content

            # Create group for the panel
            g = etree.SubElement(root, "g")
            g.set("transform", f"translate({geometry.cell.x}, {geometry.cell.y})")

            # For cover mode, wrap the image in a nested <svg> viewport that
            # clips content to the cell bounds. An explicit viewBox makes
            # this work across SVG renderers (including fitz).
            if panel.fit == "cover":
                image_parent = etree.SubElement(g, "svg")
                image_parent.set("x", "0")
                image_parent.set("y", "0")
                image_parent.set("width", str(geometry.cell.width))
                image_parent.set("height", str(geometry.cell.height))
                image_parent.set(
                    "viewBox",
                    f"0 0 {geometry.cell.width} {geometry.cell.height}",
                )
                image_parent.set("preserveAspectRatio", "none")
                image_parent.set("overflow", "hidden")
            else:
                image_parent = g

            # Embed content
            self._embed_content(image_parent, panel, content_rect, source_info.doc[0])

            # Draw label on the outer group so it isn't clipped
            self._draw_label(g, panel, index)
        finally:
            source_info.doc.close()

    def _embed_content(
        self,
        g: etree.Element,
        panel: Panel,
        content_rect,
        src_page,
    ) -> None:
        """Embed the source content into the SVG group."""
        suffix = panel.file.suffix.lower()

        if suffix == ".svg":
            data_uri = self._get_data_uri(panel.file, "image/svg+xml")
        elif suffix in [".jpg", ".jpeg"]:
            data_uri = self._get_data_uri(panel.file, "image/jpeg")
        elif suffix == ".png":
            data_uri = self._get_data_uri(panel.file, "image/png")
        elif suffix == ".pdf":
            # Rasterize PDF page to PNG
            pix = src_page.get_pixmap(dpi=self.layout.page.dpi)
            data = pix.tobytes("png")
            b64 = base64.b64encode(data).decode("utf-8")
            data_uri = f"data:image/png;base64,{b64}"
        else:
            # Fallback for unknown types
            data_uri = self._get_data_uri(panel.file, "application/octet-stream")

        img = etree.SubElement(g, "image")
        img.set("x", str(content_rect.offset_x))
        img.set("y", str(content_rect.offset_y))
        img.set("width", str(content_rect.width))
        img.set("height", str(content_rect.height))
        img.set("{http://www.w3.org/1999/xlink}href", data_uri)

    def _get_data_uri(self, path: Path, mime: str) -> str:
        """Read file and encode as data URI."""
        with open(path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _draw_label(
        self,
        parent: etree.Element,
        panel: Panel,
        index: int,
    ) -> None:
        """Draw the label for a panel."""
        text_str = self.get_label_text(panel, index)
        if not text_str:
            return

        style = self.get_label_style(panel)

        # The parent group is already translated to the panel cell origin.
        x = to_pt(style.offset_x, self.units)
        y = to_pt(style.offset_y, self.units)

        txt = etree.SubElement(parent, "text")
        txt.text = text_str
        txt.set("x", str(x))
        txt.set("y", str(y))
        txt.set("font-family", style.font_family)
        txt.set("font-size", f"{style.font_size_pt}pt")

        if style.bold:
            txt.set("font-weight", "bold")

        # Use hanging baseline so (x, y) is top-left of text
        txt.set("dominant-baseline", "hanging")
