# Figquilt Layout Specification

This document defines the YAML/JSON specification for `figquilt` layouts.

## Core Philosophy

1.  **Aspect Ratio Preservation**: Users should rarely set both width and height. Figures should scale naturally to fit their container.
2.  **Grid-First Layout**: Layouts should be defined by structure (rows/columns/ratios) rather than manual coordinate placement.
3.  **Reproducibility**: The layout file completely defines the output geometry.

## Schema Structure

### Root Object

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `page` | `Page` | Yes | Defines the canvas properties. |
| `panels` | `List[Panel]` | No* | List of panels with explicit coordinates (legacy mode). |
| `layout` | `LayoutNode` | No* | The root layout structure for grid-based positioning. |

*Either `panels` or `layout` must be specified, but not both.

### Page

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `width` | `float` | - | Total page width. |
| `height` | `float` | - | Total page height. |
| `units` | `string` | `"mm"` | Global units (`mm`, `inches`, `pt`). |
| `dpi` | `int` | `300` | Resolution for rasterized output (PNG). |
| `background` | `string` | `"white"` | Background color (name or hex). |
| `margin` | `float` | `0` | Page margin. Panel coordinates are offset by this value. |
| `label` | `LabelStyle` | (see below) | Default label styling for all panels. |

### LabelStyle

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `true` | Whether to show labels. |
| `auto_sequence` | `bool` | `true` | Auto-generate labels A, B, C... |
| `font_family` | `string` | `"Helvetica"` | Font family for labels. |
| `font_size_pt` | `float` | `8.0` | Font size in points. |
| `offset_x` | `float` | `2.0` | Horizontal offset from panel edge (in page units). |
| `offset_y` | `float` | `2.0` | Vertical offset from panel edge (in page units). |
| `bold` | `bool` | `true` | Use bold font. |
| `uppercase` | `bool` | `true` | Use uppercase letters. |

### Panel (Explicit Coordinates Mode)

When using `panels` instead of `layout`, each panel has explicit coordinates:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Yes | Unique identifier for this panel. |
| `file` | `string` | Yes | Path to source file (PDF, SVG, or PNG). |
| `x` | `float` | Yes | X position from left edge (in page units). |
| `y` | `float` | Yes | Y position from top edge (in page units). |
| `width` | `float` | Yes | Panel width (in page units). |
| `height` | `float` | No | Panel height; if omitted, computed from aspect ratio. |
| `fit` | `string` | No | `"contain"` (default) or `"cover"`. |
| `label` | `string` | No | Override the auto-generated label text. |
| `label_style` | `LabelStyle` | No | Override default label styling for this panel. |

### LayoutNode (The Grid System)

A `LayoutNode` can be a **Container** (holding other nodes) or a **Leaf** (holding a panel/figure).

#### Container Node (Grid/Flex)

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | `string` | `"row"` (horizontal) or `"col"` (vertical) |
| `children` | `List[LayoutNode]` | List of child nodes or panels. |
| `ratios` | `List[float]` | *Optional*. Relative sizing of children. E.g., `[3, 2]` means 60% / 40%. |
| `gap` | `float` | Gap between children in defined units. |
| `margin` | `float` | Inner margin of this container. |

#### Leaf Node (Panel)

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier (used for labels like A, B, C). |
| `file` | `string` | Path to the source figure. |
| `label` | `string` | *Optional*. Override the auto-generated label. |
| `label_style` | `LabelStyle` | *Optional*. Override default label styling for this panel. |
| `fit` | `string` | `"contain"` (default) or `"cover"`. |

### Sizing Rules

1.  **Implicit Sizing**: A leaf node takes the size of its grid cell.
    *   `fit: "contain"` (default): Scale to fit within the cell, preserving aspect ratio. May leave empty space.
    *   `fit: "cover"`: Scale to cover the entire cell, preserving aspect ratio. Overflow is clipped.
2.  **Explicit Panels Mode**: When using `panels` (legacy mode), each panel specifies explicit `x`, `y`, `width`, and optionally `height`.
    *   If `height` is omitted, it is computed from the source aspect ratio to preserve proportions.

## Examples

### 1. Simple 3:2 Split

Divides the page width into two columns. The first takes 3 parts, the second takes 2 parts.

```yaml
page:
  width: 180
  height: 100
  units: mm

layout:
  type: row
  ratios: [3, 2]  # Left is 60%, Right is 40%
  gap: 5
  children:
    - id: A
      file: "plot1.pdf"
    - id: B
      file: "plot2.pdf"
```

### 2. Nested Grid

Top is a full-width header. Bottom is split 1:1.

```yaml
page:
  width: 180
  height: 200
  units: mm

layout:
  type: col
  ratios: [1, 2] # Top row is 1/3 height, Bottom row is 2/3 height
  children:
    - id: A
      file: "header.pdf"
    - type: row
      ratios: [1, 1]
      gap: 5
      children:
        - id: B
          file: "left.pdf"
        - id: C
          file: "right.pdf"
```

### 3. Explicit Coordinates (Legacy Mode)

For precise control, specify exact positions and sizes for each panel.

```yaml
page:
  width: 180
  height: 120
  units: mm
  margin: 10

panels:
  - id: A
    file: "plots/scatter.pdf"
    x: 0
    y: 0
    width: 70
  - id: B
    file: "diagrams/schematic.svg"
    x: 80
    y: 0
    width: 70
    height: 50
    fit: cover
```
