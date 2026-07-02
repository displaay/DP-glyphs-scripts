# VF Preview

Glyphs 3 reporter plugin for live variable-font interpolation preview.

Inspired by [Variable Font Preview 3](https://markfromberg.com/projects/variable-font-preview-3), implemented as an open Python plugin using the Glyphs SDK.

## Install

1. Copy or symlink `VFPreview.glyphsReporter` to:
   `~/Library/Application Support/Glyphs 3/Plugins/`
   (Glyphs 2 uses `~/Library/Application Support/Glyphs/Plugins/` instead.)
2. Double-click the bundle to register it (or restart Glyphs).
3. Enable **View → VF Preview** (shortcut: Control-Option-Command-V).

Requires Glyphs 3.2+ for `internalAxesValues` / `externalAxesValues`.

## Usage

When the reporter is active, a **VF Preview** panel opens and docks to the top of the Glyphs window:

1. **Preview bar** — shows the current Edit-tab string at interpolated coordinates.
2. **Axis sliders** — compact rows below (label, slider, value) for each axis.

Moving a slider updates the preview bar and (when **Draw in Edit View** is on) the Edit view overlay.

You can drag the panel if needed; it repositions when you switch tabs or resize the window.

Use right-click in the Edit view for master/instance jumps and display options.

- **Make Instance** creates a new export instance from the current slider setup.
- Right-click in the Edit view for VF Preview context menu actions.

### Options

| Option | Description |
|--------|-------------|
| Draw in Edit View | Overlay preview in the Edit tab |
| Center Preview | Center interpolated outline in glyph bounds |
| Link to Master | Sliders follow the selected master |
| Involved Masters | Color-coded master overlays |
| Preview Nodes | Show nodes and tangents on preview |
| Hide Foreground | Hide active layer outlines |
| Measurements | H/V distance and angle for 2 selected nodes |

### Preview modes

- **Current Glyph** — active glyph only in Edit view overlay
- **Full Text** — all visible text in the Edit tab (overlay)
- **Current Line** — inactive glyphs in the Edit tab (same line)

The preview bar always shows the full Edit-tab string.

## Architecture

```
Contents/Resources/
  plugin.py              ReporterPlugin entry, opens dock panel on activate
  dock_panel.py          VFP-style floating panel (fixed layout, reliable sliders)
  preview_bar.py         TextPreviewBarView for tab-string preview
  controller.py          Axis state, GSInstance, interpolation proxy
  preview_view.py        Drawing helpers + standalone window
  charts.py              Master influence bar/radar charts
  measure.py             Two-node measurement overlay
  axis_utils.py          Axis value helpers
```

## Test checklist

- [ ] VF Preview panel opens at top of Glyphs window with visible sliders
- [ ] Preview bar shows tab text; sliders update preview and Edit view overlay
- [ ] Bracket trick glyph swaps at threshold
- [ ] Virtual master font previews correctly
- [ ] Instance preview + Make Instance
- [ ] Two-node measurement updates while sliding
- [ ] Spacebar hides overlay; preferences persist across sessions

## License

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
