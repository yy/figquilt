"""Tests for grid layout resolution (converting layout tree to flat panels)."""

from pathlib import Path

import pytest

from figquilt.layout import Layout, LayoutNode, Page, Panel


def make_page(width=180, height=100, margin=0):
    return Page(width=width, height=height, units="mm", margin=margin)


def make_leaf(id: str, file: str = "test.pdf"):
    return LayoutNode(id=id, file=Path(file))


def make_row(children, ratios=None, gap=0, margin=0):
    return LayoutNode(
        type="row", children=children, ratios=ratios, gap=gap, margin=margin
    )


def make_col(children, ratios=None, gap=0, margin=0):
    return LayoutNode(
        type="col", children=children, ratios=ratios, gap=gap, margin=margin
    )


class TestSimpleRow:
    """Tests for simple row layouts."""

    def test_two_equal_panels(self):
        """Two panels split 50/50."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=50),
            layout=make_row([make_leaf("A"), make_leaf("B")]),
        )

        panels = resolve_layout(layout)

        assert len(panels) == 2
        # Panel A: left half
        assert panels[0].id == "A"
        assert panels[0].x == 0
        assert panels[0].y == 0
        assert panels[0].width == 50
        assert panels[0].height == 50
        # Panel B: right half
        assert panels[1].id == "B"
        assert panels[1].x == 50
        assert panels[1].y == 0
        assert panels[1].width == 50
        assert panels[1].height == 50

    def test_row_with_ratios(self):
        """Row with 3:2 ratio split."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=50),
            layout=make_row([make_leaf("A"), make_leaf("B")], ratios=[3, 2]),
        )

        panels = resolve_layout(layout)

        assert len(panels) == 2
        assert panels[0].width == 60  # 3/5 of 100
        assert panels[1].width == 40  # 2/5 of 100
        assert panels[1].x == 60

    def test_row_with_gap(self):
        """Row with gap between panels."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=50),
            layout=make_row([make_leaf("A"), make_leaf("B")], gap=10),
        )

        panels = resolve_layout(layout)

        # Available width = 100 - 10 (one gap) = 90, split evenly
        assert panels[0].width == 45
        assert panels[0].x == 0
        assert panels[1].width == 45
        assert panels[1].x == 55  # 45 + 10 gap


class TestSimpleCol:
    """Tests for simple column layouts."""

    def test_two_equal_panels(self):
        """Two panels stacked equally."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=100),
            layout=make_col([make_leaf("A"), make_leaf("B")]),
        )

        panels = resolve_layout(layout)

        assert len(panels) == 2
        # Panel A: top half
        assert panels[0].id == "A"
        assert panels[0].x == 0
        assert panels[0].y == 0
        assert panels[0].width == 100
        assert panels[0].height == 50
        # Panel B: bottom half
        assert panels[1].id == "B"
        assert panels[1].y == 50
        assert panels[1].height == 50

    def test_col_with_ratios(self):
        """Column with 1:2 ratio."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=90),
            layout=make_col([make_leaf("A"), make_leaf("B")], ratios=[1, 2]),
        )

        panels = resolve_layout(layout)

        assert panels[0].height == 30  # 1/3 of 90
        assert panels[1].height == 60  # 2/3 of 90
        assert panels[1].y == 30


class TestNestedLayout:
    """Tests for nested container layouts."""

    def test_col_with_nested_row(self):
        """Column with a row nested inside."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=100),
            layout=make_col(
                [
                    make_leaf("A"),
                    make_row([make_leaf("B"), make_leaf("C")]),
                ],
                ratios=[1, 1],
            ),
        )

        panels = resolve_layout(layout)

        assert len(panels) == 3
        # A is top half, full width
        assert panels[0].id == "A"
        assert panels[0].y == 0
        assert panels[0].height == 50
        assert panels[0].width == 100
        # B and C are bottom half, split horizontally
        assert panels[1].id == "B"
        assert panels[1].y == 50
        assert panels[1].height == 50
        assert panels[1].width == 50
        assert panels[1].x == 0
        assert panels[2].id == "C"
        assert panels[2].x == 50


