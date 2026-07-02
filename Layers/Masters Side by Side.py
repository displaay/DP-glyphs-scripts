# MenuTitle: Masters Side by Side
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens a new Edit tab with selected glyphs arranged by active masters.
Master buttons are remembered per font file; axes only sort the active layers.
"""

try:
	import AppKit
except Exception:
	AppKit = None

NSAffineTransform = getattr(AppKit, "NSAffineTransform", None)
NSApp = getattr(AppKit, "NSApp", None)
NSBezierPath = getattr(AppKit, "NSBezierPath", None)
NSColor = getattr(AppKit, "NSColor", None)
NSDragOperationMove = getattr(AppKit, "NSDragOperationMove", 16)
NSFont = getattr(AppKit, "NSFont", None)
NSFontAttributeName = getattr(AppKit, "NSFontAttributeName", "NSFont")
NSForegroundColorAttributeName = getattr(AppKit, "NSForegroundColorAttributeName", "NSColor")
NSImage = getattr(AppKit, "NSImage", None)
NSMakeRect = getattr(AppKit, "NSMakeRect", None)
NSMakeSize = getattr(AppKit, "NSMakeSize", None)
NSString = getattr(AppKit, "NSString", None)

import json
import vanilla
from GlyphsApp import Glyphs, GSControlLayer, Message


SCRIPT_NAME = "Masters Side by Side"
AXIS_DROP_TYPE = "com.displaay.glyphs.masters-side-by-side.axis-row"
AXIS_DEFAULTS_KEY = "com.displaay.MastersSideBySide.axisRows"
MASTER_SELECTION_KEY = "com.displaay.MastersSideBySide.activeMasterIds"
LOW_TO_HIGH = "↑"
HIGH_TO_LOW = "↓"
LEGACY_LOW_TO_HIGH = "Low to high"
LEGACY_HIGH_TO_LOW = "High to low"
ICON_SIZE = 42
ICON_GAP = 8
CELL_GAP = 10
ROW_LABEL_WIDTH = 86
COLUMN_LABEL_HEIGHT = 22


class MastersSideBySide(object):
	def __init__(self):
		self.font = Glyphs.font
		if self.font is None:
			Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
			return

		self.updating_axis_list = False
		self.master_buttons = {}
		self.matrix_controls = []
		self.active_master_ids = self.load_active_master_ids()

		initial_layout = self.master_matrix_layout(self.default_column_axis_index(), self.default_row_axis_index())
		window_width = max(560, 30 + initial_layout["width"])
		window_height = 470 + initial_layout["height"]
		self.w = vanilla.FloatingWindow((window_width, window_height), SCRIPT_NAME)

		y = 15
		self.w.masterLabel = vanilla.TextBox((15, y, -15, 18), "Masters")
		self.w.columnAxisLabel = vanilla.TextBox((15, y + 26, 64, 18), "Columns")
		self.w.columnAxisPopup = vanilla.PopUpButton((82, y + 24, 175, 22), self.matrix_axis_items(allow_none=True), callback=self.matrixAxisCallback)
		self.w.rowAxisLabel = vanilla.TextBox((270, y + 26, 44, 18), "Rows")
		self.w.rowAxisPopup = vanilla.PopUpButton((318, y + 24, 175, 22), self.matrix_axis_items(allow_none=True), callback=self.matrixAxisCallback)
		self.w.columnAxisPopup.set(self.popup_index_for_axis(self.default_column_axis_index(), allow_none=True))
		self.w.rowAxisPopup.set(self.popup_index_for_axis(self.default_row_axis_index(), allow_none=True))

		self.w.groupLabel = vanilla.TextBox((15, 0, -15, 18), "Master groups")
		self.w.groupAxisPopup = vanilla.PopUpButton((15, 0, 170, 22), self.group_axis_items(), callback=self.groupAxisCallback)
		self.w.groupValuePopup = vanilla.PopUpButton((195, 0, -15, 22), [], callback=self.groupValueCallback)
		self.w.groupOnlyButton = vanilla.Button((15, 0, 82, 22), "Only", callback=self.groupOnlyCallback)
		self.w.groupNarrowButton = vanilla.Button((103, 0, 82, 22), "Filter", callback=self.groupNarrowCallback)
		self.w.groupAddButton = vanilla.Button((191, 0, 82, 22), "Add", callback=self.groupAddCallback)
		self.w.groupAllButton = vanilla.Button((279, 0, 82, 22), "All", callback=self.groupAllCallback)
		self.group_value_options = []
		self.update_group_values()

		self.w.axisLabel = vanilla.TextBox((15, 0, -15, 18), "Axis sort order")

		column_descriptions = [
			{"title": "Axis", "key": "axis", "width": 360, "editable": False},
			{"title": "Sort", "key": "direction", "editable": True},
		]

		self.w.axisList = vanilla.List(
			(15, 0, -15, 118),
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

		self.w.upButton = vanilla.Button((15, 0, 92, 22), "Move Up", callback=self.moveAxisUpCallback)
		self.w.downButton = vanilla.Button((113, 0, 104, 22), "Move Down", callback=self.moveAxisDownCallback)
		self.w.resetButton = vanilla.Button((223, 0, 92, 22), "Reset", callback=self.resetAxisOrderCallback)
		self.w.saveDefaultsButton = vanilla.Button((321, 0, -15, 22), "Save Sort", callback=self.saveDefaultsCallback)

		self.w.status = vanilla.TextBox((15, 0, -15, 54), self.status_text(), sizeStyle="small")

		self.w.openButton = vanilla.Button((15, -42, -15, 22), "Open Comparison Tab", callback=self.openCallback)
		self.w.setDefaultButton(self.w.openButton)
		self.layout_interface()

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

	def layout_interface(self):
		column_axis_index = self.selected_matrix_column_axis_index()
		row_axis_index = self.selected_matrix_row_axis_index()
		layout = self.master_matrix_layout(column_axis_index, row_axis_index)
		window_width = max(560, 30 + layout["width"])
		window_height = 470 + layout["height"]

		try:
			self.w.resize(window_width, window_height)
		except Exception:
			try:
				if NSMakeSize is not None:
					self.w.getNSWindow().setContentSize_(NSMakeSize(window_width, window_height))
			except Exception:
				pass

		y = 63
		self.build_master_matrix(y, layout)
		y += layout["height"] + 18

		self.w.groupLabel.setPosSize((15, y, -15, 18))
		y += 22
		self.w.groupAxisPopup.setPosSize((15, y, 170, 22))
		self.w.groupValuePopup.setPosSize((195, y, -15, 22))
		y += 30
		self.w.groupOnlyButton.setPosSize((15, y, 82, 22))
		self.w.groupNarrowButton.setPosSize((103, y, 82, 22))
		self.w.groupAddButton.setPosSize((191, y, 82, 22))
		self.w.groupAllButton.setPosSize((279, y, 82, 22))
		y += 42

		self.w.axisLabel.setPosSize((15, y, -15, 18))
		y += 22
		self.w.axisList.setPosSize((15, y, -15, 118))
		y += 130
		self.w.upButton.setPosSize((15, y, 92, 22))
		self.w.downButton.setPosSize((113, y, 104, 22))
		self.w.resetButton.setPosSize((223, y, 92, 22))
		self.w.saveDefaultsButton.setPosSize((321, y, -15, 22))
		y += 34
		self.w.status.setPosSize((15, y, -15, 54))
		self.update_status()

	def clear_master_matrix(self):
		for name, control in self.matrix_controls:
			try:
				control.getNSView().removeFromSuperview()
			except Exception:
				pass
			try:
				delattr(self.w, name)
			except Exception:
				pass
		self.matrix_controls = []
		self.master_buttons = {}

	def add_matrix_control(self, control):
		name = "matrixControl_%i" % len(self.matrix_controls)
		setattr(self.w, name, control)
		self.matrix_controls.append((name, control))

	def build_master_matrix(self, top, layout):
		self.clear_master_matrix()
		cell_width = layout["cellWidth"]
		cell_height = layout["cellHeight"]

		for column_index, column in enumerate(layout["columns"]):
			x = 15 + ROW_LABEL_WIDTH + column_index * (cell_width + CELL_GAP)
			label = vanilla.TextBox((x, top, cell_width, 18), column["label"], sizeStyle="small")
			self.add_matrix_control(label)

		for row_index, row in enumerate(layout["rows"]):
			y = top + COLUMN_LABEL_HEIGHT + row_index * (cell_height + CELL_GAP)
			label = vanilla.TextBox((15, y + 12, ROW_LABEL_WIDTH - 8, 18), row["label"], sizeStyle="small")
			self.add_matrix_control(label)

		for (row_index, column_index), masters in layout["cells"].items():
			cell_x = 15 + ROW_LABEL_WIDTH + column_index * (cell_width + CELL_GAP)
			cell_y = top + COLUMN_LABEL_HEIGHT + row_index * (cell_height + CELL_GAP)
			for stack_index, master in enumerate(masters):
				x = cell_x + stack_index * (ICON_SIZE + 4)
				y = cell_y
				if x + ICON_SIZE > cell_x + cell_width:
					continue
				self.add_master_button(master, x, y)

		self.update_master_buttons()

	def add_master_button(self, master, x, y):
		button = vanilla.Button(
			(x, y, ICON_SIZE, ICON_SIZE),
			"",
			callback=lambda sender, master_id=master.id: self.toggleMasterCallback(sender, master_id),
		)
		self.master_buttons[master.id] = button
		self.add_matrix_control(button)

		try:
			button.getNSButton().setBordered_(False)
			button.getNSButton().setToolTip_(master.name)
		except Exception:
			pass

	def matrix_axis_items(self, allow_none=False):
		items = [self.axis_label(axis) for axis in self.font.axes]
		if allow_none:
			items = ["None"] + items
		return items or ["None"]

	def popup_index_for_axis(self, axis_index, allow_none=False):
		if axis_index is None:
			return 0
		return axis_index + (1 if allow_none else 0)

	def axis_index_from_popup(self, popup, allow_none=False):
		try:
			index = int(popup.get())
		except Exception:
			index = 0
		if allow_none:
			return None if index == 0 else index - 1
		return index

	def default_column_axis_index(self):
		return 0 if self.font.axes else None

	def default_row_axis_index(self):
		return 1 if len(self.font.axes) > 1 else None

	def selected_matrix_column_axis_index(self):
		return self.axis_index_from_popup(self.w.columnAxisPopup, allow_none=True)

	def selected_matrix_row_axis_index(self):
		return self.axis_index_from_popup(self.w.rowAxisPopup, allow_none=True)

	def matrixAxisCallback(self, sender):
		if not hasattr(self.w, "groupLabel"):
			return
		self.layout_interface()

	def master_matrix_layout(self, column_axis_index, row_axis_index):
		columns = self.master_groups_for_axis(column_axis_index)
		rows = self.master_groups_for_axis(row_axis_index)
		cells = {}

		for master in self.font.masters:
			column_index = self.group_index_for_master(master, columns, column_axis_index)
			row_index = self.group_index_for_master(master, rows, row_axis_index)
			cells.setdefault((row_index, column_index), []).append(master)

		max_stack = 1
		for masters in cells.values():
			max_stack = max(max_stack, len(masters))

		cell_width = max(ICON_SIZE + 8, max_stack * (ICON_SIZE + 4) - 4)
		cell_height = ICON_SIZE
		width = ROW_LABEL_WIDTH + len(columns) * cell_width + max(0, len(columns) - 1) * CELL_GAP
		height = COLUMN_LABEL_HEIGHT + len(rows) * cell_height + max(0, len(rows) - 1) * CELL_GAP

		return {
			"columns": columns,
			"rows": rows,
			"cells": cells,
			"cellWidth": cell_width,
			"cellHeight": cell_height,
			"width": width,
			"height": height,
		}

	def master_groups_for_axis(self, axis_index):
		if axis_index is None or not self.font.axes:
			return [{"value": None, "label": "All", "sortValue": 0}]

		groups = []
		for master in self.font.masters:
			value = self.master_axis_value(master, axis_index)
			match = None
			for group in groups:
				if self.values_equal(group["value"], value):
					match = group
					break
			if match is None:
				match = {
					"value": value,
					"label": self.axis_value_label(axis_index, value),
					"sortValue": self.sortable_value(value),
				}
				groups.append(match)

		return sorted(groups, key=lambda group: group["sortValue"])

	def group_index_for_master(self, master, groups, axis_index):
		if axis_index is None:
			return 0
		value = self.master_axis_value(master, axis_index)
		for index, group in enumerate(groups):
			if self.values_equal(group["value"], value):
				return index
		return 0

	def master_icon_glyph_name(self, master):
		for attr in ("iconName", "iconGlyphName", "masterIconGlyphName"):
			value = getattr(master, attr, None)
			if value:
				return str(value)

		parameter_names = ("Master Icon Glyph Name", "MasterIconGlyphName")
		try:
			for parameter_name in parameter_names:
				value = master.customParameters[parameter_name]
				if value:
					return str(value)
		except Exception:
			pass

		try:
			for parameter in master.customParameters:
				if getattr(parameter, "name", None) in parameter_names and getattr(parameter, "active", True):
					value = getattr(parameter, "value", None)
					if value:
						return str(value)
		except Exception:
			pass

		return "n"

	def master_icon_layer(self, master):
		glyph_name = self.master_icon_glyph_name(master)
		try:
			glyph = self.font.glyphs[glyph_name]
		except Exception:
			glyph = None
		if glyph is None:
			return None

		try:
			layer = glyph.layers[master.id]
			if layer is not None:
				return layer
		except Exception:
			pass

		try:
			return glyph.layers[self.font.selectedFontMaster.id]
		except Exception:
			return None

	def layer_bezier_path(self, layer):
		if layer is None:
			return None

		for attr in ("completeBezierPath", "bezierPath"):
			try:
				path = getattr(layer, attr)
				if callable(path):
					path = path()
				if path is not None:
					return path.copy()
			except Exception:
				pass
		return None

	def master_icon_image(self, master, active):
		if NSImage is None or NSMakeSize is None or NSColor is None or NSBezierPath is None:
			return None

		image = NSImage.alloc().initWithSize_(NSMakeSize(ICON_SIZE, ICON_SIZE))
		image.lockFocus()
		try:
			if active:
				background = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.18, 0.62, 0.28, 1.0)
			else:
				background = NSColor.colorWithCalibratedWhite_alpha_(0.72, 1.0)
			background.setFill()
			rect = NSMakeRect(0, 0, ICON_SIZE, ICON_SIZE)
			NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 6, 6).fill()

			path = self.layer_bezier_path(self.master_icon_layer(master))
			if path is not None:
				self.draw_icon_path(path, active)
			else:
				self.draw_icon_text(self.compact_master_label(master), active)
		finally:
			image.unlockFocus()

		return image

	def draw_icon_path(self, path, active):
		if NSAffineTransform is None:
			return

		try:
			bounds = path.bounds()
			width = float(bounds.size.width)
			height = float(bounds.size.height)
			if width <= 0 or height <= 0:
				return

			margin = 8.0
			scale = min((ICON_SIZE - margin * 2.0) / width, (ICON_SIZE - margin * 2.0) / height)
			x = (ICON_SIZE - width * scale) * 0.5
			y = (ICON_SIZE - height * scale) * 0.5

			transform = NSAffineTransform.transform()
			transform.translateXBy_yBy_(x, y)
			transform.scaleBy_(scale)
			transform.translateXBy_yBy_(-float(bounds.origin.x), -float(bounds.origin.y))
			path.transformUsingAffineTransform_(transform)

			(NSColor.whiteColor() if active else NSColor.blackColor()).setFill()
			path.fill()
		except Exception:
			pass

	def draw_icon_text(self, text, active):
		if NSString is None or NSFont is None or NSMakeRect is None:
			return

		text = str(text or "?")[:4]
		try:
			attributes = {
				NSFontAttributeName: NSFont.boldSystemFontOfSize_(12),
				NSForegroundColorAttributeName: NSColor.whiteColor() if active else NSColor.blackColor(),
			}
			NSString.stringWithString_(text).drawInRect_withAttributes_(NSMakeRect(4, 13, ICON_SIZE - 8, 18), attributes)
		except Exception:
			pass

	def update_master_buttons(self):
		for master in self.font.masters:
			active = master.id in self.active_master_ids
			button = self.master_buttons.get(master.id)
			if button is None:
				continue

			image = self.master_icon_image(master, active)
			try:
				if image is not None:
					button.getNSButton().setImage_(image)
					button.getNSButton().setTitle_("")
				else:
					button.set(self.compact_master_label(master))
			except Exception:
				pass

	def compact_master_label(self, master):
		name = getattr(master, "name", None) or ""
		words = [word for word in name.replace("-", " ").replace("_", " ").split() if word]
		useful_words = [
			word
			for word in words
			if word.lower() not in ("regular", "upright", "normal", "roman")
		]
		if useful_words:
			return "".join([word[0] for word in useful_words[:3]]).upper()

		try:
			index = self.master_index(master) + 1
			return str(index)
		except Exception:
			return "M"

	def load_active_master_ids(self):
		all_ids = [master.id for master in self.font.masters]
		try:
			raw_value = self.font.userData.get(MASTER_SELECTION_KEY)
		except Exception:
			raw_value = None

		if raw_value:
			try:
				saved_ids = json.loads(raw_value) if isinstance(raw_value, str) else list(raw_value)
			except Exception:
				saved_ids = []
			active_ids = [master_id for master_id in saved_ids if master_id in all_ids]
			if active_ids:
				return set(active_ids)

		return set(all_ids)

	def save_active_master_ids(self):
		ordered_ids = [master.id for master in self.font.masters if master.id in self.active_master_ids]
		try:
			self.font.userData[MASTER_SELECTION_KEY] = json.dumps(ordered_ids)
		except Exception:
			pass

	def toggleMasterCallback(self, sender, master_id):
		if master_id in self.active_master_ids:
			if len(self.active_master_ids) <= 1:
				self.update_status("Keep at least one master active.")
				return
			self.active_master_ids.remove(master_id)
		else:
			self.active_master_ids.add(master_id)

		self.save_active_master_ids()
		self.update_master_buttons()
		self.update_status()

	def group_axis_items(self):
		items = [self.axis_label(axis) for axis in self.font.axes]
		return items or ["No axes"]

	def groupAxisCallback(self, sender):
		self.update_group_values()

	def groupValueCallback(self, sender):
		self.update_status()

	def update_group_values(self):
		if not self.font.axes:
			self.group_value_options = []
			self.w.groupValuePopup.setItems(["No values"])
			self.w.groupAxisPopup.enable(False)
			self.w.groupValuePopup.enable(False)
			return

		self.group_value_options = self.group_options_for_axis(self.selected_group_axis_index())
		items = [option["label"] for option in self.group_value_options]
		self.w.groupValuePopup.setItems(items or ["No values"])
		self.w.groupValuePopup.enable(bool(items))

	def selected_group_axis_index(self):
		try:
			return int(self.w.groupAxisPopup.get())
		except Exception:
			return 0

	def selected_group_option(self):
		if not self.group_value_options:
			return None
		try:
			index = int(self.w.groupValuePopup.get())
		except Exception:
			index = 0
		if index < 0 or index >= len(self.group_value_options):
			return None
		return self.group_value_options[index]

	def group_options_for_axis(self, axis_index):
		groups = []
		for master in self.font.masters:
			value = self.master_axis_value(master, axis_index)
			match = None
			for group in groups:
				if self.values_equal(group["value"], value):
					match = group
					break
			if match is None:
				match = {
					"value": value,
					"masterIds": [],
					"sortValue": self.sortable_value(value),
					"label": self.axis_value_label(axis_index, value),
				}
				groups.append(match)
			match["masterIds"].append(master.id)

		groups.sort(key=lambda group: group["sortValue"])
		for group in groups:
			group["label"] = "%s (%i)" % (group["label"], len(group["masterIds"]))
		return groups

	def axis_value_label(self, axis_index, value):
		axis = self.font.axes[axis_index]
		tag = (getattr(axis, "axisTag", None) or getattr(axis, "tag", None) or "").lower()
		name = (getattr(axis, "name", None) or "").lower()
		number = self.format_number(value)

		if tag == "wght" or name == "weight":
			weight_names = {
				100: "Thin",
				200: "ExtraLight",
				300: "Light",
				400: "Regular",
				500: "Medium",
				600: "SemiBold",
				700: "Bold",
				800: "ExtraBold",
				900: "Black",
			}
			try:
				weight_value = int(round(float(value)))
				if weight_value in weight_names:
					return "%s (%s)" % (weight_names[weight_value], number)
			except Exception:
				pass

		if tag == "slnt" or name == "slant" or "italic" in name:
			try:
				return ("Italic" if abs(float(value)) > 0.0001 else "Upright") + " (%s)" % number
			except Exception:
				pass

		if tag == "ital" or name == "italic":
			try:
				return ("Italic" if abs(float(value)) > 0.0001 else "Upright") + " (%s)" % number
			except Exception:
				pass

		if tag == "mono" or name == "mono" or "mono" in name:
			try:
				return ("Mono" if abs(float(value)) > 0.0001 else "Proportional") + " (%s)" % number
			except Exception:
				pass

		return number

	def format_number(self, value):
		try:
			value = float(value)
		except Exception:
			return str(value)
		if abs(value - round(value)) < 0.000001:
			return str(int(round(value)))
		return ("%.3f" % value).rstrip("0").rstrip(".")

	def values_equal(self, a, b):
		try:
			return abs(float(a) - float(b)) < 0.0001
		except Exception:
			return a == b

	def master_axis_value(self, master, axis_index):
		axis = self.font.axes[axis_index]
		value = self.axis_value_from_source(getattr(master, "axes", None), axis, axis_index)
		if value is None:
			value = self.axis_value_from_source(master, axis, axis_index)
		return self.sortable_value(value)

	def matching_group_master_ids(self):
		option = self.selected_group_option()
		if option is None:
			return set()
		return set(option["masterIds"])

	def apply_master_group(self, mode):
		group_ids = self.matching_group_master_ids()
		if not group_ids and mode != "all":
			self.update_status("No masters in that group.")
			return

		if mode == "only":
			next_ids = set(group_ids)
		elif mode == "narrow":
			next_ids = self.active_master_ids.intersection(group_ids)
			if not next_ids:
				self.update_status("No active masters match that group.")
				return
		elif mode == "add":
			next_ids = self.active_master_ids.union(group_ids)
		elif mode == "all":
			next_ids = set([master.id for master in self.font.masters])
		else:
			return

		if not next_ids:
			self.update_status("Keep at least one master active.")
			return

		self.active_master_ids = next_ids
		self.save_active_master_ids()
		self.update_master_buttons()
		self.update_status()

	def groupOnlyCallback(self, sender):
		self.apply_master_group("only")

	def groupNarrowCallback(self, sender):
		self.apply_master_group("narrow")

	def groupAddCallback(self, sender):
		self.apply_master_group("add")

	def groupAllCallback(self, sender):
		self.apply_master_group("all")

	def default_axis_rows(self):
		rows = []
		for index, axis in enumerate(self.font.axes):
			rows.append(
				{
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
			raw_value = Glyphs.defaults.get(AXIS_DEFAULTS_KEY)
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
					"direction": self.normalize_direction(row.get("direction")),
				}
			)

		try:
			Glyphs.defaults[AXIS_DEFAULTS_KEY] = json.dumps(rows)
			self.update_status("Saved sort as default.")
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

	def update_status(self, prefix=None):
		text = self.status_text()
		if prefix:
			text = "%s %s" % (prefix, text)
		self.w.status.set(text)

	def status_text(self):
		glyphs = self.selected_glyph_entries()
		active_count = len(self.active_master_ids)
		if not glyphs:
			return "Select glyphs. %i of %i masters active; axes only sort active layers." % (active_count, len(self.font.masters))
		return "%i selected glyph(s). %i of %i masters active." % (
			len(glyphs),
			active_count,
			len(self.font.masters),
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
		key = [self.axis_sort_value(layer, row) for row in axis_rows]
		key.extend([master_order, is_special, self.layer_label_key(layer)])
		return tuple(key)

	def layer_master_is_active(self, layer):
		master = self.master_for_layer(layer)
		return master is not None and master.id in self.active_master_ids

	def layers_for_glyph(self, glyph, axis_rows):
		layers = []

		for master in self.font.masters:
			if master.id not in self.active_master_ids:
				continue
			layer = glyph.layers[master.id]
			if layer is not None:
				layers.append(layer)

		for layer in glyph.layers:
			if not getattr(layer, "isSpecialLayer", False):
				continue
			if self.layer_master_is_active(layer):
				layers.append(layer)

		return sorted(layers, key=lambda layer: self.layer_sort_key(layer, axis_rows))

	def comparison_layers(self, entries, axis_rows):
		layers = []
		for glyph_index, entry in enumerate(entries):
			glyph, _reference_layer = entry
			layers.extend(self.layers_for_glyph(glyph, axis_rows))
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

		if not self.active_master_ids:
			Message(title=SCRIPT_NAME, message="Activate at least one master.")
			return

		layers = self.comparison_layers(entries, self.axis_rows())

		if not [layer for layer in layers if getattr(layer, "parent", None) is not None]:
			Message(title=SCRIPT_NAME, message="No matching layers found for the selected masters.")
			return

		tab = self.font.newTab()
		tab.layers = layers


MastersSideBySide()
