# Figquilt Layout Specification

This document defines the YAML/JSON specification for `figquilt` layouts.

## Core Philosophy

1. **Aspect Ratio Preservation**: Users should rarely set both width and height. Figures should scale naturally to fit their container.
2. **Grid-First Layout**: Layouts should be defined by structure (rows/columns/ratios) rather than manual coordinate placement.
3. **Reproducibility**: The layout file completely defines the output geometry.

## Schema Structure

### Root Object

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `page` | `Page` | Yes | Defines the canvas properties. |
| `layout` | `LayoutNode` | One of | The root layout structure (grid-based, recommended). |
| `panels` | `List[Panel]` | One of | List of panels with explicit coordinates (legacy mode). |

You must specify either `layout` (recommended) or `panels`, but not both.

### Page

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `width` | `float` | Required | Total page width. |
| `height` | `float` | Required | Total page height. |
| `units` | `string` | `"mm"` | Global units (`mm`, `inches`, `pt`). |
| `dpi` | `int` | `300` | Resolution for rasterized output (PNG). |
| `background` | `string` | `"white"` | Background color (name or hex). |
| `margin` | `float` | `0` | Page margin. Panel coordinates are offset by this value. |
| `label` | `LabelStyle` | See below | Default label styling for all panels. |

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

### LayoutNode (Grid System)

A `LayoutNode` can be a **Container** (holding other nodes) or a **Leaf** (holding a panel/figure).

#### Container Node

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `type` | `string` | Required | `"row"` (horizontal) or `"col"` (vertical). |
| `children` | `List[LayoutNode]` | Required | List of child nodes or panels. |
| `ratios` | `List[float]` | Equal | Relative sizing of children. E.g., `[3, 2]` means 60% / 40%. |
| `gap` | `float` | `0` | Gap between children (in page units). |
| `margin` | `float` | `0` | Inner margin of this container. |

#### Leaf Node (Panel)

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Required | Unique identifier (used for labels like A, B, C). |
| `file` | `string` | Required | Path to the source figure. |
| `label` | `string` | Auto | Override the auto-generated label. |
| `label_style` | `LabelStyle` | Inherited | Override label styling for this panel. |
| `fit` | `string` | `"contain"` | `"contain"` or `"cover"`. |
| `align` | `string` | `"center"` | Content alignment within cell (see Alignment). |

### Panel (Explicit Coordinates Mode)

When using `panels` instead of `layout`, each panel specifies explicit coordinates:

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Required | Unique identifier. |
| `file` | `string` | Required | Path to the source figure. |
| `x` | `float` | Required | X position from left edge (in page units). |
| `y` | `float` | Required | Y position from top edge (in page units). |
| `width` | `float` | Required | Panel width (in page units). |
| `height` | `float` | Auto | Panel height; if omitted, computed from aspect ratio. |
| `fit` | `string` | `"contain"` | `"contain"` or `"cover"`. |
| `align` | `string` | `"center"` | Content alignment within cell (see Alignment). |
| `label` | `string` | Auto | Override the auto-generated label. |
| `label_style` | `LabelStyle` | Inherited | Override label styling for this panel. |

### Fit Modes

- **`contain`** (default): Scale to fit within the cell, preserving aspect ratio. May leave empty space.
- **`cover`**: Scale to cover the entire cell, preserving aspect ratio. May clip overflow.

### Alignment

Controls where content is positioned within its cell when using `contain` fit mode (which may leave empty space):

- **`center`** (default): Center both horizontally and vertically.
- **`top`**: Top edge, horizontally centered.
- **`bottom`**: Bottom edge, horizontally centered.
- **`left`**: Left edge, vertically centered.
- **`right`**: Right edge, vertically centered.
- **`top-left`**: Top-left corner.
- **`top-right`**: Top-right corner.
- **`bottom-left`**: Bottom-left corner.
- **`bottom-right`**: Bottom-right corner.

## Examples

### 1. Simple 3:2 Split (Grid Layout)

Divides the page width into two columns. The first takes 3 parts, the second takes 2 parts.

```yaml
page:
  width: 180
  height: 100
  units: mm

layout:
  type: row
  ratios: [3, 2]
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
  ratios: [1, 2]
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

### 4. Custom Labels

```yaml
page:
  width: 180
  height: 100
  units: mm
  label:
    font_size_pt: 12
    bold: true

layout:
  type: row
  children:
    - id: A
      file: "plot1.pdf"
      label: "i"
    - id: B
      file: "plot2.pdf"
      label: "ii"
```
