#MenuTitle: Selective Variable Font Export
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__ = """
Export a variable font while dropping selected axes, keeping selected named instances,
and remapping chosen instances to specific wght values.
"""

import os
import re
import traceback

from AppKit import NSOpenPanel
from GlyphsApp import Glyphs, INSTANCETYPEVARIABLE, Message, PLAIN, VARIABLE
from fontTools.ttLib import TTFont, newTable
from fontTools.varLib import instancer
from fontTools.varLib.models import normalizeValue, piecewiseLinearMap

try:
	import vanilla
except ImportError:
	vanilla = None


PREFS_PREFIX = "com.codex.SelectiveVariableFontExport."


def parse_csv_list(raw_value):
	return [item.strip() for item in (raw_value or "").split(",") if item.strip()]


def parse_key_value_list(raw_value, cast=float):
	parsed = {}
	if not raw_value.strip():
		return parsed
	for chunk in raw_value.split(","):
		entry = chunk.strip()
		if not entry:
			continue
		if "=" not in entry:
			raise ValueError("Expected key=value pairs separated by commas.")
		key, value = entry.split("=", 1)
		key = key.strip()
		value = value.strip()
		if not key or not value:
			raise ValueError("Empty key or value in '%s'." % entry)
		parsed[key] = cast(value)
	return parsed


def name_for_instance(ttfont, instance_record):
	return ttfont["name"].getDebugName(instance_record.subfamilyNameID) or "Unnamed Instance"


def axis_records_by_tag(ttfont):
	return {axis.axisTag: axis for axis in ttfont["fvar"].axes}


def denormalize_value(normalized_value, axis_triple):
	minimum, default, maximum = axis_triple
	if normalized_value <= 0:
		return default + normalized_value * (default - minimum)
	return default + normalized_value * (maximum - default)


def rounded_mapping(mapping_dict, digits=8):
	return {round(key, digits): round(value, digits) for key, value in mapping_dict.items()}


def map_value_between_axis_triples(value, source_triple, target_triple):
	source_min, source_default, source_max = source_triple
	target_min, target_default, target_max = target_triple

	value = float(value)
	if source_max == source_min:
		return float(target_default)

	if value <= source_default:
		denominator = (source_default - source_min)
		if denominator == 0:
			return float(target_default)
		portion = (value - source_default) / float(denominator)
		return float(target_default + portion * (target_default - target_min))

	denominator = (source_max - source_default)
	if denominator == 0:
		return float(target_default)
	portion = (value - source_default) / float(denominator)
	return float(target_default + portion * (target_max - target_default))


def piecewise_user_map(value, anchors):
	sorted_items = sorted(anchors.items())
	if value <= sorted_items[0][0]:
		return sorted_items[0][1]
	if value >= sorted_items[-1][0]:
		return sorted_items[-1][1]
	for index in range(len(sorted_items) - 1):
		left_x, left_y = sorted_items[index]
		right_x, right_y = sorted_items[index + 1]
		if left_x <= value <= right_x:
			if right_x == left_x:
				return left_y
			portion = (value - left_x) / float(right_x - left_x)
			return left_y + portion * (right_y - left_y)
	return value


def ensure_monotonic_mapping(anchors):
	sorted_items = sorted(anchors.items())
	last_new_value = None
	for _, new_value in sorted_items:
		if last_new_value is not None and new_value < last_new_value:
			raise ValueError("Weight remap values must stay in ascending order.")
		last_new_value = new_value


def filter_named_instances(ttfont, keep_names):
	if "fvar" not in ttfont:
		return set(), set()

	fvar_table = ttfont["fvar"]
	original_name_ids = {instance.subfamilyNameID for instance in fvar_table.instances}
	if not keep_names:
		return original_name_ids, set(original_name_ids)

	kept_instances = []
	kept_name_ids = set()
	for instance_record in fvar_table.instances:
		style_name = name_for_instance(ttfont, instance_record)
		if style_name in keep_names:
			kept_instances.append(instance_record)
			kept_name_ids.add(instance_record.subfamilyNameID)

	fvar_table.instances = kept_instances
	return original_name_ids, kept_name_ids


def update_stat_for_named_instance_filter(ttfont, original_name_ids, kept_name_ids):
	if "STAT" not in ttfont:
		return

	stat_table = ttfont["STAT"].table
	if not getattr(stat_table, "AxisValueArray", None):
		return

	filtered_tables = []
	for axis_value in stat_table.AxisValueArray.AxisValue:
		value_name_id = getattr(axis_value, "ValueNameID", None)
		if axis_value.Format == 4 and value_name_id in original_name_ids and value_name_id not in kept_name_ids:
			continue
		filtered_tables.append(axis_value)

	stat_table.AxisValueArray.AxisValue = filtered_tables
	stat_table.AxisValueCount = len(filtered_tables)


def remap_axis_value_tables(ttfont, axis_tag, transform):
	if "STAT" not in ttfont:
		return

	stat_table = ttfont["STAT"].table
	if not getattr(stat_table, "DesignAxisRecord", None):
		return
	if not getattr(stat_table, "AxisValueArray", None):
		return

	axis_indices = {}
	for index, record in enumerate(stat_table.DesignAxisRecord.Axis):
		axis_indices[record.AxisTag] = index

	if axis_tag not in axis_indices:
		return

	target_index = axis_indices[axis_tag]

	for axis_value in stat_table.AxisValueArray.AxisValue:
		if axis_value.Format in (1, 2, 3) and axis_value.AxisIndex == target_index:
			if hasattr(axis_value, "Value"):
				axis_value.Value = transform(axis_value.Value)
			if hasattr(axis_value, "NominalValue"):
				axis_value.NominalValue = transform(axis_value.NominalValue)
			if hasattr(axis_value, "RangeMinValue"):
				axis_value.RangeMinValue = transform(axis_value.RangeMinValue)
			if hasattr(axis_value, "RangeMaxValue"):
				axis_value.RangeMaxValue = transform(axis_value.RangeMaxValue)
			if hasattr(axis_value, "LinkedValue"):
				axis_value.LinkedValue = transform(axis_value.LinkedValue)
		elif axis_value.Format == 4:
			for axis_value_record in axis_value.AxisValueRecord:
				if axis_value_record.AxisIndex == target_index:
					axis_value_record.Value = transform(axis_value_record.Value)


