# MenuTitle: Masters Side by Side
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens a new Edit tab with selected glyphs arranged by master. Axes can be
reordered by dragging; checked axes are used for sorting, unchecked axes are
held at the selected layer's coordinate so only that designspace slice is shown.
"""

try:
	from AppKit import NSApp, NSDragOperationMove
except Exception:
	NSApp = None
	NSDragOperationMove = 16

import json
import vanilla
from GlyphsApp import Glyphs, GSControlLayer, Message


SCRIPT_NAME = "Masters Side by Side"
AXIS_DROP_TYPE = "com.displaay.glyphs.masters-side-by-side.axis-row"
DEFAULTS_KEY = "com.displaay.MastersSideBySide.axisRows"
LOW_TO_HIGH = "↑"
HIGH_TO_LOW = "↓"
LEGACY_LOW_TO_HIGH = "Low to high"
LEGACY_HIGH_TO_LOW = "High to low"


class MastersSideBySide(object):
	def __init__(self):
		self.font = Glyphs.font
		if self.font is None:
			Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
			return

		self.updating_axis_list = False
		self.w = vanilla.FloatingWindow((430, 360), SCRIPT_NAME)

		y = 15
		self.w.axisLabel = vanilla.TextBox((15, y, -15, 18), "Axis order")
		y += 22

		column_descriptions = [
			{"title": "Use", "key": "use", "width": 42, "editable": True},
			{"title": "Axis", "key": "axis", "width": 250, "editable": False},
			{"title": "Sort", "key": "direction", "editable": True},
		]
		if hasattr(vanilla, "CheckBoxListCell"):
			column_descriptions[0]["cell"] = vanilla.CheckBoxListCell()

		self.w.axisList = vanilla.List(
			(15, y, -15, 120),
			self.default_axis_rows(),
			columnDescriptions=column_descriptions,
			showColumnTitles=True,
			allowsMultipleSelection=True,
			allowsEmptySelection=True,
			allowsSorting=False,
			rowHeight=22,
			selectionCallback=self.axisListSelectionCallback,
			editCallback=self.axisListEdited,
			selfDropSettings={
				"type": AXIS_DROP_TYPE,
				"operation": NSDragOperationMove,
				"allowDropBetweenRows": True,
				"allowDropOnRow": False,
				"callback": self.axisListDropCallback,
			},
			dragSettings={
				"type": AXIS_DROP_TYPE,
				"callback": self.axisListDragCallback,
			},
		)

		y += 132
		self.w.upButton = vanilla.Button((15, y, 92, 22), "Move Up", callback=self.moveAxisUpCallback)
		self.w.downButton = vanilla.Button((113, y, 104, 22), "Move Down", callback=self.moveAxisDownCallback)
		self.w.resetButton = vanilla.Button((223, y, 92, 22), "Reset", callback=self.resetAxisOrderCallback)
		self.w.saveDefaultsButton = vanilla.Button((321, y, -15, 22), "Save", callback=self.saveDefaultsCallback)

		y += 34
		self.w.status = vanilla.TextBox((15, y, -15, 54), self.status_text(), sizeStyle="small")

		self.w.openButton = vanilla.Button((15, -42, -15, 22), "Open Comparison Tab", callback=self.openCallback)
		self.w.setDefaultButton(self.w.openButton)

		self.w.open()
		self.activate_window()

	def activate_window(self):
		try:
			if NSApp is not None:
				NSApp.activateIgnoringOtherApps_(True)
		except Exception:
			pass

		try:
			window = self.w.getNSWindow()
			window.makeKeyAndOrderFront_(None)
		except Exception:
			try:
				self.w.makeKey()
			except Exception:
				pass

	def default_axis_rows(self):
		rows = []
		for index, axis in enumerate(self.font.axes):
			rows.append(
				{
					"use": True,
					"axis": self.axis_label(axis),
					"direction": self.default_axis_direction(axis),
					"axisIndex": index,
					"axisKey": self.axis_identifier(axis),
					"axisTag": getattr(axis, "axisTag", None) or getattr(axis, "tag", None) or "",
					"axisName": getattr(axis, "name", None) or "",
				}
			)
		return self.apply_saved_defaults(rows)

	def factory_axis_rows(self):
		rows = []
		for index, axis in enumerate(self.font.axes):
			rows.append(
				{
					"use": True,
					"axis": self.axis_label(axis),
					"direction": self.default_axis_direction(axis),
					"axisIndex": index,
					"axisKey": self.axis_identifier(axis),
					"axisTag": getattr(axis, "axisTag", None) or getattr(axis, "tag", None) or "",
					"axisName": getattr(axis, "name", None) or "",
				}
			)
		return rows

	def default_axis_direction(self, axis):
		tag = (getattr(axis, "axisTag", None) or getattr(axis, "tag", None) or "").lower()
		name = (getattr(axis, "name", None) or "").lower()
		if tag == "slnt" or name == "slant":
			return HIGH_TO_LOW
		return LOW_TO_HIGH

	def axis_label(self, axis):
		name = getattr(axis, "name", None) or "Axis"
		tag = getattr(axis, "axisTag", None) or getattr(axis, "tag", None)
		if tag:
			return "%s (%s)" % (name, tag)
		return name

	def axis_identifier(self, axis):
		return (
			getattr(axis, "axisId", None)
			or getattr(axis, "id", None)
			or getattr(axis, "axisTag", None)
			or getattr(axis, "tag", None)
			or getattr(axis, "name", "")
		)

	def axis_identifiers(self, axis):
		identifiers = []
		for attr in ("axisId", "id", "axisTag", "tag", "name"):
			value = getattr(axis, attr, None)
			if value is not None and value not in identifiers:
				identifiers.append(value)
		return identifiers

	def normalize_direction(self, direction):
		if direction in (HIGH_TO_LOW, LEGACY_HIGH_TO_LOW, "▼", "desc", "descending"):
			return HIGH_TO_LOW
		return LOW_TO_HIGH

	def row_keys(self, row):
		keys = []
		for key in ("axisKey", "axisTag", "axisName", "axis"):
			value = row.get(key)
			if value is not None and value not in keys:
				keys.append(value)
		return keys

	def row_matches_saved_row(self, row, saved_row):
		for key in self.row_keys(row):
			if key in self.row_keys(saved_row):
				return True
		return False

	def saved_axis_defaults(self):
		try:
			raw_value = Glyphs.defaults.get(DEFAULTS_KEY)
		except Exception:
			raw_value = None
		if not raw_value:
			return []

		try:
			return json.loads(raw_value)
		except Exception:
			return []

	def apply_saved_defaults(self, rows):
		saved_rows = self.saved_axis_defaults()
		if not saved_rows:
			return rows

		remaining_rows = list(rows)
		ordered_rows = []

		for saved_row in saved_rows:
			match = None
			for row in remaining_rows:
				if self.row_matches_saved_row(row, saved_row):
					match = row
					break
			if match is None:
				continue

			remaining_rows.remove(match)
			match["use"] = bool(saved_row.get("use", match.get("use", True)))
			match["direction"] = self.normalize_direction(saved_row.get("direction", match.get("direction")))
			ordered_rows.append(match)

		ordered_rows.extend(remaining_rows)
		return ordered_rows

	def saveDefaultsCallback(self, sender):
		rows = []
		for row in self.axis_rows():
			rows.append(
				{
					"axisKey": row.get("axisKey"),
					"axisTag": row.get("axisTag"),
					"axisName": row.get("axisName"),
					"use": bool(row.get("use")),
					"direction": self.normalize_direction(row.get("direction")),
				}
			)

		try:
			Glyphs.defaults[DEFAULTS_KEY] = json.dumps(rows)
			self.update_status("Saved as default.")
		except Exception as error:
			Message(title=SCRIPT_NAME, message="Could not save defaults:\n%s" % error)

	def axisListEdited(self, sender):
		self.update_status()

	def axisListSelectionCallback(self, sender):
		if self.updating_axis_list:
			return

		selection = list(sender.getSelection() or [])
		if len(selection) != 1:
			return

		row_index = selection[0]
		rows = list(sender.get())
		if row_index < 0 or row_index >= len(rows):
			return

		rows[row_index]["direction"] = HIGH_TO_LOW if self.normalize_direction(rows[row_index].get("direction")) == LOW_TO_HIGH else LOW_TO_HIGH
		self.set_axis_rows(rows, selection=[row_index])

	def set_axis_rows(self, rows, selection=None):
		self.updating_axis_list = True
		try:
			self.w.axisList.set(rows)
			if selection is not None:
				self.w.axisList.setSelection(selection)
		finally:
			self.updating_axis_list = False
		self.update_status()

	def axisListDragCallback(self, sender, indexes=None):
		if indexes is None:
			indexes = sender.getSelection()
		return [str(index) for index in indexes]

	def axisListDropCallback(self, sender, dropInfo):
		if dropInfo.get("isProposal"):
			return dropInfo.get("rowIndex") is not None and not dropInfo.get("dropOnRow")

		selected = list(sender.getSelection() or [])
		if not selected:
			return False

		target_index = dropInfo.get("rowIndex")
		if target_index is None:
			return False

		self.move_axis_rows(selected, target_index)
		return True

	def move_axis_rows(self, selected, target_index):
		rows = list(self.w.axisList.get())
		selected = sorted(set(selected))
		moving_rows = [rows[index] for index in selected]

		for index in reversed(selected):
			del rows[index]
			if index < target_index:
				target_index -= 1

		target_index = max(0, min(target_index, len(rows)))
		for offset, row in enumerate(moving_rows):
			rows.insert(target_index + offset, row)

		self.set_axis_rows(rows, selection=list(range(target_index, target_index + len(moving_rows))))

	def moveAxisUpCallback(self, sender):
		selected = sorted(self.w.axisList.getSelection() or [])
		if not selected or selected[0] == 0:
			return
		self.move_axis_rows(selected, selected[0] - 1)

	def moveAxisDownCallback(self, sender):
		selected = sorted(self.w.axisList.getSelection() or [])
		rows = self.w.axisList.get()
		if not selected or selected[-1] >= len(rows) - 1:
			return
		self.move_axis_rows(selected, selected[-1] + 2)

	def resetAxisOrderCallback(self, sender):
		self.set_axis_rows(self.factory_axis_rows(), selection=[])

	def axis_rows(self):
		return list(self.w.axisList.get())

	def active_axis_rows(self, axis_rows):
		return [row for row in axis_rows if row.get("use")]

	def locked_axis_rows(self, axis_rows):
		return [row for row in axis_rows if not row.get("use")]

	def update_status(self, prefix=None):
		text = self.status_text()
		if prefix:
			text = "%s %s" % (prefix, text)
		self.w.status.set(text)

	def status_text(self):
		glyphs = self.selected_glyph_entries()
		if not glyphs:
			return "Select one or more glyphs. Checked axes sort and vary; unchecked axes stay at the selected layer coordinate."

		rows = self.axis_rows() if hasattr(self, "w") and hasattr(self.w, "axisList") else self.default_axis_rows()
		active_count = len(self.active_axis_rows(rows))
		locked_count = len(self.locked_axis_rows(rows))
		return "%i selected glyph(s). %i axis/axes sort; %i axis/axes are locked to the selected layer." % (
			len(glyphs),
			active_count,
			locked_count,
		)

	def selected_glyph_entries(self):
		entries = []
		seen = set()
		for layer in list(self.font.selectedLayers or []):
			glyph = getattr(layer, "parent", None)
			if glyph is None or glyph.name in seen:
				continue
			seen.add(glyph.name)
			entries.append((glyph, layer))
		return entries

	def fallback_reference_layer(self, glyph):
		try:
			layer = glyph.layers[self.font.selectedFontMaster.id]
			if layer is not None:
				return layer
		except Exception:
			pass
		for layer in glyph.layers:
			return layer
		return None

	def master_for_layer(self, layer):
		master_id = getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None)
		if not master_id:
			return None
		for master in self.font.masters:
			if master.id == master_id:
				return master
		return None

	def master_index(self, master):
		if master is None:
			return len(self.font.masters)
		for index, candidate in enumerate(self.font.masters):
			if candidate.id == master.id:
				return index
		return len(self.font.masters)

	def layer_axis_value(self, layer, axis_index):
		axis = self.font.axes[axis_index]
		coordinates = None
		if getattr(layer, "isSpecialLayer", False):
			coordinates = layer.attributes.get("coordinates", {}) or {}

		value = self.axis_value_from_source(coordinates, axis, axis_index)
		if value is None:
			master = self.master_for_layer(layer)
			value = self.axis_value_from_source(getattr(master, "axes", None), axis, axis_index)
			if value is None:
				value = self.axis_value_from_source(master, axis, axis_index)

		return self.sortable_value(value)

	def axis_value_from_source(self, source, axis, axis_index):
		if source is None:
			return None

		for axis_id in self.axis_identifiers(axis):
			try:
				value = source[axis_id]
				if value is not None:
					return value
			except Exception:
				pass

			try:
				value = source.get(axis_id)
				if value is not None:
					return value
			except Exception:
				pass

		try:
			if axis_index < len(source):
				return source[axis_index]
		except Exception:
			pass

		try:
			values = list(source.values())
			if axis_index < len(values):
				return values[axis_index]
		except Exception:
			pass

		return None

	def sortable_value(self, value):
		try:
			return float(value)
		except Exception:
			return value if value is not None else 0

	def values_equal(self, a, b):
		try:
			return abs(float(a) - float(b)) < 0.0001
		except Exception:
			return a == b

	def layer_matches_locked_axes(self, layer, reference_layer, axis_rows):
		if reference_layer is None:
			return True
		for row in self.locked_axis_rows(axis_rows):
			axis_index = row.get("axisIndex")
			if axis_index is None:
				continue
			layer_value = self.layer_axis_value(layer, axis_index)
			reference_value = self.layer_axis_value(reference_layer, axis_index)
			if not self.values_equal(layer_value, reference_value):
				return False
		return True

	def layer_label_key(self, layer):
		name = getattr(layer, "name", None) or ""
		if name:
			return name
		master = self.master_for_layer(layer)
		return getattr(master, "name", "") or ""

	def axis_sort_value(self, layer, row):
		axis_index = row.get("axisIndex")
		value = self.layer_axis_value(layer, axis_index)
		if self.normalize_direction(row.get("direction")) == HIGH_TO_LOW:
			try:
				return -float(value)
			except Exception:
				pass
		return value

	def layer_sort_key(self, layer, axis_rows):
		master = self.master_for_layer(layer)
		master_order = self.master_index(master)
		is_special = 1 if getattr(layer, "isSpecialLayer", False) else 0
		key = [self.axis_sort_value(layer, row) for row in self.active_axis_rows(axis_rows)]
		key.extend([master_order, is_special, self.layer_label_key(layer)])
		return tuple(key)

	def layers_for_glyph(self, glyph, reference_layer, axis_rows):
		layers = []

		for master in self.font.masters:
			layer = glyph.layers[master.id]
			if layer is not None and self.layer_matches_locked_axes(layer, reference_layer, axis_rows):
				layers.append(layer)

		for layer in glyph.layers:
			if not getattr(layer, "isSpecialLayer", False):
				continue
			if self.layer_matches_locked_axes(layer, reference_layer, axis_rows):
				layers.append(layer)

		return sorted(layers, key=lambda layer: self.layer_sort_key(layer, axis_rows))

	def comparison_layers(self, entries, axis_rows):
		layers = []
		for glyph_index, entry in enumerate(entries):
			glyph, reference_layer = entry
			reference_layer = reference_layer or self.fallback_reference_layer(glyph)
			layers.extend(self.layers_for_glyph(glyph, reference_layer, axis_rows))
			if glyph_index < len(entries) - 1:
				try:
					layers.append(GSControlLayer.newline())
				except Exception:
					layers.append(GSControlLayer(10))
		return layers

	def openCallback(self, sender):
		entries = self.selected_glyph_entries()
		if not entries:
			Message(title=SCRIPT_NAME, message="Select one or more glyphs and run the comparison again.")
			return

		axis_rows = self.axis_rows()
		layers = self.comparison_layers(entries, axis_rows)

		if not [layer for layer in layers if getattr(layer, "parent", None) is not None]:
			Message(title=SCRIPT_NAME, message="No matching layers found for the selected axis setup.")
			return

		tab = self.font.newTab()
		tab.layers = layers


MastersSideBySide()
