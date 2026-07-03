# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import math

try:
	from AppKit import (
		NSAttributedString,
		NSBezierPath,
		NSColor,
		NSFont,
		NSFontAttributeName,
		NSForegroundColorAttributeName,
		NSMakeRect,
	)
except Exception:
	pass

try:
	from GlyphsApp import GSNode, OFFCURVE
except Exception:
	GSNode = None
	OFFCURVE = None

ON_CURVE_COLOR = (0.25, 0.78, 0.35, 0.95)
OFF_CURVE_COLOR = (0.55, 0.35, 0.88, 0.95)
HANDLE_LINE_COLOR = (0.45, 0.75, 0.45, 0.85)
VIEW_NODE_RADIUS = 3.0
VIEW_HANDLE_WIDTH = 1.0


def selected_nodes(layer):
	if layer is None:
		return []
	selection = list(getattr(layer, "selection", []) or [])
	if GSNode is not None:
		return [node for node in selection if isinstance(node, GSNode)]
	return selection


def _is_offcurve(node):
	if OFFCURVE is not None:
		try:
			return node.type == OFFCURVE
		except Exception:
			pass
	try:
		return int(node.type) == 0
	except Exception:
		return False


def _path_nodes(path):
	try:
		return list(path.nodes)
	except Exception:
		return []


def _path_is_closed(path):
	try:
		return bool(path.closed)
	except Exception:
		return False


def _neighboring_offcurves(path, index):
	nodes = _path_nodes(path)
	if not nodes:
		return []
	count = len(nodes)
	neighbors = []
	if _path_is_closed(path):
		candidates = (nodes[(index - 1) % count], nodes[(index + 1) % count])
	elif count == 1:
		candidates = ()
	else:
		candidates = []
		if index > 0:
			candidates.append(nodes[index - 1])
		if index + 1 < count:
			candidates.append(nodes[index + 1])
	for neighbor in candidates:
		if _is_offcurve(neighbor):
			neighbors.append(neighbor)
	return neighbors


def _layer_marker_radius(scale, for_panel=False):
	if for_panel:
		return VIEW_NODE_RADIUS / max(scale, 0.001)
	return 3.0 / max(scale, 0.001)


def _layer_line_width(scale, for_panel=False):
	if for_panel:
		return VIEW_HANDLE_WIDTH / max(scale, 0.001)
	return 0.8 / max(scale, 0.001)


def _draw_handle_lines(path, scale, for_panel=False):
	nodes = _path_nodes(path)
	if not nodes:
		return
	line_width = _layer_line_width(scale, for_panel=for_panel)
	line_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*HANDLE_LINE_COLOR)
	for index, node in enumerate(nodes):
		if _is_offcurve(node):
			continue
		x, y = node.x, node.y
		for neighbor in _neighboring_offcurves(path, index):
			line = NSBezierPath.bezierPath()
			line.moveToPoint_((x, y))
			line.lineToPoint_((neighbor.x, neighbor.y))
			line_color.setStroke()
			line.setLineWidth_(line_width)
			line.stroke()


def _draw_node_markers(nodes, scale, color=None, for_panel=False):
	on_curve_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*ON_CURVE_COLOR)
	off_curve_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*OFF_CURVE_COLOR)
	if color is not None:
		on_curve_color = color
	radius = _layer_marker_radius(scale, for_panel=for_panel)
	for node in nodes:
		x, y = node.x, node.y
		if _is_offcurve(node):
			size = radius * 1.15
			off_curve_color.setFill()
			NSBezierPath.fillRect_(NSMakeRect(x - size, y - size, size * 2, size * 2))
		else:
			on_curve_color.setFill()
			dot = NSBezierPath.bezierPathWithOvalInRect_(
				NSMakeRect(x - radius, y - radius, radius * 2, radius * 2)
			)
			dot.fill()


def draw_nodes(layer, scale, color=None, draw_tangents=False, for_panel=False):
	if layer is None:
		return
	for path in layer.paths:
		if draw_tangents:
			_draw_handle_lines(path, scale, for_panel=for_panel)
	for path in layer.paths:
		_draw_node_markers(_path_nodes(path), scale, color=color, for_panel=for_panel)