def remap_weight_axis(ttfont, style_to_weight_value):
	if not style_to_weight_value or "fvar" not in ttfont:
		return

	fvar_table = ttfont["fvar"]
	axes_by_tag = axis_records_by_tag(ttfont)
	if "wght" not in axes_by_tag:
		raise ValueError("The exported variable font does not contain a wght axis.")

	wght_axis = axes_by_tag["wght"]
	old_triple = (wght_axis.minValue, wght_axis.defaultValue, wght_axis.maxValue)
	anchors = {
		wght_axis.minValue: wght_axis.minValue,
		wght_axis.defaultValue: wght_axis.defaultValue,
		wght_axis.maxValue: wght_axis.maxValue,
	}

	for instance_record in fvar_table.instances:
		style_name = name_for_instance(ttfont, instance_record)
		if style_name in style_to_weight_value:
			anchors[instance_record.coordinates["wght"]] = style_to_weight_value[style_name]

	if len(anchors) <= 3:
		return

	ensure_monotonic_mapping(anchors)

	def user_space_transform(value):
		return piecewise_user_map(value, anchors)

	new_triple = tuple(user_space_transform(value) for value in old_triple)
	old_avar_segments = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}
	if "avar" in ttfont:
		old_avar_segments = ttfont["avar"].segments.get("wght", old_avar_segments)

	sample_user_values = set(anchors.keys())
	for normalized_key in old_avar_segments.keys():
		sample_user_values.add(denormalize_value(normalized_key, old_triple))

	new_segments = {}
	for old_user_value in sorted(sample_user_values):
		new_user_value = user_space_transform(old_user_value)
		new_normalized = normalizeValue(new_user_value, new_triple, extrapolate=True)
		old_normalized = normalizeValue(old_user_value, old_triple, extrapolate=True)
		final_normalized = piecewiseLinearMap(old_normalized, old_avar_segments)
		new_segments[new_normalized] = final_normalized

	new_segments[-1.0] = piecewiseLinearMap(-1.0, old_avar_segments)
	new_segments[0.0] = piecewiseLinearMap(0.0, old_avar_segments)
	new_segments[1.0] = piecewiseLinearMap(1.0, old_avar_segments)
	new_segments = rounded_mapping(new_segments)

	wght_axis.minValue, wght_axis.defaultValue, wght_axis.maxValue = new_triple

	for instance_record in fvar_table.instances:
		if "wght" in instance_record.coordinates:
			instance_record.coordinates["wght"] = user_space_transform(instance_record.coordinates["wght"])

	if "avar" not in ttfont:
		ttfont["avar"] = newTable("avar")
		ttfont["avar"].majorVersion = 1
		ttfont["avar"].minorVersion = 0
		ttfont["avar"].segments = {}

	all_segments = {}
	for axis in fvar_table.axes:
		if axis.axisTag == "wght":
			all_segments["wght"] = dict(sorted(new_segments.items()))
		elif "avar" in ttfont and axis.axisTag in ttfont["avar"].segments:
			all_segments[axis.axisTag] = ttfont["avar"].segments[axis.axisTag]
		else:
			all_segments[axis.axisTag] = {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0}

	ttfont["avar"].segments = all_segments
	remap_axis_value_tables(ttfont, "wght", user_space_transform)


def newest_ttf_in_folder(folder_path):
	font_paths = [
		os.path.join(folder_path, file_name)
		for file_name in os.listdir(folder_path)
		if file_name.lower().endswith(".ttf")
	]
	if not font_paths:
		return None
	return max(font_paths, key=os.path.getmtime)


def font_path_with_extension(font_path, extension):
	base_path, _old_extension = os.path.splitext(font_path)
	return "%s.%s" % (base_path, extension)


def save_webfont_flavors(ttf_path, flavors=("woff", "woff2")):
	output_paths = []
	errors = []
	for flavor in flavors:
		output_path = font_path_with_extension(ttf_path, flavor)
		webfont = TTFont(ttf_path)
		try:
			webfont.flavor = flavor
			webfont.save(output_path)
			output_paths.append(output_path)
		except Exception as error:
			errors.append("%s: %s" % (flavor.upper(), str(error)))
			if os.path.isfile(output_path):
				try:
					os.remove(output_path)
				except Exception:
					pass
		finally:
			webfont.close()

	if errors:
		raise RuntimeError("Could not export webfont format(s): %s" % "; ".join(errors))
	return output_paths


def analyze_feature_variations(ttfont):
	summary = {}
	if "fvar" not in ttfont:
		return summary

	axis_tags = [axis.axisTag for axis in ttfont["fvar"].axes]
	for table_tag in ("GSUB", "GPOS"):
		if table_tag not in ttfont:
			continue
		table = ttfont[table_tag].table
		feature_variations = getattr(table, "FeatureVariations", None)
		if not feature_variations:
			continue

		used_axes = set()
		used_features = set()
		records = getattr(feature_variations, "FeatureVariationRecord", []) or []
		for record in records:
			condition_set = getattr(record, "ConditionSet", None)
			if condition_set:
				for condition in getattr(condition_set, "ConditionTable", []) or []:
					if getattr(condition, "Format", None) != 1:
						continue
					axis_index = getattr(condition, "AxisIndex", None)
					if axis_index is None:
						continue
					if 0 <= axis_index < len(axis_tags):
						used_axes.add(axis_tags[axis_index])

			substitutions = getattr(record, "FeatureTableSubstitution", None)
			if substitutions:
				for sub_record in getattr(substitutions, "SubstitutionRecord", []) or []:
					feature_index = getattr(sub_record, "FeatureIndex", None)
					feature_list = getattr(table, "FeatureList", None)
					feature_records = getattr(feature_list, "FeatureRecord", []) if feature_list else []
					if feature_index is None or feature_index >= len(feature_records):
						continue
					used_features.add(feature_records[feature_index].FeatureTag)

		summary[table_tag] = {
			"axes": used_axes,
			"features": used_features,
		}
	return summary


def remaining_feature_variation_axes(ttfont):
	remaining_axes = set()
	summary = analyze_feature_variations(ttfont)
	for table_summary in summary.values():
		remaining_axes.update(table_summary["axes"])
	return remaining_axes


