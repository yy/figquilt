def mm_to_pt(mm: float) -> float:
    """Converts millimeters to points (1 inch = 25.4 mm = 72 pts)."""
    return mm * 72 / 25.4


def pt_to_mm(pt: float) -> float:
    """Converts points to millimeters."""
    return pt * 25.4 / 72


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
