# MenuTitle: Master Overview
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens a new Edit tab containing the selected glyphs in every font master.

Each selected glyph occupies one row. Its master layers are shown from left to
right in the font's master order.
"""

import traceback

from GlyphsApp import Glyphs, GSControlLayer, Message


SCRIPT_NAME = "Master Overview"


def safe_string(value):
	if value is None:
		return ""
	return str(value)


def unique_selected_glyphs(font):
	"""Return selected glyphs once each, preserving the selection order."""
	glyphs = []
	seen = set()

	try:
		selected_layers = list(font.selectedLayers or [])
	except Exception:
		selected_layers = []

	for layer in selected_layers:
		glyph = getattr(layer, "parent", None)
		if glyph is None:
			continue
		key = safe_string(getattr(glyph, "id", None)) or safe_string(getattr(glyph, "name", None))
		if not key or key in seen:
			continue
		seen.add(key)
		glyphs.append(glyph)

	return glyphs


def master_layer(glyph, master):
	try:
		return glyph.layers[master.id]
	except Exception:
		return None


def newline_layer():
	# Glyphs 4's Python convenience constructor currently calls
	# GSControlLayer(10), which fails in some builds. Use the native initializer.
	return GSControlLayer.alloc().initWithChar_(10)


def overview_layers(font, glyphs):
	layers = []
	for glyph_index, glyph in enumerate(glyphs):
		for master in font.masters:
			layer = master_layer(glyph, master)
			if layer is not None:
				layers.append(layer)

		if glyph_index < len(glyphs) - 1:
			layers.append(newline_layer())

	return layers


def main():
	font = Glyphs.font
	if font is None:
		Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
		return

	glyphs = unique_selected_glyphs(font)
	if not glyphs:
		Message(title=SCRIPT_NAME, message="Select one or more glyphs in Font View or Edit View.")
		return

	if not list(font.masters or []):
		Message(title=SCRIPT_NAME, message="The current font has no masters.")
		return

	layers = overview_layers(font, glyphs)
	if not layers:
		Message(title=SCRIPT_NAME, message="No master layers were found for the selected glyphs.")
		return

	tab = font.newTab()
	tab.layers = layers


try:
	main()
except Exception:
	Glyphs.showMacroWindow()
	print("%s Error" % SCRIPT_NAME)
	print(traceback.format_exc())
