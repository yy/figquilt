# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

figquilt is a CLI tool that composites multiple figures (PDF, SVG, PNG) into publication-ready figure layouts. It takes a YAML layout file specifying panel positions and produces a single output file (PDF, SVG, or PNG) with precise dimension control and automatic subfigure labeling.

## Commands

### Install and Setup
```bash
uv sync                    # Install dependencies and package in editable mode
```

### Running Tests
```bash
uv run pytest              # Run all tests
uv run pytest tests/test_layout.py  # Run a single test file
uv run pytest -k "test_parse"       # Run tests matching pattern
```

### Using the CLI
```bash
figquilt layout.yaml output.pdf     # Basic usage
figquilt --check layout.yaml        # Validate layout without output
figquilt --format svg layout.yaml output.svg  # Override output format
figquilt --watch layout.yaml output.pdf       # Watch mode: rebuild on changes
```

## Architecture

### Source Structure (`src/figquilt/`)
- **cli.py**: Entry point, argument parsing, dispatches to appropriate composer
- **parser.py**: YAML parsing, validates layout files, resolves file paths
- **layout.py**: Pydantic models (`Layout`, `Page`, `Panel`, `LabelStyle`)
- **compose_pdf.py**: PDF backend using PyMuPDF (fitz) - handles PDF/SVG/PNG embedding
- **compose_svg.py**: SVG backend for vector output
- **images.py**: Format detection, aspect ratio helpers
- **units.py**: Unit conversion helpers (mm to points)
- **errors.py**: Custom exceptions (`FigQuiltError`, `LayoutError`, `AssetMissingError`)

### Data Flow
1. CLI parses args → `parser.parse_layout()` loads YAML and validates with Pydantic
2. Layout object contains `Page` (dimensions, units, background, default label style) and list of `Panel` objects
3. Based on output format, either `PDFComposer` or `SVGComposer` is instantiated
4. Composer iterates panels: loads source file, computes dimensions (respecting aspect ratio), places at coordinates, draws labels

### Key Design Decisions
- All layout coordinates use mm (except font size in pt)
- Origin (0,0) is at top-left of page
- Panel height is optional; if omitted, computed from source aspect ratio to preserve proportions
- Labels auto-sequence A, B, C... by default unless overridden per-panel
- PyMuPDF (fitz) handles all input formats for PDF output, converting SVG to PDF internally for vector preservation

## Layout File Specification

See `docs/spec.md` for the full schema. Key elements:
- `page`: width, height, units (mm/inches/pt), dpi, background color
- `panels`: list with id, file, x, y, width, optional height, optional label overrides
- Future: grid-based layout with `type: row/col/grid`, ratios, gaps (see spec.md)
