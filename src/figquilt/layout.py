from __future__ import annotations
from collections.abc import Iterator
from typing import Annotated, Literal, Optional, List
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator

FitMode = Literal["contain", "cover"]
Alignment = Literal[
    "center",
    "top",
    "bottom",
    "left",
    "right",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
]

StrictFloat = Annotated[float, Field(strict=True)]
StrictPositiveFloat = Annotated[float, Field(gt=0, strict=True)]
StrictNonNegativeFloat = Annotated[float, Field(ge=0, strict=True)]
StrictUnitFloat = Annotated[float, Field(ge=0, le=1, strict=True)]
StrictPositiveInt = Annotated[int, Field(ge=1, strict=True)]
StrictBool = Annotated[bool, Field(strict=True)]


class LayoutModel(BaseModel):
    """Base model for user-authored layout configuration."""

    model_config = ConfigDict(extra="forbid")


class LabelStyle(LayoutModel):
    """Styling options for panel labels."""

    enabled: StrictBool = Field(True, description="Whether to show labels")
    auto_sequence: StrictBool = Field(
        True, description="Auto-generate labels A, B, C..."
    )
    font_family: str = Field("Helvetica", description="Font family for labels")
    font_size_pt: StrictPositiveFloat = Field(8.0, description="Font size in points")
    offset_x: StrictFloat = Field(
        2.0, description="Horizontal offset from panel edge (in page units)"
    )
    offset_y: StrictFloat = Field(
        2.0, description="Vertical offset from panel edge (in page units)"
    )
    bold: StrictBool = Field(True, description="Use bold font")
    uppercase: StrictBool = Field(True, description="Use uppercase letters")


class Panel(LayoutModel):
    """A figure panel to place on the page (with explicit coordinates)."""

    id: str = Field(..., description="Unique identifier for this panel")
    file: Path = Field(..., description="Path to source file (PDF, SVG, or PNG)")
    x: StrictFloat = Field(..., description="X position from left edge (in page units)")
    y: StrictFloat = Field(..., description="Y position from top edge (in page units)")
    width: StrictPositiveFloat = Field(..., description="Panel width (in page units)")
    height: Optional[StrictPositiveFloat] = Field(
        None, description="Panel height; if omitted, computed from aspect ratio"
    )
    fit: FitMode = Field(
        "contain",
        description="How to fit the figure: contain (preserve aspect) or cover (fill and clip)",
    )
    align: Alignment = Field(
        "center",
        description="How to align content within cell when using contain fit mode",
    )
    label: Optional[str] = Field(
        None, description="Override the auto-generated label text"
    )
    label_style: Optional[LabelStyle] = Field(
        None, description="Override default label styling for this panel"
    )


# Grid layout system


class LayoutNode(LayoutModel):
    """A node in the layout tree - either a container or a leaf panel."""

    # Container fields (used when type is "row", "col", or "auto")
    type: Optional[Literal["row", "col", "auto"]] = Field(
        None, description="Container type: row (horizontal), col (vertical), or auto"
    )
    children: Optional[List[LayoutNode]] = Field(
        None, description="Child nodes (containers or leaves)"
    )
    ratios: Optional[List[StrictPositiveFloat]] = Field(
        None, description="Relative sizing of children (e.g., [3, 2] = 60%/40%)"
    )
    gap: StrictNonNegativeFloat = Field(
        0.0, description="Gap between children (in page units)"
    )
    margin: StrictNonNegativeFloat = Field(
        0.0, description="Inner margin of this container"
    )
    auto_mode: Literal["best", "one-column", "two-column"] = Field(
        "best", description="Auto-layout bias preset"
    )
    size_uniformity: StrictUnitFloat = Field(
        0.6, description="How strongly to favor similar panel sizes"
    )
    main_scale: StrictPositiveFloat = Field(
        2.0, description="Size weight for leaves with role='main'"
    )

    # Leaf fields (used when type is None)
    id: Optional[str] = Field(None, description="Unique identifier for this panel")
    file: Optional[Path] = Field(
        None, description="Path to source file (PDF, SVG, or PNG)"
    )
    fit: FitMode = Field("contain", description="How to fit the figure in its cell")
    align: Alignment = Field(
        "center", description="How to align content within cell when using contain fit"
    )
    label: Optional[str] = Field(
        None, description="Override the auto-generated label text"
    )
    label_style: Optional[LabelStyle] = Field(
        None, description="Override default label styling for this panel"
    )
    role: Literal["normal", "main"] = Field(
        "normal", description="Optional prominence role for auto layout"
    )
    weight: Optional[StrictPositiveFloat] = Field(
        None, description="Optional explicit size weight for auto layout"
    )

    @model_validator(mode="after")
    def validate_node(self) -> LayoutNode:
        is_container = self.type is not None
        is_leaf = self.id is not None or self.file is not None

        if is_container and is_leaf:
            raise ValueError("Node cannot be both container and leaf")

        if is_container:
            self._validate_container_node()
            return self

        if is_leaf:
            self._validate_leaf_node()
            return self

        raise ValueError("Node must be either container (type) or leaf (id, file)")

    def is_container(self) -> bool:
        return self.type is not None

    def _validate_container_node(self) -> None:
        if not self.children:
            raise ValueError("Container must have children")

        if self.type == "auto":
            self._validate_auto_container()
            return

        self._validate_ratio_container()

    def _validate_auto_container(self) -> None:
        if self.ratios is not None:
            raise ValueError("Auto container does not support ratios")
        if any(child.is_container() for child in self.children or []):
            raise ValueError("Auto container children must be leaf panels")

    def _validate_ratio_container(self) -> None:
        children = self.children or []
        if self.ratios is not None and len(self.ratios) != len(children):
            raise ValueError(
                f"ratios length ({len(self.ratios)}) must match children length ({len(children)})"
            )
        if self.ratios is not None and any(r <= 0 for r in self.ratios):
            raise ValueError("All ratios must be > 0")

    def _validate_leaf_node(self) -> None:
        if not self.id:
            raise ValueError("Leaf node must have id")
        if not self.file:
            raise ValueError("Leaf node must have file")


