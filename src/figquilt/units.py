def mm_to_pt(mm: float) -> float:
    """Converts millimeters to points (1 inch = 25.4 mm = 72 pts)."""
    return mm * 72 / 25.4

def pt_to_mm(pt: float) -> float:
    """Converts points to millimeters."""
    return pt * 25.4 / 72
