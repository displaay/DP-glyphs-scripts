#MenuTitle: Transfer UFO Metrics and Kerning
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
# Intended to run inside GlyphsApp only.
# Uses GlyphsApp and AppKit only.
# vanilla was removed because it caused environment issues.

__doc__ = """
Imports spacing, kerning, and kerning groups from external UFO files into
matching Glyphs masters, with per-master assignment and transfer options.
"""

import os
import plistlib
import traceback
import xml.etree.ElementTree as ET

import AppKit
import objc
from Foundation import NSObject, NSMakeRect
from AppKit import (
	NSBackingStoreBuffered,
	NSBox,
	NSButton,
	NSTextField,
	NSWindow,
	NSModalResponseOK,
	NSOpenPanel,
)
from GlyphsApp import Glyphs, Message


EPSILON = 1e-6
EMPTY_KERNING_VALUE = 9.223372036854776e18
METRIC_KEY_NAMES = ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey")
KERNING_GROUP_MODE_OVERWRITE = "overwrite"
KERNING_GROUP_MODE_MERGE = "merge"
KERNING_GROUP_MODE_CREATE_MISSING = "create_missing"
KERNING_GROUP_MODE_TITLES = {
	KERNING_GROUP_MODE_OVERWRITE: "Overwrite existing kerning groups",
	KERNING_GROUP_MODE_MERGE: "Merge with existing kerning groups",
	KERNING_GROUP_MODE_CREATE_MISSING: "Only create missing kerning groups",
}
KERNING_GROUP_MODE_SUMMARY = {
	KERNING_GROUP_MODE_OVERWRITE: "overwrite",
	KERNING_GROUP_MODE_MERGE: "merge",
	KERNING_GROUP_MODE_CREATE_MISSING: "only missing",
}
STATE_ON = getattr(AppKit, "NSControlStateValueOn", 1)
STATE_OFF = getattr(AppKit, "NSControlStateValueOff", 0)
SWITCH_BUTTON_TYPE = getattr(AppKit, "NSSwitchButton", getattr(AppKit, "NSButtonTypeSwitch", 3))
RADIO_BUTTON_TYPE = getattr(AppKit, "NSRadioButton", getattr(AppKit, "NSButtonTypeRadio", 4))
ROUNDED_BEZEL_STYLE = getattr(AppKit, "NSRoundedBezelStyle", getattr(AppKit, "NSBezelStyleRounded", 1))
WINDOW_STYLE_MASK = (
	getattr(AppKit, "NSWindowStyleMaskTitled", 1 << 0)
	| getattr(AppKit, "NSWindowStyleMaskClosable", 1 << 1)
	| getattr(AppKit, "NSWindowStyleMaskMiniaturizable", 1 << 2)
)


def normalize_number(value):
	try:
		number = float(value)
	except Exception:
		number = 0.0
	if abs(number) < EPSILON:
		number = 0.0
	rounded = round(number)
	if abs(number - rounded) < EPSILON:
		return int(rounded)
	return number


def format_metric_value(value):
	number = normalize_number(value)
	if isinstance(number, int):
		return str(number)
	text = ("%.6f" % number).rstrip("0").rstrip(".")
	if text == "-0":
		text = "0"
	return text


def path_exists(path):
	return bool(path) and os.path.exists(os.path.expanduser(path))


def mark_font_changed(font):
	try:
		font.changed()
		return
	except Exception:
		pass


def get_selected_glyph_names(font):
	names = []
	seen = set()
	for layer in getattr(font, "selectedLayers", []) or []:
		glyph = getattr(layer, "parent", None)
		name = getattr(glyph, "name", None)
		if name and name not in seen:
			names.append(name)
			seen.add(name)
	return names


def all_glyph_names(font):
	return [glyph.name for glyph in font.glyphs if getattr(glyph, "name", None)]


def layer_has_auto_metrics(layer):
	for attrName in ("hasAlignedWidth", "isAligned"):
		try:
			value = getattr(layer, attrName)
			if callable(value):
				value = value()
			if value:
				return True
		except Exception:
			pass
	return False


def clear_layer_metrics_keys(layer):
	layer.leftMetricsKey = None
	layer.rightMetricsKey = None
	layer.widthMetricsKey = None


def clear_glyph_metrics_keys(glyph):
	glyph.leftMetricsKey = None
	glyph.rightMetricsKey = None
	glyph.widthMetricsKey = None


def set_layer_numeric_metrics(layer, width, lsb, rsb):
	layer.width = width
	layer.LSB = lsb
	layer.RSB = rsb


def lock_layer_metrics(layer, width, lsb, rsb):
	layer.leftMetricsKey = "==%s" % format_metric_value(lsb)
	layer.rightMetricsKey = "==%s" % format_metric_value(rsb)
	layer.widthMetricsKey = "==%s" % format_metric_value(width)


def same_number(valueA, valueB):
	return normalize_number(valueA) == normalize_number(valueB)


def same_text(valueA, valueB):
	return (valueA or None) == (valueB or None)


def normalize_group_value(value):
	if value is None:
		return None
	text = str(value).strip()
	return text or None


def empty_kerning_value(value):
	try:
		return abs(float(value)) >= (EMPTY_KERNING_VALUE * 0.5)
	except Exception:
		return False


def read_kerning_value(font, master_id, leftKey, rightKey):
	try:
		value = font.kerningForPair(master_id, leftKey, rightKey)
	except Exception:
		return None
	if empty_kerning_value(value):
		return None
	return normalize_number(value)


def get_real_layer_for_id(glyph, layer_id):
	layer = None
	try:
		layer = glyph.layers[layer_id]
	except Exception:
		layer = None
	if layer is None:
		try:
			layer = glyph.layerForId_(layer_id)
		except Exception:
			layer = None
	if layer is None:
		return None
	try:
		if str(layer.layerId) != str(layer_id):
			return None
	except Exception:
		return None
	return layer


def get_real_master_layer(glyph, master):
	return get_real_layer_for_id(glyph, master.id)


def get_effective_metrics_key(glyph, layer, keyName):
	try:
		layerValue = getattr(layer, keyName)
		if layerValue:
			return str(layerValue)
	except Exception:
		pass
	try:
		glyphValue = getattr(glyph, keyName)
		if glyphValue:
			return str(glyphValue)
	except Exception:
		pass
	return None


def capture_layer_state(glyph, layer):
	state = {
		"width": normalize_number(layer.width),
		"LSB": normalize_number(layer.LSB),
		"RSB": normalize_number(layer.RSB),
	}
	for keyName in METRIC_KEY_NAMES:
		layerValue = None
		glyphValue = None
		try:
			layerValue = getattr(layer, keyName)
		except Exception:
			layerValue = None
		try:
			glyphValue = getattr(glyph, keyName)
		except Exception:
			glyphValue = None
		state["local_%s" % keyName] = str(layerValue) if layerValue else None
		state["glyph_%s" % keyName] = str(glyphValue) if glyphValue else None
		state["effective_%s" % keyName] = get_effective_metrics_key(glyph, layer, keyName)
	return state


def layer_state_changed(beforeState, afterState):
	for keyName in (
		"width",
		"LSB",
		"RSB",
		"local_leftMetricsKey",
		"local_rightMetricsKey",
		"local_widthMetricsKey",
		"glyph_leftMetricsKey",
		"glyph_rightMetricsKey",
		"glyph_widthMetricsKey",
		"effective_leftMetricsKey",
		"effective_rightMetricsKey",
		"effective_widthMetricsKey",
	):
		if keyName in ("width", "LSB", "RSB"):
			if not same_number(beforeState[keyName], afterState[keyName]):
				return True
		elif not same_text(beforeState[keyName], afterState[keyName]):
			return True
	return False


def format_layer_state(state):
	return (
		"width=%s LSB=%s RSB=%s "
		"keys(local: %s / %s / %s, glyph: %s / %s / %s, effective: %s / %s / %s)"
		% (
			format_metric_value(state["width"]),
			format_metric_value(state["LSB"]),
			format_metric_value(state["RSB"]),
			state["local_leftMetricsKey"],
			state["local_rightMetricsKey"],
			state["local_widthMetricsKey"],
			state["glyph_leftMetricsKey"],
			state["glyph_rightMetricsKey"],
			state["glyph_widthMetricsKey"],
			state["effective_leftMetricsKey"],
			state["effective_rightMetricsKey"],
			state["effective_widthMetricsKey"],
		)
	)


def notify_layer_metrics(layer, sync=False):
	try:
		layer.setNeedUpdateMetrics()
	except Exception:
		pass
	if sync:
		try:
			layer.syncMetrics()
		except Exception:
			pass
	try:
		layer.updateMetrics()
	except Exception:
		pass


def write_spacing_to_layer(glyph, layer, width, lsb, rsb, removeKeys=False, lockValues=False):
	width = normalize_number(width)
	lsb = normalize_number(lsb)
	rsb = normalize_number(rsb)
	keyClearFailure = False
	if removeKeys:
		try:
			currentWidth = normalize_number(layer.width)
			currentLSB = normalize_number(layer.LSB)
			currentRSB = normalize_number(layer.RSB)
			clear_layer_metrics_keys(layer)
			clear_glyph_metrics_keys(glyph)
			set_layer_numeric_metrics(layer, currentWidth, currentLSB, currentRSB)
		except Exception:
			keyClearFailure = True
	set_layer_numeric_metrics(layer, width, lsb, rsb)
	if lockValues:
		lock_layer_metrics(layer, width, lsb, rsb)
		notify_layer_metrics(layer, sync=True)
	else:
		notify_layer_metrics(layer, sync=False)
	return keyClearFailure


