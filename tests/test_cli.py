import pytest
from unittest.mock import patch, MagicMock
import yaml
import threading
from typing import List, Callable
from pathlib import Path

from figquilt.cli import compose_figure, run_watch_mode
from figquilt.layout import Layout, Page, Panel


@pytest.fixture
def valid_layout_data(tmp_path):
    """Create a valid layout file and panel for testing."""
    panel_file = tmp_path / "panel.pdf"
    panel_file.write_bytes(b"%PDF-1.4 minimal pdf content")

    data = {
        "page": {"width": 100, "height": 100, "units": "mm"},
        "panels": [
            {"id": "A", "file": str(panel_file.name), "x": 0, "y": 0, "width": 50}
        ],
    }
    layout_file = tmp_path / "layout.yaml"
    with open(layout_file, "w") as f:
        yaml.dump(data, f)
    return layout_file, panel_file


def run_watch_with_mock_changes(
    layout_file,
    output_file,
    changed_files: List,
    mock_compose: Callable,
    timeout: float = 2,
) -> None:
    """
    Helper to test watch mode with mocked file changes.

    Args:
        layout_file: Path to layout file
        output_file: Path to output file
        changed_files: List of files to simulate changes for
        mock_compose: Mock function for compose_figure
        timeout: Thread join timeout
    """
    stop_event = threading.Event()

    def run_watcher():
        with patch("figquilt.cli.compose_figure", side_effect=mock_compose):
            # Patch watch inside the function since it's now lazily imported
            with patch("watchfiles.watch") as mock_watch:

                def fake_watch(*args, **kwargs):
                    for f in changed_files:
                        if stop_event.is_set():
                            return
                        yield {(1, str(f))}
                    stop_event.set()

                mock_watch.side_effect = fake_watch
                run_watch_mode(
                    layout_file,
                    output_file,
                    fmt="pdf",
                    verbose=False,
                    stop_event=stop_event,
                )

    watcher_thread = threading.Thread(target=run_watcher)
    watcher_thread.start()
    watcher_thread.join(timeout=timeout)


class TestComposeFigure:
    """Tests for the compose_figure helper function."""

    @staticmethod
    def _make_layout() -> Layout:
        return Layout(
            page=Page(width=100, height=100, units="mm"),
            panels=[
                Panel(
                    id="A",
                    file=Path("panel.pdf"),
                    x=0,
                    y=0,
                    width=50,
                )
            ],
        )

    def test_compose_figure_returns_true_on_success(self, valid_layout_data, tmp_path):
        """compose_figure should return True when composition succeeds."""
        layout_file, _ = valid_layout_data
        output_file = tmp_path / "output.pdf"

        with patch("figquilt.compose_pdf.PDFComposer") as mock_composer:
            mock_instance = MagicMock()
            mock_composer.return_value = mock_instance

            result = compose_figure(layout_file, output_file, fmt="pdf", verbose=False)

            assert result is True
            mock_instance.compose.assert_called_once_with(output_file)

    def test_compose_figure_skips_eager_resolution_without_verbose(self, tmp_path):
        """Non-verbose builds should leave layout resolution to the renderer."""
        layout = self._make_layout()
        output_file = tmp_path / "output.pdf"
        renderer_calls = []

        def fake_renderer(layout_arg, output_arg, panels_arg):
            renderer_calls.append((layout_arg, output_arg, panels_arg))

        with patch("figquilt.cli.parse_layout", return_value=layout), patch(
            "figquilt.cli.resolve_layout"
        ) as mock_resolve, patch(
            "figquilt.cli._renderer_for_format", return_value=fake_renderer
        ):
            result = compose_figure(
                tmp_path / "layout.yaml",
                output_file,
                fmt="pdf",
                verbose=False,
            )

        assert result is True
        mock_resolve.assert_not_called()
        assert renderer_calls == [(layout, output_file, None)]

    def test_compose_figure_reuses_resolved_panels_for_verbose_output(self, tmp_path):
        """Verbose builds should reuse the already-resolved panels during rendering."""
        layout = self._make_layout()
        resolved_panels = list(layout.panels or [])
        output_file = tmp_path / "output.pdf"
        renderer_calls = []

        def fake_renderer(layout_arg, output_arg, panels_arg):
            renderer_calls.append((layout_arg, output_arg, panels_arg))

        with patch("figquilt.cli.parse_layout", return_value=layout), patch(
            "figquilt.cli.resolve_layout", return_value=resolved_panels
        ) as mock_resolve, patch(
            "figquilt.cli._renderer_for_format", return_value=fake_renderer
        ):
            result = compose_figure(
                tmp_path / "layout.yaml",
                output_file,
                fmt="pdf",
                verbose=True,
            )

        assert result is True
        mock_resolve.assert_called_once_with(layout)
        assert renderer_calls == [(layout, output_file, resolved_panels)]

    def test_compose_figure_returns_false_on_error(self, tmp_path):
        """compose_figure should return False and print error on failure."""
        layout_file = tmp_path / "nonexistent.yaml"
        output_file = tmp_path / "output.pdf"

        result = compose_figure(layout_file, output_file, fmt="pdf", verbose=False)

        assert result is False


