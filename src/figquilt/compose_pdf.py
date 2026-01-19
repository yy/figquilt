import fitz
from pathlib import Path
from .layout import Layout, Panel
from .units import to_pt
from .errors import FigQuiltError


class PDFComposer:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.units = layout.page.units
        self.width_pt = to_pt(layout.page.width, self.units)
        self.height_pt = to_pt(layout.page.height, self.units)
        self.margin_pt = to_pt(layout.page.margin, self.units)

    def compose(self, output_path: Path):
        doc = self.build()
        doc.save(str(output_path))
        doc.close()

    def build(self) -> fitz.Document:
        doc = fitz.open()
        page = doc.new_page(width=self.width_pt, height=self.height_pt)

        # Draw background if specified
        if self.layout.page.background:
            # simple color parsing: strict names or hex?
            # PyMuPDF draw_rect color expects sequence of floats (0..1) or nothing.
            # We need to robustly parse the color string from layout (e.g. "white", "#f0f0f0").
            # fitz.utils.getColor? No, fitz doesn't have a robust color parser built-in for all CSS names.
            # But the user example uses "#f0f0f0".
            # Minimal hex parser:
            col = self._parse_color(self.layout.page.background)
            if col:
                page.draw_rect(page.rect, color=col, fill=col)

        # Get panels (resolves grid layout if needed)
        from .grid import resolve_layout

        panels = resolve_layout(self.layout)
        for i, panel in enumerate(panels):
            self._place_panel(doc, page, panel, index=i)

        return doc

    def _parse_color(self, color_str: str):
        # Very basic hex support
        if color_str.startswith("#"):
            h = color_str.lstrip("#")
            try:
                rgb = tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
                return rgb
            except:
                return None
        # Basic name support mapping could be added here
        # For now, just support hex or fallback to None (skip)
        # Using PIL ImageColor is an option if we import it, but we want minimal dep for this file?
        # We process images, so PIL is available.
        try:
            from PIL import ImageColor

            rgb = ImageColor.getrgb(color_str)
            return tuple(c / 255.0 for c in rgb)
        except:
            return None

    def _place_panel(
        self, doc: fitz.Document, page: fitz.Page, panel: Panel, index: int
    ):
        # Calculate position and size first, offset by page margin
        x = to_pt(panel.x, self.units) + self.margin_pt
        y = to_pt(panel.y, self.units) + self.margin_pt
        w = to_pt(panel.width, self.units)

        # Determine height from aspect ratio if needed
        # We need to open the source to get aspect ratio
        try:
            # fitz.open can handle PDF, PNG, JPEG, SVG...
            src_doc = fitz.open(panel.file)
        except Exception as e:
            raise FigQuiltError(f"Failed to open panel file {panel.file}: {e}")

        try:
            # Get source dimension
            if src_doc.is_pdf:
                src_page = src_doc[0]
                src_rect = src_page.rect
            else:
                # For images/SVG, fitz doc acts like a list of pages too?
                # Yes, usually page[0] is the image/svg content.
                src_page = src_doc[0]
                src_rect = src_page.rect

            src_aspect = src_rect.height / src_rect.width

            # Calculate cell height
            if panel.height is not None:
                h = to_pt(panel.height, self.units)
            else:
                # No height specified: use source aspect ratio
                h = w * src_aspect

            # Calculate content rect using fit mode and alignment
            from .units import calculate_fit

            content_w, content_h, offset_x, offset_y = calculate_fit(
                src_aspect, w, h, panel.fit, panel.align
            )
            rect = fitz.Rect(
                x + offset_x,
                y + offset_y,
                x + offset_x + content_w,
                y + offset_y + content_h,
            )

            if src_doc.is_pdf:
                page.show_pdf_page(rect, src_doc, 0)
            elif panel.file.suffix.lower() == ".svg":
                # Convert SVG to PDF in memory to allow vector embedding
                pdf_bytes = src_doc.convert_to_pdf()
                src_pdf = fitz.open("pdf", pdf_bytes)
                try:
                    page.show_pdf_page(rect, src_pdf, 0)
                finally:
                    src_pdf.close()
            else:
                # Insert as image (works for PNG/JPEG)
                page.insert_image(rect, filename=panel.file)
        finally:
            src_doc.close()

        # Labels
        self._draw_label(page, panel, rect, index)

    def _draw_label(self, page: fitz.Page, panel: Panel, rect: fitz.Rect, index: int):
        # Determine effective label settings
        style = panel.label_style if panel.label_style else self.layout.page.label

        if not style.enabled:
            return

        text = panel.label
        if text is None and style.auto_sequence:
            text = chr(65 + index)  # A, B, C...

        if not text:
            return

        if style.uppercase:
            text = text.upper()

        # Position logic
        # Design doc: offset is relative to top-left.
        # SVG implementation uses 'hanging' baseline, so (0,0) is top-left of text char.
        # PyMuPDF insert_text uses 'baseline', so (0,0) is bottom-left of text char.
        # We need to shift Y down by approximately the font sizing to match SVG visual.

        pos_x = rect.x0 + to_pt(style.offset_x, self.units)
        raw_y = rect.y0 + to_pt(style.offset_y, self.units)

        # Approximate baseline shift: font_size
        # (A more precise way uses font.ascender, but for basic standard fonts, size is decent proxy for visual top->baseline)
        pos_y = raw_y + style.font_size_pt

        # Font - PyMuPDF supports base 14 fonts by name
        fontname = "helv"  # default mapping for Helvetica
        if style.bold:
            fontname = "HeBo"  # Helvetica-Bold

        # Insert text
        page.insert_text(
            (pos_x, pos_y), text, fontsize=style.font_size_pt, fontname=fontname
        )
