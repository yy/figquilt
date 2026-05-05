"""SVG composer using lxml."""

from __future__ import annotations

import base64
from pathlib import Path

from lxml import etree

from .base_composer import BaseComposer, CellRect, ContentRect
from .layout import Panel

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
            g = self._create_panel_group(root, geometry.cell)
            image_parent = self._image_parent_for_panel(g, panel, geometry.cell)

            # Embed content
            self._embed_content(
                image_parent, panel, geometry.content, resolved.source.doc[0]
            )

            # Draw label on the outer group so it isn't clipped
            self._draw_label(g, panel, index)

    def _create_panel_group(self, root: etree.Element, cell: CellRect) -> etree.Element:
        """Create the translated group that owns one panel's SVG elements."""
        group = etree.SubElement(root, "g")
        group.set("transform", f"translate({cell.x}, {cell.y})")
        return group

    def _image_parent_for_panel(
        self,
        panel_group: etree.Element,
        panel: Panel,
        cell: CellRect,
    ) -> etree.Element:
        """Return the element that should contain the panel image."""
        if panel.fit == "cover":
            return self._create_cover_viewport(panel_group, cell)
        return panel_group

    def _create_cover_viewport(
        self, parent: etree.Element, cell: CellRect
    ) -> etree.Element:
        """Create the nested viewport that clips cover-mode content."""
        viewport = etree.SubElement(parent, "svg")
        viewport.set("x", "0")
        viewport.set("y", "0")
        viewport.set("width", str(cell.width))
        viewport.set("height", str(cell.height))
        viewport.set("viewBox", f"0 0 {cell.width} {cell.height}")
        viewport.set("preserveAspectRatio", "none")
        viewport.set("overflow", "hidden")
        return viewport

    def _embed_content(
        self,
        g: etree.Element,
        panel: Panel,
        content_rect: ContentRect,
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
        label_info = self.resolve_label_draw_info(panel, index)
        if label_info is None:
            return

        txt = etree.SubElement(parent, "text")
        txt.text = label_info.text
        txt.set("x", str(label_info.x))
        txt.set("y", str(label_info.y))
        txt.set("font-family", label_info.style.font_family)
        txt.set("font-size", f"{label_info.style.font_size_pt}pt")

        if label_info.style.bold:
            txt.set("font-weight", "bold")

        # Use hanging baseline so (x, y) is top-left of text
        txt.set("dominant-baseline", "hanging")
