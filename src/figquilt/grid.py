"""Grid layout resolution: converts layout tree to flat list of positioned panels."""

from typing import List

from .images import get_image_size
from .layout import Layout, LayoutNode, Panel
from .errors import LayoutError


def resolve_layout(layout: Layout) -> List[Panel]:
    """
    Resolve a grid-based Layout to a flat list of Panels with computed positions.

    For legacy layouts with explicit panels, returns those directly.
    For grid layouts, recursively computes panel positions based on
    container structure, ratios, gaps, and margins.
    """
    content_w, content_h = _content_area(layout)

    if layout.panels is not None:
        return _resolve_explicit_panels(
            layout.panels, content_w, content_h, layout.page.auto_scale
        )

    if layout.layout is None:
        return []

    panels: List[Panel] = []
    _resolve_node(layout.layout, 0, 0, content_w, content_h, panels, path=("layout",))
    return panels


def _content_area(layout: Layout) -> tuple[float, float]:
    """Return page content width and height after applying page margin."""
    margin = layout.page.margin
    content_w = layout.page.width - 2 * margin
    content_h = layout.page.height - 2 * margin
    if content_w <= 0 or content_h <= 0:
        raise LayoutError(
            "Page content area is non-positive after applying page margin; reduce margin or increase page size"
        )
    return content_w, content_h


def _resolve_explicit_panels(
    panels: List[Panel], content_w: float, content_h: float, auto_scale: bool
) -> List[Panel]:
    """Resolve explicit panel mode, applying optional page-level auto-scaling."""
    if not auto_scale or not panels:
        return panels

    resolved = [_resolve_panel_height(panel) for panel in panels]
    left, top, right, bottom = _panel_bounds(resolved)

    needs_transform = (
        left < 0 or top < 0 or right > content_w or bottom > content_h
    )
    if not needs_transform:
        return resolved

    bbox_w = right - left
    bbox_h = bottom - top
    if bbox_w <= 0 or bbox_h <= 0:
        raise LayoutError("Panel bounding box must have positive width and height")

    scale = min(content_w / bbox_w, content_h / bbox_h)
    if scale <= 0:
        raise LayoutError("Computed auto-scale factor must be positive")

    return [
        panel.model_copy(
            update={
                "x": (panel.x - left) * scale,
                "y": (panel.y - top) * scale,
                "width": panel.width * scale,
                "height": panel.height * scale,
            }
        )
        for panel in resolved
    ]


def _resolve_panel_height(panel: Panel) -> Panel:
    """Ensure panel height is concrete by resolving missing height from source aspect."""
    if panel.height is not None:
        return panel

    src_w, src_h = get_image_size(panel.file)
    if src_w <= 0 or src_h <= 0:
        raise LayoutError(
            f"Panel '{panel.id}' has non-positive source size for auto-scaling"
        )

    resolved_height = panel.width * (src_h / src_w)
    return panel.model_copy(update={"height": resolved_height})


def _panel_bounds(panels: List[Panel]) -> tuple[float, float, float, float]:
    """Compute bounding box (left, top, right, bottom) for explicit panels."""
    left = min(panel.x for panel in panels)
    top = min(panel.y for panel in panels)
    right = max(panel.x + panel.width for panel in panels)
    bottom = max(panel.y + _panel_height(panel) for panel in panels)
    return left, top, right, bottom


def _panel_height(panel: Panel) -> float:
    """Return panel height (must be resolved by this point)."""
    if panel.height is None:
        raise LayoutError(f"Panel '{panel.id}' height could not be resolved")
    return panel.height


def _resolve_node(
    node: LayoutNode,
    x: float,
    y: float,
    width: float,
    height: float,
    panels: List[Panel],
    path: tuple[str, ...],
) -> None:
    """
    Recursively resolve a layout node into panels.

    Args:
        node: The layout node to resolve
        x, y: Top-left position of this node's cell
        width, height: Size of this node's cell
        panels: List to append resolved panels to
    """
    if not node.is_container():
        # Leaf node: create a panel
        if width <= 0 or height <= 0:
            raise LayoutError(
                f"Leaf node '{node.id}' has non-positive size ({width}x{height}) at {'.'.join(path)}"
            )
        panels.append(
            Panel(
                id=node.id,
                file=node.file,
                x=x,
                y=y,
                width=width,
                height=height,
                fit=node.fit,
                align=node.align,
                label=node.label,
                label_style=node.label_style,
            )
        )
        return

    # Container node: apply margin and distribute children
    margin = node.margin
    inner_x = x + margin
    inner_y = y + margin
    inner_w = width - 2 * margin
    inner_h = height - 2 * margin
    if inner_w <= 0 or inner_h <= 0:
        raise LayoutError(
            f"Container at {'.'.join(path)} has non-positive inner size after margin; reduce container margin"
        )

    children = node.children or []
    n = len(children)

    # Calculate ratios (default to equal distribution)
    ratios = node.ratios if node.ratios else [1.0] * n
    total_ratio = sum(ratios)
    if total_ratio <= 0:
        raise LayoutError(f"Container at {'.'.join(path)} has non-positive ratio sum")

    # Calculate available space after gaps
    gap = node.gap
    total_gap = gap * (n - 1) if n > 1 else 0

    is_row = node.type == "row"
    available = (inner_w if is_row else inner_h) - total_gap
    if available <= 0:
        axis = "width" if is_row else "height"
        raise LayoutError(
            f"Container at {'.'.join(path)} has non-positive available {axis} after gaps"
        )

    cursor = inner_x if is_row else inner_y
    for i, child in enumerate(children):
        main_size = (ratios[i] / total_ratio) * available
        child_x = cursor if is_row else inner_x
        child_y = inner_y if is_row else cursor
        child_w = main_size if is_row else inner_w
        child_h = inner_h if is_row else main_size

        _resolve_node(
            child,
            child_x,
            child_y,
            child_w,
            child_h,
            panels,
            path=(*path, f"children[{i}]"),
        )
        cursor += main_size + gap
