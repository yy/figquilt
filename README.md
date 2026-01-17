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