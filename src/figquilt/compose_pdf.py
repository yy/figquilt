"""PDF composer using PyMuPDF (fitz)."""

from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator

import fitz

from .base_composer import BaseComposer
from .layout import Panel
from .units import alignment_factors

# PyMuPDF font name mappings
_FONT_REGULAR = "helv"  # Helvetica
_FONT_BOLD = "HeBo"  # Helvetica-Bold
_FONT_FAMILY_VARIANTS = {
    "helvetica": ("Helvetica", "Helvetica-Bold"),
    "helv": ("Helvetica", "Helvetica-Bold"),
    "courier": ("Courier", "Courier-Bold"),
    "cour": ("Courier", "Courier-Bold"),
    "times": ("Times-Roman", "Times-Bold"),
    "times-roman": ("Times-Roman", "Times-Bold"),
    "tiro": ("Times-Roman", "Times-Bold"),
}


class PDFComposer(BaseComposer):
    def compose(self, output_path: Path) -> None:
        doc = self.build()
        try:
            doc.save(str(output_path))
        finally:
            doc.close()

    def render_png(self, output_path: Path) -> None:
        """Render the composed figure to PNG via a temporary PDF document."""
        doc = self.build()
        try:
            page = doc[0]
            pix = page.get_pixmap(dpi=self.layout.page.dpi)
            output_path.write_bytes(pix.tobytes("png"))
        finally:
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
        with self.resolved_panel_source(panel) as resolved:
            geometry = resolved.geometry
            content_draw_rect = self._content_draw_rect(geometry.content)
            cell_rect = self._fitz_rect(
                geometry.cell.x,
                geometry.cell.y,
                geometry.cell.width,
                geometry.cell.height,
            )

            if panel.fit == "cover":
                self._embed_cover(page, cell_rect, resolved.source.doc, panel)
            else:
                self._embed_content(page, content_draw_rect, resolved.source.doc, panel)

        self._draw_label(page, panel, cell_rect, index)

    def _embed_content(
        self, page: fitz.Page, rect: fitz.Rect, src_doc: fitz.Document, panel: Panel
    ) -> None:
        """Embed the source content into the page at the given rect."""
        with self._open_vector_source(src_doc, panel) as vector_doc:
            if vector_doc is not None:
                page.show_pdf_page(rect, vector_doc, 0)
                return

        # Insert as image (works for PNG/JPEG)
        page.insert_image(rect, filename=panel.file)

    def _embed_cover(
        self,
        page: fitz.Page,
        cell_rect: fitz.Rect,
        src_doc: fitz.Document,
        panel: Panel,
    ) -> None:
        """Embed content in cover mode by clipping to the panel cell."""
        with self._open_vector_source(src_doc, panel) as vector_doc:
            if vector_doc is not None:
                clip_rect = self._compute_source_clip(
                    vector_doc[0].rect, cell_rect, panel.align
                )
                page.show_pdf_page(cell_rect, vector_doc, 0, clip=clip_rect)
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
        label_info = self.resolve_label_draw_info(
            panel,
            index,
            origin_x=rect.x0,
            origin_y=rect.y0,
            use_font_baseline=True,
        )
        if label_info is None:
            return

        fontname = self._resolve_font_name(
            label_info.style.font_family,
            bold=label_info.style.bold,
        )

        page.insert_text(
            (label_info.x, label_info.y),
            label_info.text,
            fontsize=label_info.style.font_size_pt,
            fontname=fontname,
        )

    @staticmethod
    def _fitz_rect(x: float, y: float, width: float, height: float) -> fitz.Rect:
        """Build a PyMuPDF rectangle from an origin and size."""
        return fitz.Rect(x, y, x + width, y + height)

    def _content_draw_rect(self, content_rect) -> fitz.Rect:
        """Return the destination rect for fitted panel content."""
        return self._fitz_rect(
            content_rect.x + content_rect.offset_x,
            content_rect.y + content_rect.offset_y,
            content_rect.width,
            content_rect.height,
        )

    @contextmanager
    def _open_vector_source(
        self, src_doc: fitz.Document, panel: Panel
    ) -> Iterator[fitz.Document | None]:
        """Yield a PDF-like document for vector sources, if applicable."""
        if src_doc.is_pdf:
            yield src_doc
            return

        if panel.file.suffix.lower() != ".svg":
            yield None
            return

        # Convert SVG to PDF in memory for vector preservation.
        pdf_bytes = src_doc.convert_to_pdf()
        src_pdf = fitz.open("pdf", pdf_bytes)
        try:
            yield src_pdf
        finally:
            src_pdf.close()

    @staticmethod
    def _resolve_font_name(font_family: str, *, bold: bool) -> str:
        """Map configured label font families to PyMuPDF base-14 font names."""
        normalized = font_family.strip().lower()
        variants = _FONT_FAMILY_VARIANTS.get(normalized)
        if variants is not None:
            return variants[1] if bold else variants[0]

        exact_match = fitz.Base14_fontdict.get(normalized)
        if exact_match is not None:
            return exact_match

        return _FONT_BOLD if bold else _FONT_REGULAR
