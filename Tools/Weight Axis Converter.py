# MenuTitle: Weight Axis Converter
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals
__doc__ = """
Converts weight axis values between Glyphs source coordinates (internal/design)
and exported variable-font coordinates (external/user), including remapped
instances such as 550 → 500.

Reads mapping points from the open font and interpolates between them.
"""

import vanilla
from GlyphsApp import Glyphs, Message, INSTANCETYPEVARIABLE

try:
	from fontTools.varLib.models import piecewiseLinearMap
except ImportError:
	def piecewiseLinearMap(value, mapping):
		"""Fallback piecewise-linear map when fontTools is unavailable."""
		if not mapping:
			return value
		keys = sorted(mapping.keys())
		if value <= keys[0]:
			k0, k1 = keys[0], keys[1] if len(keys) > 1 else keys[0]
		elif value >= keys[-1]:
			k0, k1 = keys[-2] if len(keys) > 1 else keys[-1], keys[-1]
		else:
			k0 = k1 = keys[0]
			for i in range(len(keys) - 1):
				if keys[i] <= value <= keys[i + 1]:
					k0, k1 = keys[i], keys[i + 1]
					break
		if k0 == k1:
			return mapping[k0]
		t = (value - k0) / (k1 - k0)
		return mapping[k0] + t * (mapping[k1] - mapping[k0])


def axis_index_for_tag(font, axis_tag):
	for index, axis in enumerate(font.axes):
		if axis.axisTag == axis_tag:
			return index
	return None


def read_custom_parameter(owner, name):
	try:
		value = owner.customParameters[name]
	except Exception:
		return None
	if value is None or value == "":
		return None
	return value


def entry_value(entry, key):
	if hasattr(entry, "objectForKey_"):
		return entry.objectForKey_(key)
	if hasattr(entry, "get"):
		return entry.get(key)
	return entry[key]


def popup_index(popup):
	value = popup.get()
	return value if isinstance(value, int) else 0


def axis_location_value(master_or_instance, axis_name):
	parameter = read_custom_parameter(master_or_instance, "Axis Location")
	if not parameter:
		return None
	for entry in parameter:
		if entry_value(entry, "Axis") == axis_name:
			return float(entry_value(entry, "Location"))
	return None


def internal_value(master_or_instance, axis_index, axis_tag):
	try:
		return float(master_or_instance.internalAxesValues[axis_index])
	except Exception:
		pass
	axis_id = master_or_instance.font.axes[axis_index].axisId
	return float(master_or_instance.axisValueValueForId_(axis_id))


def external_value(master_or_instance, axis_index, axis_name, axis_tag):
	try:
		return float(master_or_instance.externalAxesValues[axis_index])
	except Exception:
		pass
	location = axis_location_value(master_or_instance, axis_name)
	if location is not None:
		return location
	if hasattr(master_or_instance, "weightClassValue") and axis_tag == "wght":
		return float(master_or_instance.weightClassValue())
	return internal_value(master_or_instance, axis_index, axis_tag)


def mapping_from_axis_mappings_parameter(font, axis_tag):
	parameter = read_custom_parameter(font, "Axis Mappings")
	if not parameter:
		return {}
	points = {}
	axis_mapping = parameter.get(axis_tag) if hasattr(parameter, "get") else None
	if axis_mapping is None and hasattr(parameter, "objectForKey_"):
		axis_mapping = parameter.objectForKey_(axis_tag)
	if not axis_mapping:
		return {}
	for key in axis_mapping.allKeys() if hasattr(axis_mapping, "allKeys") else axis_mapping:
		internal = float(key)
		external = float(
			axis_mapping.objectForKey_(key)
			if hasattr(axis_mapping, "objectForKey_")
			else axis_mapping[key]
		)
		points[internal] = external
	return points


def collect_mapping_points(font, axis_tag):
	axis_index = axis_index_for_tag(font, axis_tag)
	if axis_index is None:
		return None, {}

	axis_name = font.axes[axis_index].name
	points = {}

	for master in font.masters:
		internal = internal_value(master, axis_index, axis_tag)
		external = external_value(master, axis_index, axis_name, axis_tag)
		points[internal] = external

	for instance in font.instances:
		if not instance.active or instance.type == INSTANCETYPEVARIABLE:
			continue
		internal = internal_value(instance, axis_index, axis_tag)
		external = external_value(instance, axis_index, axis_name, axis_tag)
		points[internal] = external

	font_level = mapping_from_axis_mappings_parameter(font, axis_tag)
	for internal, external in font_level.items():
		points[internal] = external

	return axis_index, points


def build_converters(points):
	internal_to_external = dict(sorted(points.items()))
	external_to_internal = {}
	for internal, external in internal_to_external.items():
		external_to_internal[external] = internal
	return internal_to_external, external_to_internal


def convert_value(value, source_is_internal, internal_to_external, external_to_internal):
	if source_is_internal:
		return piecewiseLinearMap(value, internal_to_external)
	return piecewiseLinearMap(value, external_to_internal)


