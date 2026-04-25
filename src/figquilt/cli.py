import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
import threading
from collections.abc import Callable

from .base_composer import validate_panel_sources
from .errors import FigQuiltError, OutputPathError
from .layout import Layout, Panel, iter_panels
from .grid import resolve_layout
from .parser import parse_layout

type Renderer = Callable[[Layout, Path, list[Panel] | None], None]


@dataclass
class PreparedLayout:
    """Parsed layout plus lazily cached resolved panels for CLI flows."""

    path: Path
    layout: Layout
    _resolved_panels: list[Panel] | None = None

    @classmethod
    def load(cls, layout_path: Path) -> "PreparedLayout":
        """Parse a layout file without eagerly resolving panel geometry."""
        return cls(path=layout_path, layout=parse_layout(layout_path))

    def resolved_panels(self) -> list[Panel]:
        """Resolve panel geometry once and reuse it across CLI steps."""
        if self._resolved_panels is None:
            self._resolved_panels = resolve_layout(self.layout)
        return self._resolved_panels

    def print_summary(self, *, prefix: str) -> None:
        """Print a short summary using the cached resolved panel list."""
        _print_layout_summary(
            self.path,
            self.layout,
            len(self.resolved_panels()),
            prefix=prefix,
        )


@dataclass(frozen=True)
class WatchTargets:
    """Resolved file and directory targets for watch mode."""

    files: frozenset[Path]
    dirs: frozenset[Path]

    @classmethod
    def from_layout(cls, layout_path: Path, layout: Layout) -> "WatchTargets":
        """Resolve watch targets from a parsed layout."""
        layout_path = layout_path.resolve()
        files = {layout_path}
        try:
            panels = resolve_layout(layout)
            for panel in panels:
                files.add(panel.file.resolve())
        except FigQuiltError:
            files.update(_iter_referenced_asset_paths(layout))

        dirs = {_nearest_existing_dir(path.parent) for path in files}
        return cls(files=frozenset(files), dirs=frozenset(dirs))

    @classmethod
    def layout_only(cls, layout_path: Path) -> "WatchTargets":
        """Watch just the layout file and its parent directory."""
        layout_path = layout_path.resolve()
        return cls(
            files=frozenset({layout_path}),
            dirs=frozenset({layout_path.parent}),
        )

    @classmethod
    def load(
        cls,
        layout_path: Path,
        *,
        validate_assets: bool,
        fallback_to_layout_only: bool,
    ) -> "WatchTargets | None":
        """Parse a layout and derive watch targets, with optional fallback."""
        try:
            layout = parse_layout(layout_path, validate_assets=validate_assets)
            return cls.from_layout(layout_path, layout)
        except FigQuiltError:
            if fallback_to_layout_only:
                return cls.layout_only(layout_path)
            return None

    def including_path(self, path: Path) -> "WatchTargets":
        """Track an extra path and the nearest existing directory for its events."""
        resolved_path = path.resolve()
        files = set(self.files)
        dirs = set(self.dirs)
        files.add(resolved_path)
        dirs.add(_nearest_existing_dir(resolved_path))
        return type(self)(files=frozenset(files), dirs=frozenset(dirs))

    def relevant_changes(self, changes: set[tuple[object, str]]) -> set[Path]:
        """Return changed watched files from a watchfiles change batch."""
        changed_paths = {Path(changed_path).resolve() for _, changed_path in changes}
        return changed_paths & self.files


def _print_layout_summary(
    layout_path: Path, layout: Layout, panel_count: int, *, prefix: str
) -> None:
    """Print a short summary of the resolved layout."""
    print(f"{prefix}: {layout_path}")
    print(f"Page size: {layout.page.width}x{layout.page.height} {layout.page.units}")
    print(f"Panels: {panel_count}")


def _compose_pdf(
    layout: Layout, output_path: Path, panels: list[Panel] | None = None
) -> None:
    """Render a layout directly to PDF."""
    from .compose_pdf import PDFComposer

    PDFComposer(layout, panels=panels).compose(output_path)


def _compose_svg(
    layout: Layout, output_path: Path, panels: list[Panel] | None = None
) -> None:
    """Render a layout directly to SVG."""
    from .compose_svg import SVGComposer

    SVGComposer(layout, panels=panels).compose(output_path)


def _compose_png(
    layout: Layout, output_path: Path, panels: list[Panel] | None = None
) -> None:
    """Render a layout to PNG via an intermediate PDF document."""
    from .compose_pdf import PDFComposer

    PDFComposer(layout, panels=panels).render_png(output_path)


_RENDERERS: dict[str, Renderer] = {
    "pdf": _compose_pdf,
    "svg": _compose_svg,
    "png": _compose_png,
}


def _renderer_for_format(fmt: str) -> Renderer | None:
    """Return the renderer for a supported output format."""
    return _RENDERERS.get(fmt)


def _iter_referenced_asset_paths(layout: Layout):
    """Yield asset paths referenced directly by the parsed layout."""
    for panel in iter_panels(layout):
        if panel.file is not None:
            yield panel.file.resolve()


def _nearest_existing_dir(path: Path) -> Path:
    """Return the closest existing directory for a watched file path."""
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return candidate if candidate.is_dir() else candidate.parent


def get_watched_paths(layout_path: Path, layout: Layout) -> tuple[set[Path], set[Path]]:
    """
    Return the set of files and directories to watch.

    Returns:
        Tuple of (watched_files, watched_dirs)
    """
    targets = WatchTargets.from_layout(layout_path, layout)
    return set(targets.files), set(targets.dirs)