def dedupe_gsub_feature_variation_conditions(ttfont):
	if "GSUB" not in ttfont:
		return 0
	table = ttfont["GSUB"].table
	feature_variations = getattr(table, "FeatureVariations", None)
	if not feature_variations:
		return 0

	records = getattr(feature_variations, "FeatureVariationRecord", []) or []
	if not records:
		return 0

	def condition_key(record):
		condition_set = getattr(record, "ConditionSet", None)
		if condition_set is None:
			return ("universal",)
		parts = []
		for condition in getattr(condition_set, "ConditionTable", []) or []:
			if getattr(condition, "Format", None) != 1:
				parts.append(("fmt", getattr(condition, "Format", None)))
				continue
			parts.append(
				(
					int(getattr(condition, "AxisIndex", -1)),
					round(float(getattr(condition, "FilterRangeMinValue", -1.0)), 6),
					round(float(getattr(condition, "FilterRangeMaxValue", 1.0)), 6),
				)
			)
		return tuple(parts)

	def substitution_key(record):
		substitutions = getattr(record, "FeatureTableSubstitution", None)
		if substitutions is None:
			return ()
		parts = []
		for sub_record in getattr(substitutions, "SubstitutionRecord", []) or []:
			feature_index = int(getattr(sub_record, "FeatureIndex", -1))
			feature_obj = getattr(sub_record, "Feature", None)
			lookup_count = int(getattr(feature_obj, "LookupCount", 0)) if feature_obj is not None else -1
			lookup_list = tuple(getattr(feature_obj, "LookupListIndex", []) or []) if feature_obj is not None else ()
			parts.append((feature_index, lookup_count, lookup_list))
		return tuple(parts)

	seen = set()
	new_records = []
	removed = 0
	for record in records:
		key = (condition_key(record), substitution_key(record))
		if key in seen:
			removed += 1
			continue
		seen.add(key)
		new_records.append(record)

	if removed:
		feature_variations.FeatureVariationRecord = new_records
		feature_variations.FeatureVariationCount = len(new_records)
	return removed


SUB_BY_PATTERN = re.compile(r"\bsub\s+([A-Za-z0-9_.]+)\s+by\s+([A-Za-z0-9_.]+)\s*;")


def best_default_export_folder(font):
	default_keys = [
		"GXExportPath",
		"GXExportPathManual",
		"OTFExportPath",
		"ExportPath",
	]
	for key in default_keys:
		try:
			value = Glyphs.defaults.get(key)
		except Exception:
			value = None
		if value and os.path.isdir(value):
			return value

	font_path = getattr(font, "filepath", None)
	if font_path:
		try:
			font_dir = os.path.dirname(str(font_path))
			if os.path.isdir(font_dir):
				return font_dir
		except Exception:
			pass

	return os.path.expanduser("~/Desktop")


def instance_weight_class_value(instance):
	candidates = []
	if hasattr(instance, "weightClass"):
		candidates.append(getattr(instance, "weightClass"))
	if hasattr(instance, "customParameters"):
		try:
			candidates.append(instance.customParameters["weightClass"])
		except Exception:
			pass

	for value in candidates:
		if value in (None, "", 0):
			continue
		try:
			return float(value)
		except Exception:
			continue
	return None


