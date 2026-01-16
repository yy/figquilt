def mm_to_pt(mm: float) -> float:
    """Converts millimeters to points (1 inch = 25.4 mm = 72 pts)."""
    return mm * 72 / 25.4

def in_to_pt(inches: float) -> float:
    """Converts inches to points."""
    return inches * 72.0