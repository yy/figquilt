from pathlib import Path

import pytest

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
