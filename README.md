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
  Converts sidebearings to locked `==` metrics keys (or normalizes existing keys), with options for glyph/master scope and optional MONO-axis filtering.

- `Spacing/Tabular Figures Spacer.py`  
  Sets fixed tabular widths (e.g. `.tf`, `.tosf`, `.tnum`) with options for centering, metrics keys, and component alignment behavior.

- `Spacing/Sidebearing Manager.py`  
  Sidebearing utility with options to apply per selected glyphs/all glyphs, flatten formula-derived values, and disable auto-alignment.

### Kerning

- `Kerning/Copy Kerning Exceptions to Double Accents.py`  
  Copies kerning exceptions from selected base accented glyphs to corresponding double-accent variants through a UI workflow.

### Components

- `Components/Reset all corner components.py`  
  Resets corner component hint scale values to 100% (`1.0, 1.0`) across the font.

### Layers

- `Layers/Fill Up Intermediate Layers.py`  
  Generates missing intermediate/special layers for coordinate combinations and reinterpolates them.

### Background

- `Background/Clear Backgrounds in Selected Layers.py`  
  UI tool to clear background paths/components/anchors in selected glyphs, with selectable layer scope.

### Tools

- `Tools/Validator bypass.py`  
  Decomposes corner/cap components and rebuilds paths for selected layers; `Shift` applies to all layers in selected glyphs.

- `Tools/Duplicate selected node.py`  
  Duplicates the selected node and inserts the copy after it.

- `Tools/Swapper.py`  
  Two-way swap tool for glyph/layer data (including metrics and kerning), with UI controls.

- `Tools/Horziontals calculator.py`  
  UI calculator for horizontal stem targets from reference stem values and optical reduction settings.

### Export

- `Export/Selective Variable Font Export.py`  
  Currently stored as a macOS Alias file in this repository, not a readable Python script.

## Usage Notes

- Back up your `.glyphs` file before running bulk operations.
- Open Glyphs Macro Window to review logs/errors from scripts.
- Test new workflows on a copy of your source first.

## Repository Notes

- This repo is a script collection, not a packaged Glyphs plugin.
- Script naming reflects working file names in Glyphs workflows and may include legacy typos for compatibility.
- There is currently no automated test suite in this repository.
