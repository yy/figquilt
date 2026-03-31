from unittest.mock import MagicMock, patch

import yaml

from figquilt.cli import compose_figure


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
