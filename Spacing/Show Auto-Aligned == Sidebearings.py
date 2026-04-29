# MenuTitle: Remove Negative Auto-Aligned == Sidebearings
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals
from GlyphsApp import Glyphs, Message


def component_is_auto_aligned(component):
	try:
		return bool(component.automaticAlignment)
	except Exception:
		return getattr(component, "alignment", 0) != -1


def effective_metrics_key(layer, glyph, side):
	layer_key = getattr(layer, "%sMetricsKey" % side)
	if layer_key:
		return layer_key
	return getattr(glyph, "%sMetricsKey" % side)


def metrics_key_contains_double_equal(key):
	return bool(key and "==" in key)


def clear_metrics_key(layer, glyph, side):
	key_name = "%sMetricsKey" % side
	layer_key = getattr(layer, key_name)
	glyph_key = getattr(glyph, key_name)

	if metrics_key_contains_double_equal(layer_key):
		setattr(layer, key_name, None)
		return layer_key, "layer"
	if metrics_key_contains_double_equal(glyph_key):
		setattr(glyph, key_name, None)
		return glyph_key, "glyph"
	return None, None


font = Glyphs.font

if not font:
	Message("No Font Open", "Please open a font first.")
else:
	master = font.selectedFontMaster
	master_id = master.id
	matching_glyphs = []
	matching_details = []
	changed_count = 0

	font.disableUpdateInterface()
	if font.parent:
		font.parent.undoManager().beginUndoGrouping()

	try:
		for glyph in font.glyphs:
			layer = glyph.layers[master_id]
			if not layer:
				continue

			has_auto_aligned_component = any(
				component_is_auto_aligned(component) for component in layer.components
			)
			if not has_auto_aligned_component:
				continue

			left_key = effective_metrics_key(layer, glyph, "left")
			right_key = effective_metrics_key(layer, glyph, "right")
			left_needs_clear = layer.LSB < 0 and metrics_key_contains_double_equal(left_key)
			right_needs_clear = layer.RSB < 0 and metrics_key_contains_double_equal(right_key)

			if left_needs_clear or right_needs_clear:
				original_lsb = layer.LSB
				original_rsb = layer.RSB
				changes = []

				if left_needs_clear:
					removed_key, source = clear_metrics_key(layer, glyph, "left")
					layer.LSB = original_lsb
					changed_count += 1
					changes.append(
						"removed LSB %s key %s (%s)"
						% (source, removed_key, original_lsb)
					)

				if right_needs_clear:
					removed_key, source = clear_metrics_key(layer, glyph, "right")
					layer.RSB = original_rsb
					changed_count += 1
					changes.append(
						"removed RSB %s key %s (%s)"
						% (source, removed_key, original_rsb)
					)

				matching_glyphs.append(glyph.name)
				matching_details.append(
					"%s  %s"
					% (glyph.name, "; ".join(changes))
				)
	finally:
		if font.parent:
			font.parent.undoManager().endUndoGrouping()
		font.enableUpdateInterface()

	if matching_glyphs:
		font.newTab("/" + "/".join(matching_glyphs))
		print(
			"Removed %i negative == sidebearing entries from %i auto-aligned glyphs in master '%s':"
			% (changed_count, len(matching_glyphs), master.name)
		)
		print("\n".join(matching_details))
		Glyphs.showMacroWindow()
	else:
		Message(
			"No Matches",
			"No auto-aligned glyphs with negative == sidebearing entries were found in master '%s'."
			% master.name,
		)
		print(
			"No auto-aligned glyphs with negative == sidebearing entries found in master '%s'."
			% master.name
		)
