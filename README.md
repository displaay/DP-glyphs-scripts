# DP Glyphs Scripts

A collection of utility scripts and Displaay glyphset assets for [Glyphs](https://glyphsapp.com/), focused on spacing, kerning, component cleanup, layer utilities, export helpers, and font-production tools.

The Python scripts run inside Glyphs on macOS; they are not standalone command-line tools.

## Displaay Glyphset

The [`Glyphset`](Glyphset/) folder contains a 579-glyph Glyphs project template and a custom Font View sidebar entry organized into Full Set, Numbers, Brackets, Symbols, and Accents groups.

| File | Purpose |
|---|---|
| [`Glyphset/DP GlyphSet FINAL.glyphs`](Glyphset/DP%20GlyphSet%20FINAL.glyphs) | Project template containing the complete Displaay glyph set and its predefined component structures. |
| [`Glyphset/Groups-Displaay.plist`](Glyphset/Groups-Displaay.plist) | Custom Glyphs Font View sidebar definition. |
| [`Glyphset/Icons/DisplaayTemplate.pdf`](Glyphset/Icons/DisplaayTemplate.pdf) | Scalable 16 pt sidebar icon referenced by the plist. |

See [`Glyphset/HOW TO INSTALL.txt`](Glyphset/HOW%20TO%20INSTALL.txt) for Glyphs 4 installation and usage instructions.

## Plugins

| Plugin | Description |
|---|---|
| [`Plugins/ScriptBoard.glyphsPalette`](Plugins/ScriptBoard.glyphsPalette/README.md) | Glyphs 4 right-Palette launcher for favorite installed scripts, with search, ordering, persistence, and conflict-checked shortcuts. |
| [`Plugins/GlyphNote.glyphsPalette`](Plugins/GlyphNote.glyphsPalette/README.md) | Glyphs 4 right-Palette editor for per-glyph notes, with a lock that shares one note across masters or a different note per master, plus Font View note badges. |
| [`Plugins/VFPreview.glyphsReporter`](Plugins/VFPreview.glyphsReporter/README.md) | Live variable-font interpolation preview with axis sliders, master involvement charts, standalone window, and measurement tools. Install by copying the bundle to `~/Library/Application Support/Glyphs/Plugins/`. |

## Requirements

- macOS
- Glyphs 3 for the existing scripts and VF Preview
- Glyphs 4.0.1 or later for Script Board and Glyph Note
- Glyphs 4 for the Displaay glyphset
- Glyphs Python environment

Some scripts use additional libraries:

| Dependency | Used by |
|---|---|
| `vanilla` | Most UI scripts (spacing tools, kerning UI, calculators, swapper, etc.) |
| `fontTools` | Required by `Export/Selective Variable Font Export.py`; optional for `Tools/Weight Axis Converter.py`, which falls back to a built-in mapper if unavailable. |

Some larger UI scripts build their interface directly with AppKit/objc rather than `vanilla`, notably `Spacing/master_spacing_and_kerning.py` and `Spacing/transfer_ufo_metrics_and_kerning.py`.

## Script Installation

1. Clone or download this repository.
2. In Glyphs, open the Scripts folder via **Script → Open Scripts Folder**.
3. Copy the script folders (or individual files) you want into your Glyphs Scripts folder, preserving the folder structure if you prefer.
4. Restart Glyphs (or reload scripts) so they appear in the Scripts menu.

Most files include `# MenuTitle` metadata, so they show up in the Glyphs Scripts menu with a readable label. Where the menu label differs from the filename, it is noted below.

## Script Index

**30 Python scripts** across 9 folders.

### Spacing

| File | Menu title | Description |
|---|---|---|
| `Spacing/master_spacing_and_kerning.py` | Master Spacing and Kerning Adjuster | Batch-adjust spacing per selected masters, with optional kerning updates and unit conversions (`Percent`, `Fixed value`, `InDesign`, `Figma`, `Web`). |
| `Spacing/transfer_ufo_metrics_and_kerning.py` | Transfer UFO Metrics and Kerning | Import spacing, kerning, and kerning groups from UFOs into a Glyphs source (master by master), with merge/overwrite options and metrics normalization tools. |
| `Spacing/double equals before SB.py` | Set == Sidebearings with Mono Check | Converts sidebearings to locked `==` metrics keys (or normalizes existing keys), with options for glyph/master scope, optional MONO-axis filtering, and a default safeguard that skips negative sidebearings in component glyphs. |
| `Spacing/Show Auto-Aligned == Sidebearings.py` | Remove Negative Auto-Aligned == Sidebearings | Removes negative `==` left/right sidebearing metrics keys from auto-aligned glyphs in the current master, then opens a tab with the affected glyphs. |
| `Spacing/Out of sync Metrics.py` | Find Out-of-Sync Auto-Aligned Glyphs | Finds pure composite glyphs whose auto-aligned component metrics are out of sync in the current master and opens a tab with affected glyphs. |
| `Spacing/Tabular Figures Spacer.py` | Tabular Figures Spacer | Sets fixed tabular widths (e.g. `.tf`, `.tosf`, `.tnum`) with options for centering, metrics keys, and component alignment behavior. |
| `Spacing/Sidebearing Manager.py` | Sidebearing manager Displaay | Manages LSB/RSB/width per selected or all glyphs, flattens formula-derived values, and disables auto-alignment. |
| `Spacing/Optical Center in Width.py` | Optical Center in Width | Centers glyph contents within the current advance width by balancing LSB/RSB, with optional small sampled-ink optical correction, MONO-master scope, and sidebearing guard options. |

### Kerning

| File | Menu title | Description |
|---|---|---|
| `Kerning/Copy Kerning Exceptions to Double Accents.py` | Copy Kerning Exceptions to Double Accents (with UI) | Copies kerning exceptions from selected base accented glyphs (e.g. Abreve, Acircumflex) to corresponding Vietnamese/Pinyin double-accent variants. |

### Components

| File | Menu title | Description |
|---|---|---|
| `Components/Reset all corner components.py` | Reset All Corner components | Resets corner component hint scale values to 100% (`1.0, 1.0`) across the font. |
| `Components/DP alignment manager.py` | DP alignment manager | Floating active-glyph matrix for component auto-alignment across masters, with click-to-toggle dots and batch controls for selected masters. |

### Layers

| File | Menu title | Description |
|---|---|---|
| `Layers/Master Overview.py` | Master Overview | Opens a new Edit tab with one row per selected glyph, showing that glyph's layers across all masters in font order. |
| `Layers/Fill Up Intermediate Layers.py` | Fill Up Intermediate Layers | Generates missing intermediate/special layers for coordinate combinations and reinterpolates them. |
| `Layers/Masters Side by Side.py` | Masters Side by Side | Opens a new Edit tab with selected glyphs arranged by master. Axes can be reordered by dragging; checked axes are used for sorting, unchecked axes are held at the selected layer's coordinate. |
| `Layers/Copy Selected Glyphs Between Masters.py` | Copy Selected Glyphs Between Masters | Batch-copies selected glyphs from one master to another, with toggles for strokes (paths, components, hints), metrics (LSB, RSB, width, metric keys), anchors, and master-specific kerning pairs for the selected glyphs and their groups. |

### Client Projects

| File | Menu title | Description |
|---|---|---|
| `Client Projects/Add wght 400 Intermediate Layers.py` | Add wght 400 Intermediate Layers | Adds wght=400 intermediate layers for selected glyphs, using each source layer's non-weight coordinates and copying outline paths from the heaviest matching weight layer. |

### Background

| File | Menu title | Description |
|---|---|---|
| `Background/Clear Backgrounds in Selected Layers.py` | Clear Backgrounds in Selected Layers... | UI tool to clear background paths, components, and anchors in selected glyphs, with selectable layer scope. |

### Tools

| File | Menu title | Description |
|---|---|---|
| `Tools/Assign Private Use Unicodes.py` | Assign Private Use Unicodes | Assigns consecutive Basic Private Use Area Unicode values to selected glyphs, with overwrite warnings for existing Unicode values. |
| `Tools/Validator bypass.py` | Decompose Corner and Cap Components | Decomposes corner/cap components and rebuilds paths for selected layers. Hold **Shift** to apply to all layers in selected glyphs. |
| `Tools/Duplicate selected node.py` | Duplicate selected node | Duplicates the selected node and inserts the copy after it (line/curve nodes only). |
| `Tools/DP Swapper.py` | DP Swapper | Two-way swap tool for glyph/layer data, including metrics and kerning, with UI controls and suffix-aware glyph matching. |
| `Tools/Horziontals calculator.py` | Calculate horizontals | UI calculator for horizontal stem targets from reference stem values (Dimensions palette) and optical reduction settings. |
| `Tools/Weight Axis Converter.py` | Weight Axis Converter | Converts axis values between Glyphs source coordinates (internal/design) and exported variable-font coordinates (external/user), including remapped instances (e.g. 550 → 500). Reads mapping points from masters, instances, and Axis Mappings custom parameters; supports any axis. |
| `Tools/Master Consistency Checker.py` | Master Consistency Checker | Glyphs 3 UI preflight for master-to-master inconsistencies: shape/path compatibility, components, anchors, metrics, bounds, suspicious shape-order shifts, and a visual HTML report with per-glyph master overlays, severity levels, navigation, differences, and likely fixes. |
| `Tools/CALT Contextual Cycling Generator.py` | CALT Contextual Cycling Generator | Builds synchronized OpenType classes and a `calt` feature for cycling through suffixed alternates. Supports consecutive cycling, consonant/vowel gap cycling, and multi-lookup offset chaining, with optional fallback to base glyphs when alternates are missing. |

### Export

| File | Menu title | Description |
|---|---|---|
| `Export/Selective Variable Font Export.py` | Selective Variable Font Export | Exports a variable font while dropping selected axes, keeping selected named instances, and remapping chosen instances to specific `wght` values. |

## Usage Notes

- Back up your `.glyphs` file before running bulk operations.
- Open the Glyphs Macro Window to review logs and errors from scripts.
- Test new workflows on a copy of your source first.
- Several scripts operate on the current selection, current master, or frontmost font — check each script's UI before applying to the full font.

## Repository Notes

- This repo contains a script collection, Glyphs plugins, and the Displaay glyphset assets; it is not distributed as a single packaged plugin.
- Script filenames reflect working names in Glyphs workflows and may include legacy typos for compatibility (e.g. `Horziontals calculator.py`, `Validator bypass.py`).
- Palette plug-ins include unit tests under `Tests/` for their Glyphs-independent core logic; plug-in smoke tests require the Glyphs macOS runtime.

## License

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

These scripts are proprietary utility software. No license is granted for copying, redistribution, modification, or reuse outside Displaay Type Foundry workflows unless permission is provided by Displaay Type Foundry.