def verify_spacing_write(glyph, layer, width, lsb, rsb, removeKeys=False, lockValues=False):
	try:
		glyphName = glyph.name
	except Exception:
		glyphName = None
	try:
		layerId = layer.layerId
	except Exception:
		layerId = None
	if not glyphName or not layerId:
		return False, None
	font = Glyphs.font
	if not font:
		return False, None
	try:
		targetGlyph = font.glyphs[glyphName]
	except Exception:
		targetGlyph = None
	if targetGlyph is None:
		return False, None
	targetLayer = get_real_layer_for_id(targetGlyph, layerId)
	if targetLayer is None:
		return False, None
	afterState = capture_layer_state(targetGlyph, targetLayer)
	valuesMatch = (
		same_number(afterState["width"], width)
		and same_number(afterState["LSB"], lsb)
		and same_number(afterState["RSB"], rsb)
	)
	if lockValues:
		expectedLeft = "==%s" % format_metric_value(lsb)
		expectedRight = "==%s" % format_metric_value(rsb)
		expectedWidth = "==%s" % format_metric_value(width)
		keysMatch = (
			same_text(afterState["local_leftMetricsKey"], expectedLeft)
			and same_text(afterState["local_rightMetricsKey"], expectedRight)
			and same_text(afterState["local_widthMetricsKey"], expectedWidth)
			and same_text(afterState["effective_leftMetricsKey"], expectedLeft)
			and same_text(afterState["effective_rightMetricsKey"], expectedRight)
			and same_text(afterState["effective_widthMetricsKey"], expectedWidth)
		)
	elif removeKeys:
		keysMatch = (
			afterState["effective_leftMetricsKey"] is None
			and afterState["effective_rightMetricsKey"] is None
			and afterState["effective_widthMetricsKey"] is None
		)
	else:
		keysMatch = True
	return valuesMatch and keysMatch, afterState


def mapping_items(mapping):
	if mapping is None:
		return []
	try:
		return list(mapping.items())
	except Exception:
		pass
	try:
		keys = list(mapping.keys())
		return [(key, mapping[key]) for key in keys]
	except Exception:
		pass
	return []


def get_master_kerning(font, master_id):
	try:
		return font.kerning[master_id]
	except Exception:
		pass
	try:
		return font.kerning.get(master_id)
	except Exception:
		pass
	return None


def glyph_id_name_map(font):
	mapping = {}
	for glyph in getattr(font, "glyphs", []) or []:
		name = getattr(glyph, "name", None)
		if not name:
			continue
		for attrName in ("id", "glyphId"):
			try:
				glyphId = getattr(glyph, attrName)
			except Exception:
				glyphId = None
			if glyphId:
				mapping[str(glyphId)] = name
	return mapping


def kerning_api_key(font, key, idNameMap=None):
	text = str(key)
	if text.startswith("@MMK_"):
		return text
	try:
		if font.glyphs[text] is not None:
			return text
	except Exception:
		pass
	if idNameMap and text in idNameMap:
		return idNameMap[text]
	return text


def remove_kerning_pair(font, master_id, leftKey, rightKey, idNameMap=None):
	attempts = []
	for attempt in (
		(str(leftKey), str(rightKey)),
		(
			kerning_api_key(font, leftKey, idNameMap=idNameMap),
			kerning_api_key(font, rightKey, idNameMap=idNameMap),
		),
	):
		if attempt in attempts:
			continue
		attempts.append(attempt)
	for attemptLeft, attemptRight in attempts:
		try:
			font.removeKerningForPair(master_id, attemptLeft, attemptRight)
		except Exception:
			pass


def clear_master_kerning(font, master_id, dry_run=False):
	initialCount = count_master_kerning_pairs(font, master_id)
	if dry_run or initialCount == 0:
		return initialCount
	idNameMap = glyph_id_name_map(font)
	for _pass in range(5):
		masterKerning = get_master_kerning(font, master_id)
		if not masterKerning:
			break
		pairs = []
		seen = set()
		for leftKey, rightDict in mapping_items(masterKerning):
			for rightKey, _value in mapping_items(rightDict):
				pairKey = (leftKey, rightKey)
				if pairKey in seen:
					continue
				seen.add(pairKey)
				pairs.append(pairKey)
		if not pairs:
			break
		for leftKey, rightKey in pairs:
			remove_kerning_pair(font, master_id, leftKey, rightKey, idNameMap=idNameMap)
		if count_master_kerning_pairs(font, master_id) == 0:
			break
	return initialCount


def count_master_kerning_pairs(font, master_id):
	masterKerning = get_master_kerning(font, master_id)
	if not masterKerning:
		return 0
	count = 0
	seen = set()
	for leftKey, rightDict in mapping_items(masterKerning):
		for rightKey, _value in mapping_items(rightDict):
			pairKey = (leftKey, rightKey)
			if pairKey in seen:
				continue
			seen.add(pairKey)
			count += 1
	return count


def collect_font_kerning_maps(font, overrides=None):
	glyphNames = set()
	leftGroupNames = set()
	rightGroupNames = set()
	overrides = overrides or {}
	for glyph in font.glyphs:
		name = getattr(glyph, "name", None)
		if not name:
			continue
		glyphNames.add(name)
		try:
			rightGroup = overrides.get((name, "rightKerningGroup"), glyph.rightKerningGroup)
			if rightGroup:
				leftGroupNames.add(str(rightGroup))
		except Exception:
			pass
		try:
			leftGroup = overrides.get((name, "leftKerningGroup"), glyph.leftKerningGroup)
			if leftGroup:
				rightGroupNames.add(str(leftGroup))
		except Exception:
			pass
	return glyphNames, leftGroupNames, rightGroupNames


def map_ufo_group_name_to_glyph_property(groupName):
	groupName = str(groupName)
	if groupName.startswith("public.kern1."):
		groupValue = normalize_group_value(groupName[len("public.kern1.") :])
		if groupValue:
			return "rightKerningGroup", groupValue, "left"
		return None, None, None
	if groupName.startswith("public.kern2."):
		groupValue = normalize_group_value(groupName[len("public.kern2.") :])
		if groupValue:
			return "leftKerningGroup", groupValue, "right"
		return None, None, None
	return None, None, None


def classify_ufo_kerning_key(key, side, ufoGroups):
	key = str(key)
	if side == "left":
		if key.startswith("public.kern1.") or key.startswith("@MMK_L_"):
			return "group"
		if key in ufoGroups:
			return "group"
		return "glyph"
	if key.startswith("public.kern2.") or key.startswith("@MMK_R_"):
		return "group"
	if key in ufoGroups:
		return "group"
	return "glyph"


def classify_ufo_kerning_pair(leftKey, rightKey, ufoGroups):
	leftType = classify_ufo_kerning_key(leftKey, "left", ufoGroups)
	rightType = classify_ufo_kerning_key(rightKey, "right", ufoGroups)
	if leftType == "glyph" and rightType == "glyph":
		return "glyphGlyph"
	if leftType == "group" and rightType == "glyph":
		return "groupGlyph"
	if leftType == "glyph" and rightType == "group":
		return "glyphGroup"
	return "groupGroup"


def collect_ufo_kerning_group_records(ufoGroups):
	groupRecords = []
	for rawGroupName, members in mapping_items(ufoGroups):
		propertyName, groupValue, _side = map_ufo_group_name_to_glyph_property(rawGroupName)
		if propertyName is None:
			continue
		normalizedMembers = []
		seenMembers = set()
		if isinstance(members, (list, tuple)):
			for member in members:
				glyphName = normalize_group_value(member)
				if glyphName and glyphName not in seenMembers:
					seenMembers.add(glyphName)
					normalizedMembers.append(glyphName)
		groupRecords.append(
			{
				"rawGroupName": str(rawGroupName),
				"propertyName": propertyName,
				"groupValue": groupValue,
				"members": normalizedMembers,
			}
		)
	return groupRecords


def group_value_for_glyph(font, glyphName, propertyName, overrides=None):
	if overrides and (glyphName, propertyName) in overrides:
		return normalize_group_value(overrides[(glyphName, propertyName)])
	try:
		glyph = font.glyphs[glyphName]
	except Exception:
		glyph = None
	if glyph is None:
		return None
	try:
		return normalize_group_value(getattr(glyph, propertyName))
	except Exception:
		return None


def kerning_group_side_label(propertyName):
	if propertyName == "rightKerningGroup":
		return "left side"
	return "right side"


def map_ufo_kerning_key(key, side, glyphNames, leftGroupNames, rightGroupNames, ufoGroups, activeUFOGroupNames=None):
	def ufo_group_is_available(groupKey):
		if activeUFOGroupNames is not None:
			return groupKey in activeUFOGroupNames
		return groupKey in ufoGroups
	if key in glyphNames:
		return key
	if side == "left":
		if key.startswith("public.kern1."):
			groupName = key[len("public.kern1."):]
			if ufo_group_is_available(key) and groupName in leftGroupNames:
				return "@MMK_L_%s" % groupName
			return None
		if key.startswith("@MMK_L_"):
			groupName = key[len("@MMK_L_"):]
			if groupName in leftGroupNames:
				return key
			return None
		if ufo_group_is_available(key) and key in leftGroupNames:
			return "@MMK_L_%s" % key
		return None
	if key.startswith("public.kern2."):
		groupName = key[len("public.kern2."):]
		if ufo_group_is_available(key) and groupName in rightGroupNames:
			return "@MMK_R_%s" % groupName
		return None
	if key.startswith("@MMK_R_"):
		groupName = key[len("@MMK_R_"):]
		if groupName in rightGroupNames:
			return key
		return None
	if ufo_group_is_available(key) and key in rightGroupNames:
		return "@MMK_R_%s" % key
	return None


def read_plist(path, defaultValue):
	if not os.path.exists(path):
		return defaultValue
	with open(path, "rb") as handle:
		return plistlib.load(handle)