def format_mapping_table(points):
	if not points:
		return "No mapping points found."
	lines = ["Glyphs (source) → Exported (VF)", ""]
	for internal in sorted(points.keys()):
		external = points[internal]
		if abs(internal - external) < 0.01:
			lines.append("%g  →  %g" % (internal, external))
		else:
			lines.append("%g  →  %g  (Δ %+.1f)" % (internal, external, external - internal))
	return "\n".join(lines)


class WeightAxisConverter(object):
	def __init__(self):
		self.font = Glyphs.font
		if self.font is None:
			Message(
				title="No Font Open",
				message="Open a font and run this script again.",
				OKButton=None,
			)
			return

		self.axis_tags = [axis.axisTag for axis in self.font.axes]
		if not self.axis_tags:
			Message(
				title="No Axes",
				message="This font has no axes defined.",
				OKButton=None,
			)
			return

		default_tag = "wght" if "wght" in self.axis_tags else self.axis_tags[0]
		default_index = self.axis_tags.index(default_tag)
		self.current_tag = default_tag

		window_width = 360
		window_height = 360
		self.w = vanilla.FloatingWindow(
			(window_width, window_height),
			"Weight Axis Converter",
			minSize=(window_width, window_height),
		)

		inset = 15
		line_height = 22
		y = 10

		self.w.helpText = vanilla.TextBox(
			(inset, y, -inset, 32),
			"Convert between Glyphs source values and exported VF weight coordinates.",
			sizeStyle="small",
		)
		y += 34

		self.w.axisLabel = vanilla.TextBox((inset, y + 2, 40, 18), "Axis:", sizeStyle="small")
		self.w.axisPicker = vanilla.PopUpButton(
			(inset + 45, y, 80, 20),
			self.axis_tags,
			callback=self.axisChanged,
			sizeStyle="small",
		)
		self.w.axisPicker.set(default_index)
		y += line_height

		self.w.mappingBox = vanilla.TextEditor(
			(inset, y, -inset, 130),
			text="",
			checksSpelling=False,
		)
		self.w.mappingBox.getNSTextView().setEditable_(False)
		y += 138

		self.w.directionLabel = vanilla.TextBox(
			(inset, y + 2, 60, 18),
			"Input is:",
			sizeStyle="small",
		)
		self.w.directionPicker = vanilla.PopUpButton(
			(inset + 65, y, -inset, 20),
			["Glyphs source (internal)", "Exported VF (external)"],
			sizeStyle="small",
		)
		self.w.directionPicker.set(1)
		y += line_height

		self.w.valueLabel = vanilla.TextBox(
			(inset, y + 2, 50, 18),
			"Value:",
			sizeStyle="small",
		)
		self.w.valueField = vanilla.EditText((inset + 55, y, 80, 22), "", sizeStyle="small")
		self.w.convertButton = vanilla.Button(
			(-inset - 90, y, 90, 22),
			"Convert",
			callback=self.convert,
		)
		y += line_height + 4

		self.w.resultText = vanilla.TextBox(
			(inset, y, -inset, 40),
			"",
			sizeStyle="small",
		)

		self.refresh_mapping()
		self.w.open()
		self.w.makeKey()

	def axisChanged(self, sender=None):
		self.current_tag = self.axis_tags[popup_index(self.w.axisPicker)]
		self.refresh_mapping()

	def refresh_mapping(self):
		_, points = collect_mapping_points(self.font, self.current_tag)
		self.points = points
		self.internal_to_external, self.external_to_internal = build_converters(points)
		self.w.mappingBox.set(format_mapping_table(points))

	def convert(self, sender=None):
		text = self.w.valueField.get().strip()
		if not text:
			self.w.resultText.set("Enter a numeric value.")
			return

		try:
			value = float(text)
		except ValueError:
			self.w.resultText.set("Invalid number: %s" % text)
			return

		if not self.points:
			self.w.resultText.set("No mapping data for axis %s." % self.current_tag)
			return

		source_is_internal = popup_index(self.w.directionPicker) == 0
		try:
			result = convert_value(
				value,
				source_is_internal,
				self.internal_to_external,
				self.external_to_internal,
			)
		except Exception as error:
			self.w.resultText.set("Conversion failed: %s" % error)
			return

		delta = result - value
		if source_is_internal:
			self.w.resultText.set(
				"Glyphs %g  →  VF %g  (Δ %+.2f)" % (value, result, delta)
			)
		else:
			self.w.resultText.set(
				"VF %g  →  Glyphs %g  (Δ %+.2f)" % (value, result, delta)
			)

		Glyphs.clearLog()
		print("Weight Axis Converter — %s" % self.font.familyName)
		print(format_mapping_table(self.points))
		print("")
		if source_is_internal:
			print("Input:  Glyphs source = %g" % value)
			print("Output: Exported VF  = %g" % result)
		else:
			print("Input:  Exported VF  = %g" % value)
			print("Output: Glyphs source = %g" % result)
		print("Difference: %+.4f" % delta)


if Glyphs.versionNumber < 3.2:
	Message(
		title="Glyphs Version Error",
		message="This script requires Glyphs 3.2 or later (internalAxesValues / externalAxesValues).",
		OKButton=None,
	)
else:
	WeightAxisConverter()