class TestContainerMargin:
    """Tests for container margins."""

    def test_row_with_margin(self):
        """Row with inner margin."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=50),
            layout=make_row([make_leaf("A"), make_leaf("B")], margin=10),
        )

        panels = resolve_layout(layout)

        # Container has 10px margin on all sides
        # Available width = 100 - 20 = 80, split evenly
        assert panels[0].x == 10
        assert panels[0].y == 10
        assert panels[0].width == 40
        assert panels[0].height == 30  # 50 - 20 margin


class TestPageMargin:
    """Tests for page-level margin."""

    def test_page_margin_reduces_content_area(self):
        """Page margin reduces the available content area."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=make_page(width=100, height=100, margin=10),
            layout=make_row([make_leaf("A"), make_leaf("B")]),
        )

        panels = resolve_layout(layout)

        # Content area is 80x80 (100 - 10*2 on each side)
        # Panels are in content coordinate space (0,0 = top-left of content area)
        # The composer will add the page margin offset when rendering
        assert panels[0].x == 0
        assert panels[0].y == 0
        assert panels[0].width == 40
        assert panels[0].height == 80
        assert panels[1].x == 40
        assert panels[1].width == 40


class TestEndToEndComposition:
    """End-to-end tests that actually compose a figure using grid layout."""

    def test_compose_grid_layout_to_pdf(self, tmp_path):
        """Test that a grid layout composes to PDF correctly."""
        import fitz
        from figquilt.parser import parse_layout
        from figquilt.compose_pdf import PDFComposer

        # Create test panel files (simple PDFs)
        for name in ["left.pdf", "right.pdf"]:
            doc = fitz.open()
            page = doc.new_page(width=100, height=100)
            page.draw_rect(page.rect, color=(0, 0, 0))
            doc.save(str(tmp_path / name))
            doc.close()

        # Create a grid layout file
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text("""\
page:
  width: 200
  height: 100
  units: mm

layout:
  type: row
  ratios: [1, 1]
  gap: 10
  children:
    - id: A
      file: left.pdf
    - id: B
      file: right.pdf
""")

        # Parse and compose
        layout = parse_layout(layout_file)
        output_path = tmp_path / "output.pdf"

        composer = PDFComposer(layout)
        composer.compose(output_path)

        # Verify output exists and has content
        assert output_path.exists()
        doc = fitz.open(output_path)
        assert len(doc) == 1
        doc.close()


