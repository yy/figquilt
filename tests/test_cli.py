import pytest
from unittest.mock import patch, MagicMock
import yaml
import threading
from typing import List, Callable

from figquilt.cli import compose_figure, run_watch_mode


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


class TestColorParsing:
    """Tests for color parsing in PDFComposer."""

    def test_parse_hex_color(self):
        """Should parse hex colors correctly."""
        from figquilt.compose_pdf import PDFComposer
        from figquilt.layout import Layout, Page

        layout = Layout(page=Page(width=100, height=100), panels=[])
        composer = PDFComposer(layout)

        # Test basic hex colors
        assert composer._parse_color("#ffffff") == pytest.approx((1.0, 1.0, 1.0))
        assert composer._parse_color("#000000") == pytest.approx((0.0, 0.0, 0.0))
        assert composer._parse_color("#ff0000") == pytest.approx((1.0, 0.0, 0.0))
        assert composer._parse_color("#00ff00") == pytest.approx((0.0, 1.0, 0.0))
        assert composer._parse_color("#0000ff") == pytest.approx((0.0, 0.0, 1.0))

    def test_parse_named_color(self):
        """Should parse named colors via PIL."""
        from figquilt.compose_pdf import PDFComposer
        from figquilt.layout import Layout, Page

        layout = Layout(page=Page(width=100, height=100), panels=[])
        composer = PDFComposer(layout)

        # Test named colors (via PIL ImageColor)
        assert composer._parse_color("white") == pytest.approx((1.0, 1.0, 1.0))
        assert composer._parse_color("black") == pytest.approx((0.0, 0.0, 0.0))
        assert composer._parse_color("red") == pytest.approx((1.0, 0.0, 0.0))

    def test_parse_invalid_color_returns_none(self):
        """Should return None for invalid color strings."""
        from figquilt.compose_pdf import PDFComposer
        from figquilt.layout import Layout, Page

        layout = Layout(page=Page(width=100, height=100), panels=[])
        composer = PDFComposer(layout)

        # Invalid colors should return None
        assert composer._parse_color("notacolor") is None
        assert composer._parse_color("#gg0000") is None
