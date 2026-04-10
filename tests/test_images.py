import re

import fitz
import pytest
from PIL import Image

from figquilt.images import get_image_size, is_image


def test_get_image_size_reads_raster_dimensions(tmp_path):
    asset = tmp_path / "sample.png"
    Image.new("RGB", (33, 44), color="red").save(asset)

    assert get_image_size(asset) == (33.0, 44.0)


def test_get_image_size_falls_back_to_svg_document_dimensions(tmp_path):
    asset = tmp_path / "sample.svg"
    asset.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
        '<rect width="120" height="80" fill="red"/>'
        "</svg>"
    )

    assert get_image_size(asset) == (120.0, 80.0)


def test_get_image_size_raises_for_unreadable_assets(tmp_path):
    asset = tmp_path / "sample.bin"
    asset.write_bytes(b"\x00\xff\x00\xff")

    with pytest.raises(ValueError, match=re.escape(str(asset))):
        get_image_size(asset)


def test_is_image_only_accepts_raster_assets(tmp_path):
    png_asset = tmp_path / "sample.png"
    Image.new("RGB", (20, 10), color="blue").save(png_asset)

    pdf_asset = tmp_path / "sample.pdf"
    doc = fitz.open()
    doc.new_page(width=120, height=80)
    doc.save(pdf_asset)
    doc.close()

    text_asset = tmp_path / "sample.txt"
    text_asset.write_text("not an image")

    assert is_image(png_asset) is True
    assert is_image(pdf_asset) is False
    assert is_image(text_asset) is False
