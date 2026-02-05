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


def calculate_fit(
    src_aspect: float,
    cell_w: float,
    cell_h: float,
    fit_mode: str,
    align: str = "center",
) -> tuple[float, float, float, float]:
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
        Tuple of (content_w, content_h, offset_x, offset_y)
    """
    cell_aspect = cell_h / cell_w

    if fit_mode == "cover":
        # Scale to cover entire cell (may crop)
        if src_aspect > cell_aspect:
            # Source is taller: scale by width, crop top/bottom
            content_w = cell_w
            content_h = cell_w * src_aspect
        else:
            # Source is wider: scale by height, crop left/right
            content_h = cell_h
            content_w = cell_h / src_aspect
    else:  # contain (default)
        # Scale to fit within cell, preserving aspect ratio
        if src_aspect > cell_aspect:
            # Source is taller: fit by height
            content_h = cell_h
            content_w = cell_h / src_aspect
        else:
            # Source is wider: fit by width
            content_w = cell_w
            content_h = cell_w * src_aspect

    # Calculate offsets based on alignment using lookup table
    space_x = cell_w - content_w
    space_y = cell_h - content_h
    h_factor, v_factor = _ALIGNMENT_OFFSETS.get(align, (0.5, 0.5))
    offset_x = space_x * h_factor
    offset_y = space_y * v_factor

    return content_w, content_h, offset_x, offset_y
