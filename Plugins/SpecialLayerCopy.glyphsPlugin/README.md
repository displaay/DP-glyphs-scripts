# Copy Special Layers

**⌘C / ⌘V directly in the Glyphs 4 Layers palette. No separate window.**

## Install

Requires macOS 12 or later, Glyphs 4, and a configured Glyphs Python environment.
No additional Python modules are required.

The source bundle is `Plugins/SpecialLayerCopy.glyphsPlugin` in
`DP-glyphs-scripts`. Install directly from that directory or use the packaged ZIP.

1. If using `SpecialLayerCopy-0.2.0.zip`, unzip it first.
   When updating, remove the previous installed Copy Special Layers plug-in
   through Plugin Manager. Keep only one installed copy, including any bundle
   named `SpecialLayerCopy 2.glyphsPlugin`.
2. Drag `SpecialLayerCopy.glyphsPlugin` onto the Glyphs 4 app icon in Finder
   or the Dock. Replace the previous version if already installed.
3. Relaunch Glyphs 4.

The bundle is also available in this repository's `Plugins` directory.
Its universal loader supports Apple Silicon and Intel Macs.

To rebuild the plug-in archive together with the other Python plug-ins, run
`make -C Plugins dist`. Generated archives go to the ignored `dist` directory.

## Use

1. In the Layers palette, click the special layer you want to copy.
   Shift-click or Command-click to select multiple special layers.
2. Press **⌘C**.
3. In the same font and glyph, click the destination **master row** in the
   Layers palette. You can select rows under several masters to paste to
   multiple masters at once.
4. Press **⌘V**. The copied special layers appear under those masters.

Copying captures a snapshot. Editing the source layer or changing masters
when you paste does not alter the clipboard contents. For multiple glyphs,
layers paste only to matching glyph names represented by the selected rows;
hidden source glyphs are not modified.

The shortcuts apply when the Layers list has keyboard focus. Click a layer
row before copying or pasting. Drawing-canvas and text-field shortcuts retain
their normal behavior, including editing layer names. Copying only master or
backup rows also retains Glyphs' normal behavior. Changing the system clipboard
prevents the plug-in from pasting a stale layer snapshot.

Layer clipboard contents are available within the same open font and Glyphs
session. Cross-font layer copying is not supported by this version.

## Copied data and coordinates

Supports intermediate/brace layers, alternate/bracket layers, Glyphs 4 smart
layers, and special/color layers. Master and ordinary backup layers are not
copied. New layers receive independent IDs and retain their layer settings,
paths, components, shape groups/order, foreground hint-node links, anchors,
widths, and metric keys.

An explicit intermediate coordinate equal to the source master's coordinate
follows the target master. Independent coordinates stay the same. For example,
copying `{wght: 500, ital: 0}` from a master at `{wght: 100, ital: 0}` to one
at `{wght: 100, ital: 1}` produces `{wght: 500, ital: 1}`. Sparse coordinates
remain sparse. Glyph-local smart coordinates and alternate-layer rules are
preserved. Drawings are copied without reinterpolation.

Existing target layers with matching functional settings are **skipped**.
Repeated paste does not create duplicates. To replace an existing layer,
delete that target special layer first, then paste. Master and unrelated
target layers remain in place. Duplicate copied settings are rejected before
the batch changes the font.

Pastes use Glyphs undo groups and restore touched layers if a write fails.
If nothing can be pasted, the plug-in beeps. Error details go to the Macro
Window log without opening a window or dialog.

## Development checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  Tests.test_special_layer_copy Tests.test_special_layer_copy_shortcuts
```

`Tests/test_special_layer_copy_native.py` additionally exercises real Glyphs 4
GlyphsCore objects through PyObjC without touching open documents. Run with
Glyphs-managed Python on a Mac with Glyphs 4 installed:

```sh
PYTHONDONTWRITEBYTECODE=1 \
  "$HOME/Library/Application Support/Glyphs 4/Repositories/Python/Python.framework/Versions/3.14/bin/python3" \
  -m unittest Tests.test_special_layer_copy Tests.test_special_layer_copy_shortcuts \
  Tests.test_special_layer_copy_native
```

Integration uses Glyphs 4's native `GSLayerOutlineView` and the Layers palette's
`layersForRow:` method. The outline refuses keyboard focus by default; the
plug-in enables focus on that control only and listens locally for Copy/Paste.
These native control interfaces were checked against the installed Glyphs 4
build; a future app update may require adjusting the integration. Keyboard
interaction still needs a final check inside Glyphs after installation.

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
