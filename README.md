# figquilt

**Figure quilter**: A CLI tool to compositing multiple figures (PDF, SVG, PNG) into a publication-ready figure layout.

`figquilt` takes a simple layout file (YAML) describing panels and their positions, composed of various inputs (plots from R/Python, diagrams, photos), and stitches them into a single output file (PDF, SVG) with precise dimension control and automatic labeling.

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