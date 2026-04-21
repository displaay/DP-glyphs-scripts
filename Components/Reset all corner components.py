# MenuTitle: Reset All Corner components
# -*- coding: utf-8 -*-
from AppKit import NSPoint

font = Glyphs.font  # Get the current font

for glyph in font.glyphs:
	for layer in glyph.layers:
		for hint in layer.hints:
			print (hint)
            # changes x to 100% and y to 100%
			hint.scale = (1.0, 1.0)