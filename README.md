# DP Glyphs Scripts

A collection of utility scripts for [Glyphs](https://glyphsapp.com/) focused on spacing, kerning, component cleanup, layer utilities, and font-production helpers.

These scripts are intended to run inside Glyphs on macOS, not as standalone command-line tools.

## Requirements

- macOS
- Glyphs 3
- Glyphs Python environment
- `vanilla` for scripts that open custom UI windows

## Installation

1. Clone or download this repository.
2. In Glyphs, open the Scripts folder via `Script > Open Scripts Folder`.
3. Copy the script files you want into your Glyphs Scripts folder.
4. Restart Glyphs (or reload scripts) so they appear in the Scripts menu.

Most files include `# MenuTitle` metadata, so they should show up in the Glyphs Scripts menu with a readable label.

## Script Index

### Spacing

- `Spacing/master_spacing_and_kerning.py`  
  Batch-adjust spacing per selected masters, with optional kerning updates and unit conversions (`Percent`, `Fixed value`, `InDesign`, `Figma`, `Web`).

- `Spacing/transfer_ufo_metrics_and_kerning.py`  
  Import spacing, kerning, and kerning groups from UFOs into a Glyphs source (master by master), with merge/overwrite options and metrics normalization tools.

- `Spacing/double equals before SB.py`  
  Converts sidebearings to locked `==` metrics keys (or normalizes existing keys), with options for glyph/master scope, optional MONO-axis filtering, and a default safeguard that skips negative sidebearings in component glyphs.

- `Spacing/Show Auto-Aligned == Sidebearings.py`  
  Removes negative `==` left/right sidebearing metrics keys from auto-aligned glyphs in the current master, then opens a tab with the affected glyphs.

- `Spacing/Out of sync Metrics.py`  
  Finds pure composite glyphs whose auto-aligned component metrics are out of sync in the current master and opens a tab with affected glyphs.

- `Spacing/Tabular Figures Spacer.py`  
  Sets fixed tabular widths (e.g. `.tf`, `.tosf`, `.tnum`) with options for centering, metrics keys, and component alignment behavior.

- `Spacing/Sidebearing Manager.py`  
  Sidebearing utility with options to apply per selected glyphs/all glyphs, flatten formula-derived values, and disable auto-alignment.

- `Spacing/Optical Center in Width.py`  
  Centers glyph contents within the current advance width by balancing LSB/RSB, with optional small sampled-ink optical correction, MONO-master scope, and sidebearing guard options.

### Kerning

- `Kerning/Copy Kerning Exceptions to Double Accents.py`  
  Copies kerning exceptions from selected base accented glyphs to corresponding double-accent variants through a UI workflow.

### Components

- `Components/Reset all corner components.py`  
  Resets corner component hint scale values to 100% (`1.0, 1.0`) across the font.

### Layers

- `Layers/Fill Up Intermediate Layers.py`  
  Generates missing intermediate/special layers for coordinate combinations and reinterpolates them.

### Client Projects

- `Client Projects/Add wght 400 Intermediate Layers.py`  
  Adds wght=400 intermediate layers for selected glyphs, using each source layer's non-weight coordinates and copying outline paths from the heaviest matching weight layer.

### Background

- `Background/Clear Backgrounds in Selected Layers.py`  
  UI tool to clear background paths/components/anchors in selected glyphs, with selectable layer scope.

### Tools

- `Tools/Assign Private Use Unicodes.py`  
  Assigns consecutive Basic Private Use Area Unicode values to selected glyphs, with overwrite warnings for existing Unicode values.

- `Tools/Validator bypass.py`  
  Decomposes corner/cap components and rebuilds paths for selected layers; `Shift` applies to all layers in selected glyphs.

- `Tools/Duplicate selected node.py`  
  Duplicates the selected node and inserts the copy after it.

- `Tools/Swapper.py`  
  Two-way swap tool for glyph/layer data (including metrics and kerning), with UI controls.

- `Tools/Horziontals calculator.py`  
  UI calculator for horizontal stem targets from reference stem values and optical reduction settings.

- `Tools/Master Consistency Checker.py`  
  Glyphs 3 UI preflight for master-to-master inconsistencies: shape/path compatibility, components, anchors, metrics, bounds, suspicious shape-order shifts, and a visual HTML report with per-glyph master overlays, severity levels, navigation, differences, and likely fixes.

### Export

- `Export/Selective Variable Font Export.py`  
  Exports a variable font while dropping selected axes, keeping selected named instances, and remapping chosen instances to specific `wght` values.

## Usage Notes

- Back up your `.glyphs` file before running bulk operations.
- Open Glyphs Macro Window to review logs/errors from scripts.
- Test new workflows on a copy of your source first.

## Repository Notes

- This repo is a script collection, not a packaged Glyphs plugin.
- Script naming reflects working file names in Glyphs workflows and may include legacy typos for compatibility.
- There is currently no automated test suite in this repository.

## License

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

These scripts are proprietary utility software. No license is granted for copying, redistribution, modification, or reuse outside Displaay Type Foundry workflows unless permission is provided by Displaay Type Foundry.
