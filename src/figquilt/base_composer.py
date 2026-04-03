"""Base class for figure composers with shared functionality."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple

import fitz

from .errors import FigQuiltError
from .grid import resolve_layout
from .layout import LabelStyle, Layout, Panel
from .units import calculate_fit, to_pt


class SourceInfo(NamedTuple):
    """Information about a source file."""

    doc: fitz.Document
    aspect_ratio: float


class CellRect(NamedTuple):
    """Panel cell rectangle in page coordinates."""

    x: float
    y: float
    width: float
    height: float


class ContentRect(NamedTuple):
    """Computed content rectangle within a cell."""

    x: float
    y: float
    width: float
    height: float
    offset_x: float
    offset_y: float


class PanelGeometry(NamedTuple):
    """Resolved panel cell and fitted content geometry."""

    cell: CellRect
    content: ContentRect


class BaseComposer(ABC):
    """Base class for PDF and SVG composers with shared initialization and helpers."""

    def __init__(self, layout: Layout, panels: list[Panel] | None = None):
        self.layout = layout
        self.units = layout.page.units
        self.width_pt = to_pt(layout.page.width, self.units)
        self.height_pt = to_pt(layout.page.height, self.units)
        self.margin_pt = to_pt(layout.page.margin, self.units)
        self._panels = panels

    @abstractmethod
    def compose(self, output_path: Path) -> None:
        """Compose the layout and write to output file."""
        pass

    def get_panels(self) -> list[Panel]:
        """Resolve and return the list of panels from the layout."""
        if self._panels is None:
            self._panels = resolve_layout(self.layout)
        return self._panels

    def open_source(self, panel: Panel) -> SourceInfo:
        """
        Open a source file and return its document and aspect ratio.

        Args:
            panel: Panel containing the file path

        Returns:
            SourceInfo with the opened document and aspect ratio

        Raises:
            FigQuiltError: If the file cannot be opened
        """
        try:
            src_doc = fitz.open(panel.file)
        except Exception as e:
            raise FigQuiltError(f"Failed to open panel file {panel.file}: {e}")

        src_page = src_doc[0]
        src_rect = src_page.rect
        aspect_ratio = src_rect.height / src_rect.width

        return SourceInfo(doc=src_doc, aspect_ratio=aspect_ratio)

    def calculate_content_rect(self, panel: Panel, src_aspect: float) -> ContentRect:
        """
        Calculate the content rectangle for a panel.

        Args:
            panel: Panel with position and size
            src_aspect: Source aspect ratio (height / width)

        Returns:
            ContentRect with position, dimensions, and offsets
        """
        return self.calculate_panel_geometry(panel, src_aspect).content

    def calculate_cell_rect(self, panel: Panel, src_aspect: float) -> CellRect:
        """Calculate the panel cell rectangle in page coordinates."""
        x = to_pt(panel.x, self.units) + self.margin_pt
        y = to_pt(panel.y, self.units) + self.margin_pt
        w = to_pt(panel.width, self.units)
        h = self._panel_height_pt(panel, src_aspect, width_pt=w)

        return CellRect(x=x, y=y, width=w, height=h)

    def calculate_panel_geometry(
        self, panel: Panel, src_aspect: float
    ) -> PanelGeometry:
        """Calculate panel cell geometry and fitted content placement."""
        cell = self.calculate_cell_rect(panel, src_aspect)

        content_w, content_h, offset_x, offset_y = calculate_fit(
            src_aspect, cell.width, cell.height, panel.fit, panel.align
        )

        return PanelGeometry(
            cell=cell,
            content=ContentRect(
                x=cell.x,
                y=cell.y,
                width=content_w,
                height=content_h,
                offset_x=offset_x,
                offset_y=offset_y,
            ),
        )

    def _panel_height_pt(
        self, panel: Panel, src_aspect: float, *, width_pt: float
    ) -> float:
        """Return the panel cell height in points."""
        if panel.height is not None:
            return to_pt(panel.height, self.units)
        return width_pt * src_aspect

    def get_label_text(self, panel: Panel, index: int) -> str | None:
        """
        Get the label text for a panel.

        Args:
            panel: Panel with optional label override
            index: Panel index for auto-sequencing

        Returns:
            Label text or None if labels are disabled
        """
        style = self.get_label_style(panel)

        if not style.enabled:
            return None

        text = panel.label
        if text is None and style.auto_sequence:
            text = self._index_to_label(index)

        if not text:
            return None

        if style.uppercase:
            text = text.upper()

        return text

    def get_label_style(self, panel: Panel) -> LabelStyle:
        """Resolve a panel label style by inheriting unspecified page defaults."""
        base_style = self.layout.page.label
        if panel.label_style is None:
            return base_style

        override = panel.label_style.model_dump(exclude_unset=True)
        return base_style.model_copy(update=override)

    @staticmethod
    def _index_to_label(index: int) -> str:
        """Convert zero-based index to spreadsheet-like labels (A..Z, AA..)."""
        if index < 0:
            raise ValueError("index must be non-negative")
        chars: list[str] = []
        value = index
        while True:
            value, remainder = divmod(value, 26)
            chars.append(chr(65 + remainder))
            if value == 0:
                break
            value -= 1
        return "".join(reversed(chars))

    def parse_color(self, color_str: str) -> tuple[float, float, float] | None:
        """
        Parse a color string to RGB tuple (0-1 range).

        Supports hex colors (#rrggbb) and CSS color names via PIL.

        Args:
            color_str: Color string (e.g., "#f0f0f0", "white")

        Returns:
            RGB tuple with values 0-1, or None if parsing fails
        """
        if color_str.startswith("#"):
            h = color_str.lstrip("#")
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            elif len(h) != 6:
                return None
            try:
                rgb = tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
                return rgb  # type: ignore
            except (ValueError, IndexError):
                return None

        try:
            from PIL import ImageColor

            rgb = ImageColor.getrgb(color_str)
            return tuple(c / 255.0 for c in rgb)  # type: ignore
        except (ValueError, ImportError):
            return None
