# MenuTitle: Add wght 400 Intermediate Layers
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__ = """
Adds wght 400 intermediate layers to selected glyphs, copying outlines from the
heaviest source layer at each designspace coordinate.
"""

from GlyphsApp import Glyphs, GSLayer, Message


TARGET_WEIGHT_VALUE = 400


def axis_tag(axis):
	return getattr(axis, "axisTag", None) or getattr(axis, "tag", None) or ""


def axis_identifier(axis):
	return getattr(axis, "axisId", None) or getattr(axis, "id", None) or axis_tag(axis) or getattr(axis, "name", "")


def weight_axis_index(font):
	for index, axis in enumerate(font.axes):
		tag = axis_tag(axis)
		name = (getattr(axis, "name", "") or "").lower()
		if tag == "wght" or name == "weight":
			return index
	return None


def master_for_layer(font, layer):
	master_id = getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None)
	if not master_id:
		return None

	for master in font.masters:
		if master.id == master_id:
			return master
	return None


def layer_coordinates(font, layer):
	coordinates = {}
	source_coordinates = {}
	if getattr(layer, "isSpecialLayer", False):
		source_coordinates = dict(layer.attributes.get("coordinates", {}) or {})

	master = master_for_layer(font, layer)
	master_values = list(getattr(master, "axes", []) or [])
	source_values = list(source_coordinates.values())

	for index, axis in enumerate(font.axes):
		axis_id = axis_identifier(axis)
		value = source_coordinates.get(axis_id)

		if value is None and index < len(source_values):
			value = source_values[index]
		if value is None and index < len(master_values):
			value = master_values[index]
		if value is None:
			value = 0

		coordinates[axis_id] = value

	return coordinates


def sortable_coordinate_value(value):
	try:
		return float(value)
	except Exception:
		return value


def weight_coordinate_value(value):
	try:
		return float(value)
	except Exception:
		return 0


def non_weight_signature(font, coordinates, weight_index):
	signature = []
	for index, axis in enumerate(font.axes):
		if index == weight_index:
			continue
		axis_id = axis_identifier(axis)
		signature.append(sortable_coordinate_value(coordinates.get(axis_id)))
	return tuple(signature)


def heaviest_layer_for_coordinates(font, source_layers, target_coordinates, weight_index):
	target_signature = non_weight_signature(font, target_coordinates, weight_index)
	weight_axis_id = axis_identifier(font.axes[weight_index])
	matching_layers = []

	for candidate in source_layers:
		candidate_coordinates = layer_coordinates(font, candidate)
		if non_weight_signature(font, candidate_coordinates, weight_index) != target_signature:
			continue
		matching_layers.append((weight_coordinate_value(candidate_coordinates.get(weight_axis_id, 0)), candidate))

	if not matching_layers:
		return None

	return sorted(matching_layers, key=lambda item: item[0])[-1][1]


def unique_selected_glyphs(font):
	glyphs = []
	seen = set()
	for layer in font.selectedLayers:
		glyph = layer.parent
		if glyph is None or glyph.name in seen:
			continue
		seen.add(glyph.name)
		glyphs.append(glyph)
	return glyphs


def source_layer_name(layer):
	if getattr(layer, "name", None):
		return layer.name
	master = master_for_layer(Glyphs.font, layer)
	if master is not None:
		return master.name
	return "Layer"


def add_weight_intermediates(font):
	weight_index = weight_axis_index(font)
	if weight_index is None:
		Message(
			title="Add wght 400 Intermediate Layers",
			message="No weight axis found. Add an axis tagged 'wght' or named 'Weight' and run again.",
		)
		return

	weight_axis_id = axis_identifier(font.axes[weight_index])
	selected_glyphs = unique_selected_glyphs(font)
	if not selected_glyphs:
		Message(
			title="Add wght 400 Intermediate Layers",
			message="Select one or more glyphs and run the script again.",
		)
		return

	created_count = 0
	font.disableUpdateInterface()
	try:
		for glyph in selected_glyphs:
			source_layers = [layer for layer in glyph.layers if layer.isMasterLayer or layer.isSpecialLayer]
			if not source_layers:
				continue

			glyph.beginUndo()
			try:
				for source_layer in source_layers:
					coordinates = layer_coordinates(font, source_layer)
					outline_layer = heaviest_layer_for_coordinates(font, source_layers, coordinates, weight_index) or source_layer

					new_layer = GSLayer()
					new_layer.associatedMasterId = getattr(source_layer, "associatedMasterId", None) or getattr(source_layer, "layerId", None)
					new_layer.name = "wght %s from %s" % (TARGET_WEIGHT_VALUE, source_layer_name(source_layer))
					new_layer.width = source_layer.width
					new_layer.shapes = [path.copy() for path in outline_layer.paths]

					coordinates[weight_axis_id] = TARGET_WEIGHT_VALUE
					new_layer.attributes["coordinates"] = coordinates

					glyph.layers.append(new_layer)
					created_count += 1
			finally:
				glyph.endUndo()
	finally:
		font.enableUpdateInterface()

	print("Add wght 400 Intermediate Layers: created %i layer(s)." % created_count)


font = Glyphs.font
if font is None:
	Message(
		title="Add wght 400 Intermediate Layers",
		message="Open a font and run the script again.",
	)
else:
	add_weight_intermediates(font)
