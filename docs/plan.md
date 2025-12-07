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

## Future Milestones
- [ ] Grid-based layout helpers (auto-compute positions)
- [ ] Shared legend space
- [ ] Auto-scaling to fit page
- [ ] Inkscape / Illustrator anchor export
