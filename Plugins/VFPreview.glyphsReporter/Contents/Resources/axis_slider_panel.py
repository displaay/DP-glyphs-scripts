# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import objc
import vanilla
from vanilla.vanillaGroup import Group

from axis_utils import format_axis_value

try:
	InspectorGroupBase = type(
		"PatchedGroup",
		(Group,),
		{"nsViewClass": objc.lookUpClass("GSInspectorView")},
	)
except Exception:
	InspectorGroupBase = Group


class AxisSliderPanel(object):
	MAX_AXES = 6
	LABEL_WIDTH = 90
	VALUE_WIDTH = 56
	SLIDER_HEIGHT = 22
	PADDING = 8
	ROW_GAP = 4
	LEFT_SPACER = 400

	def __init__(self, controller):
		self.controller = controller
		self.shell = None
		self.group = None
		self.axis_controls = []
		self._build_once()
		controller.add_listener(self.refresh)

	def preferred_height(self):
		font = self.controller.font
		if font is None:
			return self.PADDING * 2 + self.SLIDER_HEIGHT
		row_count = min(max(len(self.controller.axis_rows()), 1), self.MAX_AXES)
		return (
			self.PADDING * 2
			+ row_count * self.SLIDER_HEIGHT
			+ max(0, row_count - 1) * self.ROW_GAP
		)

	def ns_view(self):
		if self.group is None:
			self._build_once()
		return self.group.getNSView()

	def _build_once(self):
		if self.group is not None:
			return

		width = 800
		height = self.preferred_height()
		self.shell = vanilla.Window((width, height), "")
		self.group = InspectorGroupBase((0, 0, width, height))
		self.shell.group = self.group

		h_rules = []
		slider_row_parts = []
		for index in range(self.MAX_AXES):
			label_key = "label%i" % index
			slider_key = "slider%i" % index
			value_key = "value%i" % index
			setattr(self.group, label_key, vanilla.TextBox("auto", "Axis", sizeStyle="small"))
			setattr(
				self.group,
				slider_key,
				vanilla.Slider("auto", callback=self.sliderCallback, value=0.5),
			)
			setattr(
				self.group,
				value_key,
				vanilla.EditText("auto", "", callback=self.valueFieldCallback),
			)
			h_rules.append(
				"H:|-%i-[%s(%i)]-8-[%s]-8-[%s(%i)]-(>=%i)-|"
				% (
					self.PADDING,
					label_key,
					self.LABEL_WIDTH,
					slider_key,
					value_key,
					self.VALUE_WIDTH,
					self.LEFT_SPACER,
				)
			)
			slider_row_parts.append("[%s(%i)]" % (slider_key, self.SLIDER_HEIGHT))
			self.axis_controls.append({
				"label": getattr(self.group, label_key),
				"slider": getattr(self.group, slider_key),
				"valueField": getattr(self.group, value_key),
			})

		if len(slider_row_parts) > 1:
			v_rule = (
				"V:|-%i-" % self.PADDING
				+ ("-%i-" % self.ROW_GAP).join(slider_row_parts)
				+ "-%i-|" % self.PADDING
			)
		else:
			v_rule = "V:|-%i-%s-%i-|" % (self.PADDING, slider_row_parts[0], self.PADDING)

		self.group.addAutoPosSizeRules(h_rules + [v_rule], {})

		for control in self.axis_controls:
			control["label"].show(False)
			control["slider"].show(False)
			control["valueField"].show(False)

	def refresh(self):
		font = self.controller.font
		if font is None:
			return

		rows = self.controller.axis_rows()
		for index, control in enumerate(self.axis_controls):
			visible = index < len(rows)
			control["label"].show(visible)
			control["slider"].show(visible)
			control["valueField"].show(visible)

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


class AxisSliderInspectorController(object):
	def __init__(self, panel):
		self.panel = panel

	def view(self):
		return self.panel.ns_view()

	def preferredMinimumHeight(self):
		return self.panel.preferred_height()

	def preferredMaximumHeight(self):
		return self.preferredMinimumHeight()
