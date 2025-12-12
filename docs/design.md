# figquilt – Design Document (v0)

## 0. One-line summary

figquilt is a small, language-agnostic CLI tool that composes multiple figures (PDF/SVG/PNG) into a single publication-ready figure, based on a simple layout file (YAML/JSON). The key function is creating a PDF by composing multiple PDFs and adding subfigure labels and minimal annotations. 

## 1. Goals

### Primary goal
	•	Take multiple figure panels (from R, Python, or Illustrator / Inkscape / external sources) and compose them into a single figure with:
	•	Exact physical dimensions (mm / pt),
	•	Reproducible, scriptable, and thus automatable layout,
	•	Optional panel labels (A, B, C, …),
    •	Optional annotations (arrows, lines, dividers, bounding boxes, etc.). 

### Secondary goals
	•	Work as a CLI that any language can call (Python, R, shell).
	•	Be easy to version-control (layout spec is a text file).
	•	Be minimal: small dependency footprint, simple mental model.

### Non-goals (for v0)
	•	No GUI.
	•	No interactive resizing / dragging.
	•	No automatic figure generation (we assume input panels already exist).
	•	No complex editing of panel contents (no re-coloring, no font changes inside panels).

## 2. User stories (v0)

In all cases, the command is the same:
	•	Command: `figquilt layout.yml fig.pdf` (all specs are in the layout file)

### 1.	Basic composition
	•	“I have 4 PDFs from R/ggplot and Python. I want to place them on a 180 mm × 230 mm page as a 2×2 grid, label them A, B, C, D, and export a single PDF.”
	
### 2.	Mixing vector and raster
	•	“I have a hand-drawn PNG sketch plus two PDF plots and one SVG icon. I want them on one page.”
	
### 3.	Panel labels
	•	“I want A, B, C, D labels in the top-left of each panel with consistent font and offset.”

### 4.	Reproducible workflow using snakemake. 
	•	“I want to call figquilt from a snakemake rule to build the final figure. No manual Illustrator.”


## 3. High-level design

### 3.1 Core concept: layout file
	•	Layout file in YAML (JSON allowed later) that describes:
	•	Page size and units (unit should be set once for all dimensions),
	•	Output DPI for rasterization (if needed),
	•	Panels with positions and sizes,
	•	Optional panel labels.

### Examples (YAML):

An example with grid layout:

```yaml
page:
  units: mm
  width: 180
  height: 60
  dpi: 300
  background: white

layout:
  type: grid
  rows: 1
  cols: 3
  margin: 5        # outer margin on all sides (mm)
  gutter: 3        # space between cells (mm)

label:
  enabled: true
  auto_sequence: true
  font_family: Helvetica
  font_size_pt: 8
  style:
    bold: true
    uppercase: true
  offset:
    x: 2
    y: -2

panels:
  - id: A
    file: "panel_A.pdf"
  - id: B
    file: "panel_B.pdf"
  - id: C
    file: "panel_C.pdf"
```

An example with explicit coordinates:

```yaml
page:
  units: mm
  width: 180        # total figure width
  height: 90       # total figure height
  dpi: 300             # resolution for raster outputs (if any)
  background: white    # optional
  label:
    enabled: true
    auto_sequence: true        # if true, auto-generate labels A, B, C...
    font_family: Helvetica
    font_size_pt: 8
    style:
        bold: true
        uppercase: true
    offset:
      x: 2
      y: -2

panels:
  - id: A
    file: "panel_A.pdf"
    x: 0
    y: 0
    width: 80
    height: 70      # optional; if omitted, preserve aspect ratio from width
    label: 
        text: A         # optional; if omitted, use default
        font_family: Helvetica  # optional; if omitted, use default
        style:
            bold: true
            uppercase: true
        font_size_pt: 8  # optional; if omitted, use default
        offset:
          x: 1
          y: -1
  - id: B
    file: "panel_B.pdf"
    x: 95
    y: 0
    width: 80

```

Coordinate system:
	•	Origin (0,0) at top-left of the page. 
	•	x: distance from left edge.
	•	y: distance from top edge.


## 3.2 CLI interface

Binary name: figquilt.

Basic usage:

```sh
figquilt layout.yml output.pdf
```

Options (v0):

```sh
figquilt [OPTIONS] <layout> <output>

Options:
  --format {pdf,svg,png}   # override output format inferred from extension
  --check                  # validate layout, report issues, no output
  --verbose                # extra logging
  --version
  --help
```

Behavior:
	•	Read layout file.
	•	Validate schema and check that input files exist.
	•	Compose and write output.
	•	Exit code:
	•	0 on success,
	•	non-zero on error (validation failure, missing files, etc.).