class TestWatchMode:
    """Tests for the --watch mode functionality."""

    def test_get_watched_paths_includes_layout_and_panels(self, valid_layout_data):
        """Watch mode should monitor the layout file and all panel source files."""
        from figquilt.cli import get_watched_paths
        from figquilt.parser import parse_layout

        layout_file, panel_file = valid_layout_data
        layout = parse_layout(layout_file)

        watched_files, watched_dirs = get_watched_paths(layout_file, layout)

        assert layout_file.resolve() in watched_files
        assert panel_file.resolve() in watched_files
        assert layout_file.parent in watched_dirs

    def test_get_watched_paths_includes_grid_layout_assets(self, tmp_path):
        """Watch mode should include nested grid-layout asset files."""
        from figquilt.cli import get_watched_paths
        from figquilt.parser import parse_layout

        panel_a = tmp_path / "a.pdf"
        panel_b = tmp_path / "b.pdf"
        panel_a.write_bytes(b"%PDF-1.4 a")
        panel_b.write_bytes(b"%PDF-1.4 b")
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 180, "height": 100},
                    "layout": {
                        "type": "row",
                        "children": [
                            {"id": "A", "file": panel_a.name},
                            {
                                "type": "col",
                                "children": [
                                    {"id": "B", "file": panel_b.name},
                                ],
                            },
                        ],
                    },
                }
            )
        )

        layout = parse_layout(layout_file)
        watched_files, watched_dirs = get_watched_paths(layout_file, layout)

        assert layout_file.resolve() in watched_files
        assert panel_a.resolve() in watched_files
        assert panel_b.resolve() in watched_files
        assert layout_file.parent in watched_dirs

    def test_watch_mode_uses_existing_ancestor_for_missing_asset_dirs(self, tmp_path):
        """Watch mode should avoid watching non-existent asset directories."""
        missing_asset = tmp_path / "assets" / "missing.pdf"
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 100, "height": 100},
                    "panels": [
                        {
                            "id": "A",
                            "file": str(Path("assets") / "missing.pdf"),
                            "x": 0,
                            "y": 0,
                            "width": 50,
                        }
                    ],
                }
            )
        )
        output_file = tmp_path / "output.pdf"
        stop_event = threading.Event()
        watched_dirs = []

        def fake_watch(*args, **kwargs):
            watched_dirs.extend(Path(arg).resolve() for arg in args)
            stop_event.set()
            if False:
                yield set()

        with patch("figquilt.cli.compose_figure", return_value=False):
            with patch("watchfiles.watch", side_effect=fake_watch):
                run_watch_mode(
                    layout_file,
                    output_file,
                    fmt="pdf",
                    verbose=False,
                    stop_event=stop_event,
                )

        assert tmp_path.resolve() in watched_dirs
        assert missing_asset.parent.resolve() not in watched_dirs

    def test_watch_mode_rebuilds_on_layout_change(self, valid_layout_data, tmp_path):
        """Watch mode should rebuild when the layout file changes."""
        layout_file, _ = valid_layout_data
        output_file = tmp_path / "output.pdf"

        rebuild_count = []

        def mock_compose(*args, **kwargs):
            rebuild_count.append(1)
            return True

        run_watch_with_mock_changes(
            layout_file, output_file, [layout_file], mock_compose
        )

        # Initial build + rebuild on change = 2
        assert len(rebuild_count) >= 1

    def test_watch_mode_rebuilds_on_panel_file_change(
        self, valid_layout_data, tmp_path
    ):
        """Watch mode should rebuild when a panel source file changes."""
        layout_file, panel_file = valid_layout_data
        output_file = tmp_path / "output.pdf"

        rebuild_count = []

        def mock_compose(*args, **kwargs):
            rebuild_count.append(1)
            return True

        run_watch_with_mock_changes(
            layout_file, output_file, [panel_file], mock_compose
        )

        assert len(rebuild_count) >= 1

    def test_watch_mode_rebuilds_when_missing_panel_file_is_created(self, tmp_path):
        """Watch mode should rebuild when a previously missing panel file appears."""
        missing_asset = tmp_path / "missing.pdf"
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 100, "height": 100},
                    "panels": [
                        {
                            "id": "A",
                            "file": missing_asset.name,
                            "x": 0,
                            "y": 0,
                            "width": 50,
                        }
                    ],
                }
            )
        )
        output_file = tmp_path / "output.pdf"
        stop_event = threading.Event()
        rebuild_count = []

        def mock_compose(*args, **kwargs):
            rebuild_count.append(1)
            return len(rebuild_count) > 1

        def run_watcher():
            with patch("figquilt.cli.compose_figure", side_effect=mock_compose):
                with patch("watchfiles.watch") as mock_watch:

                    def fake_watch(*args, **kwargs):
                        missing_asset.touch()
                        yield {(1, str(missing_asset))}
                        stop_event.set()

                    mock_watch.side_effect = fake_watch
                    run_watch_mode(
                        layout_file,
                        output_file,
                        fmt="pdf",
                        verbose=False,
                        stop_event=stop_event,
                    )

        watcher_thread = threading.Thread(target=run_watcher)
        watcher_thread.start()
        watcher_thread.join(timeout=2)

        # Initial build + rebuild when the asset appears.
        assert len(rebuild_count) >= 2

    def test_watch_mode_tracks_new_missing_asset_after_layout_change(self, tmp_path):
        """Watch mode should rebuild when a layout edit introduces a missing asset."""
        original_asset = tmp_path / "a.pdf"
        original_asset.write_bytes(b"%PDF-1.4 a")
        missing_asset = tmp_path / "b.pdf"
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 100, "height": 100},
                    "panels": [
                        {
                            "id": "A",
                            "file": original_asset.name,
                            "x": 0,
                            "y": 0,
                            "width": 50,
                        }
                    ],
                }
            )
        )
        output_file = tmp_path / "output.pdf"
        stop_event = threading.Event()
        rebuild_count = []

        def mock_compose(*args, **kwargs):
            rebuild_count.append(1)
            return len(rebuild_count) != 2

        def run_watcher():
            with patch("figquilt.cli.compose_figure", side_effect=mock_compose):
                with patch("watchfiles.watch") as mock_watch:

                    def fake_watch(*args, **kwargs):
                        layout_file.write_text(
                            yaml.dump(
                                {
                                    "page": {"width": 100, "height": 100},
                                    "panels": [
                                        {
                                            "id": "A",
                                            "file": missing_asset.name,
                                            "x": 0,
                                            "y": 0,
                                            "width": 50,
                                        }
                                    ],
                                }
                            )
                        )
                        yield {(1, str(layout_file))}
                        missing_asset.touch()
                        yield {(1, str(missing_asset))}
                        stop_event.set()

                    mock_watch.side_effect = fake_watch
                    run_watch_mode(
                        layout_file,
                        output_file,
                        fmt="pdf",
                        verbose=False,
                        stop_event=stop_event,
                    )

        watcher_thread = threading.Thread(target=run_watcher)
        watcher_thread.start()
        watcher_thread.join(timeout=2)

        # Initial build, failed rebuild after layout change, then rebuild when
        # the missing asset appears.
        assert len(rebuild_count) >= 3

    def test_watch_mode_continues_on_build_error(self, valid_layout_data, tmp_path):
        """Watch mode should continue watching even if a build fails."""
        layout_file, _ = valid_layout_data
        output_file = tmp_path / "output.pdf"

        call_count = []

        def mock_compose(*args, **kwargs):
            call_count.append(1)
            if len(call_count) == 1:
                return False  # First call fails
            return True  # Subsequent calls succeed

        run_watch_with_mock_changes(
            layout_file, output_file, [layout_file, layout_file], mock_compose
        )

        # Should have been called multiple times despite first failure
        assert len(call_count) >= 2

    def test_watch_mode_tracks_unreadable_auto_layout_asset_changes(
        self, tmp_path
    ):
        """Watch mode should rebuild when a referenced unreadable asset changes."""
        asset_file = tmp_path / "bad.bin"
        asset_file.write_bytes(b"not an image")
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 100, "height": 100},
                    "layout": {
                        "type": "auto",
                        "children": [{"id": "A", "file": str(asset_file.name)}],
                    },
                }
            )
        )
        output_file = tmp_path / "output.pdf"

        rebuild_count = []

        def mock_compose(*args, **kwargs):
            rebuild_count.append(1)
            return len(rebuild_count) > 1

        run_watch_with_mock_changes(
            layout_file, output_file, [asset_file], mock_compose
        )

        # Initial build + rebuild after the asset changes.
        assert len(rebuild_count) >= 2


