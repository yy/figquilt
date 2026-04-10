from pathlib import Path

import fitz
from PIL import Image, UnidentifiedImageError

_PIL_SIZE_ERRORS = (
    OSError,
    ValueError,
    UnidentifiedImageError,
    Image.DecompressionBombError,
)
_FITZ_SIZE_ERRORS = (
    fitz.EmptyFileError,
    fitz.FileDataError,
    fitz.FileNotFoundError,
    RuntimeError,
    ValueError,
    IndexError,
)


def _probe_raster_size(path: Path) -> tuple[float, float] | None:
    """Return raster dimensions when Pillow can open the file."""
    try:
        with Image.open(path) as img:
            return float(img.width), float(img.height)
    except _PIL_SIZE_ERRORS:
        return None


def _probe_document_size(path: Path) -> tuple[float, float] | None:
    """Return first-page dimensions when PyMuPDF can open the file."""
    try:
        doc = fitz.open(path)
    except _FITZ_SIZE_ERRORS:
        return None

    try:
        page = doc[0]
        return page.rect.width, page.rect.height
    except _FITZ_SIZE_ERRORS:
        return None
    finally:
        doc.close()


def get_image_size(path: Path) -> tuple[float, float]:
    """Return asset dimensions using Pillow first, then PyMuPDF."""
    raster_size = _probe_raster_size(path)
    if raster_size is not None:
        return raster_size

    document_size = _probe_document_size(path)
    if document_size is not None:
        return document_size

    raise ValueError(f"Could not determine size of {path}")


def is_image(path: Path) -> bool:
    """Return True when Pillow recognizes the file as a raster image."""
    return _probe_raster_size(path) is not None
