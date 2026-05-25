from typing import NamedTuple


class FitResult(NamedTuple):
    """Computed fitted content size and offset inside a panel cell."""

    width: float
    height: float
    offset_x: float
    offset_y: float


def mm_to_pt(mm: float) -> float:
    """Converts millimeters to points (1 inch = 25.4 mm = 72 pts)."""
    return mm * 72 / 25.4


def inches_to_pt(inches: float) -> float:
    """Converts inches to points (1 inch = 72 pts)."""
    return inches * 72


def to_pt(value: float, units: str) -> float:
    """Convert a value from the given units to points."""
    if units == "mm":
        return mm_to_pt(value)
    elif units == "inches":
        return inches_to_pt(value)
    elif units == "pt":
        return value
    else:
        raise ValueError(f"Unknown unit: {units}")


# Alignment offset factors: (horizontal_factor, vertical_factor)
# Multiply by (space_x, space_y) to get offset
_ALIGNMENT_OFFSETS: dict[str, tuple[float, float]] = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.0),
    "bottom": (0.5, 1.0),
    "left": (0.0, 0.5),
    "right": (1.0, 0.5),
    "top-left": (0.0, 0.0),
    "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
}


def alignment_factors(align: str) -> tuple[float, float]:
    """Return horizontal / vertical alignment factors in [0, 1]."""
    return _ALIGNMENT_OFFSETS.get(align, (0.5, 0.5))


def _scaled_content_size(
    src_aspect: float,
    cell_w: float,
    cell_h: float,
    *,
    cover: bool,
) -> tuple[float, float]:
    """Return source dimensions scaled to either contain or cover the cell."""
    cell_aspect = cell_h / cell_w
    fit_by_width = src_aspect <= cell_aspect
    if cover:
        fit_by_width = not fit_by_width

    if fit_by_width:
        return cell_w, cell_w * src_aspect
    return cell_h / src_aspect, cell_h


def _alignment_offsets(
    *,
    cell_w: float,
    cell_h: float,
    content_w: float,
    content_h: float,
    align: str,
) -> tuple[float, float]:
    """Return content offsets within the cell for the configured alignment."""
    space_x = cell_w - content_w
    space_y = cell_h - content_h
    h_factor, v_factor = alignment_factors(align)
    return space_x * h_factor, space_y * v_factor


def calculate_fit(
    src_aspect: float,
    cell_w: float,
    cell_h: float,
    fit_mode: str,
    align: str = "center",
) -> FitResult:
    """
    Calculate content dimensions and offset based on fit mode and alignment.

    Args:
        src_aspect: Source aspect ratio (height / width)
        cell_w: Cell width in points
        cell_h: Cell height in points
        fit_mode: "contain" or "cover"
        align: Alignment within cell (center, top, bottom, left, right,
               top-left, top-right, bottom-left, bottom-right)

    Returns:
        FitResult with fitted width/height and x/y offsets.
    """
    content_w, content_h = _scaled_content_size(
        src_aspect,
        cell_w,
        cell_h,
        cover=fit_mode == "cover",
    )
    offset_x, offset_y = _alignment_offsets(
        cell_w=cell_w,
        cell_h=cell_h,
        content_w=content_w,
        content_h=content_h,
        align=align,
    )

    return FitResult(
        width=content_w,
        height=content_h,
        offset_x=offset_x,
        offset_y=offset_y,
    )