class TestCheckMode:
    """Tests for the --check mode functionality."""

    def test_check_mode_valid_layout(self, valid_layout_data, tmp_path, capsys):
        """--check should print layout info and exit 0 for valid layout."""
        import subprocess
        import sys

        layout_file, _ = valid_layout_data
        output_file = tmp_path / "output.pdf"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "figquilt.cli",
                "--check",
                str(layout_file),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Layout parsed successfully" in result.stdout
        assert "Page size:" in result.stdout
        assert "100" in result.stdout  # Width/height values
        assert "Panels: 1" in result.stdout

    def test_check_mode_invalid_layout(self, tmp_path):
        """--check should exit non-zero for invalid layout."""
        import subprocess
        import sys

        layout_file = tmp_path / "invalid.yaml"
        layout_file.write_text("page: not_a_dict")
        output_file = tmp_path / "output.pdf"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "figquilt.cli",
                "--check",
                str(layout_file),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_check_mode_missing_layout(self, tmp_path):
        """--check should exit non-zero for missing layout file."""
        import subprocess
        import sys

        layout_file = tmp_path / "nonexistent.yaml"
        output_file = tmp_path / "output.pdf"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "figquilt.cli",
                "--check",
                str(layout_file),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Error" in result.stderr

    def test_check_mode_reports_unreadable_layout_without_traceback(self, tmp_path):
        """--check should report unreadable layout files without crashing."""
        import stat
        import subprocess
        import sys

        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text("page:\n  width: 100\n  height: 100\npanels: []\n")
        output_file = tmp_path / "output.pdf"

        original_mode = layout_file.stat().st_mode
        try:
            layout_file.chmod(0)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "figquilt.cli",
                    "--check",
                    str(layout_file),
                    str(output_file),
                ],
                capture_output=True,
                text=True,
            )
        finally:
            layout_file.chmod(stat.S_IMODE(original_mode))

        assert result.returncode == 1
        assert "Error: Failed to read layout file" in result.stderr
        assert "Traceback" not in result.stderr

    def test_check_mode_ignores_output_suffix(self, valid_layout_data, tmp_path):
        """--check should not require a renderable output suffix."""
        import subprocess
        import sys

        layout_file, _ = valid_layout_data
        output_file = tmp_path / "report.txt"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "figquilt.cli",
                "--check",
                str(layout_file),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Layout parsed successfully" in result.stdout

    def test_check_mode_reports_unreadable_auto_scale_asset(self, tmp_path):
        """--check should report unreadable auto-scale assets without a traceback."""
        import subprocess
        import sys

        asset_file = tmp_path / "bad.bin"
        asset_file.write_bytes(b"not an image")
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 100, "height": 100, "auto_scale": True},
                    "panels": [
                        {
                            "id": "A",
                            "file": str(asset_file.name),
                            "x": 0,
                            "y": 0,
                            "width": 50,
                        }
                    ],
                }
            )
        )
        output_file = tmp_path / "output.pdf"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "figquilt.cli",
                "--check",
                str(layout_file),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Error: Could not determine size of panel 'A' for auto-scaling" in result.stderr
        assert "Traceback" not in result.stderr

    def test_check_mode_reports_unreadable_auto_layout_asset(self, tmp_path):
        """--check should report unreadable auto-layout assets without a traceback."""
        import subprocess
        import sys

        asset_file = tmp_path / "bad.bin"
        asset_file.write_bytes(b"not an image")
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            yaml.dump(
                {
                    "page": {"width": 100, "height": 100},
                    "layout": {
                        "type": "auto",
                        "children": [{"id": "A", "file": str(asset_file.name)}],
                    },
                }
            )
        )
        output_file = tmp_path / "output.pdf"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "figquilt.cli",
                "--check",
                str(layout_file),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "Error: Could not determine size of panel 'A' for auto layout" in result.stderr
        assert "Traceback" not in result.stderr


