from unittest.mock import MagicMock, patch

from pathlib import Path

import pytest
import yaml

from figquilt.cli import compose_figure
from figquilt.compose_pdf import PDFComposer
from figquilt.layout import Layout, Page, Panel


def test_compose_figure_closes_document_when_png_export_fails(tmp_path):
    """PNG export failures should still close the intermediate PDF document."""
    panel_file = tmp_path / "panel.pdf"
    panel_file.write_bytes(b"%PDF-1.4 minimal pdf content")

    layout_file = tmp_path / "layout.yaml"
    layout_file.write_text(
        yaml.dump(
            {
                "page": {"width": 100, "height": 100, "units": "mm"},
                "panels": [
                    {
                        "id": "A",
                        "file": str(panel_file.name),
                        "x": 0,
                        "y": 0,
                        "width": 50,
                    }
                ],
            }
        )
    )
    output_file = tmp_path / "output.png"

    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_doc.__getitem__.return_value = mock_page
    mock_page.get_pixmap.return_value = mock_pix
    mock_pix.save.side_effect = RuntimeError("save failed")

    with patch("figquilt.compose_pdf.PDFComposer") as mock_composer:
        mock_composer.return_value.build.return_value = mock_doc

        result = compose_figure(layout_file, output_file, fmt="png", verbose=False)

    assert result is False
    mock_doc.close.assert_called_once()


def test_pdf_composer_closes_document_when_save_fails():
    """PDF save failures should still close the generated document."""
    panel = Panel(id="A", file=Path("dummy.pdf"), x=0, y=0, width=50)
    layout = Layout(page=Page(width=100, height=100, units="mm"), panels=[panel])

    mock_doc = MagicMock()
    mock_doc.save.side_effect = RuntimeError("save failed")

    composer = PDFComposer(layout, panels=[panel])

    with patch.object(PDFComposer, "build", return_value=mock_doc):
        with pytest.raises(RuntimeError, match="save failed"):
            composer.compose(Path("output.pdf"))

    mock_doc.close.assert_called_once()
