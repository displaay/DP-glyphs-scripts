# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

try:
	from AppKit import NSBezierPath, NSMakePoint, NSMakeRect
except Exception:
	NSBezierPath = None

try:
	from GlyphsApp import OFFCURVE
except Exception:
	OFFCURVE = None


EPSILON = 0.000001


def _is_offcurve(node):
	try:
		if OFFCURVE is not None:
			return node.type == OFFCURVE
	except Exception:
		pass
	try:
		return int(node.type) == 0
	except Exception:
		return False


def _node_type_key(node):
	try:
		return int(node.type)
	except Exception:
		return str(getattr(node, "type", ""))


def glyph_change_key(glyph):
	if glyph is None:
		return None
	for name in ("lastChange", "lastOperation"):
		try:
			value = getattr(glyph, name, None)
			if callable(value):
				value = value()
			if value is not None:
				return str(value)
		except Exception:
			pass
	return id(glyph)


class FastNode(object):
	def __init__(self, x, y, node_type):
		self.x = float(x)
		self.y = float(y)
		self.type = node_type

	@property
	def position(self):
		return NSMakePoint(self.x, self.y)

	def copy(self):
		return FastNode(self.x, self.y, self.type)


class FastPath(object):
	def __init__(self, nodes, closed):
		self.nodes = nodes
		self.closed = bool(closed)

	def copy(self):
		return FastPath([node.copy() for node in self.nodes], self.closed)

	@property
	def bezierPath(self):
		path = NSBezierPath.bezierPath()
		nodes = self.nodes
		if not nodes:
			return path

		start_index = None
		for index, node in enumerate(nodes):
			if not _is_offcurve(node):
				start_index = index
				break
		if start_index is None:
			return path

		start = nodes[start_index]
		path.moveToPoint_((start.x, start.y))
		pending = []

		if self.closed:
			ordered = nodes[start_index + 1:] + nodes[:start_index + 1]
		else:
			ordered = nodes[start_index + 1:]

		for node in ordered:
			if _is_offcurve(node):
				pending.append(node)
				continue
			if len(pending) >= 2:
				path.curveToPoint_controlPoint1_controlPoint2_(
					(node.x, node.y),
					(pending[-2].x, pending[-2].y),
					(pending[-1].x, pending[-1].y),
				)
			elif len(pending) == 1:
				control = pending[0]
				path.curveToPoint_controlPoint1_controlPoint2_(
					(node.x, node.y),
					(control.x, control.y),
					(control.x, control.y),
				)
			else:
				path.lineToPoint_((node.x, node.y))
			pending = []

		if self.closed:
			path.closePath()
		return path


class FastInterpolatedLayer(object):
	def __init__(self, paths, width):
		self.paths = paths
		self.components = []
		self.width = float(width)
		self._bezier_path = None
		self._bounds = None

	def copy(self):
		return FastInterpolatedLayer(
			[path.copy() for path in self.paths],
			self.width,
		)

	@property
	def bezierPath(self):
		if self._bezier_path is not None:
			return self._bezier_path
		path = NSBezierPath.bezierPath()
		for layer_path in self.paths:
			path.appendBezierPath_(layer_path.bezierPath)
		self._bezier_path = path
		return self._bezier_path

	@property
	def bounds(self):
		if self._bounds is not None:
			return self._bounds
		min_x = None
		min_y = None
		max_x = None
		max_y = None
		for path in self.paths:
			for node in path.nodes:
				if min_x is None:
					min_x = max_x = node.x
					min_y = max_y = node.y
				else:
					min_x = min(min_x, node.x)
					min_y = min(min_y, node.y)
					max_x = max(max_x, node.x)
					max_y = max(max_y, node.y)
		if min_x is None:
			self._bounds = NSMakeRect(0.0, 0.0, 0.0, 0.0)
		else:
			self._bounds = NSMakeRect(min_x, min_y, max_x - min_x, max_y - min_y)
		return self._bounds

	def transform_checkForSelection_doComponents_(self, transform, check_selection, do_components):
		for path in self.paths:
			for node in path.nodes:
				point = transform.transformPoint_((node.x, node.y))
				try:
					node.x = point.x
					node.y = point.y
				except Exception:
					node.x = point[0]
					node.y = point[1]
		self._bezier_path = None
		self._bounds = None


class FastDisplayPath(object):
	def __init__(self, nodes, closed):
		self.nodes = nodes
		self.closed = bool(closed)

	def copy(self):
		return FastDisplayPath([node.copy() for node in self.nodes], self.closed)


class FastBezierLayer(object):
	def __init__(self, bezier_path, width, paths=None):
		self.paths = paths or []
		self.components = []
		self.width = float(width)
		self._bezier_path = bezier_path

	def copy(self):
		try:
			path = self._bezier_path.copy()
		except Exception:
			path = self._bezier_path
		return FastBezierLayer(
			path,
			self.width,
			[layer_path.copy() for layer_path in self.paths],
		)

	@property
	def bezierPath(self):
		return self._bezier_path

	@property
	def bounds(self):
		try:
			return self._bezier_path.bounds()
		except Exception:
			return NSMakeRect(0.0, 0.0, 0.0, 0.0)

	def transform_checkForSelection_doComponents_(self, transform, check_selection, do_components):
		try:
			self._bezier_path.transformUsingAffineTransform_(transform)
		except Exception:
			pass
		for path in self.paths:
			for node in path.nodes:
				point = transform.transformPoint_((node.x, node.y))
				try:
					node.x = point.x
					node.y = point.y
				except Exception:
					node.x = point[0]
					node.y = point[1]


