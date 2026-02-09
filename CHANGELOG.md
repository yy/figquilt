# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Highlights
- Added `page.auto_scale` for explicit `panels` layouts to auto-fit oversized/off-page compositions into the page content area.

### Behavior
- Auto-scale now resolves missing explicit panel heights from source aspect ratios before fitting.
- Auto-scale uses one global transform (translate-to-origin + uniform scale), preserving relative panel geometry.
- Auto-scale respects `page.margin` and fits to the content area (`page - 2 * margin`).

### Refactoring and Quality
- Simplified grid row/column child-resolution logic to a single axis-driven path.
- Added regression tests for explicit-panel auto-scale behavior, including margin-aware fitting and negative-coordinate normalization.
- Regenerated JSON schema to include the new `page.auto_scale` field.

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