class SelectiveVariableFontExport(object):
	def __init__(self):
		if vanilla is None:
			Message(
				"Missing Vanilla Module",
				"Install the Vanilla module in Glyphs and run the script again.",
			)
			return

		self.font = Glyphs.font
		if self.font is None:
			Message("No Font Open", "Open a Glyphs file first.")
			return

		self.variable_settings = [
			instance for instance in self.font.instances if getattr(instance, "type", None) == INSTANCETYPEVARIABLE
		]
		self.has_existing_variable_settings = bool(self.variable_settings)

		self.axes = list(self.font.axes)
		if not self.axes:
			Message(
				"No Axes Found",
				"This font has no variable axes in Font Info > Font. Add axes first and run again.",
			)
			return
		self.axis_tags = [axis.axisTag for axis in self.axes]
		self.axis_index_by_tag = {axis.axisTag: index for index, axis in enumerate(self.axes)}
		self.exportable_instances = [
			instance
			for instance in self.font.instances
			if getattr(instance, "type", None) != INSTANCETYPEVARIABLE
		]

		self.axis_meta = {}
		self.axis_controls = {}
		self.instance_items = []
		self.instance_axis_values = {}
		self.instance_default_weight_classes = {}
		self.origin_instance_index = None
		self._updating_instance_list = False
		for index, axis in enumerate(self.axes):
			self.axis_meta[axis.axisTag] = self.estimate_axis_bounds(index)

		axis_box_height = 48 + len(self.axes) * 34
		instance_top = 174 + axis_box_height
		desired_list_height = min(300, max(160, len(self.exportable_instances) * 24 + 28))
		window_height = instance_top + 24 + desired_list_height + 90
		window_height = max(640, min(920, window_height))
		list_height = window_height - (instance_top + 24) - 90

		self.window = vanilla.FloatingWindow(
			(980, window_height),
			"Selective Variable Font Export",
			minSize=(980, 640),
		)

		self.window.introText = vanilla.TextBox(
			(15, 14, -15, 34),
			"Choose which axes stay variable, which named instances stay in fvar, and optional weight remaps."
			+ ("" if self.has_existing_variable_settings else " No Variable Font Setting found: a temporary one will be created."),
		)
		self.window.settingLabel = vanilla.TextBox((15, 52, 150, 20), "Variable font setting")
		self.window.settingPopup = vanilla.PopUpButton(
			(180, 50, -15, 25),
			[item.name or "Variable" for item in self.variable_settings]
			if self.variable_settings
			else ["Auto (temporary setting)"],
		)
		self.window.exportPathLabel = vanilla.TextBox((15, 86, 150, 20), "Export folder")
		self.window.exportPathInput = vanilla.EditText(
			(180, 84, -110, 24),
			self.load_last_export_folder(),
		)
		self.window.exportPathButton = vanilla.Button(
			(-100, 84, 85, 24),
			"Choose...",
			callback=self.choose_export_folder,
		)

		self.window.axisHeader = vanilla.TextBox(
			(15, 122, -15, 20),
			"Axes: use exact values. Keep checked = variable range. Uncheck = pin axis.",
		)
		self.window.axisGroup = vanilla.Group((15, 146, -15, axis_box_height))
		self.window.axisGroup.axisHeader = vanilla.TextBox((10, 8, 130, 20), "Axis")
		self.window.axisGroup.minHeader = vanilla.TextBox((165, 8, 90, 20), "Min")
		self.window.axisGroup.maxHeader = vanilla.TextBox((265, 8, 90, 20), "Max")
		self.window.axisGroup.pinHeader = vanilla.TextBox((365, 8, 110, 20), "Pin (dropped)")
		self.window.axisGroup.pickHeader = vanilla.TextBox((490, 8, 285, 20), "Pick Existing Instance Value")
		self.window.axisGroup.targetHeader = vanilla.TextBox((780, 8, 90, 20), "Set To")

		for row_index, axis in enumerate(self.axes):
			tag = axis.axisTag
			meta = self.axis_meta[tag]
			y = 30 + row_index * 34
			row = {}
			row["keepCheck"] = vanilla.CheckBox(
				(10, y + 2, 130, 20),
				tag,
				value=True,
				callback=self.axis_mode_changed,
			)
			row["keepCheck"].axisTag = tag
			row["minInput"] = vanilla.EditText(
				(165, y, 90, 22),
				self.format_number(meta["min"]),
				callback=self.axis_input_changed,
			)
			row["minInput"].axisTag = tag
			row["minInput"].inputRole = "min"
			row["maxInput"] = vanilla.EditText(
				(265, y, 90, 22),
				self.format_number(meta["max"]),
				callback=self.axis_input_changed,
			)
			row["maxInput"].axisTag = tag
			row["maxInput"].inputRole = "max"
			row["pinInput"] = vanilla.EditText(
				(365, y, 110, 22),
				self.format_number(meta["default"]),
				callback=self.axis_input_changed,
			)
			row["pinInput"].axisTag = tag
			row["pinInput"].inputRole = "pin"
			row["pinFollowsOrigin"] = True
			picker_labels, picker_values = self.axis_picker_items(tag)
			row["pickerValues"] = picker_values
			row["pickerPopup"] = vanilla.PopUpButton((490, y - 1, 285, 25), picker_labels)
			row["pickerPopup"].axisTag = tag
			row["targetPopup"] = vanilla.PopUpButton((780, y - 1, 80, 25), ["Min", "Max", "Pin"])
			row["targetPopup"].axisTag = tag
			row["usePickButton"] = vanilla.Button((865, y - 1, 80, 25), "Use", callback=self.axis_pick_value_clicked)
			row["usePickButton"].axisTag = tag

			row["pinInput"].enable(False)
			self.axis_controls[tag] = row

			for control_name, control in row.items():
				setattr(self.window.axisGroup, "%s_%s" % (tag, control_name), control)

		self.window.instanceHeader = vanilla.TextBox(
			(15, instance_top, -15, 20),
			"Instances: include in fvar and optionally remap named instances to wght values.",
		)
		self.window.selectAllInstancesButton = vanilla.Button(
			(-215, instance_top - 2, 95, 24),
			"Select All",
			callback=self.select_all_instances,
		)
		self.window.unselectAllInstancesButton = vanilla.Button(
			(-115, instance_top - 2, 100, 24),
			"Unselect All",
			callback=self.unselect_all_instances,
		)
		for instance in self.exportable_instances:
			instance_index = len(self.instance_items)
			axis_values = {}
			raw_values = getattr(instance, "axes", None) or []
			for axis_index, axis in enumerate(self.axes):
				if axis_index < len(raw_values):
					axis_values[axis.axisTag] = float(raw_values[axis_index])
			self.instance_axis_values[instance_index] = axis_values
			weight_class = instance_weight_class_value(instance)
			self.instance_default_weight_classes[instance_index] = (
				None if weight_class is None else float(weight_class)
			)
			self.instance_items.append(
				{
					"include": True,
					"origin": False,
					"name": instance.name,
					"weightRemap": "" if weight_class is None else self.format_number(weight_class),
				}
			)
		include_column = {"title": "Include", "key": "include", "width": 70, "editable": True}
		origin_column = {"title": "Origin", "key": "origin", "width": 70, "editable": True}
		if hasattr(vanilla, "CheckBoxListCell"):
			include_column["cell"] = vanilla.CheckBoxListCell()
			origin_column["cell"] = vanilla.CheckBoxListCell()

		self.window.instanceList = vanilla.List(
			(15, instance_top + 24, -15, list_height),
			self.instance_items,
			columnDescriptions=[
				include_column,
				origin_column,
				{"title": "Instance", "key": "name", "width": 260, "editable": False},
				{"title": "wght Remap", "key": "weightRemap", "editable": True},
			],
			showColumnTitles=True,
			allowsMultipleSelection=False,
			editCallback=self.instance_list_edited,
		)

		self.window.hintText = vanilla.TextBox(
			(15, -64, -15, 18),
			"Leave wght remap empty to keep original values. Use numbers like 400 or 700.",
		)
		self.window.cancelButton = vanilla.Button((15, -36, 120, 25), "Close", callback=self.close_window)
		self.window.exportButton = vanilla.Button((400, -36, -15, 25), "Export", callback=self.export)
		self.window.setDefaultButton(self.window.exportButton)
		self.window.open()
		self.window.makeKey()
		self.set_initial_origin_instance()
		self.update_instances_from_axis_constraints()

	def format_number(self, value):
		return ("%.2f" % float(value)).rstrip("0").rstrip(".")

	def estimate_axis_bounds(self, axis_index):
		values = []
		for master in self.font.masters:
			axis_values = getattr(master, "axes", None)
			if axis_values and len(axis_values) > axis_index:
				values.append(float(axis_values[axis_index]))
		for instance in self.exportable_instances:
			axis_values = getattr(instance, "axes", None)
			if axis_values and len(axis_values) > axis_index:
				values.append(float(axis_values[axis_index]))
		if not values:
			return {"min": 0.0, "default": 0.0, "max": 1.0}

		minimum = min(values)
		maximum = max(values)
		if minimum == maximum:
			maximum = minimum + 1.0

		default_value = values[0]
		for master in self.font.masters:
			axis_values = getattr(master, "axes", None)
			if axis_values and len(axis_values) > axis_index:
				default_value = float(axis_values[axis_index])
				break
		default_value = min(max(default_value, minimum), maximum)
		return {"min": minimum, "default": default_value, "max": maximum}

	def collect_axis_marker_values(self, axis_tag):
		axis_index = self.axis_index_by_tag[axis_tag]
		by_value = {}
		for instance in self.exportable_instances:
			raw_values = getattr(instance, "axes", None) or []
			if axis_index >= len(raw_values):
				continue
			value = float(raw_values[axis_index])
			key = round(value, 4)
			if key not in by_value:
				by_value[key] = {"value": value, "names": []}
			by_value[key]["names"].append(instance.name)
		return [by_value[key] for key in sorted(by_value.keys())]

	def axis_picker_items(self, axis_tag):
		labels = ["Pick instance value..."]
		values = [None]
		for item in self.collect_axis_marker_values(axis_tag):
			label_names = ", ".join(item["names"][:2])
			if len(item["names"]) > 2:
				label_names += " +%d" % (len(item["names"]) - 2)
			labels.append("%s (%s)" % (self.format_number(item["value"]), label_names))
			values.append(float(item["value"]))
		return labels, values

	def close_window(self, sender):
		self.window.close()

	def load_last_export_folder(self):
		saved_path = Glyphs.defaults.get(PREFS_PREFIX + "lastExportFolder")
		if saved_path and os.path.isdir(saved_path):
			return saved_path
		return best_default_export_folder(self.font)

	def save_last_export_folder(self, folder_path):
		if folder_path and os.path.isdir(folder_path):
			Glyphs.defaults[PREFS_PREFIX + "lastExportFolder"] = folder_path

	def axis_mode_changed(self, sender):
		tag = sender.axisTag
		controls = self.axis_controls[tag]
		keep_enabled = bool(controls["keepCheck"].get())
		controls["minInput"].enable(keep_enabled)
		controls["maxInput"].enable(keep_enabled)
		controls["pinInput"].enable(not keep_enabled)
		if keep_enabled:
			controls["pinFollowsOrigin"] = True
		self.sync_axis_inputs(tag)
		self.update_instances_from_axis_constraints()

	def axis_input_changed(self, sender):
		tag = sender.axisTag
		controls = self.axis_controls[tag]
		role = sender.inputRole
		meta = self.axis_meta[tag]
		min_bound = meta["min"]
		max_bound = meta["max"]

		def read_or_current_value(input_control, fallback):
			try:
				value = float(str(input_control.get()).strip())
			except Exception:
				value = float(fallback)
			return min(max(value, min_bound), max_bound)

		current_min = self.safe_float(controls["minInput"].get(), meta["min"])
		current_max = self.safe_float(controls["maxInput"].get(), meta["max"])
		current_pin = self.safe_float(controls["pinInput"].get(), meta["default"])

		if role == "min":
			min_value = read_or_current_value(controls["minInput"], current_min)
			max_value = read_or_current_value(controls["maxInput"], current_max)
			if min_value > max_value:
				max_value = min_value
			controls["minInput"].set(self.format_number(min_value))
			controls["maxInput"].set(self.format_number(max_value))
		elif role == "max":
			min_value = read_or_current_value(controls["minInput"], current_min)
			max_value = read_or_current_value(controls["maxInput"], current_max)
			if max_value < min_value:
				min_value = max_value
			controls["minInput"].set(self.format_number(min_value))
			controls["maxInput"].set(self.format_number(max_value))
		else:
			pin_value = read_or_current_value(controls["pinInput"], current_pin)
			controls["pinInput"].set(self.format_number(pin_value))
			controls["pinFollowsOrigin"] = False
		self.sync_axis_inputs(tag)
		self.update_instances_from_axis_constraints()

	def axis_pick_value_clicked(self, sender):
		tag = sender.axisTag
		controls = self.axis_controls[tag]
		pick_index = controls["pickerPopup"].get()
		if pick_index <= 0:
			return
		values = controls.get("pickerValues", [None])
		if pick_index >= len(values):
			return
		value = values[pick_index]
		if value is None:
			return
		target_index = controls["targetPopup"].get()
		target_role = ["min", "max", "pin"][target_index]
		if target_role == "min":
			controls["minInput"].set(self.format_number(value))
			self.axis_input_changed(controls["minInput"])
		elif target_role == "max":
			controls["maxInput"].set(self.format_number(value))
			self.axis_input_changed(controls["maxInput"])
		else:
			controls["pinInput"].set(self.format_number(value))
			controls["pinFollowsOrigin"] = False
			self.axis_input_changed(controls["pinInput"])
		controls["pickerPopup"].set(0)

	def sync_axis_inputs(self, tag):
		controls = self.axis_controls[tag]
		controls["minInput"].set(self.format_number(self.safe_float(controls["minInput"].get(), self.axis_meta[tag]["min"])))
		controls["maxInput"].set(self.format_number(self.safe_float(controls["maxInput"].get(), self.axis_meta[tag]["max"])))
		controls["pinInput"].set(self.format_number(self.safe_float(controls["pinInput"].get(), self.axis_meta[tag]["default"])))

	def safe_float(self, raw_value, fallback):
		try:
			return float(str(raw_value).strip())
		except Exception:
			return float(fallback)

	def is_active_regular_instance(self, instance):
		if not self.is_instance_active(instance):
			return False
		if not self.instance_name_contains_regular(instance):
			return False
		return True

	def is_instance_active(self, instance):
		if hasattr(instance, "active"):
			return bool(getattr(instance, "active", True))
		return bool(getattr(instance, "exports", True))

	def instance_name_contains_regular(self, instance):
		name_candidates = [
			(getattr(instance, "name", "") or "").strip().lower(),
			(getattr(instance, "styleName", "") or "").strip().lower(),
		]
		for name in name_candidates:
			if not name:
				continue
			if "regular" in name:
				return True
		return False

	def set_initial_origin_instance(self):
		if not self.instance_items:
			return
		default_index = None
		active_indices = []
		for index, instance in enumerate(self.exportable_instances):
			if self.is_instance_active(instance):
				active_indices.append(index)

		for index in active_indices:
			if self.instance_name_contains_regular(self.exportable_instances[index]):
				default_index = index
				break

		if default_index is None and active_indices:
			best_distance = None
			best_index = None
			for index in active_indices:
				weight_class = instance_weight_class_value(self.exportable_instances[index])
				if weight_class is None:
					continue
				distance = abs(float(weight_class) - 400.0)
				if best_distance is None or distance < best_distance:
					best_distance = distance
					best_index = index
			if best_index is not None:
				default_index = best_index

		if default_index is None:
			for index, row in enumerate(self.instance_items):
				if row.get("include", True):
					default_index = index
					break
		if default_index is None:
			default_index = 0
		self.origin_instance_index = default_index
		rows = list(self.window.instanceList.get())
		for index, row in enumerate(rows):
			row["origin"] = index == default_index
		self._updating_instance_list = True
		self.window.instanceList.set(rows)
		self._updating_instance_list = False
		self.apply_origin_to_dropped_axes()

	def apply_origin_to_dropped_axes(self):
		if self.origin_instance_index is None:
			return False
		origin_axis_values = self.instance_axis_values.get(self.origin_instance_index, {})
		changed = False
		for axis in self.axes:
			tag = axis.axisTag
			if tag not in self.axis_controls:
				continue
			controls = self.axis_controls[tag]
			if controls["keepCheck"].get():
				continue
			if not controls.get("pinFollowsOrigin", True):
				continue
			if tag not in origin_axis_values:
				continue
			new_value = self.format_number(origin_axis_values[tag])
			if str(controls["pinInput"].get()).strip() != new_value:
				controls["pinInput"].set(new_value)
				changed = True
		return changed

	def choose_valid_origin_index(self, rows):
		marked_indices = [
			index for index, row in enumerate(rows) if row.get("origin", False) and row.get("include", True)
		]
		if marked_indices:
			if self.origin_instance_index in marked_indices and len(marked_indices) > 1:
				for index in reversed(marked_indices):
					if index != self.origin_instance_index:
						return index
			return marked_indices[-1]
		included_indices = [index for index, row in enumerate(rows) if row.get("include", True)]
		if not included_indices:
			return None

		# Prefer "Regular" among included instances. Active regular is preferred, but
		# non-active regular is still better than arbitrary fallback.
		active_regular_indices = []
		regular_indices = []
		for index in included_indices:
			if index >= len(self.exportable_instances):
				continue
			instance = self.exportable_instances[index]
			if self.instance_name_contains_regular(instance):
				regular_indices.append(index)
				if self.is_instance_active(instance):
					active_regular_indices.append(index)
		if active_regular_indices:
			return active_regular_indices[0]
		if regular_indices:
			return regular_indices[0]

		# Next best: usWeightClass closest to 400 among included instances.
		best_weight_index = None
		best_weight_distance = None
		for index in included_indices:
			if index >= len(self.exportable_instances):
				continue
			weight_class = instance_weight_class_value(self.exportable_instances[index])
			if weight_class is None:
				continue
			distance = abs(float(weight_class) - 400.0)
			if best_weight_distance is None or distance < best_weight_distance:
				best_weight_distance = distance
				best_weight_index = index
		if best_weight_index is not None:
			return best_weight_index

		# Then keep current origin if still valid.
		if self.origin_instance_index in included_indices:
			return self.origin_instance_index
		return included_indices[0]

	def normalize_origin_selection(self, rows):
		updated = False
		valid_origin = self.choose_valid_origin_index(rows)
		self.origin_instance_index = valid_origin
		for index, row in enumerate(rows):
			should_be_origin = (valid_origin is not None and index == valid_origin)
			if bool(row.get("origin", False)) != should_be_origin:
				row["origin"] = should_be_origin
				updated = True
		return updated

	def select_all_instances(self, sender):
		rows = list(self.window.instanceList.get())
		for row in rows:
			row["include"] = True
		if self.normalize_origin_selection(rows):
			pass
		self._updating_instance_list = True
		self.window.instanceList.set(rows)
		self._updating_instance_list = False
		self.update_instances_from_axis_constraints()

	def unselect_all_instances(self, sender):
		rows = list(self.window.instanceList.get())
		for row in rows:
			row["include"] = False
		if self.normalize_origin_selection(rows):
			pass
		self._updating_instance_list = True
		self.window.instanceList.set(rows)
		self._updating_instance_list = False
		self.update_instances_from_axis_constraints()

	def instance_list_edited(self, sender):
		if self._updating_instance_list:
			return
		rows = list(self.window.instanceList.get())
		changed = self.normalize_origin_selection(rows)
		if changed:
			self._updating_instance_list = True
			self.window.instanceList.set(rows)
			self._updating_instance_list = False
		if self.apply_origin_to_dropped_axes():
			self.update_instances_from_axis_constraints()

	def instance_matches_axis_constraints(self, instance_index):
		axis_values = self.instance_axis_values.get(instance_index, {})
		for axis in self.axes:
			tag = axis.axisTag
			if tag not in axis_values:
				return False
			controls = self.axis_controls[tag]
			meta = self.axis_meta[tag]
			value = axis_values[tag]
			if controls["keepCheck"].get():
				min_value = self.safe_float(controls["minInput"].get(), meta["min"])
				max_value = self.safe_float(controls["maxInput"].get(), meta["max"])
				if min_value > max_value:
					min_value, max_value = max_value, min_value
				if value < min_value - 1e-4 or value > max_value + 1e-4:
					return False
			else:
				pin_value = self.safe_float(controls["pinInput"].get(), meta["default"])
				if abs(value - pin_value) > 1e-4:
					return False
		return True

	def update_instances_from_axis_constraints(self):
		if self._updating_instance_list:
			return
		rows = list(self.window.instanceList.get())
		updated = False
		for index, row in enumerate(rows):
			should_include = self.instance_matches_axis_constraints(index)
			if bool(row.get("include", True)) != bool(should_include):
				row["include"] = bool(should_include)
				updated = True
		if self.normalize_origin_selection(rows):
			updated = True
		if updated:
			self._updating_instance_list = True
			self.window.instanceList.set(rows)
			self._updating_instance_list = False
		if self.apply_origin_to_dropped_axes():
			# Origin changed pin defaults for dropped axes; re-evaluate instance matches once.
			rows = list(self.window.instanceList.get())
			second_update = False
			for index, row in enumerate(rows):
				should_include = self.instance_matches_axis_constraints(index)
				if bool(row.get("include", True)) != bool(should_include):
					row["include"] = bool(should_include)
					second_update = True
			if self.normalize_origin_selection(rows):
				second_update = True
			if second_update:
				self._updating_instance_list = True
				self.window.instanceList.set(rows)
				self._updating_instance_list = False

	def collect_axis_configuration(self):
		keep_axes = set()
		axis_limits = {}
		for axis in self.axes:
			tag = axis.axisTag
			controls = self.axis_controls[tag]
			meta = self.axis_meta[tag]
			if controls["keepCheck"].get():
				keep_axes.add(tag)
				min_value = self.safe_float(controls["minInput"].get(), meta["min"])
				max_value = self.safe_float(controls["maxInput"].get(), meta["max"])
				if min_value > max_value:
					min_value, max_value = max_value, min_value
				min_value = min(max(min_value, meta["min"]), meta["max"])
				max_value = min(max(max_value, meta["min"]), meta["max"])
				if abs(min_value - meta["min"]) > 1e-6 or abs(max_value - meta["max"]) > 1e-6:
					axis_limits[tag] = (min_value, max_value)
			else:
				pin_value = self.safe_float(controls["pinInput"].get(), meta["default"])
				pin_value = min(max(pin_value, meta["min"]), meta["max"])
				axis_limits[tag] = pin_value

		if not keep_axes:
			raise ValueError("Keep at least one axis as variable.")
		return keep_axes, axis_limits

	def collect_instance_configuration(self):
		keep_instances = set()
		weight_remap = {}
		for index, row in enumerate(self.window.instanceList.get()):
			name = row.get("name", "").strip()
			if not name:
				continue
			if row.get("include", True):
				keep_instances.add(name)
			raw_weight = str(row.get("weightRemap", "")).strip()
			if raw_weight:
				current_value = float(raw_weight)
				default_value = self.instance_default_weight_classes.get(index)
				if default_value is None or abs(current_value - default_value) > 1e-6:
					weight_remap[name] = current_value
		return keep_instances, weight_remap

	def choose_export_folder(self, sender):
		open_panel = NSOpenPanel.openPanel()
		open_panel.setCanChooseFiles_(False)
		open_panel.setCanChooseDirectories_(True)
		open_panel.setAllowsMultipleSelection_(False)
		open_panel.setCanCreateDirectories_(True)
		open_panel.setPrompt_("Choose")
		response = open_panel.runModal()
		if response == 1 and open_panel.URL():
			selected_folder = open_panel.URL().path()
			self.window.exportPathInput.set(selected_folder)
			self.save_last_export_folder(selected_folder)

	def collect_variable_substitution_targets(self):
		targets = set()
		features = getattr(self.font, "features", []) or []
		for feature in features:
			code = getattr(feature, "code", "") or ""
			in_variable_block = False
			for raw_line in code.splitlines():
				line = raw_line.strip()
				if line.startswith("#ifdef") and "VARIABLE" in line:
					in_variable_block = True
					continue
				if line.startswith("#endif"):
					in_variable_block = False
					continue
				if not in_variable_block:
					continue
				match = SUB_BY_PATTERN.search(line)
				if match:
					targets.add(match.group(2))
		return sorted(targets)

	def is_glyph_master_compatible(self, glyph_name):
		try:
			glyph = self.font.glyphs[glyph_name]
		except Exception:
			glyph = None
		if glyph is None:
			return False, "missing glyph"

		compare_strings = set()
		for master in self.font.masters:
			layer = glyph.layers[master.id]
			if layer is None:
				return False, "missing master layer"
			signature = ""
			try:
				compare_attr = getattr(layer, "compareString", None)
				if callable(compare_attr):
					signature = compare_attr() or ""
				elif compare_attr is not None:
					signature = compare_attr
			except Exception:
				signature = ""
			compare_strings.add(str(signature))
		if len(compare_strings) > 1:
			return False, "master shapes are incompatible"
		return True, ""

	def validate_variable_substitution_targets(self):
		targets = self.collect_variable_substitution_targets()
		if not targets:
			return

		issues = []
		for glyph_name in targets:
			ok, reason = self.is_glyph_master_compatible(glyph_name)
			if not ok:
				issues.append("%s (%s)" % (glyph_name, reason))

		if issues:
			Glyphs.clearLog()
			print("Potential VARIABLE substitution interpolation issues:")
			for issue in issues:
				print(" - %s" % issue)
			Glyphs.showNotification(
				"Selective VF Export",
				"Interpolation preflight: check Script Console for VARIABLE substitution glyph issues.",
			)

	def export(self, sender):
		try:
			self.validate_variable_substitution_targets()
			keep_axes, axis_limits = self.collect_axis_configuration()
			keep_instances, weight_remap = self.collect_instance_configuration()

			setting = None
			if self.variable_settings:
				setting = self.variable_settings[self.window.settingPopup.get()]
			destination_folder = self.window.exportPathInput.get().strip()
			if not destination_folder:
				raise ValueError("Please set an export folder.")
			if not os.path.isdir(destination_folder):
				os.makedirs(destination_folder)
			self.save_last_export_folder(destination_folder)
			setting_name = (setting.name if setting is not None else "") or "SubsetVF"
			file_name = "%s-%s.ttf" % (self.font.familyName, setting_name)
			destination_path = os.path.join(destination_folder, file_name)

			source_font_path = self.export_selected_variable_setting(setting, destination_folder)
			if source_font_path is None:
				raise RuntimeError("Glyphs did not produce a TTF variable font export.")

			exported_paths = self.postprocess_export(
				source_font_path=source_font_path,
				destination_path=destination_path,
				axis_limits=axis_limits,
				keep_instances=keep_instances,
				weight_remap=weight_remap,
				keep_axes=keep_axes,
			)
			if source_font_path != destination_path and os.path.isfile(source_font_path):
				try:
					os.remove(source_font_path)
				except Exception:
					pass

			Glyphs.showNotification(
				"Selective VF Export",
				"Exported TTF, WOFF and WOFF2",
			)
			for exported_path in exported_paths:
				print("Exported: %s" % exported_path)
			self.window.close()
		except Exception as error:
			Glyphs.clearLog()
			print(traceback.format_exc())
			Message(str(error), "Selective VF Export Failed")

	def export_selected_variable_setting(self, selected_setting, export_folder):
		# If no variable setting exists, try native variable export without toggling instances.
		if selected_setting is None:
			exported_ttf_path = self.try_export_variable_font(export_folder)
			if exported_ttf_path is None:
				raise RuntimeError(
					"Glyphs could not export a variable font without a Variable Font Setting. "
					"Please add one in Font Info > Exports."
				)
			return exported_ttf_path

		original_export_states = {}
		for instance in self.variable_settings:
			original_export_states[id(instance)] = getattr(instance, "exports", True)

		try:
			for instance in self.variable_settings:
				instance.exports = instance is selected_setting

			exported_ttf_path = self.try_export_variable_font(export_folder)
			if exported_ttf_path is None:
				raise RuntimeError("Glyphs did not produce a TTF variable font export.")
			return exported_ttf_path
		finally:
			for instance in self.variable_settings:
				instance.exports = original_export_states[id(instance)]

	def try_export_variable_font(self, export_folder):
		existing_ttf_mtimes = {}
		for file_name in os.listdir(export_folder):
			if not file_name.lower().endswith(".ttf"):
				continue
			file_path = os.path.join(export_folder, file_name)
			existing_ttf_mtimes[file_path] = os.path.getmtime(file_path)

		export_attempts = [
			{"Format": VARIABLE, "Containers": [PLAIN], "FontPath": export_folder},
			{"format": VARIABLE, "containers": [PLAIN], "fontPath": export_folder},
			{"Format": VARIABLE, "fontPath": export_folder},
			{"format": VARIABLE, "fontPath": export_folder},
			{"FontPath": export_folder},
			{"fontPath": export_folder},
			{},
		]

		last_error = None
		for kwargs in export_attempts:
			try:
				self.font.export(**kwargs)
				candidates = []
				for file_name in os.listdir(export_folder):
					if not file_name.lower().endswith(".ttf"):
						continue
					file_path = os.path.join(export_folder, file_name)
					current_mtime = os.path.getmtime(file_path)
					previous_mtime = existing_ttf_mtimes.get(file_path)
					if previous_mtime is None or current_mtime > previous_mtime + 1e-6:
						candidates.append(file_path)
				if candidates:
					return max(candidates, key=os.path.getmtime)
			except TypeError as error:
				last_error = error
				continue
			except Exception as error:
				last_error = error
				continue
		if last_error is not None:
			raise RuntimeError(
				"Variable font export failed for all API signatures: %s" % str(last_error)
			)
		return None

	def postprocess_export(self, source_font_path, destination_path, axis_limits, keep_instances, weight_remap, keep_axes):
		ttfont = TTFont(source_font_path)
		if "fvar" not in ttfont:
			raise ValueError("The exported font does not contain an fvar table.")

		feature_variation_summary = analyze_feature_variations(ttfont)
		feature_variation_axes = set()
		for table_summary in feature_variation_summary.values():
			feature_variation_axes.update(table_summary["axes"])
		gsub_summary = feature_variation_summary.get("GSUB", {"axes": set(), "features": set()})
		gsub_fv_axes = set(gsub_summary.get("axes", set()))
		gsub_fv_features = set(gsub_summary.get("features", set()))
		if feature_variation_summary:
			Glyphs.clearLog()
			print("FeatureVariations detected in exported VF source:")
			for table_tag in sorted(feature_variation_summary.keys()):
				info = feature_variation_summary[table_tag]
				print(
					" - %s axes=[%s] features=[%s]"
					% (
						table_tag,
						", ".join(sorted(info["axes"])) or "-",
						", ".join(sorted(info["features"])) or "-",
					)
				)

		exported_axis_tags = {axis.axisTag for axis in ttfont["fvar"].axes}
		unknown_axis_limit_tags = sorted(set(axis_limits.keys()).difference(exported_axis_tags))
		if unknown_axis_limit_tags:
			raise ValueError(
				"The exported font does not contain axis tag(s): %s" % ", ".join(unknown_axis_limit_tags)
			)

		if weight_remap and "wght" not in keep_axes:
			raise ValueError("Weight remapping requires the wght axis to be kept.")
		if weight_remap and "wght" in feature_variation_axes:
			raise ValueError(
				"Weight remap is disabled because GSUB/GPOS FeatureVariations use the wght axis. "
				"Keep the original wght scale for this export, or rewrite the feature-variation thresholds in the source first."
			)

		# Warn (but don't hard-block) when GSUB FeatureVariations span dropped+kept axes.
		# We validate against the actual post-instanced font below.
		if gsub_fv_axes:
			dropped_gsub_fv_axes = sorted(gsub_fv_axes.difference(set(keep_axes)))
			kept_gsub_fv_axes = sorted(gsub_fv_axes.intersection(set(keep_axes)))
			if dropped_gsub_fv_axes and kept_gsub_fv_axes:
				feature_label = "rlig" if "rlig" in gsub_fv_features else "GSUB feature variations"
				print(
					"Warning: %s use axes [%s] and this export drops [%s] while keeping [%s]. "
					"Proceeding with instancing and validating the result."
					% (
						feature_label,
						", ".join(sorted(gsub_fv_axes)),
						", ".join(dropped_gsub_fv_axes),
						", ".join(kept_gsub_fv_axes),
					)
				)
		else:
			dropped_gsub_fv_axes = []

		# UI axis values can be in Glyphs design-space coordinates, while exported VF
		# may use remapped user-space coordinates. Convert limits/pins before instancing.
		mapped_axis_limits = {}
		for axis in ttfont["fvar"].axes:
			tag = axis.axisTag
			if tag not in axis_limits:
				continue
			export_triple = (axis.minValue, axis.defaultValue, axis.maxValue)
			ui_meta = self.axis_meta.get(tag)
			if ui_meta:
				ui_triple = (ui_meta["min"], ui_meta["default"], ui_meta["max"])
			else:
				ui_triple = export_triple

			limit_value = axis_limits[tag]
			if isinstance(limit_value, tuple):
				mapped_min = map_value_between_axis_triples(limit_value[0], ui_triple, export_triple)
				mapped_max = map_value_between_axis_triples(limit_value[1], ui_triple, export_triple)
				if mapped_min > mapped_max:
					mapped_min, mapped_max = mapped_max, mapped_min
				mapped_min = min(max(mapped_min, axis.minValue), axis.maxValue)
				mapped_max = min(max(mapped_max, axis.minValue), axis.maxValue)
				mapped_axis_limits[tag] = (mapped_min, mapped_max)
			else:
				mapped_pin = map_value_between_axis_triples(limit_value, ui_triple, export_triple)
				mapped_pin = min(max(mapped_pin, axis.minValue), axis.maxValue)
				mapped_axis_limits[tag] = mapped_pin

		# Build final limits against the exported font axes so unchecked axes are always pinned/dropped.
		effective_axis_limits = {}
		for axis in ttfont["fvar"].axes:
			tag = axis.axisTag
			if tag in mapped_axis_limits:
				effective_axis_limits[tag] = mapped_axis_limits[tag]
				continue
			if tag not in keep_axes:
				pin_value = None
				if tag in self.axis_controls:
					ui_default = self.axis_meta.get(tag, {}).get("default", axis.defaultValue)
					ui_pin = self.safe_float(self.axis_controls[tag]["pinInput"].get(), ui_default)
					ui_triple = (
						self.axis_meta.get(tag, {}).get("min", axis.minValue),
						ui_default,
						self.axis_meta.get(tag, {}).get("max", axis.maxValue),
					)
					export_triple = (axis.minValue, axis.defaultValue, axis.maxValue)
					pin_value = map_value_between_axis_triples(ui_pin, ui_triple, export_triple)
					pin_value = min(max(pin_value, axis.minValue), axis.maxValue)
				effective_axis_limits[tag] = pin_value

		if effective_axis_limits:
			ttfont = instancer.instantiateVariableFont(
				ttfont,
				effective_axis_limits,
				inplace=False,
				updateFontNames=False,
			)
			if "fvar" in ttfont:
				remaining_axis_tags = {axis.axisTag for axis in ttfont["fvar"].axes}
				unexpected_axes = sorted(remaining_axis_tags.difference(keep_axes))
				if unexpected_axes:
					raise ValueError(
						"Could not drop axis tag(s): %s. Check axis tags in the source VF setting."
						% ", ".join(unexpected_axes)
					)

		if dropped_gsub_fv_axes:
			removed_records = dedupe_gsub_feature_variation_conditions(ttfont)
			if removed_records:
				print(
					"GSUB cleanup: removed %d duplicate FeatureVariation condition records after axis drop."
					% removed_records
				)

		still_referenced_axes = remaining_feature_variation_axes(ttfont)
		invalid_feature_axes = sorted(still_referenced_axes.difference(set(keep_axes)))
		if invalid_feature_axes:
			raise ValueError(
				"FeatureVariations still reference dropped axis tag(s): %s." % ", ".join(invalid_feature_axes)
			)

		original_name_ids, kept_name_ids = filter_named_instances(ttfont, keep_instances)
		update_stat_for_named_instance_filter(ttfont, original_name_ids, kept_name_ids)
		remap_weight_axis(ttfont, weight_remap)

		output_folder = os.path.dirname(destination_path)
		if output_folder and not os.path.isdir(output_folder):
			os.makedirs(output_folder)
		try:
			ttfont.save(destination_path)
		finally:
			ttfont.close()
		return [destination_path] + save_webfont_flavors(destination_path)


SelectiveVariableFontExport()