def _view_point(layer_x, node_x, node_y, origin_x, baseline_y, scale):
	return (
		origin_x + (layer_x + node_x) * scale,
		baseline_y - node_y * scale,
	)


def collect_view_node_data(layer, layer_x, origin_x, baseline_y, scale):
	points = []
	connections = []
	if layer is None:
		return points, connections
	for path in layer.paths:
		nodes = _path_nodes(path)
		for index, node in enumerate(nodes):
			x, y = _view_point(layer_x, node.x, node.y, origin_x, baseline_y, scale)
			points.append({"x": x, "y": y, "offcurve": _is_offcurve(node)})
			if _is_offcurve(node):
				continue
			on_x, on_y = x, y
			for neighbor in _neighboring_offcurves(path, index):
				nx, ny = _view_point(layer_x, neighbor.x, neighbor.y, origin_x, baseline_y, scale)
				connections.append({"x1": on_x, "y1": on_y, "x2": nx, "y2": ny})
	return points, connections


def draw_nodes_view_space(points, connections):
	line_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*HANDLE_LINE_COLOR)
	on_curve_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*ON_CURVE_COLOR)
	off_curve_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(*OFF_CURVE_COLOR)
	for connection in connections:
		line = NSBezierPath.bezierPath()
		line.moveToPoint_((connection["x1"], connection["y1"]))
		line.lineToPoint_((connection["x2"], connection["y2"]))
		line_color.setStroke()
		line.setLineWidth_(VIEW_HANDLE_WIDTH)
		line.stroke()
	for point in points:
		x, y = point["x"], point["y"]
		if point["offcurve"]:
			size = VIEW_NODE_RADIUS * 1.15
			off_curve_color.setFill()
			NSBezierPath.fillRect_(NSMakeRect(x - size, y - size, size * 2, size * 2))
		else:
			on_curve_color.setFill()
			dot = NSBezierPath.bezierPathWithOvalInRect_(
				NSMakeRect(x - VIEW_NODE_RADIUS, y - VIEW_NODE_RADIUS, VIEW_NODE_RADIUS * 2, VIEW_NODE_RADIUS * 2)
			)
			dot.fill()


def draw_measurement(layer, scale, center_shift=0.0):
	nodes = selected_nodes(layer)
	if len(nodes) != 2:
		return

	p1 = nodes[0].position
	p2 = nodes[1].position
	dx = p2.x - p1.x
	dy = p2.y - p1.y
	distance = math.hypot(dx, dy)
	angle = math.degrees(math.atan2(dy, dx))

	x1, y1 = p1.x + center_shift, p1.y
	x2, y2 = p2.x + center_shift, p2.y

	line_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.95, 0.25, 0.35, 0.9)
	line_color.setStroke()
	path = NSBezierPath.bezierPath()
	path.moveToPoint_((x1, y1))
	path.lineToPoint_((x2, y2))
	path.setLineWidth_(1.0 / max(scale, 0.001))
	path.stroke()

	dot_size = 4.0 / max(scale, 0.001)
	for x, y in ((x1, y1), (x2, y2)):
		NSColor.whiteColor().setFill()
		NSBezierPath.fillRect_(NSMakeRect(x - dot_size, y - dot_size, dot_size * 2, dot_size * 2))
		line_color.setStroke()
		NSBezierPath.strokeRect_(NSMakeRect(x - dot_size, y - dot_size, dot_size * 2, dot_size * 2))

	mid_x = (x1 + x2) / 2.0
	mid_y = (y1 + y2) / 2.0
	label_text = "dx %.2f  dy %.2f  angle %.1f  d %.2f" % (dx, dy, angle, distance)
	font = NSFont.systemFontOfSize_(11)
	attrs = {
		NSFontAttributeName: font,
		NSForegroundColorAttributeName: NSColor.blackColor(),
	}
	background = NSMakeRect(mid_x - 80, mid_y + 8, 160, 16)
	NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.85).setFill()
	NSBezierPath.fillRect_(background)
	label = NSAttributedString.alloc().initWithString_attributes_(label_text, attrs)
	label.drawAtPoint_((mid_x - 78, mid_y + 10))
