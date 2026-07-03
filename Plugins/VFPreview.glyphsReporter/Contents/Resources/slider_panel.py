# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import vanilla

from AppKit import NSMakeRect
from GlyphsApp import Glyphs
from axis_utils import exportable_instances, format_axis_value, effective_axis_count
from charts import MasterChartView
from preview_view import PreviewCanvasView


class SliderPanel(object):
	PREVIEW_HEIGHT = 130
	DOCK_PREVIEW_HEIGHT = 60
	ROW_HEIGHT = 30
	OPTIONS_HEIGHT = 108
	MIN_DOCK_WIDTH = 480

	def __init__(self, controller, drawer):
		self.controller = controller
		self.drawer = drawer
		self.axis_controls = []
		self.w = None
		self.bar_chart = None
		self.preview_view = None
		self._dock_mode = False
		self._built_height = 0
		self._built_width = 320
		self._built_axis_count = -1
		controller.add_listener(self.refresh)

	def open_dock(self, force_rebuild=False):
		try:
			if self.w is not None and self._dock_mode and not force_rebuild:
				ns_window = self.w.getNSWindow()
				if ns_window is not None:
					self.w.open()
					self.reposition()
					self.refresh()
					return
			self.close()
			self.build_dock_window()
			self.w.open()
			self._raise_axis_controls()
			self.reposition()
			self.refresh()
			try:
				from AppKit import NSFloatingWindowLevel
				self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)
			except Exception:
				pass
		except Exception:
			self.close()

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
			return max(self.MIN_DOCK_WIDTH, main_window.contentView().frame().size.width)
		except Exception:
			return 720

	def reposition(self):
		if self.w is None or not self._dock_mode:
			return
		try:
			ns_window = self.w.getNSWindow()
			main_window = self._glyphs_main_window()
			if ns_window is None or main_window is None:
				return
			content_frame = main_window.contentView().frame()
			screen_frame = main_window.convertRectToScreen_(content_frame)
			content_height = self._built_height
			win_width = self._built_width
			content_top = screen_frame.origin.y + screen_frame.size.height
			content_rect = NSMakeRect(screen_frame.origin.x, content_top - content_height, win_width, content_height)
			frame_rect = ns_window.frameRectForContentRect_(content_rect)
			ns_window.setFrame_display_(frame_rect, True)
			try:
				ns_window.setContentSize_((win_width, content_height))
				ns_window.setMinSize_((float(self.MIN_DOCK_WIDTH), float(content_height)))
				ns_window.setMaxSize_((100000.0, float(content_height)))
			except Exception:
				pass
		except Exception:
			pass

	def _raise_axis_controls(self):
		if self.w is None:
			return
		try:
			content = self.w.getNSWindow().contentView()
			for attr in ("axesLabel",):
				content.addSubview_(getattr(self.w, attr).getNSView())
			for control in self.axis_controls:
				for key in ("label", "slider", "valueField"):
					content.addSubview_(control[key].getNSView())
		except Exception:
			pass

	def _dock_height(self, axis_count):
		return (
			self.PADDING_DOCK * 2
			+ self.DOCK_PREVIEW_HEIGHT
			+ 10
			+ 16
			+ 20
			+ axis_count * self.ROW_HEIGHT
		)

	PADDING_DOCK = 12

	def build_dock_window(self):
		self._dock_mode = True
		font = self.controller.font
		axis_count = max(effective_axis_count(font), 1 if font is None else 0)
		self._built_axis_count = axis_count
		width = int(self._target_width())
		height = self._dock_height(axis_count)
		self._built_height = height
		self._built_width = width

		self.w = vanilla.FloatingWindow(
			(width, height),
			"VF Preview",
			minSize=(self.MIN_DOCK_WIDTH, height),
			maxSize=(100000, height),
		)

		inner_width = max(200, width - 24)

		# Bottom-left origin: stack from top of window downward using decreasing y.
		y = height - self.PADDING_DOCK
		y -= self.DOCK_PREVIEW_HEIGHT
		self.preview_view = PreviewCanvasView.alloc().initWithFrame_(
			NSMakeRect(0, 0, inner_width, self.DOCK_PREVIEW_HEIGHT)
		)
		self.preview_view.setController_(self.controller)
		self.preview_view.drawer = self.drawer
		self.w.previewGroup = vanilla.Group((12, y, inner_width, self.DOCK_PREVIEW_HEIGHT))
		preview_group = self.w.previewGroup.getNSView()
		preview_group.setClipsToBounds_(True)
		preview_group.addSubview_(self.preview_view)
		y -= 10
		y -= 16
		self.w.axesLabel = vanilla.TextBox((12, y, 120, 16), "Axes", sizeStyle="small")
		y -= 20

		self.axis_controls = []
		for index in range(axis_count):
			y -= self.ROW_HEIGHT
			label = vanilla.TextBox((12, y + 6, 78, 18), "Axis", sizeStyle="small")
			slider = vanilla.Slider((94, y + 2, 104, 22), callback=self.sliderCallback, value=0.5)
			value_field = vanilla.EditText((204, y, 80, 22), "", callback=self.valueFieldCallback)
			self.axis_controls.append({
				"label": label,
				"slider": slider,
				"valueField": value_field,
			})

	def open(self):
		if self.w is not None:
			try:
				if self.w.getNSWindow() is not None:
					self.w.open()
					self.refresh()
					return
			except Exception:
				pass
			self.w = None
		self.build_window()
		self.refresh()
		self.w.open()
		try:
			from AppKit import NSFloatingWindowLevel
			self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)
		except Exception:
			pass
		try:
			self.w.makeKey()
		except Exception:
			pass

	def close(self):
		if self.w is None:
			return
		try:
			ns_window = self.w.getNSWindow()
			if ns_window is not None:
				self.w.close()
		except Exception:
			pass
		self.w = None
		self.bar_chart = None
		self.preview_view = None
		self.axis_controls = []
		self._dock_mode = False
		self._built_height = 0
		self._built_axis_count = -1

	def build_window(self):
		font = self.controller.font
		axis_count = max(effective_axis_count(font), 1 if font is None else 0)
		height = (
			12
			+ self.PREVIEW_HEIGHT
			+ 24
			+ axis_count * self.ROW_HEIGHT
			+ self.OPTIONS_HEIGHT
			+ 88
			+ 100
			+ 12
		)
		self.w = vanilla.FloatingWindow((320, height), "VF Preview", minSize=(300, 420))

		y = 12
		self.w.previewLabel = vanilla.TextBox((12, y, 120, 16), "Preview", sizeStyle="small")
		y += 18
		self.preview_view = PreviewCanvasView.alloc().initWithFrame_(NSMakeRect(0, 0, 296, self.PREVIEW_HEIGHT))
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
			slider = vanilla.Slider((94, y + 2, 104, 22), callback=self.sliderCallback, value=0.5)
			value_field = vanilla.EditText((204, y, -12, 22), "", callback=self.valueFieldCallback)
			self.axis_controls.append({
				"label": label,
				"slider": slider,
				"valueField": value_field,
			})
			y += self.ROW_HEIGHT

		self.w.drawEdit = vanilla.CheckBox((12, y, 145, 18), "Draw in Edit View", callback=self.toggleDrawEditCallback, value=bool(self.controller.pref("drawInEditView")))
		self.w.showMasters = vanilla.CheckBox((165, y, -12, 18), "Involved Masters", callback=self.toggleShowMastersCallback, value=bool(self.controller.pref("showInvolvedMasters")))
		y += 22
		self.w.linkMaster = vanilla.CheckBox((12, y, 145, 18), "Link to Master", callback=self.linkMasterCallback, value=bool(self.controller.pref("linkToMaster")))
		self.w.centerPreview = vanilla.CheckBox((165, y, -12, 18), "Center Preview", callback=self.toggleCenterPreviewCallback, value=bool(self.controller.pref("centerPreview")))
		y += 22
		self.w.roundValues = vanilla.CheckBox((12, y, 145, 18), "Round Values", callback=self.toggleRoundValuesCallback, value=bool(self.controller.pref("roundValues")))
		self.w.hideForeground = vanilla.CheckBox((165, y, -12, 18), "Hide Foreground", callback=self.toggleHideForegroundCallback, value=bool(self.controller.pref("hideForeground")))
		y += 22
		self.w.showNodes = vanilla.CheckBox((12, y, 145, 18), "Preview Nodes", callback=self.toggleShowNodesCallback, value=bool(self.controller.pref("showPreviewNodes")))
		self.w.showMeasurements = vanilla.CheckBox((165, y, -12, 18), "Measurements", callback=self.toggleShowMeasurementsCallback, value=bool(self.controller.pref("showMeasurements")))
		y += 28

		self.w.masterMenu = vanilla.PopUpButton((12, y, 145, 22), ["Jump to Master…"], callback=self.masterMenuCallback)
		self.w.instanceMenu = vanilla.PopUpButton((165, y, -12, 22), ["Preview Instance…"], callback=self.instanceMenuCallback)
		y += 28
		self.w.makeInstance = vanilla.Button((12, y, 145, 22), "Make Instance", callback=self.makeInstanceCallback)
		self.w.previewMode = vanilla.PopUpButton((165, y, -12, 22), ["Current Glyph", "Full Text", "Current Line"], callback=self.previewModeCallback)
		y += 30

		self.w.barLabel = vanilla.TextBox((12, y, 120, 16), "Master Influence", sizeStyle="small")
		y += 18
		self.bar_chart = MasterChartView.alloc().initWithFrame_(NSMakeRect(0, 0, 296, 80))
		self.bar_chart.setMode_("bar")
		self.w.barGroup = vanilla.Group((12, y, -12, 80))
		self.w.barGroup.getNSView().addSubview_(self.bar_chart)
		y += 88

		self.w.resize(320, y + 12)

	def refresh(self):
		if self.w is None:
			return
		font = self.controller.font
		if font is None:
			return

		rows = self.controller.axis_rows()
		if len(rows) != len(self.axis_controls):
			if self._dock_mode:
				self.open_dock(force_rebuild=True)
			else:
				self.close()
				self.open()
			return

		for control, row in zip(self.axis_controls, rows):
			label_text = row["name"]
			if not self._dock_mode:
				label_text = "%s (%s)" % (row["name"], row["tag"])
			control["label"].set(label_text)
			minimum = row["minimum"]
			maximum = row["maximum"]
			value = row["value"]
			if row["binary"]:
				control["slider"].enable(False)
				control["valueField"].enable(True)
			else:
				control["slider"].enable(True)
				if abs(maximum - minimum) < 0.0001:
					slider_value = 0.5
				else:
					slider_value = (value - minimum) / (maximum - minimum)
				control["slider"].set(max(0.0, min(1.0, slider_value)))
			display = format_axis_value(value, bool(self.controller.pref("roundValues")))
			control["valueField"].set(display)

		if self._dock_mode:
			if self.preview_view is not None:
				self.preview_view.setNeedsDisplay_(True)
			return

		master_titles = ["Jump to Master…"]
		for master in font.masters:
			master_titles.append(master.name)
		self.w.masterMenu.setItems(master_titles)

		instance_titles = ["Preview Instance…"]
		for instance in exportable_instances(font):
			instance_titles.append(instance.name)
		self.w.instanceMenu.setItems(instance_titles)

		mode = self.controller.pref("previewMode") or "glyph"
		mode_index = {"glyph": 0, "text": 1, "line": 2}.get(mode, 0)
		self.w.previewMode.set(mode_index)

		entries = self.controller.weight_entries()
		if self.bar_chart is not None:
			self.bar_chart.setEntries_(entries)
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
		minimum = row["minimum"]
		maximum = row["maximum"]
		value = minimum + sender.get() * (maximum - minimum)
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

	def toggleDrawEditCallback(self, sender):
		self.controller.set_pref("drawInEditView", int(bool(sender.get())))
		self.controller.notify_listeners()

	def toggleCenterPreviewCallback(self, sender):
		self.controller.set_pref("centerPreview", int(bool(sender.get())))
		self.controller.notify_listeners()
		self.refresh()

	def toggleRoundValuesCallback(self, sender):
		self.controller.set_pref("roundValues", int(bool(sender.get())))
		self.refresh()
		self.controller.notify_listeners()

	def toggleShowMastersCallback(self, sender):
		self.controller.set_pref("showInvolvedMasters", int(bool(sender.get())))
		self.controller.notify_listeners()
		self.refresh()

	def toggleShowNodesCallback(self, sender):
		self.controller.set_pref("showPreviewNodes", int(bool(sender.get())))
		self.controller.notify_listeners()
		self.refresh()

	def toggleHideForegroundCallback(self, sender):
		self.controller.set_pref("hideForeground", int(bool(sender.get())))
		self.controller.notify_listeners()

	def toggleShowMeasurementsCallback(self, sender):
		self.controller.set_pref("showMeasurements", int(bool(sender.get())))
		self.controller.notify_listeners()

	def linkMasterCallback(self, sender):
		self.controller.set_pref("linkToMaster", int(bool(sender.get())))
		self.controller.sync_preview_instance()
		self.controller.notify_listeners()
		self.refresh()

	def masterMenuCallback(self, sender):
		index = sender.get()
		if index <= 0:
			return
		master = self.controller.font.masters[index - 1]
		self.controller.apply_master(master)
		self.refresh()

	def instanceMenuCallback(self, sender):
		index = sender.get()
		if index <= 0:
			return
		instance = exportable_instances(self.controller.font)[index - 1]
		self.controller.apply_instance(instance)
		self.refresh()

	def makeInstanceCallback(self, sender):
		self.controller.make_instance_from_current()
		self.refresh()

	def previewModeCallback(self, sender):
		modes = ("glyph", "text", "line")
		index = sender.get()
		if 0 <= index < len(modes):
			self.controller.set_pref("previewMode", modes[index])
			self.controller.notify_listeners()
