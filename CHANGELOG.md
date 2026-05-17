# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [0.3.0] - 2026-05-17

### Highlights
- Added `figquilt --check` support without requiring an output path, making layout validation easier in scripts and CI.
- Added checked-in example assets and example-layout tests to guard common usage patterns.
- Improved layout parsing, asset validation, and error reporting for invalid or missing inputs.

### Behavior and Fixes
- Tightened layout numeric validation so booleans and quoted numeric strings are rejected early.
- Prevented outputs from overwriting input figure assets.
- Fixed PNG format-override output and improved zero-size/unreadable source handling.
- Improved `cover`/`contain` geometry handling across PDF and SVG rendering.
- Improved watch mode so missing assets introduced after layout edits are tracked correctly.
- Rejected non-opaque RGBA colors in `parse_color`.

### Refactoring and Quality
- Refactored shared composer geometry, panel source handling, label draw-info resolution, and PDF vector embedding.
- Added shared CLI/watch target data structures and `python -m figquilt` entry point.
- Expanded tests for CLI behavior, parser asset validation, fit modes, image helpers, package version fallback, examples, and PDF rendering.
- Test suite: 170 passing tests.

## [0.2.0] - 2026-02-09

### Highlights
- Added `page.auto_scale` for explicit `panels` layouts to auto-fit oversized/off-page compositions into the page content area.
- Added ordered `layout.type: auto` mode to compute panel layouts from a sequence while preserving reading order.

### Behavior
- Auto-scale now resolves missing explicit panel heights from source aspect ratios before fitting.
- Auto-scale uses one global transform (translate-to-origin + uniform scale), preserving relative panel geometry.
- Auto-scale respects `page.margin` and fits to the content area (`page - 2 * margin`).
- Auto layout supports bias presets (`one-column`, `two-column`, `best`), a panel-size uniformity preference, and panel prominence hints (`role: main` / `weight`).
- Auto layout preserves panel aspect ratios and only computes panel cell geometry; rendering still follows each panel's `fit` / `align`.

### Refactoring and Quality
- Simplified grid row/column child-resolution logic to a single axis-driven path.
- Added regression tests for explicit-panel auto-scale behavior, including margin-aware fitting and negative-coordinate normalization.
- Refactored auto-layout scoring internals with prefix-sum geometry for simpler and faster row optimization.
- Regenerated JSON schema to include the new `page.auto_scale` field.
- Test suite: 82 passing tests.
- Ruff lint: all checks passing.

## [0.1.10] - 2026-02-09

### Highlights
- Fixed `fit: cover` behavior in PDF output so content is correctly clipped to panel bounds.
- Added safer layout validation to prevent runtime crashes from invalid geometry.
- Improved auto-label sequencing past `Z` (`AA`, `AB`, ...).
- Synced SVG PDF rasterization with `page.dpi` instead of a hardcoded value.

### Fixes
- PDF backend now applies alignment-aware cropping for `cover` mode.
- Grid resolution now fails early with clear errors for invalid margins, gaps, ratios, and non-positive content areas.
- Enforced unique panel IDs to avoid ambiguous output behavior.
- Avoided duplicate SVG clip-path IDs for panels.
- Aligned package runtime version behavior with package metadata.

### Validation and Schema
- Added stronger model constraints (positive dimensions and ratios, nonnegative margins and gaps, valid DPI, margin bounds).
- Regenerated JSON schema to match updated validation rules.

### Tests and Quality
- Added regression tests for PDF cover clipping, invalid ratio and margin edge cases, duplicate panel IDs, label sequencing after `Z`, and SVG rasterization honoring configured DPI.
- Test suite: 70 passing tests.
- Ruff lint: all checks passing.
