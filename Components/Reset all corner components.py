# MenuTitle: Reset All Corner components
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__ = """
Resets all corner-component hint scales to 100% on every layer in the font.
"""

from AppKit import NSPoint

font = Glyphs.font  # Get the current font

for glyph in font.glyphs:
	for layer in glyph.layers:
		for hint in layer.hints:
			print (hint)
            # changes x to 100% and y to 100%
			hint.scale = (1.0, 1.0)