def _layer_paths(layer):
	try:
		return list(layer.paths)
	except Exception:
		return []


def _layer_has_components(layer):
	try:
		return bool(layer.components)
	except Exception:
		return False


def _layer_signature(layer):
	if layer is None or _layer_has_components(layer):
		return None
	signature = []
	for path in _layer_paths(layer):
		try:
			nodes = list(path.nodes)
			closed = bool(path.closed)
		except Exception:
			return None
		signature.append((closed, tuple(_node_type_key(node) for node in nodes)))
	return tuple(signature)


def _weighted_sum(nodes_by_layer, weights, node_index, attr):
	value = 0.0
	for nodes, weight in zip(nodes_by_layer, weights):
		value += weight * float(getattr(nodes[node_index], attr))
	return value


def _weighted_width(layers, weights):
	width = 0.0
	for layer, weight in zip(layers, weights):
		try:
			width += weight * float(layer.width)
		except Exception:
			pass
	return width


def _weighted_point(nodes_by_layer, weights, node_index):
	x = _weighted_sum(nodes_by_layer, weights, node_index, "x")
	y = _weighted_sum(nodes_by_layer, weights, node_index, "y")
	return x, y


def _append_interpolated_path(bezier_path, source_nodes, nodes_by_layer, weights, closed):
	if not source_nodes:
		return

	start_index = None
	for index, node in enumerate(source_nodes):
		if not _is_offcurve(node):
			start_index = index
			break
	if start_index is None:
		return

	bezier_path.moveToPoint_(_weighted_point(nodes_by_layer, weights, start_index))
	pending = []
	if closed:
		ordered = list(range(start_index + 1, len(source_nodes))) + list(range(0, start_index + 1))
	else:
		ordered = list(range(start_index + 1, len(source_nodes)))

	for node_index in ordered:
		source_node = source_nodes[node_index]
		point = _weighted_point(nodes_by_layer, weights, node_index)
		if _is_offcurve(source_node):
			pending.append(point)
			continue
		if len(pending) >= 2:
			bezier_path.curveToPoint_controlPoint1_controlPoint2_(
				point,
				pending[-2],
				pending[-1],
			)
		elif len(pending) == 1:
			bezier_path.curveToPoint_controlPoint1_controlPoint2_(
				point,
				pending[0],
				pending[0],
			)
		else:
			bezier_path.lineToPoint_(point)
		pending = []

	if closed:
		bezier_path.closePath()


def _direct_bezier_layer(layers, weights):
	path = NSBezierPath.bezierPath()
	display_paths = []
	path_count = len(_layer_paths(layers[0]))
	for path_index in range(path_count):
		source_paths = [_layer_paths(layer)[path_index] for layer in layers]
		nodes_by_layer = [list(path.nodes) for path in source_paths]
		source_nodes = nodes_by_layer[0]
		display_nodes = []
		for node_index, source_node in enumerate(source_nodes):
			x, y = _weighted_point(nodes_by_layer, weights, node_index)
			display_nodes.append(FastNode(x, y, source_node.type))
		display_paths.append(FastDisplayPath(display_nodes, bool(source_paths[0].closed)))
		_append_interpolated_path(
			path,
			source_nodes,
			nodes_by_layer,
			weights,
			bool(source_paths[0].closed),
		)
	return FastBezierLayer(path, _weighted_width(layers, weights), display_paths)


def _glyph_has_special_layers(glyph):
	try:
		for layer in glyph.layers:
			if getattr(layer, "isSpecialLayer", False):
				return True
	except Exception:
		pass
	return False


def direct_interpolated_layer(controller, glyph):
	if NSBezierPath is None or controller.font is None or glyph is None:
		return None
	if _glyph_has_special_layers(glyph):
		return None

	weights_by_master_id = controller.interpolation_weights()
	if not weights_by_master_id:
		return None

	layers = []
	weights = []
	master_ids = set(master.id for master in controller.font.masters)
	for master_id, weight in weights_by_master_id.items():
		if abs(float(weight or 0.0)) > EPSILON and master_id not in master_ids:
			return None
	for master in controller.font.masters:
		weight = float(weights_by_master_id.get(master.id, 0.0) or 0.0)
		if abs(weight) <= EPSILON:
			continue
		layer = controller.master_layer_for_glyph(master, glyph)
		if layer is None:
			return None
		layers.append(layer)
		weights.append(weight)

	if not layers:
		return None

	first_signature = _layer_signature(layers[0])
	if first_signature is None:
		return None
	for layer in layers[1:]:
		if _layer_signature(layer) != first_signature:
			return None

	try:
		if controller.is_live_previewing():
			return _direct_bezier_layer(layers, weights)
	except Exception:
		pass

	result_paths = []
	path_count = len(_layer_paths(layers[0]))
	for path_index in range(path_count):
		source_paths = [_layer_paths(layer)[path_index] for layer in layers]
		nodes_by_layer = [list(path.nodes) for path in source_paths]
		source_nodes = nodes_by_layer[0]
		result_nodes = []
		for node_index, source_node in enumerate(source_nodes):
			x = _weighted_sum(nodes_by_layer, weights, node_index, "x")
			y = _weighted_sum(nodes_by_layer, weights, node_index, "y")
			result_nodes.append(FastNode(x, y, source_node.type))
		result_paths.append(FastPath(result_nodes, bool(source_paths[0].closed)))

	return FastInterpolatedLayer(result_paths, _weighted_width(layers, weights))