class Page(LayoutModel):
    """Page dimensions and default settings."""

    width: StrictPositiveFloat = Field(
        ..., description="Page width (in specified units)"
    )
    height: StrictPositiveFloat = Field(
        ..., description="Page height (in specified units)"
    )
    units: Literal["mm", "inches", "pt"] = Field(
        "mm", description="Units for dimensions"
    )
    dpi: StrictPositiveInt = Field(300, description="Resolution for rasterized output")
    background: Optional[str] = Field(
        "white", description="Background color (name or hex)"
    )
    margin: StrictNonNegativeFloat = Field(
        0.0, description="Page margin; panel coordinates are offset by this"
    )
    auto_scale: StrictBool = Field(
        False,
        description="Auto-fit oversized explicit panel layouts to the page content area",
    )
    label: LabelStyle = Field(
        default_factory=LabelStyle, description="Default label style"
    )

    @model_validator(mode="after")
    def validate_margin(self) -> Page:
        max_margin = min(self.width, self.height) / 2
        if self.margin >= max_margin:
            raise ValueError(
                f"Page margin ({self.margin}) must be less than half of smaller page dimension ({max_margin})"
            )
        return self


class Layout(LayoutModel):
    """Root layout object for figquilt."""

    page: Page = Field(..., description="Page dimensions and settings")
    panels: Optional[List[Panel]] = Field(
        None, description="List of panels with explicit coordinates (legacy mode)"
    )
    layout: Optional[LayoutNode] = Field(
        None, description="Root layout node for grid-based layout"
    )

    @model_validator(mode="after")
    def validate_layout_or_panels(self) -> Layout:
        if self.panels is None and self.layout is None:
            raise ValueError("Must specify either 'panels' or 'layout'")
        if self.panels is not None and self.layout is not None:
            raise ValueError("Cannot specify both 'panels' and 'layout'")

        ids = list(iter_panel_ids(self))
        if any(panel_id == "" for panel_id in ids):
            raise ValueError("Panel IDs must be non-empty")
        if len(ids) != len(set(ids)):
            raise ValueError("Panel IDs must be unique")
        return self


def iter_layout_leaves(node: Optional[LayoutNode]) -> Iterator[LayoutNode]:
    """Yield leaf nodes from a layout tree in declaration order."""
    if node is None:
        return
    if node.is_container():
        for child in node.children or []:
            yield from iter_layout_leaves(child)
        return
    yield node


def iter_panels(layout: Layout) -> Iterator[Panel | LayoutNode]:
    """Yield declared panels in declaration order across both layout modes."""
    if layout.panels is not None:
        yield from layout.panels
        return

    yield from iter_layout_leaves(layout.layout)


def iter_panel_ids(layout: Layout) -> Iterator[str]:
    """Yield panel IDs from either explicit-panel or grid layout mode."""
    for panel in iter_panels(layout):
        if panel.id is not None:
            yield panel.id
