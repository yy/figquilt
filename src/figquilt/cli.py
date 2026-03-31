import argparse
import sys
from pathlib import Path
from typing import Optional, Set, Tuple
import threading
from collections.abc import Callable

from .parser import parse_layout
from .errors import FigQuiltError
from .layout import Layout, Panel
from .grid import resolve_layout


def _load_layout_and_panels(layout_path: Path) -> tuple[Layout, list[Panel]]:
    """Parse a layout file and resolve it to concrete panels."""
    layout = parse_layout(layout_path)
    return layout, resolve_layout(layout)


def _print_layout_summary(
    layout_path: Path, layout: Layout, panel_count: int, *, prefix: str
) -> None:
    """Print a short summary of the resolved layout."""
    print(f"{prefix}: {layout_path}")
    print(f"Page size: {layout.page.width}x{layout.page.height} {layout.page.units}")
    print(f"Panels: {panel_count}")


def _compose_pdf(layout: Layout, output_path: Path) -> None:
    """Render a layout directly to PDF."""
    from .compose_pdf import PDFComposer

    PDFComposer(layout).compose(output_path)


def _compose_svg(layout: Layout, output_path: Path) -> None:
    """Render a layout directly to SVG."""
    from .compose_svg import SVGComposer

    SVGComposer(layout).compose(output_path)


def _compose_png(layout: Layout, output_path: Path) -> None:
    """Render a layout to PNG via an intermediate PDF document."""
    from .compose_pdf import PDFComposer

    doc = PDFComposer(layout).build()
    try:
        page = doc[0]
        pix = page.get_pixmap(dpi=layout.page.dpi)
        pix.save(str(output_path))
    finally:
        doc.close()


def _renderer_for_format(fmt: str) -> Callable[[Layout, Path], None] | None:
    """Return the renderer for a supported output format."""
    if fmt == "pdf":
        return _compose_pdf
    if fmt == "svg":
        return _compose_svg
    if fmt == "png":
        return _compose_png
    return None


def get_watched_paths(layout_path: Path, layout: Layout) -> Tuple[Set[Path], Set[Path]]:
    """
    Return the set of files and directories to watch.

    Returns:
        Tuple of (watched_files, watched_dirs)
    """
    layout_path = layout_path.resolve()
    files = {layout_path}
    panels = resolve_layout(layout)
    for panel in panels:
        files.add(panel.file.resolve())
    dirs = {f.parent for f in files}
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

        layout, panels = _load_layout_and_panels(layout_path)
        if verbose:
            _print_layout_summary(
                layout_path, layout, len(panels), prefix="Layout parsed"
            )

        renderer(layout, output_path)

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
    try:
        layout = parse_layout(layout_path)
        watched_files, watch_dirs = get_watched_paths(layout_path, layout)
    except FigQuiltError:
        # If layout is invalid, just watch the layout file itself
        layout_path_resolved = layout_path.resolve()
        watched_files = {layout_path_resolved}
        watch_dirs = {layout_path_resolved.parent}

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

                # Re-parse layout to update watched files (panels might have changed)
                try:
                    layout = parse_layout(layout_path)
                    new_files, new_dirs = get_watched_paths(layout_path, layout)
                    if new_dirs != watch_dirs:
                        # Directories changed, need to restart the watcher
                        watched_files = new_files
                        watch_dirs = new_dirs
                        restart_watcher = True
                        if verbose:
                            print("Watch directories changed, restarting watcher...")
                        break
                    watched_files = new_files
                except FigQuiltError:
                    pass  # Keep watching existing files if layout is invalid

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
            layout, panels = _load_layout_and_panels(args.layout)
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

    if fmt not in ("pdf", "svg", "png"):
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
