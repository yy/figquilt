"""PDF composer using PyMuPDF (fitz)."""

from pathlib import Path

import fitz

from .base_composer import BaseComposer
from .layout import Layout, Panel
from .units import to_pt

# PyMuPDF font name mappings
_FONT_REGULAR = "helv"  # Helvetica
_FONT_BOLD = "HeBo"  # Helvetica-Bold


class PDFComposer(BaseComposer):
    def __init__(self, layout: Layout):
        super().__init__(layout)

    def compose(self, output_path: Path) -> None:
        doc = self.build()
        doc.save(str(output_path))
        doc.close()

    def build(self) -> fitz.Document:
        doc = fitz.open()
        page = doc.new_page(width=self.width_pt, height=self.height_pt)

        self._draw_background(page)

        panels = self.get_panels()
        for i, panel in enumerate(panels):
            self._place_panel(page, panel, index=i)

        return doc

    def _draw_background(self, page: fitz.Page) -> None:
        """Draw background color if specified."""
        if not self.layout.page.background:
            return

        col = self.parse_color(self.layout.page.background)
        if col:
            page.draw_rect(page.rect, color=col, fill=col)

    def _place_panel(self, page: fitz.Page, panel: Panel, index: int) -> None:
        """Place a panel on the page."""
        source_info = self.open_source(panel)

        try:
            content_rect = self.calculate_content_rect(panel, source_info.aspect_ratio)
            rect = fitz.Rect(
                content_rect.x + content_rect.offset_x,
                content_rect.y + content_rect.offset_y,
                content_rect.x + content_rect.offset_x + content_rect.width,
                content_rect.y + content_rect.offset_y + content_rect.height,
            )

            self._embed_content(page, rect, source_info.doc, panel)
        finally:
            source_info.doc.close()

        self._draw_label(page, panel, rect, index)

    def _embed_content(
        self, page: fitz.Page, rect: fitz.Rect, src_doc: fitz.Document, panel: Panel
    ) -> None:
        """Embed the source content into the page at the given rect."""
        if src_doc.is_pdf:
            page.show_pdf_page(rect, src_doc, 0)
        elif panel.file.suffix.lower() == ".svg":
            # Convert SVG to PDF in memory for vector preservation
            pdf_bytes = src_doc.convert_to_pdf()
            src_pdf = fitz.open("pdf", pdf_bytes)
            try:
                page.show_pdf_page(rect, src_pdf, 0)
            finally:
                src_pdf.close()
        else:
            # Insert as image (works for PNG/JPEG)
            page.insert_image(rect, filename=panel.file)

    def _draw_label(
        self, page: fitz.Page, panel: Panel, rect: fitz.Rect, index: int
    ) -> None:
        """Draw the label for a panel."""
        text = self.get_label_text(panel, index)
        if not text:
            return

        style = panel.label_style if panel.label_style else self.layout.page.label

        # Position: offset relative to top-left of content rect
        # PyMuPDF uses baseline positioning, so add font_size to Y
        pos_x = rect.x0 + to_pt(style.offset_x, self.units)
        pos_y = rect.y0 + to_pt(style.offset_y, self.units) + style.font_size_pt

        fontname = _FONT_BOLD if style.bold else _FONT_REGULAR

        page.insert_text(
            (pos_x, pos_y), text, fontsize=style.font_size_pt, fontname=fontname
        )
