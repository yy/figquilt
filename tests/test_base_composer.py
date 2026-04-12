from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz
import pytest

from figquilt.base_composer import SourceInfo, open_panel_source, validate_panel_sources
from figquilt.compose_pdf import PDFComposer
from figquilt.layout import Layout, Page, Panel


def test_calculate_panel_geometry_derives_implicit_height_from_aspect_ratio():
    panel = Panel(id="A", file=Path("dummy.pdf"), x=5, y=10, width=20)
    layout = Layout(page=Page(width=100, height=100, units="pt"), panels=[panel])

    geometry = PDFComposer(layout, panels=[panel]).calculate_panel_geometry(
        panel, src_aspect=1.5
    )

    assert geometry.cell.x == pytest.approx(5.0)
    assert geometry.cell.y == pytest.approx(10.0)
    assert geometry.cell.width == pytest.approx(20.0)
    assert geometry.cell.height == pytest.approx(30.0)
    assert geometry.content.width == pytest.approx(20.0)
    assert geometry.content.height == pytest.approx(30.0)
    assert geometry.content.offset_x == pytest.approx(0.0)
    assert geometry.content.offset_y == pytest.approx(0.0)


def test_calculate_panel_geometry_separates_cell_origin_from_letterboxed_content():
    panel = Panel(
        id="A",
        file=Path("dummy.pdf"),
        x=5,
        y=7,
        width=100,
        height=100,
        fit="contain",
        align="center",
    )
    layout = Layout(
        page=Page(width=200, height=200, units="pt", margin=10),
        panels=[panel],
    )

    geometry = PDFComposer(layout, panels=[panel]).calculate_panel_geometry(
        panel, src_aspect=0.5
    )

    assert geometry.cell.x == pytest.approx(15.0)
    assert geometry.cell.y == pytest.approx(17.0)
    assert geometry.cell.width == pytest.approx(100.0)
    assert geometry.cell.height == pytest.approx(100.0)
    assert geometry.content.x == pytest.approx(15.0)
    assert geometry.content.y == pytest.approx(17.0)
    assert geometry.content.width == pytest.approx(100.0)
    assert geometry.content.height == pytest.approx(50.0)
    assert geometry.content.offset_x == pytest.approx(0.0)
    assert geometry.content.offset_y == pytest.approx(25.0)


def test_open_panel_source_reports_aspect_ratio_without_renderer_instance(tmp_path):
    asset = tmp_path / "panel.pdf"
    doc = fitz.open()
    doc.new_page(width=120, height=60)
    doc.save(asset)
    doc.close()

    source_info = open_panel_source(Panel(id="A", file=asset, x=0, y=0, width=50))
    try:
        assert source_info.aspect_ratio == pytest.approx(0.5)
    finally:
        source_info.doc.close()


def test_validate_panel_sources_checks_multiple_panels(tmp_path):
    asset_a = tmp_path / "a.pdf"
    asset_b = tmp_path / "b.pdf"

    for asset, width, height in ((asset_a, 100, 100), (asset_b, 80, 160)):
        doc = fitz.open()
        doc.new_page(width=width, height=height)
        doc.save(asset)
        doc.close()

    panels = [
        Panel(id="A", file=asset_a, x=0, y=0, width=50),
        Panel(id="B", file=asset_b, x=0, y=0, width=50),
    ]

    validate_panel_sources(panels)


def test_resolved_panel_source_yields_geometry_and_closes_document():
    panel = Panel(id="A", file=Path("dummy.pdf"), x=0, y=0, width=20)
    layout = Layout(page=Page(width=100, height=100, units="pt"), panels=[panel])
    composer = PDFComposer(layout, panels=[panel])
    mock_doc = MagicMock()

    with patch.object(
        composer,
        "open_source",
        return_value=SourceInfo(doc=mock_doc, aspect_ratio=1.5),
    ):
        with composer.resolved_panel_source(panel) as resolved:
            assert resolved.source.doc is mock_doc
            assert resolved.geometry.cell.width == pytest.approx(20.0)
            assert resolved.geometry.cell.height == pytest.approx(30.0)

    mock_doc.close.assert_called_once()


def test_resolved_panel_source_closes_document_when_geometry_fails():
    panel = Panel(id="A", file=Path("dummy.pdf"), x=0, y=0, width=20)
    layout = Layout(page=Page(width=100, height=100, units="pt"), panels=[panel])
    composer = PDFComposer(layout, panels=[panel])
    mock_doc = MagicMock()

    with (
        patch.object(
            composer,
            "open_source",
            return_value=SourceInfo(doc=mock_doc, aspect_ratio=1.5),
        ),
        patch.object(
            composer,
            "calculate_panel_geometry",
            side_effect=RuntimeError("geometry failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="geometry failed"):
            with composer.resolved_panel_source(panel):
                pass

    mock_doc.close.assert_called_once()
