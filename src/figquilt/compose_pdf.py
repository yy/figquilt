"""PDF composer using PyMuPDF (fitz)."""

from pathlib import Path

import fitz

from .base_composer import BaseComposer
from .layout import Layout, Panel
from .units import alignment_factors, to_pt

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
            content_draw_rect = fitz.Rect(
                content_rect.x + content_rect.offset_x,
                content_rect.y + content_rect.offset_y,
                content_rect.x + content_rect.offset_x + content_rect.width,
                content_rect.y + content_rect.offset_y + content_rect.height,
            )
            cell_w = to_pt(panel.width, self.units)
            cell_h = (
                to_pt(panel.height, self.units)
                if panel.height is not None
                else cell_w * source_info.aspect_ratio
            )
            cell_rect = fitz.Rect(
                content_rect.x,
                content_rect.y,
                content_rect.x + cell_w,
                content_rect.y + cell_h,
            )

            if panel.fit == "cover":
                self._embed_cover(page, cell_rect, source_info.doc, panel)
                label_rect = cell_rect
            else:
                self._embed_content(page, content_draw_rect, source_info.doc, panel)
                label_rect = content_draw_rect
        finally:
            source_info.doc.close()

        self._draw_label(page, panel, label_rect, index)

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

    def _embed_cover(
        self, page: fitz.Page, cell_rect: fitz.Rect, src_doc: fitz.Document, panel: Panel
    ) -> None:
        """Embed content in cover mode by clipping to the panel cell."""
        if src_doc.is_pdf:
            clip_rect = self._compute_source_clip(src_doc[0].rect, cell_rect, panel.align)
            page.show_pdf_page(cell_rect, src_doc, 0, clip=clip_rect)
            return

        if panel.file.suffix.lower() == ".svg":
            pdf_bytes = src_doc.convert_to_pdf()
            src_pdf = fitz.open("pdf", pdf_bytes)
            try:
                clip_rect = self._compute_source_clip(
                    src_pdf[0].rect, cell_rect, panel.align
                )
                page.show_pdf_page(cell_rect, src_pdf, 0, clip=clip_rect)
            finally:
                src_pdf.close()
            return

        # Raster images: render cropped source area into the destination cell.
        src_page = src_doc[0]
        clip_rect = self._compute_source_clip(src_page.rect, cell_rect, panel.align)
        zoom_x = cell_rect.width / clip_rect.width
        zoom_y = cell_rect.height / clip_rect.height
        pix = src_page.get_pixmap(
            matrix=fitz.Matrix(zoom_x, zoom_y),
            clip=clip_rect,
            alpha=False,
        )
        page.insert_image(cell_rect, pixmap=pix, keep_proportion=False)

    def _compute_source_clip(
        self, src_rect: fitz.Rect, target_rect: fitz.Rect, align: str
    ) -> fitz.Rect:
        """Compute a source clip rectangle for cover mode with alignment-aware crop."""
        src_w = src_rect.width
        src_h = src_rect.height
        src_aspect = src_h / src_w
        target_aspect = target_rect.height / target_rect.width
        h_factor, v_factor = alignment_factors(align)

        if src_aspect > target_aspect:
            # Source is taller than target: crop top/bottom.
            clip_h = src_w * target_aspect
            extra_h = src_h - clip_h
            clip_y0 = src_rect.y0 + extra_h * v_factor
            return fitz.Rect(src_rect.x0, clip_y0, src_rect.x1, clip_y0 + clip_h)

        # Source is wider than target: crop left/right.
        clip_w = src_h / target_aspect
        extra_w = src_w - clip_w
        clip_x0 = src_rect.x0 + extra_w * h_factor
        return fitz.Rect(clip_x0, src_rect.y0, clip_x0 + clip_w, src_rect.y1)

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
