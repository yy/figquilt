"""Grid layout resolution: converts layout tree to flat list of positioned panels."""

from typing import List
from .layout import Layout, LayoutNode, Panel


def resolve_layout(layout: Layout) -> List[Panel]:
    """
    Resolve a grid-based Layout to a flat list of Panels with computed positions.

    For legacy layouts with explicit panels, returns those directly.
    For grid layouts, recursively computes panel positions based on
    container structure, ratios, gaps, and margins.
    """
    if layout.panels is not None:
        return layout.panels

    if layout.layout is None:
        return []

    # Calculate content area after page margin
    # Note: x, y are in content coordinate space (0,0 = top-left of content area)
    # The composer will add the page margin offset when rendering
    margin = layout.page.margin
    content_w = layout.page.width - 2 * margin
    content_h = layout.page.height - 2 * margin

    panels: List[Panel] = []
    _resolve_node(layout.layout, 0, 0, content_w, content_h, panels)
    return panels


def _resolve_node(
    node: LayoutNode,
    x: float,
    y: float,
    width: float,
    height: float,
    panels: List[Panel],
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
        panels.append(
            Panel(
                id=node.id,
                file=node.file,
                x=x,
                y=y,
                width=width,
                height=height,
                fit=node.fit,
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

    children = node.children
    n = len(children)

    # Calculate ratios (default to equal distribution)
    ratios = node.ratios if node.ratios else [1.0] * n
    total_ratio = sum(ratios)

    # Calculate available space after gaps
    gap = node.gap
    total_gap = gap * (n - 1) if n > 1 else 0

    if node.type == "row":
        # Horizontal layout
        available = inner_w - total_gap
        cursor = inner_x
        for i, child in enumerate(children):
            child_w = (ratios[i] / total_ratio) * available
            _resolve_node(child, cursor, inner_y, child_w, inner_h, panels)
            cursor += child_w + gap
    else:
        # Vertical layout (col)
        available = inner_h - total_gap
        cursor = inner_y
        for i, child in enumerate(children):
            child_h = (ratios[i] / total_ratio) * available
            _resolve_node(child, inner_x, cursor, inner_w, child_h, panels)
            cursor += child_h + gap