def midpoint(pointA, pointB):
	return (
		(pointA[0] + pointB[0]) * 0.5,
		(pointA[1] + pointB[1]) * 0.5,
	)


def transform_point(point, transform):
	x, y = point
	xx, xy, yx, yy, dx, dy = transform
	return (
		(xx * x) + (yx * y) + dx,
		(xy * x) + (yy * y) + dy,
	)


def transform_segment(segment, transform):
	segmentType = segment[0]
	if segmentType == "line":
		return (
			"line",
			transform_point(segment[1], transform),
			transform_point(segment[2], transform),
		)
	if segmentType == "quad":
		return (
			"quad",
			transform_point(segment[1], transform),
			transform_point(segment[2], transform),
			transform_point(segment[3], transform),
		)
	return (
		"cubic",
		transform_point(segment[1], transform),
		transform_point(segment[2], transform),
		transform_point(segment[3], transform),
		transform_point(segment[4], transform),
	)


def solve_quadratic(a, b, c):
	if abs(a) < EPSILON:
		if abs(b) < EPSILON:
			return []
		return [(-c) / b]
	discriminant = (b * b) - (4.0 * a * c)
	if discriminant < -EPSILON:
		return []
	if discriminant < 0.0:
		discriminant = 0.0
	root = discriminant ** 0.5
	denominator = 2.0 * a
	return [(-b - root) / denominator, (-b + root) / denominator]


def quad_value(p0, p1, p2, t):
	mt = 1.0 - t
	return (mt * mt * p0) + (2.0 * mt * t * p1) + (t * t * p2)


def cubic_value(p0, p1, p2, p3, t):
	mt = 1.0 - t
	return (
		(mt * mt * mt * p0)
		+ (3.0 * mt * mt * t * p1)
		+ (3.0 * mt * t * t * p2)
		+ (t * t * t * p3)
	)


def quad_bounds(p0, p1, p2):
	xValues = [p0[0], p2[0]]
	yValues = [p0[1], p2[1]]
	for axis in (0, 1):
		a = p0[axis] - (2.0 * p1[axis]) + p2[axis]
		b = -2.0 * p0[axis] + (2.0 * p1[axis])
		if abs(a) < EPSILON:
			continue
		t = -b / (2.0 * a)
		if EPSILON < t < (1.0 - EPSILON):
			xValues.append(quad_value(p0[0], p1[0], p2[0], t))
			yValues.append(quad_value(p0[1], p1[1], p2[1], t))
	return (min(xValues), min(yValues), max(xValues), max(yValues))


def cubic_bounds(p0, p1, p2, p3):
	xValues = [p0[0], p3[0]]
	yValues = [p0[1], p3[1]]
	for axis in (0, 1):
		a = -p0[axis] + (3.0 * p1[axis]) - (3.0 * p2[axis]) + p3[axis]
		b = (3.0 * p0[axis]) - (6.0 * p1[axis]) + (3.0 * p2[axis])
		c = (-3.0 * p0[axis]) + (3.0 * p1[axis])
		for t in solve_quadratic(3.0 * a, 2.0 * b, c):
			if EPSILON < t < (1.0 - EPSILON):
				xValues.append(cubic_value(p0[0], p1[0], p2[0], p3[0], t))
				yValues.append(cubic_value(p0[1], p1[1], p2[1], p3[1], t))
	return (min(xValues), min(yValues), max(xValues), max(yValues))


def union_bounds(boundsA, boundsB):
	if boundsA is None:
		return boundsB
	if boundsB is None:
		return boundsA
	return (
		min(boundsA[0], boundsB[0]),
		min(boundsA[1], boundsB[1]),
		max(boundsA[2], boundsB[2]),
		max(boundsA[3], boundsB[3]),
	)


def segments_bounds(segments):
	bounds = None
	for segment in segments:
		segmentType = segment[0]
		if segmentType == "line":
			xValues = [segment[1][0], segment[2][0]]
			yValues = [segment[1][1], segment[2][1]]
			segmentBounds = (min(xValues), min(yValues), max(xValues), max(yValues))
		elif segmentType == "quad":
			segmentBounds = quad_bounds(segment[1], segment[2], segment[3])
		else:
			segmentBounds = cubic_bounds(segment[1], segment[2], segment[3], segment[4])
		bounds = union_bounds(bounds, segmentBounds)
	return bounds


def quad_segments(startPoint, offcurves, endPoint):
	segments = []
	current = startPoint
	controls = list(offcurves)
	if not controls:
		segments.append(("line", current, endPoint))
		return segments
	for index, control in enumerate(controls[:-1]):
		implied = midpoint(control, controls[index + 1])
		segments.append(("quad", current, control, implied))
		current = implied
	segments.append(("quad", current, controls[-1], endPoint))
	return segments


def contour_to_segments(points):
	if not points:
		return []
	openContour = points[0]["type"] == "move"
	segments = []
	offcurves = []
	if openContour:
		startPoint = points[0]["point"]
		current = startPoint
		iterable = points[1:]
	else:
		if points[0]["type"] is None and points[-1]["type"] is None:
			startPoint = midpoint(points[-1]["point"], points[0]["point"])
			current = startPoint
			iterable = points
		else:
			startIndex = None
			for index, point in enumerate(points):
				if point["type"] is not None:
					startIndex = index
					break
			if startIndex is None:
				return []
			startPoint = points[startIndex]["point"]
			current = startPoint
			iterable = points[startIndex + 1 :] + points[: startIndex + 1]
	for point in iterable:
		pointType = point["type"]
		coords = point["point"]
		if pointType is None:
			offcurves.append(coords)
			continue
		if pointType == "move":
			current = coords
			offcurves = []
			continue
		if pointType == "line":
			segments.append(("line", current, coords))
			current = coords
			offcurves = []
			continue
		if pointType == "curve":
			if len(offcurves) != 2:
				raise ValueError("Invalid cubic contour")
			segments.append(("cubic", current, offcurves[0], offcurves[1], coords))
			current = coords
			offcurves = []
			continue
		if pointType == "qcurve":
			segments.extend(quad_segments(current, offcurves, coords))
			current = coords
			offcurves = []
			continue
		raise ValueError("Unsupported point type: %s" % pointType)
	if offcurves:
		if openContour:
			raise ValueError("Dangling offcurve in open contour")
		segments.extend(quad_segments(current, offcurves, startPoint))
	return segments


class UFOFontData(object):
	def __init__(self, ufoPath):
		self.path = os.path.expanduser(ufoPath)
		self.groups = read_plist(os.path.join(self.path, "groups.plist"), {})
		self.kerning = read_plist(os.path.join(self.path, "kerning.plist"), {})
		self.defaultLayerPath = self._default_layer_path()
		self.contents = read_plist(os.path.join(self.defaultLayerPath, "contents.plist"), {})
		self._shapeCache = {}

	def _default_layer_path(self):
		glyphsPath = os.path.join(self.path, "glyphs")
		if os.path.exists(os.path.join(glyphsPath, "contents.plist")):
			return glyphsPath
		layerContentsPath = os.path.join(self.path, "layercontents.plist")
		layerContents = read_plist(layerContentsPath, [])
		if layerContents:
			for _layerName, directoryName in layerContents:
				layerPath = os.path.join(self.path, directoryName)
				if directoryName == "glyphs" and os.path.exists(os.path.join(layerPath, "contents.plist")):
					return layerPath
			firstLayerPath = os.path.join(self.path, layerContents[0][1])
			if os.path.exists(os.path.join(firstLayerPath, "contents.plist")):
				return firstLayerPath
		raise IOError("No default UFO layer found: %s" % self.path)

	def glyph_exists(self, glyphName):
		return glyphName in self.contents

	def glyph_metrics(self, glyphName):
		shape = self._glyph_shape(glyphName, set())
		width = normalize_number(shape["width"])
		bounds = shape["bounds"]
		if bounds is None:
			lsb = 0
			rsb = width
		else:
			lsb = normalize_number(bounds[0])
			rsb = normalize_number(width - bounds[2])
		return normalize_number(width), normalize_number(lsb), normalize_number(rsb)

	def _glyph_shape(self, glyphName, stack):
		if glyphName in self._shapeCache:
			return self._shapeCache[glyphName]
		if glyphName in stack:
			raise ValueError("Component cycle in %s" % glyphName)
		if glyphName not in self.contents:
			raise KeyError("Glyph missing in UFO: %s" % glyphName)
		stack = set(stack)
		stack.add(glyphName)
		glifName = self.contents[glyphName]
		glifPath = os.path.join(self.defaultLayerPath, glifName)
		root = ET.parse(glifPath).getroot()
		advance = root.find("advance")
		width = 0.0
		if advance is not None and advance.get("width") is not None:
			width = float(advance.get("width"))
		segments = []
		outline = root.find("outline")
		if outline is not None:
			for child in list(outline):
				if child.tag == "contour":
					points = []
					for pointNode in child.findall("point"):
						points.append(
							{
								"point": (
									float(pointNode.get("x", 0.0)),
									float(pointNode.get("y", 0.0)),
								),
								"type": pointNode.get("type"),
							}
						)
					segments.extend(contour_to_segments(points))
				elif child.tag == "component":
					baseGlyph = child.get("base")
					if not baseGlyph:
						continue
					transform = (
						float(child.get("xScale", 1.0)),
						float(child.get("xyScale", 0.0)),
						float(child.get("yxScale", 0.0)),
						float(child.get("yScale", 1.0)),
						float(child.get("xOffset", 0.0)),
						float(child.get("yOffset", 0.0)),
					)
					baseShape = self._glyph_shape(baseGlyph, stack)
					for segment in baseShape["segments"]:
						segments.append(transform_segment(segment, transform))
		shape = {
			"width": width,
			"segments": segments,
			"bounds": segments_bounds(segments),
		}
		self._shapeCache[glyphName] = shape
		return shape


