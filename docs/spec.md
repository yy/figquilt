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
| `auto_scale` | `bool` | `false` | In explicit `panels` mode, auto-fit oversized/off-page panel layouts into the page content area. |
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

#### Auto Container (`type: auto`)

`type: auto` computes panel positions automatically from an ordered list of leaf children:

- Preserves input sequence in reading order (left to right, top to bottom).
- Computes contiguous row breaks (no reordering).
- Fits within the container bounds without distorting panel aspect ratios.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `type` | `string` | Required | `"auto"` |
| `children` | `List[LayoutNode]` | Required | Ordered leaf panels. |
| `gap` | `float` | `0` | Horizontal and vertical spacing between auto-placed panels. |
| `margin` | `float` | `0` | Inner margin of the auto container. |
| `auto_mode` | `string` | `"best"` | Bias preset: `"best"`, `"one-column"`, `"two-column"`. |
| `size_uniformity` | `float` | `0.6` | `0..1`, higher prefers more similar panel areas. |
| `main_scale` | `float` | `2.0` | Size weight used for panels marked `role: main` (unless explicit `weight` is set). |

#### Leaf Node (Panel)

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Required | Unique identifier (used for labels like A, B, C). |
| `file` | `string` | Required | Path to the source figure. |
| `label` | `string` | Auto | Override the auto-generated label. |
| `label_style` | `LabelStyle` | Inherited | Override label styling for this panel. |
| `fit` | `string` | `"contain"` | `"contain"` or `"cover"`. |
| `align` | `string` | `"center"` | Content alignment within cell (see Alignment). |
| `role` | `string` | `"normal"` | Optional prominence hint for auto-layout (`"normal"` or `"main"`). |
| `weight` | `float` | Auto | Optional explicit area weight for auto-layout; higher tends to produce a larger panel. |

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

### Page Auto-Scale (`page.auto_scale`)

When `page.auto_scale: true` is set in explicit `panels` mode:

- figquilt computes the bounding box of all panels in content coordinates (after resolving implicit panel heights from source aspect ratios).
- If the layout is already fully within the page content area (after `page.margin`), no transform is applied.
- If the layout overflows (too wide/tall, negative coordinates, or extends beyond content bounds), figquilt applies one global transform:
  - translate so the layout bounding box starts at `(0, 0)`,
  - then uniformly scale down by `min(content_width / bbox_width, content_height / bbox_height)`.

This preserves relative geometry (all panel positions/sizes stay proportional) while guaranteeing the full composed layout fits within the page content area.

Notes:

- This setting is only used for explicit `panels` mode.
- Grid `layout` mode already resolves directly into the page content area, so no additional auto-scale is needed.

### Auto Layout Objective (`type: auto`)

Auto layout uses an ordered row-partition strategy with a scoring objective:

- Keep input sequence order.
- Prefer rows that align with the selected `auto_mode`:
  - `one-column`: fewer panels per row (taller rows),
  - `two-column`: more panels per row (shorter rows),
  - `best`: evaluate both tendencies and choose lower score.
- Penalize panel-area imbalance based on `size_uniformity`.
- Respect panel prominence hints (`role: main` and `weight`) when distributing area.

The resolver computes panel cell sizes and positions only. Panel content rendering still follows each panel's `fit`/`align` settings.

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
