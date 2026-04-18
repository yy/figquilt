"""SVG composer using lxml."""

import base64
from pathlib import Path

from lxml import etree

from .base_composer import BaseComposer
from .layout import Panel
from .units import to_pt

_EMBEDDED_MIME_TYPES = {
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


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
        with self.resolved_panel_source(panel) as resolved:
            geometry = resolved.geometry
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
            self._embed_content(
                image_parent, panel, content_rect, resolved.source.doc[0]
            )

            # Draw label on the outer group so it isn't clipped
            self._draw_label(g, panel, index)

    def _embed_content(
        self,
        g: etree.Element,
        panel: Panel,
        content_rect,
        src_page,
    ) -> None:
        """Embed the source content into the SVG group."""
        img = etree.SubElement(g, "image")
        img.set("x", str(content_rect.offset_x))
        img.set("y", str(content_rect.offset_y))
        img.set("width", str(content_rect.width))
        img.set("height", str(content_rect.height))
        img.set(
            "{http://www.w3.org/1999/xlink}href",
            self._data_uri_for_panel_source(panel, src_page),
        )

    def _data_uri_for_panel_source(self, panel: Panel, src_page) -> str:
        """Return the data URI used to embed a panel source in the output SVG."""
        if panel.file.suffix.lower() == ".pdf":
            return self._pdf_page_data_uri(src_page)

        mime = _EMBEDDED_MIME_TYPES.get(
            panel.file.suffix.lower(), "application/octet-stream"
        )
        return self._file_data_uri(panel.file, mime)

    def _pdf_page_data_uri(self, src_page) -> str:
        """Rasterize a PDF page and return it as a PNG data URI."""
        pix = src_page.get_pixmap(dpi=self.layout.page.dpi)
        return self._encode_data_uri(pix.tobytes("png"), "image/png")

    def _file_data_uri(self, path: Path, mime: str) -> str:
        """Read file and encode as data URI."""
        with open(path, "rb") as f:
            return self._encode_data_uri(f.read(), mime)

    @staticmethod
    def _encode_data_uri(data: bytes, mime: str) -> str:
        """Encode raw bytes as a data URI."""
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