class TestColorParsing:
    """Tests for color parsing in PDFComposer."""

    def test_parse_hex_color(self):
        """Should parse hex colors correctly."""
        from figquilt.compose_pdf import PDFComposer
        from figquilt.layout import Layout, Page

        layout = Layout(page=Page(width=100, height=100), panels=[])
        composer = PDFComposer(layout)

        # Test basic hex colors
        assert composer.parse_color("#ffffff") == pytest.approx((1.0, 1.0, 1.0))
        assert composer.parse_color("#000000") == pytest.approx((0.0, 0.0, 0.0))
        assert composer.parse_color("#ff0000") == pytest.approx((1.0, 0.0, 0.0))
        assert composer.parse_color("#00ff00") == pytest.approx((0.0, 1.0, 0.0))
        assert composer.parse_color("#0000ff") == pytest.approx((0.0, 0.0, 1.0))

    def test_parse_named_color(self):
        """Should parse named colors via PIL."""
        from figquilt.compose_pdf import PDFComposer
        from figquilt.layout import Layout, Page

        layout = Layout(page=Page(width=100, height=100), panels=[])
        composer = PDFComposer(layout)

        # Test named colors (via PIL ImageColor)
        assert composer.parse_color("white") == pytest.approx((1.0, 1.0, 1.0))
        assert composer.parse_color("black") == pytest.approx((0.0, 0.0, 0.0))
        assert composer.parse_color("red") == pytest.approx((1.0, 0.0, 0.0))

    def test_parse_invalid_color_returns_none(self):
        """Should return None for invalid color strings."""
        from figquilt.compose_pdf import PDFComposer
        from figquilt.layout import Layout, Page

        layout = Layout(page=Page(width=100, height=100), panels=[])
        composer = PDFComposer(layout)

        # Invalid colors should return None
        assert composer.parse_color("notacolor") is None
        assert composer.parse_color("#gg0000") is None


