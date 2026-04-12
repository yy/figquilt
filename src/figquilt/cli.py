import argparse
import sys
from pathlib import Path
from typing import Optional, Set, Tuple
import threading
from collections.abc import Callable

from .base_composer import validate_panel_sources
from .parser import parse_layout
from .errors import FigQuiltError
from .layout import Layout, Panel, iter_panels
from .grid import resolve_layout

type Renderer = Callable[[Layout, Path, list[Panel] | None], None]
type WatchedPaths = tuple[Set[Path], Set[Path]]


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

    doc = PDFComposer(layout, panels=panels).build()
    try:
        page = doc[0]
        pix = page.get_pixmap(dpi=layout.page.dpi)
        output_path.write_bytes(pix.tobytes("png"))
    finally:
        doc.close()


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


def _layout_only_watch_paths(layout_path: Path) -> WatchedPaths:
    """Watch just the layout file and its parent directory."""
    layout_path = layout_path.resolve()
    return {layout_path}, {layout_path.parent}


def _load_watched_paths(
    layout_path: Path,
    *,
    validate_assets: bool,
    fallback_to_layout_only: bool,
) -> WatchedPaths | None:
    """Parse a layout and derive the file and directory watch targets."""
    try:
        layout = parse_layout(layout_path, validate_assets=validate_assets)
        return get_watched_paths(layout_path, layout)
    except FigQuiltError:
        if fallback_to_layout_only:
            return _layout_only_watch_paths(layout_path)
        return None


def get_watched_paths(layout_path: Path, layout: Layout) -> Tuple[Set[Path], Set[Path]]:
    """
    Return the set of files and directories to watch.

    Returns:
        Tuple of (watched_files, watched_dirs)
    """
    layout_path = layout_path.resolve()
    files = {layout_path}
    try:
        panels = resolve_layout(layout)
        for panel in panels:
            files.add(panel.file.resolve())
    except FigQuiltError:
        files.update(_iter_referenced_asset_paths(layout))
    dirs = {_nearest_existing_dir(f.parent) for f in files}
    return files, dirs


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

        layout = parse_layout(layout_path)
        panels: list[Panel] | None = None
        if verbose:
            panels = resolve_layout(layout)
            _print_layout_summary(
                layout_path, layout, len(panels), prefix="Layout parsed"
            )

        renderer(layout, output_path, panels)

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
    stop_event: Optional[threading.Event] = None,
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
    watched_paths = _load_watched_paths(
        layout_path,
        validate_assets=False,
        fallback_to_layout_only=True,
    )
    assert watched_paths is not None
    watched_files, watch_dirs = watched_paths

    while True:
        restart_watcher = False

        for changes in watch(*watch_dirs, stop_event=stop_event):
            if stop_event and stop_event.is_set():
                return

            # Check if any changed file is in our watched set
            changed_paths = {Path(change[1]).resolve() for change in changes}
            relevant_changes = changed_paths & watched_files

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
                refreshed_paths = _load_watched_paths(
                    layout_path,
                    validate_assets=False,
                    fallback_to_layout_only=True,
                )
                assert refreshed_paths is not None
                new_files, new_dirs = refreshed_paths
                if new_dirs != watch_dirs:
                    # Directories changed, need to restart the watcher
                    watched_files = new_files
                    watch_dirs = new_dirs
                    restart_watcher = True
                    if verbose:
                        print("Watch directories changed, restarting watcher...")
                    break
                watched_files = new_files

        if stop_event and stop_event.is_set():
            return
        if not restart_watcher:
            break


def main():
    parser = argparse.ArgumentParser(
        description="FigQuilt: Compose figures from multiple panels."
    )
    parser.add_argument("layout", type=Path, help="Path to layout YAML file")
    parser.add_argument("output", type=Path, help="Path to output file (PDF/SVG/PNG)")
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
            layout = parse_layout(args.layout)
            panels = resolve_layout(layout)
            validate_panel_sources(panels)
            _print_layout_summary(
                args.layout,
                layout,
                len(panels),
                prefix="Layout parsed successfully",
            )
            sys.exit(0)
        except FigQuiltError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

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
