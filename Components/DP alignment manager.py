# MenuTitle: DP alignment manager
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Floating component auto-alignment matrix for the active glyph.

Rows are masters and columns are component slots. Green dots are auto-aligned
components; yellow dots are manually aligned components. Click a dot to toggle
that component in that master, or use the checked master rows for batch changes.
"""

import traceback

import vanilla
from GlyphsApp import Glyphs, Message

try:
	import objc
except Exception:
	objc = None

try:
	from GlyphsApp import UPDATEINTERFACE
except Exception:
	UPDATEINTERFACE = None

try:
	from AppKit import (
		NSApp,
		NSAttributedString,
		NSBezierPath,
		NSColor,
		NSFont,
		NSFontAttributeName,
		NSForegroundColorAttributeName,
		NSMakeRect,
		NSMakeSize,
		NSParagraphStyleAttributeName,
		NSScrollView,
		NSSize,
		NSTextAlignmentCenter,
		NSTextAlignmentLeft,
		NSTextAlignmentRight,
		NSView,
		NSFloatingWindowLevel,
		NSMutableParagraphStyle,
	)
except Exception:
	NSApp = None
	NSFloatingWindowLevel = 3


SCRIPT_NAME = "DP alignment manager"

LEFT_LABEL_WIDTH = 178
HEADER_HEIGHT = 46
ROW_HEIGHT = 30
CELL_WIDTH = 76
DOT_SIZE = 14
CHECK_SIZE = 12
MATRIX_RIGHT_PADDING = 18
MATRIX_BOTTOM_PADDING = 18


def make_color(red, green, blue, alpha=1.0):
	return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, alpha)


COLOR_BACKGROUND = make_color(0.985, 0.985, 0.975)
COLOR_GRID = make_color(0.84, 0.84, 0.82)
COLOR_GRID_LIGHT = make_color(0.91, 0.91, 0.89)
COLOR_TEXT = make_color(0.14, 0.14, 0.13)
COLOR_MUTED = make_color(0.44, 0.44, 0.42)
COLOR_ROW_SELECTED = make_color(0.87, 0.93, 1.0)
COLOR_AUTO = make_color(0.0, 0.62, 0.32)
COLOR_MANUAL = make_color(0.94, 0.66, 0.08)
COLOR_EMPTY = make_color(0.77, 0.77, 0.74)
COLOR_CURRENT = make_color(0.18, 0.36, 0.74)


AlignmentMatrixView = None
if objc is not None:
	try:
		AlignmentMatrixView = objc.lookUpClass("DPAlignmentMatrixView")
	except Exception:
		AlignmentMatrixView = None

if AlignmentMatrixView is None:
	class DPAlignmentMatrixView(NSView):
		def isFlipped(self):
			return True
	
		def draw_text(self, text, rect, color=None, font=None, alignment=NSTextAlignmentLeft):
			if color is None:
				color = COLOR_TEXT
			if font is None:
				font = NSFont.systemFontOfSize_(11)
	
			style = NSMutableParagraphStyle.alloc().init()
			style.setAlignment_(alignment)
			style.setLineBreakMode_(4)
			attributes = {
				NSFontAttributeName: font,
				NSForegroundColorAttributeName: color,
				NSParagraphStyleAttributeName: style,
			}
			string = NSAttributedString.alloc().initWithString_attributes_(unicode_string(text), attributes)
			string.drawInRect_(rect)
	
		def drawRect_(self, rect):
			controller = getattr(self, "controller", None)
			if controller is None:
				return
	
			rows = controller.matrix_rows
			column_count = controller.column_count
			width = max(self.bounds().size.width, LEFT_LABEL_WIDTH + column_count * CELL_WIDTH + MATRIX_RIGHT_PADDING)
			height = max(self.bounds().size.height, HEADER_HEIGHT + len(rows) * ROW_HEIGHT + MATRIX_BOTTOM_PADDING)
	
			COLOR_BACKGROUND.setFill()
			NSBezierPath.fillRect_(NSMakeRect(0, 0, width, height))
	
			header_font = NSFont.systemFontOfSize_(10)
			row_font = NSFont.systemFontOfSize_(11)
			bold_font = NSFont.boldSystemFontOfSize_(11)
	
			self.draw_text("Masters", NSMakeRect(16, 16, LEFT_LABEL_WIDTH - 30, 18), COLOR_MUTED, header_font)
	
			for column_index in range(column_count):
				x = LEFT_LABEL_WIDTH + column_index * CELL_WIDTH
				COLOR_GRID_LIGHT.setStroke()
				line = NSBezierPath.bezierPath()
				line.moveToPoint_((x, 0))
				line.lineToPoint_((x, height))
				line.stroke()
	
				label = controller.component_label(column_index)
				self.draw_text(label, NSMakeRect(x + 5, 10, CELL_WIDTH - 10, 28), COLOR_MUTED, header_font, NSTextAlignmentCenter)
	
			COLOR_GRID.setStroke()
			header_line = NSBezierPath.bezierPath()
			header_line.moveToPoint_((0, HEADER_HEIGHT))
			header_line.lineToPoint_((width, HEADER_HEIGHT))
			header_line.stroke()
	
			for row_index, row in enumerate(rows):
				y = HEADER_HEIGHT + row_index * ROW_HEIGHT
				master = row.get("master")
				master_id = row.get("master_id")
				selected = master_id in controller.selected_master_ids
	
				if selected:
					COLOR_ROW_SELECTED.setFill()
					NSBezierPath.fillRect_(NSMakeRect(0, y, width, ROW_HEIGHT))
	
				if master_id == controller.current_master_id:
					COLOR_CURRENT.setFill()
					NSBezierPath.fillRect_(NSMakeRect(0, y, 4, ROW_HEIGHT))
	
				self.draw_checkbox(14, y + 9, selected)
	
				master_name = getattr(master, "name", None) or "Master"
				name_color = COLOR_TEXT if row.get("layer") is not None else COLOR_MUTED
				self.draw_text(master_name, NSMakeRect(34, y + 7, LEFT_LABEL_WIDTH - 42, 17), name_color, bold_font if master_id == controller.current_master_id else row_font)
	
				for column_index in range(column_count):
					x = LEFT_LABEL_WIDTH + column_index * CELL_WIDTH
					component = controller.component_at(row_index, column_index)
					self.draw_dot(x + (CELL_WIDTH - DOT_SIZE) * 0.5, y + (ROW_HEIGHT - DOT_SIZE) * 0.5, component)
	
				COLOR_GRID_LIGHT.setStroke()
				line = NSBezierPath.bezierPath()
				line.moveToPoint_((0, y + ROW_HEIGHT))
				line.lineToPoint_((width, y + ROW_HEIGHT))
				line.stroke()
	
		def draw_checkbox(self, x, y, checked):
			box = NSMakeRect(x, y, CHECK_SIZE, CHECK_SIZE)
			path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(box, 2, 2)
			NSColor.whiteColor().setFill()
			path.fill()
			(COLOR_CURRENT if checked else COLOR_EMPTY).setStroke()
			path.stroke()
	
			if checked:
				COLOR_CURRENT.setFill()
				NSBezierPath.fillRect_(NSMakeRect(x + 2, y + 2, CHECK_SIZE - 4, CHECK_SIZE - 4))
	
		def draw_dot(self, x, y, component):
			rect = NSMakeRect(x, y, DOT_SIZE, DOT_SIZE)
	
			if component is None:
				COLOR_EMPTY.setStroke()
				path = NSBezierPath.bezierPathWithOvalInRect_(rect)
				path.stroke()
				return
	
			color = COLOR_AUTO if component_is_auto_aligned(component) else COLOR_MANUAL
			color.setFill()
			path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 3, 3)
			path.fill()
	
			make_color(0.0, 0.0, 0.0, 0.16).setStroke()
			path.stroke()
	
		def mouseDown_(self, event):
			controller = getattr(self, "controller", None)
			if controller is None:
				return
	
			point = self.convertPoint_fromView_(event.locationInWindow(), None)
			x = point.x
			y = point.y
	
			if y < HEADER_HEIGHT:
				return
	
			row_index = int((y - HEADER_HEIGHT) // ROW_HEIGHT)
			if row_index < 0 or row_index >= len(controller.matrix_rows):
				return
	
			row_y = HEADER_HEIGHT + row_index * ROW_HEIGHT
			if 10 <= x <= 30 and row_y <= y <= row_y + ROW_HEIGHT:
				controller.toggle_master_selection(row_index)
				return
	
			if x < LEFT_LABEL_WIDTH:
				return

			column_index = int((x - LEFT_LABEL_WIDTH) // CELL_WIDTH)
			controller.toggle_component(row_index, column_index)

	AlignmentMatrixView = DPAlignmentMatrixView


def unicode_string(value):
	try:
		return unicode(value)
	except NameError:
		return str(value)


def component_is_auto_aligned(component):
	try:
		return bool(component.automaticAlignment)
	except Exception:
		pass
	try:
		return getattr(component, "alignment", 0) != -1
	except Exception:
		return False


def set_component_auto_alignment(component, value):
	value = bool(value)
	set_success = False

	try:
		component.automaticAlignment = value
		set_success = True
	except Exception:
		pass

	try:
		if value and getattr(component, "alignment", 0) == -1:
			component.alignment = 0
		elif not value:
			component.alignment = -1
		set_success = True
	except Exception:
		pass

	if not set_success:
		raise RuntimeError("Could not set component auto alignment")


class DPAlignmentManager(object):
	def __init__(self):
		self.font = Glyphs.font
		if self.font is None:
			Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
			return

		self.current_glyph = None
		self.current_master_id = getattr(self.font.selectedFontMaster, "id", None)
		self.matrix_rows = []
		self.column_count = 0
		self.selected_master_ids = set([self.current_master_id]) if self.current_master_id else set()
		self.callback_registered = False
		self.interface_callback = self.interface_update_callback
		self.updating = False

		self.w = vanilla.FloatingWindow((690, 470), SCRIPT_NAME, minSize=(480, 300))
		try:
			self.w.bind("close", self.close_callback)
		except Exception:
			pass

		y = 14
		self.w.glyphLabel = vanilla.TextBox((16, y, -148, 20), "", sizeStyle="small")
		self.w.refreshButton = vanilla.Button((-132, y - 2, 116, 22), "Refresh", callback=self.refresh_callback, sizeStyle="small")

		y += 30
		self.w.watchActiveGlyph = vanilla.CheckBox((16, y, 168, 20), "Follow active glyph", value=True, callback=self.watch_callback, sizeStyle="small")
		self.w.selectCurrentButton = vanilla.Button((192, y - 2, 100, 22), "Current", callback=self.select_current_callback, sizeStyle="small")
		self.w.selectAllButton = vanilla.Button((298, y - 2, 70, 22), "All", callback=self.select_all_callback, sizeStyle="small")
		self.w.selectNoneButton = vanilla.Button((374, y - 2, 70, 22), "None", callback=self.select_none_callback, sizeStyle="small")

		self.w.autoOnButton = vanilla.Button((-226, y - 2, 66, 22), "Auto", callback=self.auto_on_callback, sizeStyle="small")
		self.w.autoOffButton = vanilla.Button((-154, y - 2, 66, 22), "Manual", callback=self.auto_off_callback, sizeStyle="small")
		self.w.matchCurrentButton = vanilla.Button((-82, y - 2, 66, 22), "Match", callback=self.match_current_callback, sizeStyle="small")

		y += 31
		self.matrix_view = AlignmentMatrixView.alloc().initWithFrame_(NSMakeRect(0, 0, 640, 260))
		self.matrix_view.controller = self
		self.w.matrixScroll = vanilla.ScrollView((16, y, -16, -56), self.matrix_view, hasHorizontalScroller=True, hasVerticalScroller=True)

		self.w.legend = vanilla.TextBox((16, -44, 270, 18), "Green: auto aligned    Yellow: manual    Empty: no component", sizeStyle="small")
		self.w.status = vanilla.TextBox((300, -44, -16, 18), "", sizeStyle="small")

		self.register_callback()
		self.refresh()
		self.w.open()
		self.float_window()

	def float_window(self):
		try:
			window = self.w.getNSWindow()
			window.setLevel_(NSFloatingWindowLevel)
			window.setHidesOnDeactivate_(False)
			window.makeKeyAndOrderFront_(None)
		except Exception:
			pass

		try:
			if NSApp is not None:
				NSApp.activateIgnoringOtherApps_(True)
		except Exception:
			pass

	def register_callback(self):
		if UPDATEINTERFACE is None:
			return
		try:
			Glyphs.addCallback(self.interface_callback, UPDATEINTERFACE)
			self.callback_registered = True
		except Exception:
			self.callback_registered = False

	def close_callback(self, sender):
		if self.callback_registered:
			try:
				Glyphs.removeCallback(self.interface_callback)
			except Exception:
				pass
			self.callback_registered = False

	def interface_update_callback(self, sender=None):
		if self.updating:
			return
		try:
			if not self.w.watchActiveGlyph.get():
				return
		except Exception:
			return

		glyph = self.active_glyph()
		master_id = getattr(getattr(self.font, "selectedFontMaster", None), "id", None)
		if glyph is not self.current_glyph or master_id != self.current_master_id:
			self.refresh()

	def active_layer(self):
		tab = getattr(self.font, "currentTab", None)
		if tab is not None:
			try:
				layer = tab.activeLayer()
				if layer is not None:
					return layer
			except Exception:
				pass
			try:
				layer = tab.activeLayer
				if layer is not None:
					return layer
			except Exception:
				pass

		try:
			selected_layers = list(self.font.selectedLayers or [])
			if selected_layers:
				return selected_layers[0]
		except Exception:
			pass
		return None

	def active_glyph(self):
		layer = self.active_layer()
		if layer is None:
			return None
		return getattr(layer, "parent", None)

	def master_layer(self, glyph, master):
		try:
			return glyph.layers[master.id]
		except Exception:
			return None

	def refresh_callback(self, sender):
		self.refresh(force=True)

	def watch_callback(self, sender):
		if sender.get():
			self.refresh(force=True)

	def refresh(self, force=False):
		self.font = Glyphs.font
		if self.font is None:
			return

		glyph = self.active_glyph()
		self.current_glyph = glyph
		self.current_master_id = getattr(getattr(self.font, "selectedFontMaster", None), "id", None)

		if glyph is None:
			self.matrix_rows = []
			self.column_count = 0
			self.w.glyphLabel.set("No active glyph")
			self.w.status.set("Select a glyph in Font View or Edit View.")
			self.update_matrix_size()
			return

		valid_master_ids = set(getattr(master, "id", None) for master in self.font.masters)
		self.selected_master_ids = set(master_id for master_id in self.selected_master_ids if master_id in valid_master_ids)
		if not self.selected_master_ids and self.current_master_id:
			self.selected_master_ids.add(self.current_master_id)

		rows = []
		column_count = 0
		for master in self.font.masters:
			layer = self.master_layer(glyph, master)
			components = list(getattr(layer, "components", []) or []) if layer is not None else []
			column_count = max(column_count, len(components))
			rows.append(
				{
					"master": master,
					"master_id": getattr(master, "id", None),
					"layer": layer,
					"components": components,
				}
			)

		self.matrix_rows = rows
		self.column_count = column_count
		self.update_labels()
		self.update_matrix_size()

	def update_labels(self):
		glyph_name = getattr(self.current_glyph, "name", None) or "No active glyph"
		component_count = self.column_count
		selected_count = len(self.selected_master_ids)
		master_count = len(self.matrix_rows)
		self.w.glyphLabel.set("Glyph: %s" % glyph_name)
		if component_count:
			self.w.status.set("%i component slot%s, %i/%i master%s selected" % (
				component_count,
				"" if component_count == 1 else "s",
				selected_count,
				master_count,
				"" if master_count == 1 else "s",
			))
		else:
			self.w.status.set("No components in this glyph.")

	def update_matrix_size(self):
		width = LEFT_LABEL_WIDTH + max(1, self.column_count) * CELL_WIDTH + MATRIX_RIGHT_PADDING
		height = HEADER_HEIGHT + max(1, len(self.matrix_rows)) * ROW_HEIGHT + MATRIX_BOTTOM_PADDING
		try:
			self.matrix_view.setFrameSize_(NSMakeSize(width, height))
		except Exception:
			self.matrix_view.setFrameSize_(NSSize(width, height))
		self.matrix_view.setNeedsDisplay_(True)

	def component_label(self, column_index):
		names = []
		for row in self.matrix_rows:
			components = row.get("components") or []
			if column_index < len(components):
				name = getattr(components[column_index], "componentName", None) or "component"
				if name not in names:
					names.append(name)
		if not names:
			return "#%i" % (column_index + 1)
		if len(names) == 1:
			return "#%i %s" % (column_index + 1, names[0])
		return "#%i mixed" % (column_index + 1)

	def component_at(self, row_index, column_index):
		if row_index < 0 or row_index >= len(self.matrix_rows):
			return None
		components = self.matrix_rows[row_index].get("components") or []
		if column_index < 0 or column_index >= len(components):
			return None
		return components[column_index]

	def toggle_master_selection(self, row_index):
		if row_index < 0 or row_index >= len(self.matrix_rows):
			return
		master_id = self.matrix_rows[row_index].get("master_id")
		if master_id in self.selected_master_ids:
			self.selected_master_ids.remove(master_id)
		elif master_id is not None:
			self.selected_master_ids.add(master_id)
		self.update_labels()
		self.matrix_view.setNeedsDisplay_(True)

	def selected_rows(self):
		return [row for row in self.matrix_rows if row.get("master_id") in self.selected_master_ids]

	def select_current_callback(self, sender):
		self.selected_master_ids = set([self.current_master_id]) if self.current_master_id else set()
		self.update_labels()
		self.matrix_view.setNeedsDisplay_(True)

	def select_all_callback(self, sender):
		self.selected_master_ids = set(row.get("master_id") for row in self.matrix_rows if row.get("master_id") is not None)
		self.update_labels()
		self.matrix_view.setNeedsDisplay_(True)

	def select_none_callback(self, sender):
		self.selected_master_ids = set()
		self.update_labels()
		self.matrix_view.setNeedsDisplay_(True)

	def auto_on_callback(self, sender):
		self.set_selected_masters(True)

	def auto_off_callback(self, sender):
		self.set_selected_masters(False)

	def match_current_callback(self, sender):
		self.match_current_master()

	def toggle_component(self, row_index, column_index):
		component = self.component_at(row_index, column_index)
		if component is None:
			return
		row = self.matrix_rows[row_index]
		layer = row.get("layer")
		new_value = not component_is_auto_aligned(component)
		label = "enabled" if new_value else "disabled"
		self.perform_alignment_change(
			"Toggle component auto alignment",
			lambda: self.set_component_on_layer(layer, component, new_value),
			"Auto alignment %s for %s component #%i in %s." % (
				label,
				getattr(self.current_glyph, "name", "glyph"),
				column_index + 1,
				getattr(row.get("master"), "name", "master"),
			),
		)

	def set_selected_masters(self, value):
		rows = self.selected_rows()
		if not rows:
			Message(title=SCRIPT_NAME, message="Check at least one master row first.")
			return

		label = "Auto alignment enabled" if value else "Auto alignment disabled"

		def change():
			for row in rows:
				layer = row.get("layer")
				if layer is None:
					continue
				for component in row.get("components") or []:
					self.set_component_on_layer(layer, component, value, sync=False)
				self.sync_layer(layer)

		self.perform_alignment_change(
			"Batch component auto alignment",
			change,
			"%s on %i selected master%s." % (label, len(rows), "" if len(rows) == 1 else "s"),
		)

	def match_current_master(self):
		source_row = None
		for row in self.matrix_rows:
			if row.get("master_id") == self.current_master_id:
				source_row = row
				break
		if source_row is None:
			Message(title=SCRIPT_NAME, message="No current master row found.")
			return

		source_components = source_row.get("components") or []
		if not source_components:
			Message(title=SCRIPT_NAME, message="The current master has no components to match.")
			return

		target_rows = [row for row in self.selected_rows() if row is not source_row]
		if not target_rows:
			Message(title=SCRIPT_NAME, message="Check one or more other master rows to match.")
			return

		source_states = [component_is_auto_aligned(component) for component in source_components]

		def change():
			for row in target_rows:
				layer = row.get("layer")
				if layer is None:
					continue
				for index, component in enumerate(row.get("components") or []):
					if index >= len(source_states):
						continue
					self.set_component_on_layer(layer, component, source_states[index], sync=False)
				self.sync_layer(layer)

		self.perform_alignment_change(
			"Match component auto alignment",
			change,
			"Matched alignment states from the current master to %i master%s." % (
				len(target_rows),
				"" if len(target_rows) == 1 else "s",
			),
		)

	def set_component_on_layer(self, layer, component, value, sync=True):
		set_component_auto_alignment(component, value)
		if sync:
			self.sync_layer(layer)

	def sync_layer(self, layer):
		if layer is None:
			return
		try:
			layer.doAlignComponents()
		except Exception:
			pass
		try:
			layer.syncMetrics()
		except Exception:
			pass

	def perform_alignment_change(self, undo_name, change_function, status_text):
		if self.current_glyph is None:
			return

		undo_manager = None
		success = True
		self.updating = True
		try:
			try:
				undo_manager = self.font.parent.undoManager()
				undo_manager.beginUndoGrouping()
				try:
					undo_manager.setActionName_(undo_name)
				except Exception:
					pass
			except Exception:
				undo_manager = None

			try:
				self.font.disableUpdateInterface()
			except Exception:
				pass

			change_function()
		except Exception:
			success = False
			print(traceback.format_exc())
			Glyphs.showMacroWindow()
			Message(title=SCRIPT_NAME, message="Something went wrong. See the Macro window for details.")
		finally:
			try:
				self.font.enableUpdateInterface()
			except Exception:
				pass
			if undo_manager is not None:
				try:
					undo_manager.endUndoGrouping()
				except Exception:
					pass
			self.updating = False

		try:
			Glyphs.redraw()
		except Exception:
			pass
		self.refresh(force=True)
		if success:
			self.w.status.set(status_text)
		else:
			self.w.status.set("Change failed. See the Macro window.")


try:
	DP_ALIGNMENT_MANAGER.close_callback(None)
	try:
		DP_ALIGNMENT_MANAGER.w.close()
	except Exception:
		pass
except Exception:
	pass

DP_ALIGNMENT_MANAGER = DPAlignmentManager()
