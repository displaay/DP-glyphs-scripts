# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import vanilla

from AppKit import NSMakeRect
from GlyphsApp import Glyphs
from axis_utils import format_axis_value, effective_axis_count
from preview_view import PreviewCanvasView


class VFPDockPanel(object):
	PREVIEW_HEIGHT = 100
	ROW_HEIGHT = 30
	PADDING = 12
	MIN_WIDTH = 480

	def __init__(self, controller, drawer):
		self.controller = controller
		self.drawer = drawer
		self.w = None
		self.preview_view = None
		self.axis_controls = []
		self._built_axis_count = -1
		self._built_height = 0
		controller.add_listener(self.refresh)

	def _axis_count(self):
		font = self.controller.font
		if font is None:
			return 1
		return max(effective_axis_count(font), 1)

	def window_height(self):
		return (
			self.PADDING
			+ self.PREVIEW_HEIGHT
			+ 10
			+ 20
			+ self._axis_count() * self.ROW_HEIGHT
			+ self.PADDING
		)

	def open(self, force_rebuild=False):
		try:
			if self.w is not None and not force_rebuild:
				ns_window = self.w.getNSWindow()
				if ns_window is not None:
					self.w.open()
					self.reposition()
					self.refresh()
					return
			self.close()
			self.build_window()
			self.w.open()
			self.reposition()
			self.refresh()
		except Exception:
			self.close()

	def close(self):
		self.preview_view = None
		self.axis_controls = []
		self._built_axis_count = -1
		self._built_height = 0
		if self.w is None:
			return
		try:
			ns_window = self.w.getNSWindow()
			if ns_window is not None:
				self.w.close()
		except Exception:
			pass
		self.w = None

	def _glyphs_main_window(self):
		font = self.controller.font or Glyphs.font
		if font is not None:
			try:
				document = font.parent
				if document is not None:
					controller = document.windowController()
					if controller is not None:
						window = controller.window()
						if window is not None:
							return window
			except Exception:
				pass
		try:
			document = Glyphs.currentDocument
			if document is not None:
				return document.windowController().window()
		except Exception:
			pass
		return None

	def _target_width(self):
		main_window = self._glyphs_main_window()
		if main_window is None:
			return 720
		try:
			return max(self.MIN_WIDTH, main_window.contentView().frame().size.width)
		except Exception:
			return 720

	def reposition(self):
		if self.w is None:
			return
		try:
			ns_window = self.w.getNSWindow()
			main_window = self._glyphs_main_window()
			if ns_window is None or main_window is None:
				return
			content_frame = main_window.contentView().frame()
			screen_frame = main_window.convertRectToScreen_(content_frame)
			content_height = self._built_height or self.window_height()
			win_width = max(self.MIN_WIDTH, content_frame.size.width)
			content_top = screen_frame.origin.y + screen_frame.size.height
			content_rect = NSMakeRect(screen_frame.origin.x, content_top - content_height, win_width, content_height)
			frame_rect = ns_window.frameRectForContentRect_(content_rect)
			ns_window.setFrame_display_(frame_rect, True)
			try:
				self.w.resize(win_width, content_height)
			except Exception:
				pass
			try:
				ns_window.setMaxSize_((100000.0, float(content_height)))
				ns_window.setMinSize_((float(self.MIN_WIDTH), float(content_height)))
			except Exception:
				pass
			try:
				from AppKit import NSFloatingWindowLevel
				ns_window.setLevel_(NSFloatingWindowLevel)
			except Exception:
				pass
		except Exception:
			pass

	def build_window(self):
		axis_count = self._axis_count()
		width = self._target_width()
		self._built_axis_count = axis_count

		self.w = vanilla.FloatingWindow(
			(120, 120, width, 400),
			"VF Preview",
			minSize=(self.MIN_WIDTH, 200),
		)

		# Match slider_panel.py: y starts at 12 and increases (Glyphs vanilla).
		y = 12
		self.preview_view = PreviewCanvasView.alloc().initWithFrame_(
			NSMakeRect(0, 0, max(100, width - 24), self.PREVIEW_HEIGHT)
		)
		self.preview_view.setController_(self.controller)
		self.preview_view.drawer = self.drawer
		self.w.previewGroup = vanilla.Group((12, y, -12, self.PREVIEW_HEIGHT))
		self.w.previewGroup.getNSView().addSubview_(self.preview_view)
		y += self.PREVIEW_HEIGHT + 10

		self.w.axesLabel = vanilla.TextBox((12, y, 120, 16), "Axes", sizeStyle="small")
		y += 20

		self.axis_controls = []
		for index in range(axis_count):
			label = vanilla.TextBox((12, y + 6, 78, 18), "Axis", sizeStyle="small")
			slider = vanilla.Slider(
				(94, y + 2, 104, 22),
				callback=self.sliderCallback,
				value=0.5,
			)
			value_field = vanilla.EditText((204, y, -12, 22), "", callback=self.valueFieldCallback)
			self.axis_controls.append({
				"label": label,
				"slider": slider,
				"valueField": value_field,
			})
			y += self.ROW_HEIGHT

		self._built_height = y + 12
		try:
			self.w.resize(width, self._built_height)
		except Exception:
			pass

	def refresh(self):
		if self.w is None:
			return
		font = self.controller.font
		if font is None:
			return

		rows = self.controller.axis_rows()
		if len(rows) != self._built_axis_count:
			self.open(force_rebuild=True)
			return

		for control, row in zip(self.axis_controls, rows):
			control["label"].set(row["name"])
			minimum = row["minimum"]
			maximum = row["maximum"]
			value = row["value"]
			if row["binary"]:
				control["slider"].enable(False)
			else:
				control["slider"].enable(True)
				if abs(maximum - minimum) < 0.0001:
					slider_value = 0.5
				else:
					slider_value = (value - minimum) / (maximum - minimum)
				control["slider"].set(max(0.0, min(1.0, slider_value)))
			control["valueField"].set(format_axis_value(value, bool(self.controller.pref("roundValues"))))

		if self.preview_view is not None:
			self.preview_view.setNeedsDisplay_(True)

	def row_for_sender(self, sender):
		for control in self.axis_controls:
			if sender in (control["slider"], control["valueField"]):
				return control
		return None

	def sliderCallback(self, sender):
		control = self.row_for_sender(sender)
		if control is None:
			return
		index = self.axis_controls.index(control)
		row = self.controller.axis_rows()[index]
		value = row["minimum"] + sender.get() * (row["maximum"] - row["minimum"])
		self.controller.set_axis_value(row["axisId"], value)

	def valueFieldCallback(self, sender):
		control = self.row_for_sender(sender)
		if control is None:
			return
		index = self.axis_controls.index(control)
		row = self.controller.axis_rows()[index]
		text = sender.get().strip()
		if not text:
			return
		try:
			value = float(text)
		except ValueError:
			return
		self.controller.set_axis_value(row["axisId"], value)
