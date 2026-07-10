# VF Preview

Glyphs 3 reporter plugin for live variable-font interpolation preview.

This v1 build uses a native Objective-C reporter bundle for the live preview path: axis sliders, Edit-view overlay drawing, preview text, nodes, center preview, and hide-foreground drawing are handled by the `VFPreview` executable in `Contents/MacOS/`.

## Runtime Requirements

- Glyphs 3
- macOS frameworks provided by the system: Cocoa, CoreText, CoreGraphics, QuartzCore, Foundation, AppKit, CoreFoundation, libobjc, and libSystem
- `GlyphsCore.framework`, loaded from Glyphs at runtime through the bundle rpath

There is no Python, Vanilla, pip, Homebrew, or third-party runtime dependency for the native entrypoint.

## Install

1. Copy `VFPreview.glyphsReporter` to:
   `~/Library/Application Support/Glyphs 3/Plugins/`
2. Restart Glyphs.
3. Enable **View > VF Preview**.

## Usage

When the reporter is active, a **VF Preview** panel opens with:

- A live preview text field using the current Edit-tab string
- Continuous axis sliders
- Toggles for Edit-view drawing, nodes, centering, and hiding the foreground

Dragging an axis slider updates the Edit-view overlay and preview panel during the drag. Editing the source glyph or changing the Edit-tab text invalidates the native preview cache and redraws from current Glyphs data.

## Architecture

```
Contents/
  Info.plist             Native Glyphs reporter bundle entrypoint
  MacOS/
    VFPreview            Native Objective-C reporter executable
```

`Info.plist` uses:

- `CFBundleExecutable = VFPreview`
- `NSPrincipalClass = DPVFPreview`

The shipped bundle does not include the legacy Python implementation or its old loader. Historical Python reference files are kept outside the distributable bundle under `Plugins/VFPreviewPythonReference/`.

## Build

Build from the repository root:

```sh
make -C Plugins/VFPreviewNative clean all
```

Build requirements:

- Xcode Command Line Tools `clang`
- Glyphs 3 installed at `/Applications/Glyphs 3.app` for build-time GlyphsCore headers/framework lookup

The Makefile writes the universal macOS bundle executable to:

```text
Plugins/VFPreview.glyphsReporter/Contents/MacOS/VFPreview
```

## Sharing Checklist

Before sharing the plugin externally:

```sh
make -C Plugins/VFPreviewNative clean all
file Plugins/VFPreview.glyphsReporter/Contents/MacOS/VFPreview
otool -L Plugins/VFPreview.glyphsReporter/Contents/MacOS/VFPreview
plutil -p Plugins/VFPreview.glyphsReporter/Contents/Info.plist
make -C Plugins/VFPreviewNative dist
```

Expected dynamic libraries are only system frameworks plus `@rpath/GlyphsCore.framework/Versions/A/GlyphsCore`.

The `dist` target writes `dist/VFPreview.glyphsReporter.zip` with resource forks and extended attributes omitted.

The checked-in binary is ad-hoc/linker signed, not Developer ID notarized. That is suitable for direct Glyphs plugin-folder installation, but a public macOS download may still need Developer ID signing and notarization depending on the distribution channel.

## Current Scope

Implemented in the native v1 core:

- Continuous axis-slider redraw
- Live Edit-view overlay
- Live preview-panel text
- Native compatible-outline interpolation
- Recursive compatible component preview
- Node and tangent drawing from the same interpolated frame
- Center preview and hide foreground
- GlyphsCore fallback for complex/special cases

Deferred from v1:

- Charts
- MIDI and external controller hooks
- Rich context menu actions
- Measurements
- Make-instance UI
- Exported-font/CoreText preview mode

## License

Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
