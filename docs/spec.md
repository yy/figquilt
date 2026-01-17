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
| `layout` | `LayoutNode` | Yes | The root layout structure (grid or manual). |

### Page

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `width` | `float` | - | Total page width. |
| `height` | `float` | - | Total page height. |
| `units` | `string` | `"mm"` | global units (`mm`, `inches`, `pt`). |
| `background` | `string` | `"white"` | Background color. |
| `margin` | `float` | `0` | Page margin. Panel coordinates are offset by this value. |

### LayoutNode (The Grid System)

A `LayoutNode` can be a **Container** (holding other nodes) or a **Leaf** (holding a panel/figure).

#### Container Node (Grid/Flex)

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | `string` | `"row"` (horizontal) or `"col"` (vertical) or `"grid"` |
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
| `fit` | `string` | `"contain"` (default), `"cover"`, or `"exact"`. |

### Sizing Rules

1.  **Implicit Sizing**: A leaf node takes the size of its grid cell.
    *   The figure is scaled to fit within the cell while preserving aspect ratio (`contain`).
    *   If `fit: "cover"` is used, it might crop (future feature).
2.  **Explicit Sizing (Discouraged)**:
    *   `width`/`height` on a Leaf Node overrides grid sizing.
    *   **Constraint**: Setting *both* `width` and `height` is invalid unless `force_distortion: true` is set (to prevent accidental stretching).

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