⸻

## 4. Data model

### 4.1 Page

Internal representation (Python-style pseudocode):

```python
class Page:
    width: float
    height: float
    dpi: int
    background: Color  # simple tuple (r, g, b, a)
```

### 4.2 Panel

```python
class Panel:
    id: str
    file: Path
    x: float
    y: float
    width: float
    height: Optional[float]  # if None, compute from aspect ratio
    label: Optional[str]
    label_style: Optional[LabelStyle]
```

	•	height optional: if missing, compute from input file aspect ratio using width.
	•	Input aspect ratio for vector files requires reading page box from PDF/SVG.

### 4.3 Label style

```python
class LabelStyle:
    enabled: bool
    auto_sequence: bool
    font_family: str
    font_size_pt: float
    offset_x_mm: float
    offset_y_mm: float
    bold: bool
```

Label placement:
	•	For each panel:
	•	Determine top-left corner in page coordinates.
	•	Apply offset (e.g., small shift inward).
	•	Draw text string (panel.label or auto-seq) at that coordinate.

⸻

## 5. Supported formats (v0)

### 5.1 Input formats (minimum)
	•	PDF (single-page)
	•	SVG
	•	PNG

Implementation idea (Python):
	•	Use a unified “drawable” abstraction:
	•	For PDF: embed page from input into the output PDF at scaled coordinates.
	•	For SVG: parse and place group under a <g> transform.
	•	For PNG: raster image drawn at specified size and position.

### 5.2 Output formats (minimum)
	•	PDF (primary target for journals).
	•	SVG (for further editing in Illustrator/Inkscape).

PNG output is optional but nice to have (export final preview).

⸻

## 6. Architecture (Python v0)

Module structure (suggested):

```sh
figquilt/
  __init__.py
  cli.py           # argument parsing, entry point
  layout.py        # schema, parsing, validation
  units.py         # helpers for mm/pt/px conversions
  compose_pdf.py   # PDF backend
  compose_svg.py   # SVG backend
  images.py        # detection of format, aspect ratio helpers
  errors.py        # custom exceptions
```

### 6.1 Flow
	1.	CLI parse
	•	Parse args, load layout YAML.
	2.	Layout parse + validate
	•	Use pydantic or similar for schema validation.
	•	Check for:
	•	Missing required keys,
	•	Overlapping panels only if a “no overlap” option is later added (for v0, allow overlap).
	3.	Prepare page + panels
	•	Convert mm → points (1 pt = 1/72 inch; 1 inch = 25.4 mm).
	•	Build internal Page and Panel objects.
	4.	Determine output backend
	•	Based on output extension or --format.
	•	Call compose_pdf or compose_svg.
	5.	Backend
	•	Create an empty canvas of given size.
	•	For each panel:
	•	Load input file.
	•	Compute scaling factors.
	•	Place at correct coordinates.
	•	Draw labels.
	•	Save file.

⸻

## 7. Conventions and assumptions
	•	Units in layout are mm everywhere (except font size in pt).
	•	No automatic panel alignment in v0 (user sets x_mm / y_mm). Alignment helpers can be added later as a separate feature or script.
	•	figquilt does not change the internal font sizes and properties of the panel contents; it only scales the panel as a whole.
	•	All coordinates refer to page space, not to any panel’s internal axes.

⸻

## 8. Extension ideas (for later versions)

These are out-of-scope for v0, but useful to keep in mind when designing the data model.

### 8.1 Grid-based layout helpers
	•	Allow a “grid” spec (rows, columns, gutters), auto-compute positions:

```yaml
grid:
  rows: 2
  cols: 2
  margin: 10
  gutter: 4
panels:
  - id: A
    file: "panel_A.pdf"
    grid_position: [1, 1]
  - id: B
    file: "panel_B.pdf"
    grid_position: [1, 2]
```

### 8.2 Shared legend space
	•	Reserve a panel slot for a legend and place it without scaling others.

### 8.3 Auto-scaling to fit page
	•	Given a desired layout, compute uniform scale so everything fits.

### 8.4 Inkscape / Illustrator anchors
	•	Option to export guides or layers to help fine-tuning in vector editors.
	5.	Rust core
	•	Reimplement core composition engine in Rust later, keeping the same CLI and layout spec, with Python as a thin wrapper if needed.

### 8.6 Auto-fill Layout
	•	Input: A list of figure files. Optionally, a rough figure dimensions (width and approximate aspect ratio)
	•	Output: Automatically computed layout that tiles them efficiently based on their aspect ratios.

⸻

## 9. Development plan (for AI coding assistants)





