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


class TestAutoLayout:
    """Tests for automatic ordered layout mode."""

    @staticmethod
    def _make_pdf(path, width, height):
        import fitz

        doc = fitz.open()
        doc.new_page(width=width, height=height)
        doc.save(path)
        doc.close()

    @staticmethod
    def _area_by_id(panels):
        return {p.id: p.width * (p.height if p.height is not None else 0.0) for p in panels}

    @staticmethod
    def _cv(values):
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return (var**0.5) / mean

    def test_auto_layout_preserves_sequence_and_fits_bounds(self, tmp_path):
        """Auto layout should preserve order and fit the page content area."""
        from figquilt.grid import resolve_layout
        from figquilt.parser import parse_layout

        self._make_pdf(tmp_path / "a.pdf", 200, 100)
        self._make_pdf(tmp_path / "b.pdf", 100, 160)
        self._make_pdf(tmp_path / "c.pdf", 240, 100)
        self._make_pdf(tmp_path / "d.pdf", 100, 100)
        self._make_pdf(tmp_path / "e.pdf", 120, 180)

        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text("""\
page:
  width: 180
  height: 120
  margin: 6

layout:
  type: auto
  auto_mode: best
  size_uniformity: 0.7
  gap: 4
  children:
    - id: A
      file: a.pdf
    - id: B
      file: b.pdf
    - id: C
      file: c.pdf
    - id: D
      file: d.pdf
    - id: E
      file: e.pdf
""")

        layout = parse_layout(layout_file)
        panels = resolve_layout(layout)
        ids = [p.id for p in panels]
        assert ids == ["A", "B", "C", "D", "E"]

        content_w = layout.page.width - 2 * layout.page.margin
        content_h = layout.page.height - 2 * layout.page.margin
        for panel in panels:
            assert panel.x >= -1e-6
            assert panel.y >= -1e-6
            assert panel.x + panel.width <= content_w + 1e-6
            assert panel.y + panel.height <= content_h + 1e-6

    def test_auto_layout_higher_uniformity_reduces_area_spread(self, tmp_path):
        """Higher size_uniformity should reduce panel area variance."""
        from figquilt.grid import resolve_layout
        from figquilt.parser import parse_layout

        self._make_pdf(tmp_path / "a.pdf", 300, 90)
        self._make_pdf(tmp_path / "b.pdf", 90, 220)
        self._make_pdf(tmp_path / "c.pdf", 180, 120)
        self._make_pdf(tmp_path / "d.pdf", 140, 140)
        self._make_pdf(tmp_path / "e.pdf", 100, 260)

        base_yaml = """\
page:
  width: 180
  height: 130
  margin: 6

layout:
  type: auto
  auto_mode: best
  size_uniformity: {uniformity}
  gap: 4
  children:
    - id: A
      file: a.pdf
    - id: B
      file: b.pdf
    - id: C
      file: c.pdf
    - id: D
      file: d.pdf
    - id: E
      file: e.pdf
"""
        low_file = tmp_path / "low.yaml"
        low_file.write_text(base_yaml.format(uniformity=0.0))
        high_file = tmp_path / "high.yaml"
        high_file.write_text(base_yaml.format(uniformity=1.0))

        low_layout = parse_layout(low_file)
        high_layout = parse_layout(high_file)

        low_panels = resolve_layout(low_layout)
        high_panels = resolve_layout(high_layout)

        low_cv = self._cv(list(self._area_by_id(low_panels).values()))
        high_cv = self._cv(list(self._area_by_id(high_panels).values()))
        assert high_cv <= low_cv

    def test_auto_layout_main_role_increases_target_panel_area(self, tmp_path):
        """A panel marked as main should receive a larger area than in normal mode."""
        from figquilt.grid import resolve_layout
        from figquilt.parser import parse_layout

        self._make_pdf(tmp_path / "a.pdf", 120, 100)
        self._make_pdf(tmp_path / "b.pdf", 260, 100)
        self._make_pdf(tmp_path / "c.pdf", 120, 100)
        self._make_pdf(tmp_path / "d.pdf", 120, 100)

        normal_file = tmp_path / "normal.yaml"
        normal_file.write_text("""\
page:
  width: 160
  height: 150
  margin: 5

layout:
  type: auto
  auto_mode: one-column
  size_uniformity: 0.8
  gap: 4
  children:
    - id: B
      file: b.pdf
    - id: A
      file: a.pdf
    - id: C
      file: c.pdf
    - id: D
      file: d.pdf
""")

        main_file = tmp_path / "main.yaml"
        main_file.write_text("""\
page:
  width: 160
  height: 150
  margin: 5

layout:
  type: auto
  auto_mode: one-column
  size_uniformity: 0.8
  main_scale: 2.5
  gap: 4
  children:
    - id: B
      file: b.pdf
      role: main
    - id: A
      file: a.pdf
    - id: C
      file: c.pdf
    - id: D
      file: d.pdf
""")

        normal_panels = resolve_layout(parse_layout(normal_file))
        main_panels = resolve_layout(parse_layout(main_file))

        area_normal_b = self._area_by_id(normal_panels)["B"]
        area_main_b = self._area_by_id(main_panels)["B"]
        assert area_main_b > area_normal_b


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
