# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import vanilla

from AppKit import NSMakeRect
from GlyphsApp import Glyphs
from axis_utils import format_axis_value, effective_axis_count
from preview_view import PreviewCanvasView


class SplitVFPanel(object):
	PREVIEW_HEIGHT = 80
	ROW_HEIGHT = 30
	PADDING = 12
	MIN_WIDTH = 480
	AXES_WIDTH = 320

	def __init__(self, controller, drawer):
		self.controller = controller
		self.drawer = drawer
		self.preview_w = None
		self.axes_w = None
		self.preview_view = None
		self.axis_controls = []
		self._built_axis_count = -1
		self._preview_height = 0
		self._axes_height = 0
		self._preview_width = self.MIN_WIDTH
		self._syncing_ui = False
		controller.add_listener(self.refresh)

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

	def _preview_width_target(self):
		main_window = self._glyphs_main_window()
		if main_window is None:
			return self.MIN_WIDTH
		try:
			return max(self.MIN_WIDTH, main_window.contentView().frame().size.width)
		except Exception:
			return self.MIN_WIDTH

	def preview_height(self):
		return self.PADDING * 2 + self.PREVIEW_HEIGHT

	def axes_height(self, axis_count):
		return self.PADDING * 2 + 16 + 20 + axis_count * self.ROW_HEIGHT

	def open(self, force_rebuild=False):
		try:
			if self.preview_w is not None and self.axes_w is not None and not force_rebuild:
				if self.preview_w.getNSWindow() is not None and self.axes_w.getNSWindow() is not None:
					self.preview_w.open()
					self.axes_w.open()
					self.reposition()
					self.refresh()
					return
			self.close()
			self.build_windows()
			self.preview_w.open()
			self.axes_w.open()
			self.reposition()
			self.refresh()
			try:
				from AppKit import NSFloatingWindowLevel
				for window in (self.preview_w, self.axes_w):
					ns_window = window.getNSWindow()
					if ns_window is not None:
						ns_window.setLevel_(NSFloatingWindowLevel)
				axes_ns = self.axes_w.getNSWindow()
				if axes_ns is not None:
					axes_ns.orderFrontRegardless()
					axes_ns.makeKeyAndOrderFront_(None)
			except Exception:
				pass
		except Exception:
			self.close()

	def close(self):
		self.preview_view = None
		self.axis_controls = []
		self._built_axis_count = -1
		for window in (self.preview_w, self.axes_w):
			if window is None:
				continue
			try:
				ns_window = window.getNSWindow()
				if ns_window is not None:
					window.close()
			except Exception:
				pass
		self.preview_w = None
		self.axes_w = None

	def _build_axes_window(self, axis_count):
		height = self._axes_height
		self.axes_w = vanilla.FloatingWindow(
			(self.AXES_WIDTH, height),
			"VF Preview Axes",
			minSize=(self.AXES_WIDTH, height),
		)

		y = height - self.PADDING
		y -= 16
		self.axes_w.axesLabel = vanilla.TextBox((12, y, 120, 16), "Axes", sizeStyle="small")
		y -= 20

		self.axis_controls = []
		inner_width = self.AXES_WIDTH - 24
		for index in range(axis_count):
			y -= self.ROW_HEIGHT
			row_key = "axisRow%i" % index
			row = vanilla.Group((12, y, inner_width, self.ROW_HEIGHT))
			setattr(self.axes_w, row_key, row)
			row.label = vanilla.TextBox((0, 6, 78, 18), "Axis", sizeStyle="small")
			row.slider = vanilla.Slider(
				(82, 2, 104, 22),
				callback=self.sliderCallback,
				value=0.5,
				minValue=0,
				maxValue=1,
				continuous=True,
			)
			row.valueField = vanilla.EditText((192, 0, 80, 22), "", callback=self.valueFieldCallback)
			try:
				row.slider.getNSView().setContinuous_(True)
			except Exception:
				pass
			self.axis_controls.append({
				"label": row.label,
				"slider": row.slider,
				"valueField": row.valueField,
			})

	def build_windows(self):
		font = self.controller.font
		axis_count = max(effective_axis_count(font), 1 if font is None else 0)
		self._built_axis_count = axis_count
		preview_width = int(self._preview_width_target())
		self._preview_width = preview_width
		self._preview_height = self.preview_height()
		self._axes_height = self.axes_height(axis_count)

		self.preview_w = vanilla.FloatingWindow(
			(preview_width, self._preview_height),
			"VF Preview",
			minSize=(self.MIN_WIDTH, self._preview_height),
			maxSize=(100000, self._preview_height),
		)
		inner_width = max(200, preview_width - 24)
		self.preview_view = PreviewCanvasView.alloc().initWithFrame_(
			NSMakeRect(0, 0, inner_width, self.PREVIEW_HEIGHT)
		)
		self.preview_view.setController_(self.controller)
		self.preview_view.drawer = self.drawer
		self.preview_w.previewGroup = vanilla.Group((12, 12, inner_width, self.PREVIEW_HEIGHT))
		self.preview_w.previewGroup.getNSView().addSubview_(self.preview_view)

		self._build_axes_window(axis_count)

	def reposition(self):
		if self.preview_w is None or self.axes_w is None:
			return
		try:
			main_window = self._glyphs_main_window()
			preview_ns = self.preview_w.getNSWindow()
			axes_ns = self.axes_w.getNSWindow()
			if main_window is None or preview_ns is None or axes_ns is None:
				return
			content_frame = main_window.contentView().frame()
			screen_frame = main_window.convertRectToScreen_(content_frame)
			content_top = screen_frame.origin.y + screen_frame.size.height

			preview_rect = NSMakeRect(
				screen_frame.origin.x,
				content_top - self._preview_height,
				self._preview_width,
				self._preview_height,
			)
			preview_frame = preview_ns.frameRectForContentRect_(preview_rect)
			preview_ns.setFrame_display_(preview_frame, True)

			preview_window_frame = preview_ns.frame()
			axes_window_frame = axes_ns.frame()
			axes_x = preview_window_frame.origin.x
			axes_y = preview_window_frame.origin.y - axes_window_frame.size.height
			axes_ns.setFrameOrigin_((axes_x, axes_y))
			try:
				self.axes_w.resize(self.AXES_WIDTH, self._axes_height)
				axes_ns.setContentSize_((float(self.AXES_WIDTH), float(self._axes_height)))
			except Exception:
				pass
		except Exception:
			pass

	def _set_slider_normalized(self, slider_control, normalized_value):
		value = max(0.0, min(1.0, float(normalized_value)))
		try:
			slider_control.set(value)
		except Exception:
			pass
		try:
			ns_slider = slider_control.getNSView()
			if ns_slider is not None:
				ns_slider.setMinValue_(0.0)
				ns_slider.setMaxValue_(1.0)
				ns_slider.setContinuous_(True)
				ns_slider.setDoubleValue_(value)
				ns_slider.setNeedsDisplay_(True)
		except Exception:
			pass

	def refresh_preview_only(self, immediate=False):
		if self.preview_view is not None:
			self.preview_view.setNeedsDisplay_(True)
			if immediate:
				try:
					self.preview_view.displayIfNeeded()
				except Exception:
					pass

	def invalidate_preview_cache(self):
		if self.preview_view is not None:
			try:
				self.preview_view.invalidatePreviewCache()
			except Exception:
				pass

	def refresh(self):
		if self.preview_w is None or self.axes_w is None:
			return
		font = self.controller.font
		if font is None:
			return

		rows = self.controller.axis_rows()
		if len(rows) != self._built_axis_count:
			self.open(force_rebuild=True)
			return

		self._syncing_ui = True
		try:
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
					self._set_slider_normalized(control["slider"], slider_value)
				control["valueField"].set(
					format_axis_value(value, bool(self.controller.pref("roundValues")))
				)
		finally:
			self._syncing_ui = False

		if self.preview_view is not None:
			self.preview_view.setNeedsDisplay_(True)

	def _update_dragged_value_field(self, control, value):
		control["valueField"].set(
			format_axis_value(value, bool(self.controller.pref("roundValues")))
		)

	def sliderCallback(self, sender):
		if self._syncing_ui:
			return
		control = self.row_for_sender(sender)
		if control is None:
			return
		index = self.axis_controls.index(control)
		row = self.controller.axis_rows()[index]
		normalized = sender.get()
		value = row["minimum"] + normalized * (row["maximum"] - row["minimum"])
		self.controller.set_axis_value(row["axisId"], value, notify="preview")
		stored_value = self.controller.axis_values.get(row["axisId"], value)
		self._update_dragged_value_field(control, stored_value)
		self.controller.schedule_ui_flush()

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
		self.controller._cancel_ui_flush()
		self.controller.set_axis_value(row["axisId"], value)

	def row_for_sender(self, sender):
		for control in self.axis_controls:
			if sender in (control["slider"], control["valueField"]):
				return control
		return None
