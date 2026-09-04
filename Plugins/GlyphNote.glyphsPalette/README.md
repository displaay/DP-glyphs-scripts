# Glyph Note

Glyph Note is a native Glyphs 4 Palette plug-in for writing notes on the
current glyph, with an option to keep one shared note or a different note
per master.

It is an independent implementation inspired by
[mekkablue/NotePalettes](https://github.com/mekkablue/NotePalettes). It does
not reuse that plug-in’s source.

## Requirements

- Glyphs 4.0.1 (4003) or later
- macOS 12 or later
- The Python module selected in **Glyphs → Settings → Addons** (the
  Glyphs-managed Python is recommended)

## Install

For development, symlink the bundle into the Glyphs 4 plug-in folder:

```sh
ln -s /absolute/path/to/DP-glyphs-scripts/Plugins/GlyphNote.glyphsPalette \
  "$HOME/Library/Application Support/Glyphs 4/Plugins/GlyphNote.glyphsPalette"
```

For a normal installation, drag `GlyphNote.glyphsPalette` onto the Glyphs 4
app icon (in Finder or the Dock) and let Glyphs install it. Relaunch Glyphs
after installing or updating the plug-in.

Do not manually copy a downloaded plug-in into the Glyphs plug-in folder;
letting Glyphs install it preserves macOS security metadata.

If mekkablue’s **Glyph Note** palette is also installed, disable or remove it
to avoid two note palettes in the sidebar.

## Use

1. Open a font and show the right Palette (**Window → Palette**).
2. Expand **Glyph Note**.
3. Select one or more glyphs in Font View or Edit View.
4. Type in the note field. **⌘B**, **⌘I**, and **⌘⇧X** apply bold, italic,
   and strikethrough in the panel. Existing `*bold*`, `_italic_`, and
   `~~strikethrough~~` notes are imported as styled text; the markers are not
   shown and are not written back after you save.
5. Check **Lock for all masters** to keep the same note on every master.
   Uncheck it to give the current master its own note.

The master label shows which master the unlocked note belongs to. Switching
masters (for example with Cmd-1 / Cmd-2) updates the editor to that master’s
note when the lock is off.

The Palette gear menu can lock or unlock the selection, clear the active
master note, clear every stored note on the selection, and toggle Font View
badges.

## Note icon in the glyph list

Yes. Glyphs 4 already draws a native note icon on a Font View cell when
`glyph.note` is not empty. Glyph Note keeps that property in sync:

- Locked: `glyph.note` is the shared text, so the native icon appears whenever
  the glyph has a note.
- Unlocked: `glyph.note` is set to the active master’s note, or to another
  master’s note if the active one is empty, so the native icon still marks
  glyphs that have any note without rewriting the file on every master switch.

List View has a built-in **Notes** column (right-click the table header to
show it). That column reads the same `glyph.note` value.

An optional custom badge, drawn through the Glyphs 3.3+ `DrawFontView` API,
can also appear in the bottom-left of a cell when the **current master layer**
has a note. Toggle it from the Palette gear menu (**Show Badges in Font View**).
Font View does not always refresh immediately after a note change; scrolling
or reselecting cells will redraw the badges.

## Storage

- Native `glyph.note` for the shared / list-view note (plain text, no markup).
- `glyph.userData["com.displaay.GlyphNote.styles"]` for bold/italic/strike runs.
- `glyph.userData["com.displaay.GlyphNote.locked"]` for the lock flag.
- `glyph.userData["com.displaay.GlyphNote.masterNotes"]` for per-master text.
- `glyph.userData["com.displaay.GlyphNote.masterStyles"]` for per-master style runs.
- `layer.userData["com.displaay.GlyphNote.note"]` as a per-layer mirror.

Existing `glyph.note` values are treated as locked notes and are not discarded.

The Font View badge preference is stored in
`com.displaay.GlyphNote.showBadges`.

## Architecture

```text
Contents/
  Info.plist
  MacOS/plugin                 Standard Glyphs Python plug-in loader
  Resources/
    plugin.py                  Glyphs/AppKit integration and callbacks
    glyphnote/core.py          Pure lock, storage, and selection logic
    glyphnote/markup.py        Style runs and import of *bold* / _italic_ / ~~strike~~
    glyphnote/ui.py            Native Palette checkbox, label, and editor
```

The plug-in uses the public `GlyphsPalette.sortID` contract with a value of 6,
placing it after Script Board (5) and immediately before Dimensions (10).

## Troubleshooting

- If the palette does not appear, confirm that a Glyphs Python version is
  selected and relaunch Glyphs.
- Empty selection shows “No glyph selected.” Differing notes on a multi-
  selection show “Multiple values.”
- List View and Glyphs’ native note icon show the plain note text. Bold,
  italic, and strikethrough are Glyph Note panel styles and are not drawn
  by Glyphs’ built-in Notes column.
- Custom Font View badges only draw in Grid View cells; the native note icon
  and List View Notes column use `glyph.note`.

## License

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
