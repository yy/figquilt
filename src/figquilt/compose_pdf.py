import fitz
from pathlib import Path
from .layout import Layout, Panel
from .units import mm_to_pt
from .errors import FigQuiltError

class PDFComposer:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.width_pt = mm_to_pt(layout.page.width)
        self.height_pt = mm_to_pt(layout.page.height)

    def compose(self, output_path: Path):
        doc = self.build()
        doc.save(str(output_path))
        doc.close()

    def build(self) -> fitz.Document:
        doc = fitz.open()
        page = doc.new_page(width=self.width_pt, height=self.height_pt)

        # Draw panels
        for i, panel in enumerate(self.layout.panels):
            self._place_panel(doc, page, panel, index=i)
        
        return doc

    def _place_panel(self, doc: fitz.Document, page: fitz.Page, panel: Panel, index: int):
        # Calculate position and size first
        x = mm_to_pt(panel.x)
        y = mm_to_pt(panel.y)
        w = mm_to_pt(panel.width)
        
        # Determine height from aspect ratio if needed
        # We need to open the source to get aspect ratio
        try:
            # fitz.open can handle PDF, PNG, JPEG, SVG...
            src_doc = fitz.open(panel.file)
        except Exception as e:
            raise FigQuiltError(f"Failed to open panel file {panel.file}: {e}")

        # Get source dimension
        if src_doc.is_pdf:
            src_page = src_doc[0]
            src_rect = src_page.rect
        else:
            # For images/SVG, fitz doc acts like a list of pages too?
            # Yes, usually page[0] is the image/svg content.
            src_page = src_doc[0]
            src_rect = src_page.rect

        aspect = src_rect.height / src_rect.width
        
        if panel.height is not None:
             h = mm_to_pt(panel.height)
        else:
            h = w * aspect

        rect = fitz.Rect(x, y, x + w, y + h)

        if src_doc.is_pdf:
             page.show_pdf_page(rect, src_doc, 0)
        elif panel.file.suffix.lower() == ".svg":
             # Convert SVG to PDF in memory to allow vector embedding
             pdf_bytes = src_doc.convert_to_pdf()
             src_pdf = fitz.open("pdf", pdf_bytes)
             page.show_pdf_page(rect, src_pdf, 0)
        else:
            # Insert as image (works for PNG/JPEG)
            page.insert_image(rect, filename=panel.file)

        # Labels
        self._draw_label(page, panel, rect, index)

    def _draw_label(self, page: fitz.Page, panel: Panel, rect: fitz.Rect, index: int):
        # Determine effective label settings
        # Priority: Panel specific > Page default
        # But panel.label_style is optional, page.label is required (defaulted)
        
        # Merge logic is a bit complex if we want partial overrides.
        # For v0 simplicity: if panel has style, use it fully, else use page style.
        # But commonly we want to just change text but keep style.
        
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

        # Calculate label position
        # Offset is from top-left of the panel (rect.tl)
        # x direction: + is right, - is left? 
        # Usually offset is inside the panel, so +x and +y from top-left.
        # But if user wants negative offset?
        # Let's assume offset is in mm relative to panel top-left.
        
        pos_x = rect.x0 + mm_to_pt(style.offset_x_mm)
        pos_y = rect.y0 - mm_to_pt(style.offset_y_mm) # y grows down in PDF usually?
        # PyMuPDF y grows down (0 at top).
        # if offset_y_mm is negative (e.g. -2), it means 2mm DOWN?
        # Wait, design doc said: "offset: x: 2, y: -2".
        # Usually graphics y is up, but PDF/Screen often y is down.
        # Let's interpret y: -2 as "2mm down from top edge". 
        # So essentially we ADD the offset if we consider the standard top-left origin.
        # But if the value is negative in the config, we should probably subtract it?
        # Let's stick to: pos = origin + offset.
        
        pos_y = rect.y0 + mm_to_pt(style.offset_y_mm) # standard addition.
        # If user puts negative, it goes up (outside panel).
        # Design doc example has y: -2. Maybe they meant 2mm margin?
        # Let's assume standard vector addition.

        # Font - PyMuPDF supports base 14 fonts by name
        fontname = "helv"  # default mapping for Helvetica
        if style.bold:
            fontname = "HeBo" # Helvetica-Bold
        
        # Insert text
        page.insert_text((pos_x, pos_y), text, fontsize=style.font_size_pt, fontname=fontname)
