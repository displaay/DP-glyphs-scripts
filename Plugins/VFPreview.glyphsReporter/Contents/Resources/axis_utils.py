# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

try:
	from GlyphsApp import INSTANCETYPEVARIABLE
except Exception:
	INSTANCETYPEVARIABLE = None

SYNTHETIC_AXIS_ID = "__vfpreview_axis0__"


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


def axis_index_for_tag(font, axis_tag):
	for index, axis in enumerate(font.axes):
		if axis.axisTag == axis_tag:
			return index
	return None


def axis_identifiers(axis):
	identifiers = []
	for key in ("axisId", "id"):
		value = getattr(axis, key, None)
		if value is not None:
			identifiers.append(value)
	return identifiers


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
	try:
		axis_id = master_or_instance.font.axes[axis_index].axisId
		return float(master_or_instance.axisValueValueForId_(axis_id))
	except Exception:
		return 0.0


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


def axis_value_from_source(source, axis, axis_index):
	if source is None:
		return None
	for axis_id in axis_identifiers(axis):
		try:
			value = source[axis_id]
			if value is not None:
				return float(value)
		except Exception:
			pass
		try:
			value = source.get(axis_id)
			if value is not None:
				return float(value)
		except Exception:
			pass
	try:
		if axis_index < len(source):
			return float(source[axis_index])
	except Exception:
		pass
	try:
		values = list(source.values())
		if axis_index < len(values):
			return float(values[axis_index])
	except Exception:
		pass
	return None


def layer_axis_value(font, layer, axis_index):
	axis = font.axes[axis_index]
	coordinates = None
	if getattr(layer, "isSpecialLayer", False):
		coordinates = dict(layer.attributes.get("coordinates", {}) or {})
	value = axis_value_from_source(coordinates, axis, axis_index)
	if value is not None:
		return value
	master = master_for_layer(font, layer)
	if master is not None:
		value = axis_value_from_source(getattr(master, "axes", None), axis, axis_index)
		if value is None:
			value = axis_value_from_source(master, axis, axis_index)
		if value is not None:
			return value
	return 0.0


def master_for_layer(font, layer):
	master_id = getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None)
	if not master_id:
		return None
	for master in font.masters:
		if master.id == master_id:
			return master
	return None


def master_axis_values(font, master):
	values = {}
	if uses_synthetic_axis(font):
		values[SYNTHETIC_AXIS_ID] = master_internal_axis_value(master, 0)
		return values
	for index, axis in enumerate(font.axes):
		value = axis_value_from_source(getattr(master, "axes", None), axis, index)
		if value is None:
			value = internal_value(master, index, axis.axisTag)
		values[axis.axisId] = value
	return values


def selected_master_axis_values(font):
	master = font.selectedFontMaster
	if master is None:
		return {}
	return master_axis_values(font, master)


def axis_limits(font, axis_index):
	values = []
	axis = font.axes[axis_index]
	for master in font.masters:
		values.append(internal_value(master, axis_index, axis.axisTag))
	for layer in all_special_layers(font):
		values.append(layer_axis_value(font, layer, axis_index))
	if not values:
		return 0.0, 0.0
	return min(values), max(values)


def all_special_layers(font):
	for glyph in font.glyphs:
		for layer in glyph.layers:
			if getattr(layer, "isSpecialLayer", False):
				yield layer


def is_extrapolated(font, axis_index, value):
	minimum, maximum = axis_limits(font, axis_index)
	return value < minimum - 0.0001 or value > maximum + 0.0001


def format_axis_value(value, round_values):
	if round_values:
		return str(int(round(value)))
	return "%.4g" % value


def uses_synthetic_axis(font):
	return font is not None and len(font.axes) == 0 and len(font.masters) >= 2


def effective_axis_count(font):
	if font is None:
		return 0
	if len(font.axes) > 0:
		return len(font.axes)
	if len(font.masters) >= 2:
		return 1
	return 0


def master_internal_axis_value(master, axis_index=0):
	try:
		values = master.internalAxesValues
		if values is not None and axis_index < len(values):
			return float(values[axis_index])
	except Exception:
		pass
	try:
		value = master.internalAxesValues[axis_index]
		return float(value)
	except Exception:
		pass
	return 0.0


def synthetic_axis_limits(font, axis_index=0):
	values = []
	for master in font.masters:
		values.append(master_internal_axis_value(master, axis_index))
	if not values:
		return 0.0, 1.0
	return min(values), max(values)


def exportable_instances(font):
	instances = []
	for instance in font.instances:
		if not instance.active:
			continue
		if INSTANCETYPEVARIABLE is not None and instance.type == INSTANCETYPEVARIABLE:
			continue
		instances.append(instance)
	return instances


def default_axis_values(font):
	if font.selectedFontMaster is not None:
		return master_axis_values(font, font.selectedFontMaster)
	if uses_synthetic_axis(font):
		minimum, maximum = synthetic_axis_limits(font)
		return {SYNTHETIC_AXIS_ID: (minimum + maximum) / 2.0}
	values = {}
	for index, axis in enumerate(font.axes):
		minimum, maximum = axis_limits(font, index)
		values[axis.axisId] = (minimum + maximum) / 2.0
	return values


def set_instance_axis_values(instance, font, values_by_axis_id):
	if uses_synthetic_axis(font):
		value = values_by_axis_id.get(SYNTHETIC_AXIS_ID)
		if value is None:
			minimum, maximum = synthetic_axis_limits(font)
			value = (minimum + maximum) / 2.0
		try:
			instance.axes = [float(value)]
		except Exception:
			pass
		return
	for axis in font.axes:
		if axis.axisId not in values_by_axis_id:
			continue
		value = float(values_by_axis_id[axis.axisId])
		try:
			instance.setAxisValueValue_forId_(value, axis.axisId)
		except Exception:
			pass
	axes_list = []
	for axis in font.axes:
		axes_list.append(float(values_by_axis_id.get(axis.axisId, 0.0)))
	try:
		instance.axes = axes_list
	except Exception:
		pass


def instance_axis_values(font, instance):
	values = {}
	for index, axis in enumerate(font.axes):
		values[axis.axisId] = internal_value(instance, index, axis.axisTag)
	return values