# PyObjC registers Objective-C subclass names globally in the runtime.
# Redefining the same class name in one session causes objc.error.
# This script therefore looks up and reuses the class if it already exists.
try:
	DisplaayUFOTransferWindowVerifiedWrites = objc.lookUpClass("DisplaayUFOTransferWindowVerifiedWrites")
except objc.nosuchclass_error:
	class DisplaayUFOTransferWindowVerifiedWrites(NSObject):
		def init(self):
			self = objc.super(DisplaayUFOTransferWindowVerifiedWrites, self).init()
			if self is None:
				return None
			self.font = Glyphs.font
			self.masterRows = []
			self.optionControls = {}
			self.window = None
			self.contentView = None
			self.contentHeight = 0
			if not self.font:
				Message("No Font Open", "Open a Glyphs file and run the script again.", OKButton="OK")
				return self
			self.build_ui()
			return self

		def frame_from_top(self, x, y, width, height):
			return NSMakeRect(x, self.contentHeight - y - height, width, height)

		def add_label(self, x, y, width, height, text):
			label = NSTextField.alloc().initWithFrame_(self.frame_from_top(x, y, width, height))
			label.setStringValue_(text)
			label.setBezeled_(False)
			label.setBordered_(False)
			label.setDrawsBackground_(False)
			label.setEditable_(False)
			label.setSelectable_(False)
			self.contentView.addSubview_(label)
			return label

		def add_text_field(self, x, y, width, height, value):
			field = NSTextField.alloc().initWithFrame_(self.frame_from_top(x, y, width, height))
			field.setStringValue_(value)
			self.contentView.addSubview_(field)
			return field

		def add_checkbox(self, x, y, width, height, title, value):
			button = NSButton.alloc().initWithFrame_(self.frame_from_top(x, y, width, height))
			button.setButtonType_(SWITCH_BUTTON_TYPE)
			button.setTitle_(title)
			button.setState_(STATE_ON if value else STATE_OFF)
			self.contentView.addSubview_(button)
			return button

		def add_radio(self, x, y, width, height, title, value):
			button = NSButton.alloc().initWithFrame_(self.frame_from_top(x, y, width, height))
			button.setButtonType_(RADIO_BUTTON_TYPE)
			button.setTitle_(title)
			button.setState_(STATE_ON if value else STATE_OFF)
			self.contentView.addSubview_(button)
			return button

		def add_button(self, x, y, width, height, title, action=None, tag=None):
			button = NSButton.alloc().initWithFrame_(self.frame_from_top(x, y, width, height))
			button.setTitle_(title)
			button.setBezelStyle_(ROUNDED_BEZEL_STYLE)
			if action:
				button.setTarget_(self)
				button.setAction_(action)
			if tag is not None:
				button.setTag_(tag)
			self.contentView.addSubview_(button)
			return button

		def add_box(self, x, y, width, height):
			box = NSBox.alloc().initWithFrame_(self.frame_from_top(x, y, width, height))
			box.setTitle_("")
			self.contentView.addSubview_(box)
			return box

		def checkbox_value(self, button):
			return bool(button.state() == STATE_ON)

		def set_button_enabled(self, button, enabled):
			try:
				button.setEnabled_(bool(enabled))
			except Exception:
				pass

		def set_control_enabled(self, control, enabled):
			try:
				control.setEnabled_(bool(enabled))
			except Exception:
				pass

		def transfer_action_enabled(self):
			return (
				self.checkbox_value(self.optionControls["transferSpacing"])
				or self.checkbox_value(self.optionControls["transferKerning"])
				or self.checkbox_value(self.optionControls["importKerningGroups"])
			)

		def kerning_group_mode(self):
			if self.checkbox_value(self.kerningGroupMergeRadio):
				return KERNING_GROUP_MODE_MERGE
			if self.checkbox_value(self.kerningGroupCreateMissingRadio):
				return KERNING_GROUP_MODE_CREATE_MISSING
			return KERNING_GROUP_MODE_OVERWRITE

		def kerning_group_mode_summary(self):
			return KERNING_GROUP_MODE_SUMMARY.get(self.kerning_group_mode(), "overwrite")

		def selected_transfer_master_count(self):
			count = 0
			for row in self.masterRows:
				if self.checkbox_value(row["transfer"]):
					count += 1
			return count

		def selected_transfer_rows(self):
			rows = []
			for row in self.masterRows:
				if not self.checkbox_value(row["transfer"]):
					continue
				path = os.path.expanduser(str(row["path"].stringValue()).strip())
				if path_exists(path):
					rows.append({"master": row["master"], "path": path})
			return rows

		def selected_glyph_count(self):
			return len(get_selected_glyph_names(self.font))

		def transfer_scope_glyph_count(self):
			if self.checkbox_value(self.optionControls["selectedOnly"]):
				return self.selected_glyph_count()
			return len(self.font.glyphs)

		def transfer_scope_text(self):
			if self.checkbox_value(self.optionControls["selectedOnly"]):
				count = self.selected_glyph_count()
				if count > 0:
					return "%d selected glyphs" % count
				return "selected glyphs"
			return "~%d glyphs" % self.transfer_scope_glyph_count()

		def selected_normalise_master_count(self):
			count = 0
			for row in self.masterRows:
				if self.checkbox_value(row["norm"]):
					count += 1
			return count

		def format_transfer_master_lines(self):
			lines = []
			for row in self.masterRows:
				if not self.checkbox_value(row["transfer"]):
					continue
				path = os.path.expanduser(str(row["path"].stringValue()).strip())
				if path_exists(path):
					lines.append("%s -> %s" % (row["master"].name, path))
				elif path:
					lines.append("%s -> [invalid path] %s" % (row["master"].name, path))
				else:
					lines.append("%s -> [no UFO assigned]" % row["master"].name)
			return lines

		def format_normalise_master_names(self):
			names = []
			for row in self.masterRows:
				if self.checkbox_value(row["norm"]):
					names.append(row["master"].name)
			return names

		def update_transfer_summary(self):
			readyMasters = len(self.selected_transfer_rows())
			scopeText = self.transfer_scope_text()
			kerningStatus = "ON" if self.checkbox_value(self.optionControls["transferKerning"]) else "OFF"
			groupStatus = "off"
			if self.checkbox_value(self.optionControls["importKerningGroups"]):
				groupStatus = self.kerning_group_mode_summary()
			autoStatus = "preserved" if self.checkbox_value(self.optionControls["preserveAuto"]) else "overridden"
			text = "Will process: %d masters | %s | kerning %s | kerning groups: %s | auto spacing %s" % (
				readyMasters,
				scopeText,
				kerningStatus,
				groupStatus,
				autoStatus,
			)
			self.whatWillHappenLabel.setStringValue_(text)

		def update_ui_state(self):
			self.update_transfer_summary()
			selectedMasters = self.selected_transfer_master_count()
			readyMasters = len(self.selected_transfer_rows())
			actionEnabled = self.transfer_action_enabled()
			transferEnabled = selectedMasters > 0 and readyMasters > 0 and actionEnabled
			self.set_button_enabled(self.runTransferButton, transferEnabled)
			kerningGroupControlsEnabled = self.checkbox_value(self.optionControls["importKerningGroups"])
			self.set_control_enabled(self.kerningGroupOverwriteRadio, kerningGroupControlsEnabled)
			self.set_control_enabled(self.kerningGroupMergeRadio, kerningGroupControlsEnabled)
			self.set_control_enabled(self.kerningGroupCreateMissingRadio, kerningGroupControlsEnabled)
			if transferEnabled:
				tooltip = "Process the selected masters with valid UFO assignments."
			elif selectedMasters == 0:
				tooltip = "Enable Transfer for at least one master."
			elif not actionEnabled:
				tooltip = "Enable spacing, kerning, or kerning-group import."
			else:
				tooltip = "Assign a valid UFO path to at least one selected transfer master."
			self.runTransferButton.setToolTip_(tooltip)
			selectedOnly = self.checkbox_value(self.normaliseSelectedRadio)
			hasSelectedGlyphs = self.selected_glyph_count() > 0
			normaliseMasters = self.selected_normalise_master_count()
			normaliseEnabled = normaliseMasters > 0 and ((not selectedOnly) or hasSelectedGlyphs)
			self.set_button_enabled(self.normaliseButton, normaliseEnabled)
			if normaliseEnabled:
				normaliseTooltip = "Convert metric formulas to fixed values for the selected normalisation masters."
			elif normaliseMasters == 0:
				normaliseTooltip = "Enable Normalise for at least one master."
			else:
				normaliseTooltip = "Select one or more glyphs in Font View, or switch scope to All glyphs."
			self.normaliseButton.setToolTip_(normaliseTooltip)

		def uiStateChanged_(self, sender):
			self.update_ui_state()

		def kerningGroupModeChanged_(self, sender):
			self.kerningGroupOverwriteRadio.setState_(STATE_ON if sender == self.kerningGroupOverwriteRadio else STATE_OFF)
			self.kerningGroupMergeRadio.setState_(STATE_ON if sender == self.kerningGroupMergeRadio else STATE_OFF)
			self.kerningGroupCreateMissingRadio.setState_(STATE_ON if sender == self.kerningGroupCreateMissingRadio else STATE_OFF)
			self.update_ui_state()

		def normaliseScopeChanged_(self, sender):
			if sender == self.normaliseSelectedRadio:
				self.normaliseSelectedRadio.setState_(STATE_ON)
				self.normaliseAllRadio.setState_(STATE_OFF)
			else:
				self.normaliseSelectedRadio.setState_(STATE_OFF)
				self.normaliseAllRadio.setState_(STATE_ON)
			self.update_ui_state()

		def controlTextDidChange_(self, notification):
			self.update_ui_state()

		def build_ui(self):
			masters = list(self.font.masters)
			contentWidth = 980
			rowHeight = 28
			transferBoxHeight = 334
			normaliseBoxHeight = 150
			y = 12
			self.contentHeight = 548 + (len(masters) * rowHeight)
			self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
				NSMakeRect(120, 120, contentWidth, self.contentHeight),
				WINDOW_STYLE_MASK,
				NSBackingStoreBuffered,
				False,
			)
			self.window.setTitle_("Transfer UFO Metrics and Kerning")
			self.window.setReleasedWhenClosed_(False)
			self.window.center()
			self.contentView = self.window.contentView()

			self.add_label(14, y, 60, 18, "Transfer")
			self.add_label(82, y, 70, 18, "Normalise")
			self.add_label(158, y, 150, 18, "Master")
			self.add_label(322, y, 400, 18, "UFO Path")
			self.add_label(798, y, 120, 18, "Actions")
			y += 24

			for index, master in enumerate(masters):
				row = {}
				row["master"] = master
				row["transfer"] = self.add_checkbox(14, y, 60, 20, "", True)
				row["norm"] = self.add_checkbox(82, y, 70, 20, "", True)
				row["name"] = self.add_label(158, y + 2, 150, 18, master.name)
				row["path"] = self.add_text_field(322, y - 2, 466, 22, "")
				row["transfer"].setTarget_(self)
				row["transfer"].setAction_("uiStateChanged:")
				row["norm"].setTarget_(self)
				row["norm"].setAction_("uiStateChanged:")
				row["path"].setDelegate_(self)
				row["choose"] = self.add_button(798, y - 3, 80, 24, "Choose", "chooseUFO:", index)
				row["clear"] = self.add_button(886, y - 3, 70, 24, "Clear", "clearUFO:", index)
				self.masterRows.append(row)
				y += rowHeight

			self.add_box(12, y, contentWidth - 24, transferBoxHeight)
			self.add_label(24, y + 10, 200, 18, "Transfer")
			self.add_label(24, y + 36, 180, 18, "Main import options")
			self.optionControls["transferSpacing"] = self.add_checkbox(24, y + 60, 300, 20, "Import spacing (width + sidebearings)", True)
			self.optionControls["transferKerning"] = self.add_checkbox(24, y + 84, 220, 20, "Import kerning from UFO", True)
			self.add_label(24, y + 128, 180, 18, "Spacing behaviour")
			self.optionControls["selectedOnly"] = self.add_checkbox(24, y + 152, 180, 20, "Only selected glyphs", False)
			self.optionControls["preserveAuto"] = self.add_checkbox(24, y + 176, 260, 20, "Keep auto spacing", True)
			self.optionControls["preserveAuto"].setToolTip_("Glyphs using automatic spacing won't be modified.")
			self.autoSpacingHelperLabel = self.add_label(44, y + 198, 360, 18, "Glyphs using automatic spacing will be skipped.")
			self.add_label(360, y + 36, 180, 18, "Kerning behaviour")
			self.optionControls["clearKerning"] = self.add_checkbox(360, y + 60, 220, 20, "Replace existing kerning", True)
			self.optionControls["importKerningGroups"] = self.add_checkbox(360, y + 92, 310, 20, "Import kerning groups before kerning", True)
			self.kerningGroupOverwriteRadio = self.add_radio(380, y + 116, 300, 20, KERNING_GROUP_MODE_TITLES[KERNING_GROUP_MODE_OVERWRITE], True)
			self.kerningGroupMergeRadio = self.add_radio(380, y + 140, 300, 20, KERNING_GROUP_MODE_TITLES[KERNING_GROUP_MODE_MERGE], False)
			self.kerningGroupCreateMissingRadio = self.add_radio(380, y + 164, 300, 20, KERNING_GROUP_MODE_TITLES[KERNING_GROUP_MODE_CREATE_MISSING], False)
			self.optionControls["removeKeys"] = self.add_checkbox(360, y + 208, 330, 20, "Remove existing metrics keys before import", False)
			self.optionControls["lockImported"] = self.add_checkbox(360, y + 232, 220, 20, "Lock imported values with ==", False)
			self.kerningGroupOverwriteRadio.setTarget_(self)
			self.kerningGroupOverwriteRadio.setAction_("kerningGroupModeChanged:")
			self.kerningGroupMergeRadio.setTarget_(self)
			self.kerningGroupMergeRadio.setAction_("kerningGroupModeChanged:")
			self.kerningGroupCreateMissingRadio.setTarget_(self)
			self.kerningGroupCreateMissingRadio.setAction_("kerningGroupModeChanged:")
			self.whatWillHappenLabel = self.add_label(24, y + 286, 900, 18, "")
			self.runTransferButton = self.add_button(764, y + 300, 184, 28, "Transfer Metrics & Kerning", "runTransfer:")
			for key in ("transferSpacing", "transferKerning", "clearKerning", "selectedOnly", "preserveAuto", "removeKeys", "lockImported", "importKerningGroups"):
				self.optionControls[key].setTarget_(self)
				self.optionControls[key].setAction_("uiStateChanged:")
			y += transferBoxHeight + 14

			self.add_box(12, y, contentWidth - 24, normaliseBoxHeight)
			self.add_label(24, y + 10, 300, 18, "Clean & Normalise Metrics")
			self.add_label(24, y + 32, 440, 18, "Convert metric formulas to fixed values and optionally lock them.")
			self.add_label(24, y + 58, 80, 18, "Scope")
			self.normaliseSelectedRadio = self.add_radio(24, y + 80, 160, 20, "Selected glyphs", True)
			self.normaliseAllRadio = self.add_radio(24, y + 104, 120, 20, "All glyphs", False)
			self.normaliseSelectedRadio.setTarget_(self)
			self.normaliseSelectedRadio.setAction_("normaliseScopeChanged:")
			self.normaliseAllRadio.setTarget_(self)
			self.normaliseAllRadio.setAction_("normaliseScopeChanged:")
			self.optionControls["lockNormalized"] = self.add_checkbox(360, y + 92, 290, 20, "Lock values with == after normalising", False)
			self.optionControls["lockNormalized"].setTarget_(self)
			self.optionControls["lockNormalized"].setAction_("uiStateChanged:")
			self.normaliseButton = self.add_button(748, y + 108, 200, 28, "Normalise Metrics Now", "normaliseMetrics:")
			if hasattr(self.window, "setDefaultButtonCell_"):
				self.window.setDefaultButtonCell_(self.runTransferButton.cell())
			self.window.makeKeyAndOrderFront_(None)
			self.update_ui_state()

		def chooseUFO_(self, sender):
			index = sender.tag()
			panel = NSOpenPanel.openPanel()
			panel.setCanChooseFiles_(True)
			panel.setCanChooseDirectories_(True)
			panel.setAllowsMultipleSelection_(False)
			if hasattr(panel, "setAllowedFileTypes_"):
				panel.setAllowedFileTypes_(["ufo"])
			if panel.runModal() == NSModalResponseOK:
				urls = panel.URLs()
				if urls:
					self.masterRows[index]["path"].setStringValue_(urls[0].path())
			self.update_ui_state()

		def clearUFO_(self, sender):
			self.masterRows[sender.tag()]["path"].setStringValue_("")
			self.update_ui_state()

		def runTransfer_(self, sender):
			print("UI: Transfer Metrics & Kerning")
			self.run_transfer(sender)

		def normaliseSelected_(self, sender):
			print("UI: Normalise Selected Glyphs")
			self.normalize_selected(sender)

		def normaliseAll_(self, sender):
			print("UI: Normalise All Glyphs")
			self.normalize_all(sender)

		def normaliseMetrics_(self, sender):
			print("UI: Normalise Metrics")
			selectedOnly = self.checkbox_value(self.normaliseSelectedRadio)
			self.run_normalisation(selectedOnly=selectedOnly)

		def normalizeSelected_(self, sender):
			self.normaliseSelected_(sender)

		def normalizeAll_(self, sender):
			self.normaliseAll_(sender)

		def current_options(self):
			return {
				"transferSpacing": self.checkbox_value(self.optionControls["transferSpacing"]),
				"transferKerning": self.checkbox_value(self.optionControls["transferKerning"]),
				"importKerningGroups": self.checkbox_value(self.optionControls["importKerningGroups"]),
				"kerningGroupMode": self.kerning_group_mode(),
				"clearKerning": self.checkbox_value(self.optionControls["clearKerning"]),
				"selectedOnly": self.checkbox_value(self.optionControls["selectedOnly"]),
				"removeKeys": self.checkbox_value(self.optionControls["removeKeys"]),
				"lockImported": self.checkbox_value(self.optionControls["lockImported"]),
				"preserveAuto": self.checkbox_value(self.optionControls["preserveAuto"]),
				"lockNormalized": self.checkbox_value(self.optionControls["lockNormalized"]),
			}

		def assigned_master_rows(self):
			return self.selected_transfer_rows()

		def normalisation_masters(self):
			masters = []
			for row in self.masterRows:
				if self.checkbox_value(row["norm"]):
					masters.append(row["master"])
			return masters

		def print_global_header(self, title, options, assignedRows):
			fontName = self.font.familyName or "Untitled"
			print("")
			print("=" * 72)
			print(title)
			print("Font: %s" % fontName)
			print("Masters: %d" % len(self.font.masters))
			print("Selected transfer masters: %d" % self.selected_transfer_master_count())
			print("Assigned masters: %d" % len(assignedRows))
			print("Skipped masters: %d" % (len(self.font.masters) - len(assignedRows)))
			print("Transfer master paths:")
			for line in self.format_transfer_master_lines():
				print("  %s" % line)
			print("Selected normalisation masters: %s" % (", ".join(self.format_normalise_master_names()) or "[none]"))
			print("Options:")
			print("  Import spacing: %s" % ("ON" if options["transferSpacing"] else "OFF"))
			print("  Import kerning from UFO: %s" % ("ON" if options["transferKerning"] else "OFF"))
			print("  Import kerning groups before kerning: %s" % ("ON" if options["importKerningGroups"] else "OFF"))
			print("  Kerning-group mode: %s" % KERNING_GROUP_MODE_TITLES.get(options["kerningGroupMode"], "Overwrite existing kerning groups"))
			print("  Replace existing kerning: %s" % ("ON" if options["clearKerning"] else "OFF"))
			print("  Only selected glyphs: %s" % ("ON" if options["selectedOnly"] else "OFF"))
			print("  Remove metrics keys before import: %s" % ("ON" if options["removeKeys"] else "OFF"))
			print("  Lock imported values with ==: %s" % ("ON" if options["lockImported"] else "OFF"))
			print("  Keep auto spacing: %s" % ("ON" if options["preserveAuto"] else "OFF"))
			print("  Lock after normalisation: %s" % ("ON" if options["lockNormalized"] else "OFF"))
			print("=" * 72)

		def write_kerning_group_assignment(self, glyph, propertyName, groupValue):
			beforeValue = normalize_group_value(getattr(glyph, propertyName))
			setattr(glyph, propertyName, groupValue)
			afterValue = normalize_group_value(getattr(glyph, propertyName))
			return beforeValue, afterValue

		def verify_ufo_group_records(self, groupRecords, overrides=None):
			activeGroupNames = set()
			mismatchedGroups = []
			for groupRecord in groupRecords:
				rawGroupName = groupRecord["rawGroupName"]
				propertyName = groupRecord["propertyName"]
				groupValue = groupRecord["groupValue"]
				members = groupRecord["members"]
				if not members:
					mismatchedGroups.append(rawGroupName)
					continue
				groupMatches = True
				for glyphName in members:
					currentValue = group_value_for_glyph(self.font, glyphName, propertyName, overrides=overrides)
					if currentValue != groupValue:
						groupMatches = False
						break
				if groupMatches:
					activeGroupNames.add(rawGroupName)
				else:
					mismatchedGroups.append(rawGroupName)
			return activeGroupNames, mismatchedGroups

		def import_kerning_groups_for_ufo(self, ufo, master, ufoPath, options, groupState, stats):
			mode = options["kerningGroupMode"]
			sourceLabel = "%s (%s)" % (master.name, os.path.basename(ufoPath))
			groupRecords = collect_ufo_kerning_group_records(ufo.groups)
			stats["sourceGroupCount"] = len(groupRecords)
			for groupRecord in groupRecords:
				rawGroupName = groupRecord["rawGroupName"]
				propertyName = groupRecord["propertyName"]
				groupValue = groupRecord["groupValue"]
				members = groupRecord["members"]
				if not members:
					stats["groupSkipped"] += 1
					print("  skip kerning group %s: empty members" % rawGroupName)
					continue
				targetRows = []
				groupBlocked = False
				for glyphName in members:
					try:
						targetGlyph = self.font.glyphs[glyphName]
					except Exception:
						targetGlyph = None
					if targetGlyph is None:
						stats["groupMissingGlyphs"] += 1
						groupBlocked = True
						print("  skip kerning group %s -> %s: missing target glyph" % (rawGroupName, glyphName))
						continue
					key = (glyphName, propertyName)
					currentValue = group_value_for_glyph(self.font, glyphName, propertyName, overrides=groupState["plannedValues"])
					seenDefinition = groupState["seenDefinitions"].get(key)
					if seenDefinition and seenDefinition["value"] != groupValue:
						stats["groupConflicts"] += 1
						print(
							"  kerning-group conflict %s / %s: %s from %s vs %s from %s"
							% (
								glyphName,
								kerning_group_side_label(propertyName),
								seenDefinition["value"],
								seenDefinition["source"],
								groupValue,
								sourceLabel,
							)
						)
						if mode != KERNING_GROUP_MODE_OVERWRITE:
							groupBlocked = True
					if mode != KERNING_GROUP_MODE_OVERWRITE and currentValue and currentValue != groupValue:
						stats["groupConflicts"] += 1
						groupBlocked = True
						print(
							"  skip kerning group %s: %s already has %s"
							% (
								rawGroupName,
								glyphName,
								currentValue,
							)
						)
					targetRows.append((glyphName, targetGlyph, currentValue))
				if groupBlocked:
					stats["groupSkipped"] += 1
					continue
				for glyphName, targetGlyph, currentValue in targetRows:
					key = (glyphName, propertyName)
					if currentValue == groupValue:
						stats["groupReused"] += 1
						groupState["plannedValues"][key] = groupValue
						groupState["seenDefinitions"][key] = {"value": groupValue, "source": sourceLabel}
						continue
					beforeValue, afterValue = self.write_kerning_group_assignment(targetGlyph, propertyName, groupValue)
					groupState["seenDefinitions"][key] = {"value": groupValue, "source": sourceLabel}
					if afterValue == groupValue:
						if beforeValue == afterValue:
							stats["groupReused"] += 1
						else:
							stats["groupImported"] += 1
						groupState["plannedValues"][key] = afterValue
					else:
						stats["groupSkipped"] += 1
						print("  skip kerning group %s / %s: verification failed" % (glyphName, kerning_group_side_label(propertyName)))

		def collect_canonical_kerning_pairs(self, ufo, activeGroupNames, glyphNamesSet, leftGroupNames, rightGroupNames, stats):
			canonicalPairs = []
			canonicalIndex = {}
			sourcePairCount = 0
			for leftKey, rightDict in mapping_items(ufo.kerning):
				for rightKey, value in mapping_items(rightDict):
					sourcePairCount += 1
					pairCategory = classify_ufo_kerning_pair(leftKey, rightKey, ufo.groups)
					stats[pairCategory] += 1
					leftMapped = map_ufo_kerning_key(str(leftKey), "left", glyphNamesSet, leftGroupNames, rightGroupNames, ufo.groups, activeGroupNames)
					rightMapped = map_ufo_kerning_key(str(rightKey), "right", glyphNamesSet, leftGroupNames, rightGroupNames, ufo.groups, activeGroupNames)
					if not leftMapped or not rightMapped:
						stats["unmappable"] += 1
						print("  skip kerning %s %s: unmappable" % (leftKey, rightKey))
						continue
					canonicalKey = (str(leftMapped), str(rightMapped))
					normalizedValue = normalize_number(value)
					existingIndex = canonicalIndex.get(canonicalKey)
					if existingIndex is not None:
						existingRecord = canonicalPairs[existingIndex]
						if same_number(existingRecord["value"], normalizedValue):
							stats["duplicatePairs"] += 1
							continue
						stats["pairConflicts"] += 1
						print(
							"  kerning conflict %s %s -> %s %s: %s replaced with %s"
							% (
								leftKey,
								rightKey,
								canonicalKey[0],
								canonicalKey[1],
								format_metric_value(existingRecord["value"]),
								format_metric_value(normalizedValue),
							)
						)
						existingRecord["value"] = normalizedValue
						existingRecord["leftKey"] = str(leftKey)
						existingRecord["rightKey"] = str(rightKey)
						continue
					canonicalIndex[canonicalKey] = len(canonicalPairs)
					canonicalPairs.append(
						{
							"targetKey": canonicalKey,
							"value": normalizedValue,
							"leftKey": str(leftKey),
							"rightKey": str(rightKey),
						}
					)
			stats["sourcePairCount"] = sourcePairCount
			return canonicalPairs

		def execute_transfer(self):
			options = self.current_options()
			assignedRows = self.assigned_master_rows()
			kerningGroupImportEnabled = options["importKerningGroups"] or options["transferKerning"]
			Glyphs.clearLog()
			Glyphs.showMacroWindow()
			self.print_global_header("TRANSFER", options, assignedRows)
			if not options["transferSpacing"] and not options["transferKerning"] and not options["importKerningGroups"]:
				Message("Nothing To Do", "Enable spacing, kerning, and/or kerning-group import.", OKButton="OK")
				return
			if not assignedRows:
				Message("No UFO Assigned", "Assign at least one UFO to a master.", OKButton="OK")
				return
			if options["selectedOnly"]:
				glyphNames = get_selected_glyph_names(self.font)
			else:
				glyphNames = all_glyph_names(self.font)
			if options["transferSpacing"] and not glyphNames:
				Message("No Glyphs In Scope", "There are no glyphs to process.", OKButton="OK")
				return
			totalSpacingAttempted = 0
			totalSpacingVerified = 0
			totalSpacingUnchanged = 0
			totalMissing = 0
			totalAuto = 0
			totalKeyClearFailures = 0
			totalSpacingVerificationFailures = 0
			totalErrors = 0
			totalSourceGroups = 0
			totalImportedGroups = 0
			totalSourcePairs = 0
			totalKerningAttempted = 0
			totalKerningVerified = 0
			totalKerningCleared = 0
			totalUnmappable = 0
			totalLocked = 0
			masterResults = []
			preparedRows = []
			try:
				self.font.disableUpdateInterface()
				for assigned in assignedRows:
					master = assigned["master"]
					ufoPath = assigned["path"]
					stats = {
						"master": master.name,
						"spacingAttempted": 0,
						"spacingVerified": 0,
						"spacingUnchanged": 0,
						"missingGlyphs": 0,
						"autoGlyphs": 0,
						"keyClearFailures": 0,
						"spacingVerificationFailures": 0,
						"errors": 0,
						"groupImported": 0,
						"groupReused": 0,
						"groupSkipped": 0,
						"groupConflicts": 0,
						"groupMissingGlyphs": 0,
						"sourceGroupCount": 0,
						"importedGroupCount": 0,
						"groupMismatchCount": 0,
						"postClearTargetPairCount": 0,
						"sourcePairCount": 0,
						"glyphGlyph": 0,
						"groupGlyph": 0,
						"glyphGroup": 0,
						"groupGroup": 0,
						"duplicatePairs": 0,
						"pairConflicts": 0,
						"finalTargetPairCount": 0,
						"kerningAttempted": 0,
						"kerningVerified": 0,
						"unmappable": 0,
						"locked": 0,
						"clearedKerning": 0,
					}
					masterResults.append(stats)
					print("")
					print("Master: %s" % master.name)
					print("UFO: %s" % ufoPath)
					if not path_exists(ufoPath):
						stats["errors"] += 1
						print("  ERROR: UFO path not found")
						totalErrors += 1
						continue
					try:
						ufo = UFOFontData(ufoPath)
					except Exception:
						stats["errors"] += 1
						totalErrors += 1
						print("  ERROR: Failed to load UFO")
						print(traceback.format_exc())
						continue
					preparedRows.append(
						{
							"master": master,
							"path": ufoPath,
							"ufo": ufo,
							"stats": stats,
							"groupRecords": collect_ufo_kerning_group_records(ufo.groups),
							"activeKerningGroups": set(),
						}
					)
					if options["transferSpacing"]:
						for glyphName in glyphNames:
							glyph = self.font.glyphs[glyphName]
							layer = get_real_master_layer(glyph, master)
							if layer is None:
								stats["missingGlyphs"] += 1
								totalMissing += 1
								print("  skip spacing %s: missing target layer" % glyphName)
								continue
							try:
								if options["preserveAuto"] and layer_has_auto_metrics(layer):
									stats["autoGlyphs"] += 1
									totalAuto += 1
									print("  skip spacing %s: auto metrics" % glyphName)
									continue
								if not ufo.glyph_exists(glyphName):
									stats["missingGlyphs"] += 1
									totalMissing += 1
									print("  skip spacing %s: missing in UFO" % glyphName)
									continue
								width, lsb, rsb = ufo.glyph_metrics(glyphName)
								beforeState = capture_layer_state(glyph, layer)
								stats["spacingAttempted"] += 1
								totalSpacingAttempted += 1
								keyClearFailure = write_spacing_to_layer(
									glyph,
									layer,
									width,
									lsb,
									rsb,
									removeKeys=options["removeKeys"],
									lockValues=options["lockImported"],
								)
								verified, afterState = verify_spacing_write(
									glyph,
									layer,
									width,
									lsb,
									rsb,
									removeKeys=options["removeKeys"],
									lockValues=options["lockImported"],
								)
								if keyClearFailure:
									stats["keyClearFailures"] += 1
									totalKeyClearFailures += 1
								if verified:
									if layer_state_changed(beforeState, afterState):
										stats["spacingVerified"] += 1
										totalSpacingVerified += 1
										if options["lockImported"]:
											stats["locked"] += 1
											totalLocked += 1
									else:
										stats["spacingUnchanged"] += 1
										totalSpacingUnchanged += 1
								else:
									stats["spacingVerificationFailures"] += 1
									totalSpacingVerificationFailures += 1
							except Exception:
								stats["errors"] += 1
								totalErrors += 1
								print("  ERROR spacing %s" % glyphName)
								print(traceback.format_exc())
				groupState = {"plannedValues": {}, "seenDefinitions": {}}
				if options["transferKerning"] and not options["importKerningGroups"]:
					print("")
					print("KERNING GROUP IMPORT")
					print("Kerning import requires source kerning groups. Running strict kerning-group import first.")
				if kerningGroupImportEnabled:
					print("")
					if not (options["transferKerning"] and not options["importKerningGroups"]):
						print("KERNING GROUP IMPORT")
					print("Kerning groups are glyph/font-level assignments in Glyphs.")
					for prepared in preparedRows:
						master = prepared["master"]
						stats = prepared["stats"]
						print("")
						print("Master: %s" % master.name)
						print("UFO: %s" % prepared["path"])
						try:
							self.import_kerning_groups_for_ufo(
								prepared["ufo"],
								master,
								prepared["path"],
								options,
								groupState,
								stats,
							)
						except Exception:
							stats["errors"] += 1
							totalErrors += 1
							print("  ERROR kerning-group phase")
							print(traceback.format_exc())
					print("")
					print("KERNING GROUP VERIFICATION")
					for prepared in preparedRows:
						stats = prepared["stats"]
						activeGroupNames, mismatchedGroups = self.verify_ufo_group_records(
							prepared["groupRecords"],
							overrides=groupState["plannedValues"],
						)
						prepared["activeKerningGroups"] = activeGroupNames
						stats["sourceGroupCount"] = len(prepared["groupRecords"])
						stats["importedGroupCount"] = len(activeGroupNames)
						stats["groupMismatchCount"] = len(mismatchedGroups)
						totalSourceGroups += stats["sourceGroupCount"]
						totalImportedGroups += stats["importedGroupCount"]
						print("")
						print("Master: %s" % prepared["master"].name)
						groupSummary = "  Kerning groups: Source: %d -> Imported: %d" % (
							stats["sourceGroupCount"],
							stats["importedGroupCount"],
						)
						if stats["sourceGroupCount"] != stats["importedGroupCount"]:
							groupSummary += " (WARNING: mismatch, difference: %d)" % abs(stats["sourceGroupCount"] - stats["importedGroupCount"])
						print(groupSummary)
						if mismatchedGroups:
							print("  group mismatches: %d" % len(mismatchedGroups))
				glyphNamesSet, leftGroupNames, rightGroupNames = collect_font_kerning_maps(
					self.font,
					groupState["plannedValues"] if kerningGroupImportEnabled else None,
				)
				if options["transferKerning"]:
					print("")
					print("KERNING IMPORT")
					for prepared in preparedRows:
						master = prepared["master"]
						ufo = prepared["ufo"]
						stats = prepared["stats"]
						print("")
						print("Master: %s" % master.name)
						print("UFO: %s" % prepared["path"])
						try:
							canonicalPairs = self.collect_canonical_kerning_pairs(
								ufo,
								prepared["activeKerningGroups"] if kerningGroupImportEnabled else None,
								glyphNamesSet,
								leftGroupNames,
								rightGroupNames,
								stats,
							)
							totalSourcePairs += stats["sourcePairCount"]
							if options["clearKerning"]:
								stats["clearedKerning"] = clear_master_kerning(self.font, master.id)
								totalKerningCleared += stats["clearedKerning"]
								stats["postClearTargetPairCount"] = count_master_kerning_pairs(self.font, master.id)
								if stats["postClearTargetPairCount"] != 0:
									stats["finalTargetPairCount"] = stats["postClearTargetPairCount"]
									stats["errors"] += 1
									totalErrors += 1
									print("  ERROR replace mode clear failed: target master still has %d kerning pairs" % stats["postClearTargetPairCount"])
									continue
							for pairRecord in canonicalPairs:
								try:
									leftMapped, rightMapped = pairRecord["targetKey"]
									value = pairRecord["value"]
									stats["kerningAttempted"] += 1
									totalKerningAttempted += 1
									self.font.setKerningForPair(master.id, leftMapped, rightMapped, value)
									if same_number(read_kerning_value(self.font, master.id, leftMapped, rightMapped), value):
										stats["kerningVerified"] += 1
										totalKerningVerified += 1
									else:
										print("  WARNING kerning verification failed for %s %s" % (leftMapped, rightMapped))
								except Exception:
									stats["errors"] += 1
									totalErrors += 1
									print("  ERROR kerning %s %s" % (pairRecord["leftKey"], pairRecord["rightKey"]))
									print(traceback.format_exc())
							stats["finalTargetPairCount"] = count_master_kerning_pairs(self.font, master.id)
						except Exception:
							stats["errors"] += 1
							totalErrors += 1
							print("  ERROR kerning phase")
							print(traceback.format_exc())
				for stats in masterResults:
					print("")
					print("Master: %s" % stats["master"])
					print("  spacing attempted: %d" % stats["spacingAttempted"])
					print("  spacing verified: %d" % stats["spacingVerified"])
					print("  spacing unchanged after write attempt: %d" % stats["spacingUnchanged"])
					print("  skipped glyphs missing: %d" % stats["missingGlyphs"])
					print("  skipped glyphs auto: %d" % stats["autoGlyphs"])
					print("  layers with key clear failures: %d" % stats["keyClearFailures"])
					print("  layers with post-write verification failure: %d" % stats["spacingVerificationFailures"])
					print("  kerning-group assignments imported: %d" % stats["groupImported"])
					print("  kerning-group assignments reused: %d" % stats["groupReused"])
					print("  kerning-group assignments skipped: %d" % stats["groupSkipped"])
					print("  kerning-group conflicts: %d" % stats["groupConflicts"])
					print("  kerning-group target glyphs missing: %d" % stats["groupMissingGlyphs"])
					groupWarnings = []
					if stats["sourceGroupCount"] != stats["importedGroupCount"]:
						groupWarnings.append("mismatch")
					groupSummary = "  Kerning groups: Source: %d -> Imported: %d" % (stats["sourceGroupCount"], stats["importedGroupCount"])
					if groupWarnings:
						groupSummary += " (WARNING: %s, difference: %d)" % (", ".join(groupWarnings), abs(stats["sourceGroupCount"] - stats["importedGroupCount"]))
					print(groupSummary)
					print("  source UFO kerning pair count: %d" % stats["sourcePairCount"])
					print("  source glyph-glyph pairs: %d" % stats["glyphGlyph"])
					print("  source group-glyph pairs: %d" % stats["groupGlyph"])
					print("  source glyph-group pairs: %d" % stats["glyphGroup"])
					print("  source group-group pairs: %d" % stats["groupGroup"])
					print("  kerning pairs attempted: %d" % stats["kerningAttempted"])
					print("  kerning pairs verified: %d" % stats["kerningVerified"])
					print("  duplicate pairs skipped: %d" % stats["duplicatePairs"])
					print("  pair conflicts: %d" % stats["pairConflicts"])
					print("  kerning pairs unmappable: %d" % stats["unmappable"])
					print("  kerning pairs cleared: %d" % stats["clearedKerning"])
					print("  post-clear target kerning count: %d" % stats["postClearTargetPairCount"])
					print("  final target master kerning count: %d" % stats["finalTargetPairCount"])
					pairWarnings = []
					if stats["sourcePairCount"] != stats["kerningVerified"]:
						pairWarnings.append("mismatch")
					if options["clearKerning"] and stats["finalTargetPairCount"] != stats["kerningVerified"]:
						pairWarnings.append("final target count mismatch")
					pairSummary = "  Kerning pairs: Source: %d -> Imported: %d" % (stats["sourcePairCount"], stats["kerningVerified"])
					if pairWarnings:
						pairSummary += " (WARNING: %s, difference: %d)" % (", ".join(pairWarnings), abs(stats["sourcePairCount"] - stats["kerningVerified"]))
					print(pairSummary)
					print("  verified layers locked with ==: %d" % stats["locked"])
					print("  errors: %d" % stats["errors"])
			finally:
				try:
					self.font.enableUpdateInterface()
				except Exception:
					pass
				try:
					Glyphs.redraw()
				except Exception:
					pass
			totalGroupImported = sum(stats["groupImported"] for stats in masterResults)
			totalGroupReused = sum(stats["groupReused"] for stats in masterResults)
			totalGroupSkipped = sum(stats["groupSkipped"] for stats in masterResults)
			totalGroupConflicts = sum(stats["groupConflicts"] for stats in masterResults)
			totalGroupMissing = sum(stats["groupMissingGlyphs"] for stats in masterResults)
			totalDuplicatePairs = sum(stats["duplicatePairs"] for stats in masterResults)
			totalPairConflicts = sum(stats["pairConflicts"] for stats in masterResults)
			totalFinalTargetPairs = sum(stats["finalTargetPairCount"] for stats in masterResults)
			totalUnmappable = sum(stats["unmappable"] for stats in masterResults)
			if totalSpacingVerified > 0 or totalKerningVerified > 0 or totalKerningCleared > 0 or totalGroupImported > 0:
				mark_font_changed(self.font)
			summaryWarnings = []
			if totalSourcePairs != totalKerningVerified:
				summaryWarnings.append("mismatch")
			if options["clearKerning"] and totalFinalTargetPairs != totalKerningVerified:
				summaryWarnings.append("final target count mismatch")
			groupImportSummary = "Kerning groups: Source: %d -> Imported: %d" % (totalSourceGroups, totalImportedGroups)
			if totalSourceGroups != totalImportedGroups:
				groupImportSummary += " (WARNING: mismatch, difference: %d)" % abs(totalSourceGroups - totalImportedGroups)
			sourceImportSummary = "Kerning pairs: Source: %d -> Imported: %d" % (totalSourcePairs, totalKerningVerified)
			if summaryWarnings:
				sourceImportSummary += " (WARNING: %s, difference: %d)" % (", ".join(summaryWarnings), abs(totalSourcePairs - totalKerningVerified))
			summaryLines = [
				"Font: %s" % (self.font.familyName or "Untitled"),
				"Masters processed: %d" % len(masterResults),
				groupImportSummary,
				sourceImportSummary,
				"Kerning-group import: %s" % (
					"ON (%s)" % KERNING_GROUP_MODE_TITLES.get(options["kerningGroupMode"], "Overwrite existing kerning groups")
					if kerningGroupImportEnabled
					else "OFF"
				),
				"Spacing attempted: %d" % totalSpacingAttempted,
				"Verified layer updates: %d" % totalSpacingVerified,
				"Layers unchanged after write attempt: %d" % totalSpacingUnchanged,
				"Glyphs skipped missing/invalid: %d" % totalMissing,
				"Glyphs skipped auto: %d" % totalAuto,
				"Layers with key clear failures: %d" % totalKeyClearFailures,
				"Layers with post-write verification failure: %d" % totalSpacingVerificationFailures,
				"Kerning-group assignments imported: %d" % totalGroupImported,
				"Kerning-group assignments reused: %d" % totalGroupReused,
				"Kerning-group assignments skipped: %d" % totalGroupSkipped,
				"Kerning-group conflicts: %d" % totalGroupConflicts,
				"Kerning-group target glyphs missing: %d" % totalGroupMissing,
				"Kerning pairs attempted: %d" % totalKerningAttempted,
				"Verified kerning pairs: %d" % totalKerningVerified,
				"Duplicate pairs skipped: %d" % totalDuplicatePairs,
				"Pair conflicts: %d" % totalPairConflicts,
				"Kerning pairs unmappable: %d" % totalUnmappable,
				"Final target master kerning total: %d" % totalFinalTargetPairs,
				"Verified layers locked with ==: %d" % totalLocked,
				"Errors: %d" % totalErrors,
			]
			print("")
			print("FINAL")
			for line in summaryLines:
				print(line)
			Message("Transfer Complete", "\n".join(summaryLines), OKButton="OK")

		def run_transfer(self, sender=None):
			self.execute_transfer()

		def run_normalisation(self, selectedOnly):
			options = self.current_options()
			masters = self.normalisation_masters()
			Glyphs.clearLog()
			Glyphs.showMacroWindow()
			print("")
			print("=" * 72)
			print("METRICS NORMALISATION")
			print("Font: %s" % (self.font.familyName or "Untitled"))
			print("Masters selected: %d" % len(masters))
			print("Selected normalisation masters: %s" % (", ".join([master.name for master in masters]) or "[none]"))
			print("Lock with == after normalisation: %s" % ("ON" if options["lockNormalized"] else "OFF"))
			print("=" * 72)
			if selectedOnly:
				glyphNames = get_selected_glyph_names(self.font)
			else:
				glyphNames = all_glyph_names(self.font)
			if not glyphNames:
				Message("No Glyphs In Scope", "There are no glyphs to process.", OKButton="OK")
				return
			if not masters:
				Message("No Masters Selected", "Enable at least one master for metrics normalisation.", OKButton="OK")
				return
			glyphsProcessed = len(glyphNames)
			layersAttempted = 0
			layersConverted = 0
			layersUnchanged = 0
			layersSkippedAuto = 0
			layersLocked = 0
			keyClearFailures = 0
			verificationFailures = 0
			errors = 0
			try:
				self.font.disableUpdateInterface()
				for master in masters:
					print("")
					print("Master: %s" % master.name)
					for glyphName in glyphNames:
						glyph = self.font.glyphs[glyphName]
						layer = get_real_master_layer(glyph, master)
						if layer is None:
							print("  skip %s: missing target layer" % glyphName)
							continue
						try:
							if layer_has_auto_metrics(layer):
								layersSkippedAuto += 1
								print("  skip %s: auto metrics" % glyphName)
								continue
							width = normalize_number(layer.width)
							lsb = normalize_number(layer.LSB)
							rsb = normalize_number(layer.RSB)
							beforeState = capture_layer_state(glyph, layer)
							layersAttempted += 1
							keyClearFailure = write_spacing_to_layer(
								glyph,
								layer,
								width,
								lsb,
								rsb,
								removeKeys=True,
								lockValues=options["lockNormalized"],
							)
							verified, afterState = verify_spacing_write(
								glyph,
								layer,
								width,
								lsb,
								rsb,
								removeKeys=True,
								lockValues=options["lockNormalized"],
							)
							if keyClearFailure:
								keyClearFailures += 1
							if verified:
								if layer_state_changed(beforeState, afterState):
									layersConverted += 1
									if options["lockNormalized"]:
										layersLocked += 1
								else:
									layersUnchanged += 1
							else:
								verificationFailures += 1
						except Exception:
							errors += 1
							print("  ERROR %s" % glyphName)
							print(traceback.format_exc())
			finally:
				try:
					self.font.enableUpdateInterface()
				except Exception:
					pass
				try:
					Glyphs.redraw()
				except Exception:
					pass
			if layersConverted > 0:
				mark_font_changed(self.font)
			print("")
			print("FINAL")
			print("Glyphs processed: %d" % glyphsProcessed)
			print("Layers attempted: %d" % layersAttempted)
			print("Layers converted: %d" % layersConverted)
			print("Layers unchanged after write attempt: %d" % layersUnchanged)
			print("Layers skipped auto: %d" % layersSkippedAuto)
			print("Layers with key clear failures: %d" % keyClearFailures)
			print("Layers with post-write verification failure: %d" % verificationFailures)
			print("Layers locked with ==: %d" % layersLocked)
			print("Errors: %d" % errors)
			summaryLines = [
				"Glyphs processed: %d" % glyphsProcessed,
				"Layers attempted: %d" % layersAttempted,
				"Layers converted: %d" % layersConverted,
				"Layers unchanged after write attempt: %d" % layersUnchanged,
				"Layers skipped auto: %d" % layersSkippedAuto,
				"Layers with key clear failures: %d" % keyClearFailures,
				"Layers with post-write verification failure: %d" % verificationFailures,
				"Layers locked with ==: %d" % layersLocked,
				"Errors: %d" % errors,
			]
			Message("Metrics Normalisation Complete", "\n".join(summaryLines), OKButton="OK")

		def normalize_selected(self, sender=None):
			self.run_normalisation(selectedOnly=True)

		def normalize_all(self, sender=None):
			self.run_normalisation(selectedOnly=False)


UFO_TRANSFER_WINDOW = DisplaayUFOTransferWindowVerifiedWrites.alloc().init()
