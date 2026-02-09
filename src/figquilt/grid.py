"""Grid layout resolution: converts layout tree to flat list of positioned panels."""

import math
from typing import List

from .images import get_image_size
from .errors import LayoutError
from .layout import Layout, LayoutNode, Panel


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


def _resolve_auto(
    node: LayoutNode,
    x: float,
    y: float,
    width: float,
    height: float,
    panels: List[Panel],
    path: tuple[str, ...],
) -> None:
    """Resolve an auto container into ordered leaf panels."""
    children = node.children or []
    n = len(children)
    if n == 0:
        return

    aspects = [_leaf_width_over_height(child, path, i) for i, child in enumerate(children)]
    weights = [_leaf_weight(child, node.main_scale) for child in children]

    if node.auto_mode == "best":
        modes = ("one-column", "two-column")
    else:
        modes = (node.auto_mode,)

    best_plan: list[tuple[int, int, float]] | None = None
    best_score = float("inf")
    for mode in modes:
        for target_h in _target_row_heights(mode, n, width, height, node.gap):
            score, plan = _optimize_rows(
                aspects=aspects,
                weights=weights,
                width=width,
                height=height,
                gap=node.gap,
                size_uniformity=node.size_uniformity,
                target_row_h=target_h,
            )
            if score < best_score:
                best_score = score
                best_plan = plan

    if best_plan is None:
        raise LayoutError(f"Auto layout failed at {'.'.join(path)}")

    total_h = sum(row_h for _, _, row_h in best_plan) + node.gap * (len(best_plan) - 1)
    fit_scale = 1.0 if total_h <= height else height / total_h

    cursor_y = y
    for row_idx, (start, end, row_h) in enumerate(best_plan):
        scaled_row_h = row_h * fit_scale
        cursor_x = x
        for i in range(start, end):
            child = children[i]
            panel_w = aspects[i] * row_h * fit_scale
            panels.append(
                Panel(
                    id=child.id,
                    file=child.file,
                    x=cursor_x,
                    y=cursor_y,
                    width=panel_w,
                    height=scaled_row_h,
                    fit=child.fit,
                    align=child.align,
                    label=child.label,
                    label_style=child.label_style,
                )
            )
            cursor_x += panel_w + node.gap * fit_scale
        if row_idx < len(best_plan) - 1:
            cursor_y += scaled_row_h + node.gap * fit_scale


def _leaf_width_over_height(
    node: LayoutNode, path: tuple[str, ...], index: int
) -> float:
    """Return leaf width/height aspect ratio."""
    if node.file is None or node.id is None:
        raise LayoutError(
            f"Auto layout child at {'.'.join((*path, f'children[{index}]'))} must be a leaf panel"
        )
    src_w, src_h = get_image_size(node.file)
    if src_w <= 0 or src_h <= 0:
        raise LayoutError(
            f"Panel '{node.id}' has non-positive source size for auto layout"
        )
    return src_w / src_h


def _leaf_weight(node: LayoutNode, main_scale: float) -> float:
    """Return target size weight for a leaf."""
    if node.weight is not None:
        return node.weight
    if node.role == "main":
        return main_scale
    return 1.0


def _target_row_heights(
    mode: str, n: int, width: float, height: float, gap: float
) -> list[float]:
    """Return candidate row-height targets for a mode."""
    if mode == "one-column":
        target_rows = max(1, math.ceil(math.sqrt(n) * 1.45))
    elif mode == "two-column":
        target_rows = max(1, math.ceil(math.sqrt(n) * 0.9))
    else:
        target_rows = max(1, math.ceil(math.sqrt(n)))

    baseline = (height - gap * (target_rows - 1)) / target_rows
    if baseline <= 0:
        baseline = height / target_rows
    if baseline <= 0:
        baseline = max(width, height) / max(1, n)
    multipliers = (0.72, 0.86, 1.0, 1.14, 1.28)
    return [baseline * m for m in multipliers if baseline * m > 0]


def _optimize_rows(
    *,
    aspects: list[float],
    weights: list[float],
    width: float,
    height: float,
    gap: float,
    size_uniformity: float,
    target_row_h: float,
) -> tuple[float, list[tuple[int, int, float]]]:
    """
    Compute an ordered row partition with dynamic programming.

    Returns:
        (score, rows) where rows is list of (start, end, row_height)
    """
    n = len(aspects)
    dp = [float("inf")] * (n + 1)
    prev = [-1] * (n + 1)
    row_h_at = [0.0] * (n + 1)
    dp[0] = 0.0

    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise LayoutError("Auto layout weight sum must be positive")
    base_area = (width * height) / max(1, n)
    target_area = [base_area * (w * n / weight_sum) for w in weights]
    uniformity_weight = 3.5 * size_uniformity
    aspect_prefix = _prefix_sums(aspects)

    for end in range(1, n + 1):
        for start in range(0, end):
            count = end - start
            available_w = width - gap * (count - 1)
            if available_w <= 0:
                continue
            sum_aspect = aspect_prefix[end] - aspect_prefix[start]
            if sum_aspect <= 0:
                continue
            row_h = available_w / sum_aspect
            if row_h <= 0:
                continue

            row_h_penalty = ((row_h - target_row_h) / target_row_h) ** 2

            area_penalty = 0.0
            if uniformity_weight > 0:
                for i in range(start, end):
                    panel_area = aspects[i] * row_h * row_h
                    ratio = max(panel_area, 1e-12) / max(target_area[i], 1e-12)
                    area_penalty += math.log(ratio) ** 2
                area_penalty /= count

            transition_cost = row_h_penalty + uniformity_weight * area_penalty
            cand = dp[start] + transition_cost
            if cand < dp[end]:
                dp[end] = cand
                prev[end] = start
                row_h_at[end] = row_h

    if prev[n] == -1:
        raise LayoutError("Auto layout could not find a valid row partition")

    rows: list[tuple[int, int, float]] = []
    idx = n
    while idx > 0:
        start = prev[idx]
        rows.append((start, idx, row_h_at[idx]))
        idx = start
    rows.reverse()

    total_h = sum(row_h for _, _, row_h in rows) + gap * (len(rows) - 1)
    fit_penalty = ((total_h - height) / max(height, 1e-9)) ** 2
    if total_h > height:
        fit_penalty *= 4.0
    score = dp[n] + 5.0 * fit_penalty
    return score, rows


def _prefix_sums(values: list[float]) -> list[float]:
    """Return prefix sums with an initial zero."""
    prefix = [0.0]
    total = 0.0
    for value in values:
        total += value
        prefix.append(total)
    return prefix


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

    if node.type == "auto":
        _resolve_auto(node, inner_x, inner_y, inner_w, inner_h, panels, path)
        return

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