def _watch_targets_for_output_path(
    watch_targets: WatchTargets, output_path: Path
) -> WatchTargets:
    """Track creation of an invalid output parent so watch mode can recover."""
    output_parent = output_path.parent.resolve()
    if output_parent.exists() and output_parent.is_dir():
        return watch_targets
    return watch_targets.including_path(output_parent)


def _validate_output_path(output_path: Path) -> None:
    """Fail fast when the requested output directory is not writable as a path."""
    parent = output_path.parent
    if not parent.exists():
        raise OutputPathError(f"Output directory does not exist: {parent}")
    if not parent.is_dir():
        raise OutputPathError(f"Output path parent is not a directory: {parent}")
    if output_path.exists() and output_path.is_dir():
        raise OutputPathError(f"Output path is a directory: {output_path}")


def compose_figure(
    layout_path: Path, output_path: Path, fmt: str, verbose: bool
) -> bool:
    """
    Compose a figure from a layout file.

    Returns True on success, False on error.
    """
    try:
        renderer = _renderer_for_format(fmt)
        if renderer is None:
            print(f"Unsupported format: {fmt}", file=sys.stderr)
            return False

        _validate_output_path(output_path)
        prepared_layout = PreparedLayout.load(layout_path)
        panels: list[Panel] | None = None
        if verbose:
            panels = prepared_layout.resolved_panels()
            prepared_layout.print_summary(prefix="Layout parsed")

        renderer(prepared_layout.layout, output_path, panels)

        return True

    except FigQuiltError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return False


def run_watch_mode(
    layout_path: Path,
    output_path: Path,
    fmt: str,
    verbose: bool,
    stop_event: threading.Event | None = None,
) -> None:
    """
    Watch layout and panel files for changes and rebuild on each change.

    Args:
        layout_path: Path to the layout YAML file
        output_path: Path to the output file
        fmt: Output format (pdf, svg, png)
        verbose: Whether to print verbose output
        stop_event: Optional threading event to stop watching (for testing)
    """
    from watchfiles import watch

    print("Watching for changes... (Ctrl+C to stop)")

    # Initial build
    if compose_figure(layout_path, output_path, fmt, verbose):
        print(f"Created: {output_path}")
    else:
        print("Initial build failed, watching for changes...")

    # Get initial set of watched files and directories
    watch_targets = WatchTargets.load(
        layout_path,
        validate_assets=False,
        fallback_to_layout_only=True,
    )
    assert watch_targets is not None
    watch_targets = _watch_targets_for_output_path(watch_targets, output_path)

    while True:
        restart_watcher = False

        for changes in watch(*watch_targets.dirs, stop_event=stop_event):
            if stop_event and stop_event.is_set():
                return

            # Check if any changed file is in our watched set
            relevant_changes = watch_targets.relevant_changes(changes)

            if relevant_changes:
                if verbose:
                    for p in relevant_changes:
                        print(f"Changed: {p}")

                print("Rebuilding...", end=" ", flush=True)
                if compose_figure(layout_path, output_path, fmt, verbose):
                    print(f"done: {output_path}")
                else:
                    print("failed")

                # Refresh watch targets from the latest layout even if the rebuild
                # failed, so newly referenced missing assets can still trigger
                # another rebuild when they appear.
                refreshed_targets = WatchTargets.load(
                    layout_path,
                    validate_assets=False,
                    fallback_to_layout_only=True,
                )
                assert refreshed_targets is not None
                refreshed_targets = _watch_targets_for_output_path(
                    refreshed_targets, output_path
                )
                if refreshed_targets.dirs != watch_targets.dirs:
                    # Directories changed, need to restart the watcher
                    watch_targets = refreshed_targets
                    restart_watcher = True
                    if verbose:
                        print("Watch directories changed, restarting watcher...")
                    break
                watch_targets = refreshed_targets

        if stop_event and stop_event.is_set():
            return
        if not restart_watcher:
            break


def main():
    parser = argparse.ArgumentParser(
        description="FigQuilt: Compose figures from multiple panels."
    )
    parser.add_argument("layout", type=Path, help="Path to layout YAML file")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Path to output file (PDF/SVG/PNG); not required with --check",
    )
    parser.add_argument(
        "--format", choices=["pdf", "svg", "png"], help="Override output format"
    )
    parser.add_argument("--check", action="store_true", help="Validate layout only")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--watch", action="store_true", help="Watch for changes and rebuild"
    )

    args = parser.parse_args()

    # Check-only mode
    if args.check:
        try:
            prepared_layout = PreparedLayout.load(args.layout)
            panels = prepared_layout.resolved_panels()
            validate_panel_sources(panels)
            prepared_layout.print_summary(prefix="Layout parsed successfully")
            sys.exit(0)
        except FigQuiltError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    if args.output is None:
        parser.error("the following arguments are required: output")

    # Determine output format
    suffix = args.output.suffix.lower()
    fmt = args.format or suffix.lstrip(".")

    if fmt not in _RENDERERS:
        print(f"Unsupported format: {fmt}", file=sys.stderr)
        sys.exit(1)

    # Watch mode
    if args.watch:
        try:
            run_watch_mode(args.layout, args.output, fmt, args.verbose)
        except KeyboardInterrupt:
            print("\nStopped watching.")
            sys.exit(0)
        return

    # Single build mode
    if compose_figure(args.layout, args.output, fmt, args.verbose):
        print(f"Successfully created: {args.output}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
