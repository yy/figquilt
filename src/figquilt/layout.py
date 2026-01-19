from __future__ import annotations
from typing import Literal, Optional, List
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator

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


class LabelStyle(BaseModel):
    """Styling options for panel labels."""

    enabled: bool = Field(True, description="Whether to show labels")
    auto_sequence: bool = Field(True, description="Auto-generate labels A, B, C...")
    font_family: str = Field("Helvetica", description="Font family for labels")
    font_size_pt: float = Field(8.0, description="Font size in points")
    offset_x: float = Field(
        2.0, description="Horizontal offset from panel edge (in page units)"
    )
    offset_y: float = Field(
        2.0, description="Vertical offset from panel edge (in page units)"
    )
    bold: bool = Field(True, description="Use bold font")
    uppercase: bool = Field(True, description="Use uppercase letters")


class Panel(BaseModel):
    """A figure panel to place on the page (with explicit coordinates)."""

    id: str = Field(..., description="Unique identifier for this panel")
    file: Path = Field(..., description="Path to source file (PDF, SVG, or PNG)")
    x: float = Field(..., description="X position from left edge (in page units)")
    y: float = Field(..., description="Y position from top edge (in page units)")
    width: float = Field(..., description="Panel width (in page units)")
    height: Optional[float] = Field(
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

    @field_validator("file")
    @classmethod
    def validate_file(cls, v: Path) -> Path:
        return v


# Grid layout system


class LayoutNode(BaseModel):
    """A node in the layout tree - either a container or a leaf panel."""

    # Container fields (used when type is "row" or "col")
    type: Optional[Literal["row", "col"]] = Field(
        None, description="Container type: row (horizontal) or col (vertical)"
    )
    children: Optional[List[LayoutNode]] = Field(
        None, description="Child nodes (containers or leaves)"
    )
    ratios: Optional[List[float]] = Field(
        None, description="Relative sizing of children (e.g., [3, 2] = 60%/40%)"
    )
    gap: float = Field(0.0, description="Gap between children (in page units)")
    margin: float = Field(0.0, description="Inner margin of this container")

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

    @field_validator("file")
    @classmethod
    def validate_file(cls, v: Optional[Path]) -> Optional[Path]:
        return v

    @model_validator(mode="after")
    def validate_node(self) -> LayoutNode:
        is_container = self.type is not None
        is_leaf = self.id is not None or self.file is not None

        if is_container and is_leaf:
            raise ValueError("Node cannot be both container and leaf")

        if is_container:
            if not self.children:
                raise ValueError("Container must have children")
            if self.ratios is not None and len(self.ratios) != len(self.children):
                raise ValueError(
                    f"ratios length ({len(self.ratios)}) must match children length ({len(self.children)})"
                )
        elif is_leaf:
            if not self.id:
                raise ValueError("Leaf node must have id")
            if not self.file:
                raise ValueError("Leaf node must have file")
        else:
            raise ValueError("Node must be either container (type) or leaf (id, file)")

        return self

    def is_container(self) -> bool:
        return self.type is not None


class Page(BaseModel):
    """Page dimensions and default settings."""

    width: float = Field(..., description="Page width (in specified units)")
    height: float = Field(..., description="Page height (in specified units)")
    units: Literal["mm", "inches", "pt"] = Field(
        "mm", description="Units for dimensions"
    )
    dpi: int = Field(300, description="Resolution for rasterized output")
    background: Optional[str] = Field(
        "white", description="Background color (name or hex)"
    )
    margin: float = Field(
        0.0, description="Page margin; panel coordinates are offset by this"
    )
    label: LabelStyle = Field(
        default_factory=LabelStyle, description="Default label style"
    )


class Layout(BaseModel):
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
        return self
