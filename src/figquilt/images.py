from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
import fitz

def get_image_size(path: Path) -> Tuple[float, float]:
    """Returns (width, height) in pixels/points."""
    try:
        with Image.open(path) as img:
            return float(img.width), float(img.height)
    except Exception:
        # Try fitz for PDF/SVG
        try:
            doc = fitz.open(path)
            page = doc[0]
            return page.rect.width, page.rect.height
        except Exception:
            raise ValueError(f"Could not determine size of {path}")

def is_image(path: Path) -> bool:
    """Checks if the file is a raster image supported by Pillow."""
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False
