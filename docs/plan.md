# Development Plan & Milestones

This document outlines the roadmap and progress for the `figquilt` project.

## Milestone 1: Skeleton & Layout Parsing (✅ Completed)
- [x] Initialize Python package structure with `uv`
- [x] Create `Layout` and `Panel` pydantic models
- [x] Implement YAML parsing and validation logic
- [x] Create basic CLI entry point (`figquilt`)
- [x] Add tests for layout validation (valid/invalid cases)

## Milestone 2: PDF Composition Engine (✅ Completed)
- [x] Select PDF backend (`PyMuPDF`)
- [x] Implement mm to point conversion helpers
- [x] Implement single panel placement
- [x] Implement multi-panel composition
- [x] Add basic label drawing (text) logic
- [x] Integration test: composed PDF from two input PDFs

## Milestone 3: SVG and PNG Support (✅ Completed)
- [x] Implement SVG backend (using `lxml`)
- [x] Implement PNG backend (using `Pillow` and `PyMuPDF`)
- [x] Add integration tests for mixed media input (PDF + PNG + SVG)

## Milestone 4: Polish & Release (✅ Completed)
- [x] Refine CLI error messages
- [x] Add documentation (API docs + User guide)
- [x] Finalize CI/CD pipeline (tests, linting)
- [x] Publish initial version
- [x] Add watch mode (`--watch`) for automatic rebuilds

## Milestone 5: Grid Layout System (✅ Completed)
- [x] Implement `row` and `col` container types
- [x] Support nested layouts with arbitrary depth
- [x] Add `ratios` for proportional sizing of children
- [x] Implement `gap` and `margin` for spacing control
- [x] Add `fit` modes (`contain`, `cover`) for panels

## Milestone 6: Explicit Layout Auto-Fit (✅ Completed)
- [x] Add `page.auto_scale` for explicit `panels` mode
- [x] Fit overflow layouts to page content area (`page.margin` aware)
- [x] Resolve missing explicit panel heights from source aspect ratio before fitting
- [x] Add regression tests for scaling, translation, and margin behavior

## Future Milestones
- [ ] Shared legend space
- [ ] Inkscape / Illustrator anchor export