class TestExplicitPanelsAutoScale:
    """Tests for page-level auto-scaling in explicit panels mode."""

    def test_default_mode_keeps_explicit_panel_geometry(self):
        """Without auto_scale, explicit panel geometry is unchanged."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=Page(width=100, height=100, units="mm"),
            panels=[
                Panel(
                    id="A",
                    file=Path("a.pdf"),
                    x=0,
                    y=0,
                    width=80,
                    height=50,
                ),
                Panel(
                    id="B",
                    file=Path("b.pdf"),
                    x=90,
                    y=60,
                    width=30,
                    height=40,
                ),
            ],
        )

        panels = resolve_layout(layout)
        assert panels[0].x == 0
        assert panels[0].y == 0
        assert panels[0].width == 80
        assert panels[0].height == 50
        assert panels[1].x == 90
        assert panels[1].y == 60
        assert panels[1].width == 30
        assert panels[1].height == 40

    def test_auto_scale_scales_down_oversized_layout(self):
        """Auto-scale shrinks oversized explicit layouts to fit the page."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=Page(width=100, height=100, units="mm", auto_scale=True),
            panels=[
                Panel(
                    id="A",
                    file=Path("a.pdf"),
                    x=0,
                    y=0,
                    width=80,
                    height=50,
                ),
                Panel(
                    id="B",
                    file=Path("b.pdf"),
                    x=90,
                    y=60,
                    width=30,
                    height=40,
                ),
            ],
        )

        panels = resolve_layout(layout)

        assert panels[0].x == pytest.approx(0)
        assert panels[0].y == pytest.approx(0)
        assert panels[0].width == pytest.approx(66.6666667, rel=1e-6)
        assert panels[0].height == pytest.approx(41.6666667, rel=1e-6)
        assert panels[1].x == pytest.approx(75.0, rel=1e-6)
        assert panels[1].y == pytest.approx(50.0, rel=1e-6)
        assert panels[1].width == pytest.approx(25.0, rel=1e-6)
        assert panels[1].height == pytest.approx(33.3333333, rel=1e-6)

    def test_auto_scale_shifts_negative_coords_without_unnecessary_scaling(self):
        """Auto-scale should translate into bounds when size already fits."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=Page(width=100, height=100, units="mm", auto_scale=True),
            panels=[
                Panel(
                    id="A",
                    file=Path("a.pdf"),
                    x=-10,
                    y=-5,
                    width=50,
                    height=50,
                ),
                Panel(
                    id="B",
                    file=Path("b.pdf"),
                    x=60,
                    y=20,
                    width=30,
                    height=20,
                ),
            ],
        )

        panels = resolve_layout(layout)
        assert panels[0].x == pytest.approx(0)
        assert panels[0].y == pytest.approx(0)
        assert panels[0].width == pytest.approx(50)
        assert panels[0].height == pytest.approx(50)
        assert panels[1].x == pytest.approx(70)
        assert panels[1].y == pytest.approx(25)
        assert panels[1].width == pytest.approx(30)
        assert panels[1].height == pytest.approx(20)

    def test_auto_scale_uses_margin_adjusted_content_area(self):
        """Auto-scale should fit into page content area (page minus margins)."""
        from figquilt.grid import resolve_layout

        layout = Layout(
            page=Page(width=100, height=100, units="mm", margin=10, auto_scale=True),
            panels=[
                Panel(
                    id="A",
                    file=Path("a.pdf"),
                    x=0,
                    y=0,
                    width=100,
                    height=100,
                )
            ],
        )

        panels = resolve_layout(layout)
        assert panels[0].x == pytest.approx(0)
        assert panels[0].y == pytest.approx(0)
        assert panels[0].width == pytest.approx(80)
        assert panels[0].height == pytest.approx(80)

    def test_auto_scale_resolves_missing_height_from_source_size(self, tmp_path):
        """Missing panel height should be resolved before auto-scaling."""
        import fitz
        from figquilt.grid import resolve_layout

        panel_file = tmp_path / "source.pdf"
        doc = fitz.open()
        doc.new_page(width=200, height=100)  # aspect ratio (h/w) = 0.5
        doc.save(panel_file)
        doc.close()

        layout = Layout(
            page=Page(width=100, height=100, units="mm", auto_scale=True),
            panels=[
                Panel(
                    id="A",
                    file=panel_file,
                    x=0,
                    y=0,
                    width=120,
                    height=None,
                )
            ],
        )

        panels = resolve_layout(layout)
        assert panels[0].width == pytest.approx(100, rel=1e-6)
        assert panels[0].height == pytest.approx(50, rel=1e-6)

    def test_compose_nested_grid_layout(self, tmp_path):
        """Test that a nested grid layout composes correctly."""
        import fitz
        from figquilt.parser import parse_layout
        from figquilt.compose_pdf import PDFComposer

        # Create test panel files
        for name in ["header.pdf", "left.pdf", "right.pdf"]:
            doc = fitz.open()
            doc.new_page(width=100, height=100)
            doc.save(str(tmp_path / name))
            doc.close()

        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text("""\
page:
  width: 180
  height: 200
  units: mm

layout:
  type: col
  ratios: [1, 2]
  children:
    - id: A
      file: header.pdf
    - type: row
      ratios: [1, 1]
      gap: 5
      children:
        - id: B
          file: left.pdf
        - id: C
          file: right.pdf
""")

        layout = parse_layout(layout_file)
        output_path = tmp_path / "output.pdf"

        composer = PDFComposer(layout)
        composer.compose(output_path)

        assert output_path.exists()
        doc = fitz.open(output_path)
        assert len(doc) == 1
        doc.close()
