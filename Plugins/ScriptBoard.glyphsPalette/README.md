# Script Board

Script Board is a native Glyphs 4 Palette plug-in for keeping frequently used
installed scripts within one click. It reads the same script commands Glyphs
already exposes in the **Script** menu, so launching a board item uses Glyphs’
own scripting runtime and the active Glyphs document.

## Requirements

- Glyphs 4.0.1 (4003) or later
- macOS 12 or later
- The Python module selected in **Glyphs → Settings → Addons** (the
  Glyphs-managed Python is recommended)

The initial build was developed against Glyphs 4.0.1 (4003), Python 3.14.6,
and PyObjC 12.2.1.

## Install

For development, symlink the bundle into the Glyphs 4 plug-in folder:

```sh
ln -s /absolute/path/to/DP-glyphs-scripts/Plugins/ScriptBoard.glyphsPalette \
  "$HOME/Library/Application Support/Glyphs 4/Plugins/ScriptBoard.glyphsPalette"
```

For a normal installation, drag `ScriptBoard.glyphsPalette` onto the Glyphs 4
app icon (in Finder or the Dock) and let Glyphs install it. Relaunch Glyphs
after installing or updating the plug-in.

Do not manually copy a downloaded plug-in into the Glyphs plug-in folder;
letting Glyphs install it preserves macOS security metadata.

## Use

1. Open a font and show the right Palette.
2. Expand **Script Board**, directly above **Dimensions**.
3. Click **+** and search the scripts currently installed in Glyphs.
4. Select one or more scripts and click **Add Selected**.
5. Click a board row to run it.

Drag rows to reorder them. Right-click a row to run, reveal, inspect, remove,
or assign a shortcut. Drag the divider below Script Board to resize it
vertically; Glyphs remembers the chosen height across launches. The Palette
gear menu contains refresh and reset actions. Script names keep the standard
system-font width when they fit and narrow progressively only when the current
Palette width requires it. Widths recalculate as the Palette changes; names
that still exceed the readable compression limit truncate at the trailing edge.

## Shortcuts

- Printable keys require Command, Option, or Control.
- Function keys can be assigned without a modifier.
- Special keys such as arrows require a modifier so normal Glyphs editing is
  not intercepted.
- Duplicate board shortcuts and shortcuts already present in the Glyphs menu
  are rejected.
- Delete clears a shortcut while recording; Escape cancels recording.

Shortcuts are installed as ordinary items in a **Script → Script Board** menu,
so they are active only while Glyphs is active. Script Board never installs a
global event tap or requests Accessibility permission.

## Persistence and moved scripts

Board state is stored in the namespaced Glyphs preference
`com.displaay.ScriptBoard.state`. The schema stores a source, relative path,
last-known absolute path, display title, order, and shortcut—never script code.

After Glyphs reloads scripts, Script Board resolves items against the new Script
menu. A uniquely moved script is rebound automatically. Unresolved items stay
on the board with a **Missing** label instead of being silently deleted.

## Architecture

```text
Contents/
  Info.plist
  MacOS/plugin                 Standard Glyphs Python plug-in loader
  Resources/
    plugin.py                  Glyphs/AppKit integration and Palette UI
    scriptboard/core.py        Pure state, search, shortcut, and reorder logic
    scriptboard/ui.py          Searchable native script picker
```

The plug-in uses the public `GlyphsPalette.sortID` contract with a value of 5.
Glyphs 4 documents Dimensions as 10, Fit Curve as 20, Layers as 30, and
Transformations as 40, placing Script Board immediately before Dimensions
without rewriting the user’s Palette preferences.

## Troubleshooting

- If the board is empty after installing scripts, choose **Refresh Installed
  Scripts** from the Palette gear menu after using **Script → Reload Scripts**.
- If a row says **Missing**, reload Glyphs’ scripts or remove and re-add the
  moved script.
- Script exceptions are handled by Glyphs and appear in the Macro window.
- If the Palette does not appear, confirm that a Glyphs Python version is
  selected and relaunch Glyphs.

## Prior art

[FastScripts](https://github.com/ViktorRubenko/FastScripts) established the
usefulness of a favorite-script Palette. Script Board is an independent Glyphs
4 implementation; it does not reuse FastScripts source code.

## License

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