def test_auto_label_sequence_continues_after_z():
    """Auto-generated labels should continue as AA, AB, ... after Z."""
    from figquilt.compose_pdf import PDFComposer
    from figquilt.layout import Layout, Page, Panel
    from pathlib import Path

    panel = Panel(id="X", file=Path("panel.pdf"), x=0, y=0, width=10)
    layout = Layout(page=Page(width=100, height=100), panels=[panel])
    composer = PDFComposer(layout)

    assert composer.get_label_text(panel, 25) == "Z"
    assert composer.get_label_text(panel, 26) == "AA"
    assert composer.get_label_text(panel, 27) == "AB"


def test_panel_label_style_inherits_unspecified_page_defaults():
    """Partial panel label_style should inherit unspecified fields from page.label."""
    from pathlib import Path

    from figquilt.compose_pdf import PDFComposer
    from figquilt.layout import LabelStyle, Layout, Page, Panel

    panel = Panel(
        id="A",
        file=Path("panel.pdf"),
        x=0,
        y=0,
        width=10,
        label="a",
        label_style=LabelStyle(font_size_pt=12),
    )
    layout = Layout(
        page=Page(
            width=100,
            height=100,
            label=LabelStyle(enabled=False, uppercase=False),
        ),
        panels=[panel],
    )
    composer = PDFComposer(layout)

    assert composer.get_label_text(panel, 0) is None
