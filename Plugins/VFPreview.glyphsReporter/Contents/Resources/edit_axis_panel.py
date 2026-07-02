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


class EditViewAxisPanel(object):
	PANEL_WIDTH = 320
	ROW_HEIGHT = 24
	MAX_AXES = 6

	def __init__(self, controller):
		self.controller = controller
		self.shell = None
		self.group = None
		self.axis_controls = []
		self._build_panel_once()
		controller.add_listener(self.refresh)

	def ns_view(self):
		return self.group.getNSView()

	def _build_panel_once(self):
		if self.group is not None:
			return

		height = 12 + self.MAX_AXES * self.ROW_HEIGHT + 6
		self.shell = vanilla.Window((self.PANEL_WIDTH, height), "")
		self.group = InspectorGroupBase((0, 0, self.PANEL_WIDTH, height))
		self.shell.group = self.group

		h_rules = []
		row_parts = []
		for index in range(self.MAX_AXES):
			label_key = "label%i" % index
			slider_key = "slider%i" % index
			value_key = "value%i" % index
			setattr(self.group, label_key, vanilla.TextBox("auto", "Axis", sizeStyle="small"))
			setattr(self.group, slider_key, vanilla.Slider("auto", callback=self.sliderCallback, value=0.5))
			setattr(self.group, value_key, vanilla.EditText("auto", "", callback=self.valueFieldCallback))
			h_rules.append(
				"H:|-8-[%s(78)]-8-[%s]-8-[%s(72)]-8-|" % (label_key, slider_key, value_key)
			)
			row_parts.append("[%s(%i)]" % (label_key, self.ROW_HEIGHT))
			self.axis_controls.append({
				"label": getattr(self.group, label_key),
				"slider": getattr(self.group, slider_key),
				"valueField": getattr(self.group, value_key),
			})
		v_rule = "V:|-6-" + "-4-".join(row_parts) + "-6-|"
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
			if index < len(rows):
				control["label"].show(True)
				control["slider"].show(True)
				control["valueField"].show(True)
			else:
				control["label"].show(False)
				control["slider"].show(False)
				control["valueField"].show(False)

		for control, row in zip(self.axis_controls, rows):
			control["label"].set("%s (%s)" % (row["name"], row["tag"]))
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
