# figquilt

**Figure quilter**: A declarative CLI tool for compositing multiple figures (PDF, SVG, PNG) into publication-ready layouts.

`figquilt` takes a simple layout file (YAML) describing panels and their structure, composed of various inputs (plots from R/Python, diagrams, photos), and stitches them into a single output file (PDF, SVG) with automatic labeling and precise dimension control.

## Philosophy

- **Declarative over imperative**: Describe *what* your figure should look like, not *how* to construct it. Layouts are data, not scripts.
- **Structural composition first**: Prefer high-level layout (rows, columns, ratios) over manual coordinate placement. Let the tool handle positioning.
- **Fine control when needed**: Override with explicit coordinates and dimensions when precision matters.
- **Automation-friendly**: Designed to fit into reproducible workflows (Snakemake, Make, CI pipelines). No GUI, no manual steps.

## Features

- **Precise Layout**: Define exact physical dimensions (mm) for the page and panels.
- **Mixed Media**: Combine PDF, SVG, and PNG inputs in one figure.
- **Automated Labeling**: Automatically add subfigure labels (A, B, C...) with consistent styling.
- **Reproducible**: Layouts are defined in version-controllable text files (YAML).
- **Language Agnostic**: It is a CLI tool, so it works with outputs from any tool (R, Python, Julia, Inkscape, etc.).

## Installation

```bash
uv tool install figquilt
```

Or add it as a project dependency:

```bash
uv add figquilt
```

### Development Installation

```bash
git clone https://github.com/yy/figquilt.git
cd figquilt
uv sync
```

## Usage

Define a layout in a YAML file (e.g., `figure1.yaml`):

```yaml
page:
  width: 180  # mm
  height: 120 # mm
  
panels:
  - id: A
    file: "plots/scatter.pdf"
    width: 80
    x: 0
    y: 0
  - id: B
    file: "diagrams/schematic.svg"
    width: 80
    x: 90
    y: 0
```

Run `figquilt` to generate the figure:

```bash
figquilt figure1.yaml figure1.pdf
```

### Watch Mode

Use `--watch` to automatically rebuild when the layout file or any panel source files change:

```bash
figquilt --watch figure1.yaml figure1.pdf
```

This is useful during layout iteration - edit your YAML or regenerate a panel, and the output updates automatically.

### Fit Modes

When specifying both `width` and `height` for a panel, use `fit` to control how the source image scales:

- **`contain`** (default): Scale to fit within the cell, preserving aspect ratio. May leave empty space (letterbox/pillarbox).
- **`cover`**: Scale to cover the entire cell, preserving aspect ratio. May crop overflow.

```yaml
panels:
  - id: A
    file: "photo.png"
    x: 0
    y: 0
    width: 80
    height: 60
    fit: cover  # Fill the cell, cropping if needed
```

If `height` is omitted, the panel automatically sizes to preserve the source aspect ratio.

### Page Margins

Add consistent margins around your content with the `margin` property on the page:

```yaml
page:
  width: 180
  height: 120
  margin: 10  # 10mm margin on all sides

panels:
  - id: A
    file: "plots/scatter.pdf"
    width: 70
    x: 0   # Positioned relative to margin, not page edge
    y: 0
```

Panel coordinates are relative to the margin edge. A panel at `x: 0, y: 0` with a 10mm margin will appear at position (10mm, 10mm) on the page.

### Grid Layout

Instead of manually specifying x/y coordinates for each panel, use the grid layout system to define structure with rows and columns:

```yaml
page:
  width: 180
  height: 100
  units: mm

layout:
  type: row
  ratios: [3, 2]  # Left panel is 60%, right is 40%
  gap: 5
  children:
    - id: A
      file: "plot1.pdf"
    - id: B
      file: "plot2.pdf"
```

#### Container Types

- **`row`**: Arranges children horizontally (left to right)
- **`col`**: Arranges children vertically (top to bottom)

#### Container Properties

| Property | Default | Description |
|----------|---------|-------------|
| `ratios` | Equal | Relative sizing of children (e.g., `[3, 2]` = 60%/40%) |
| `gap` | 0 | Space between children (in page units) |
| `margin` | 0 | Inner padding of the container |

#### Nested Layouts

Containers can be nested for complex layouts:

```yaml
layout:
  type: col
  ratios: [1, 2]  # Top row 1/3 height, bottom row 2/3
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

This creates:
- Panel A spanning the full width in the top third
- Panels B and C side-by-side in the bottom two-thirds

### Editor Autocomplete (JSON Schema)

For autocomplete and validation in your editor, reference the JSON schema in your layout file:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/yy/figquilt/main/schema/layout.schema.json
page:
  width: 180
  height: 120

panels:
  - id: A
    file: "plots/scatter.pdf"
    # ... your editor will now provide autocomplete for all fields
```

This works with [YAML Language Server](https://github.com/redhat-developer/yaml-language-server) in VS Code (via the YAML extension) and other editors.