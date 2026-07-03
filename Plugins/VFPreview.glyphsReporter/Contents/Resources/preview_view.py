# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

try:
	from AppKit import (
		NSAffineTransform,
		NSBezierPath,
		NSColor,
		NSCompositeSourceOver,
		NSFloatingWindowLevel,
		NSGraphicsContext,
		NSImage,
		NSMakeRect,
		NSView,
		NSWindow,
	)
except Exception:
	NSView = object


from axis_utils import exportable_instances
from fast_interpolator import glyph_change_key
from measure import (
	collect_view_node_data,
	draw_measurement,
	draw_nodes,
	draw_nodes_view_space,
)
from preview_context_menu import build_preview_panel_menu


def make_color(red, green, blue, alpha=1.0):
	return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, alpha)


class PreviewCanvasView(NSView):
	def isFlipped(self):
		return True

	def setController_(self, controller):
		self.controller = controller
		self._preview_cache_key = None
		self._preview_cache_image = None
		try:
			self.setWantsLayer_(True)
		except Exception:
			pass
		try:
			self.setCanDrawConcurrently_(True)
		except Exception:
			pass

	def invalidatePreviewCache(self):
		self._preview_cache_key = None
		self._preview_cache_image = None

	def _preview_cache_key_for_draw(self, drawer, layers):
		controller = self.controller
		if controller is None:
			return None
		bounds = self.bounds()
		glyph_ids = []
		for layer in layers or []:
			glyph = drawer.glyph_for_layer(controller.font, layer)
			if glyph is not None:
				glyph_ids.append((glyph.id, glyph_change_key(glyph)))
		return (
			controller._current_values_key(),
			int(bounds.size.width),
			int(bounds.size.height),
			bool(controller.pref("centerPreview")),
			bool(drawer._show_panel_nodes(controller)),
			tuple(glyph_ids),
		)

	def _draw_cached_preview(self):
		image = self._preview_cache_image
		if image is None:
			return False
		size = image.size()
		if size.width <= 0 or size.height <= 0:
			return False
		image.drawInRect_fromRect_operation_fraction_(
			self.bounds(),
			NSMakeRect(0, 0, size.width, size.height),
			NSCompositeSourceOver,
			1.0,
		)
		return True

	def _render_preview_to_image(self, drawer, layers, center):
		bounds = self.bounds()
		width = max(1, int(bounds.size.width))
		height = max(1, int(bounds.size.height))
		image = NSImage.alloc().initWithSize_((width, height))
		image.lockFocus()
		try:
			NSColor.whiteColor().setFill()
			NSBezierPath.fillRect_(NSMakeRect(0, 0, width, height))
			drawer.draw_interpolated_string(
				NSMakeRect(0, 0, width, height),
				layers=layers,
				for_panel=True,
				center=center,
			)
		finally:
			image.unlockFocus()
		return image

	def _draw_preview_content(self, drawer):
		layers = drawer.tab_layers()
		if layers:
			center = False
		else:
			layer, glyph = self.current_glyph_layer()
			if layer is None or glyph is None:
				return False
			layers = [layer]
			center = True

		cache_key = self._preview_cache_key_for_draw(drawer, layers)
		if cache_key == self._preview_cache_key and self._preview_cache_image is not None:
			return self._draw_cached_preview()

		controller = self.controller
		bounds = self.bounds()
		if controller is not None and controller._defer_ui_sync:
			drawn = drawer.draw_interpolated_string(
				bounds,
				layers=layers,
				for_panel=True,
				center=center,
			)
			return drawn

		image = self._render_preview_to_image(drawer, layers, center)
		self._preview_cache_key = cache_key
		self._preview_cache_image = image
		return self._draw_cached_preview()

	def _plugin(self):
		controller = getattr(self, "controller", None)
		if controller is None:
			return None
		return controller.plugin

	def _refresh_all(self):
		plugin = self._plugin()
		if plugin is not None:
			plugin._refresh_dock()
			plugin.refreshViews()
		self.setNeedsDisplay_(True)

	def _toggle_pref(self, key, notify=True):
		controller = self.controller
		value = 0 if controller.pref(key) else 1
		controller.set_pref(key, value)
		if key == "linkToMaster":
			controller.sync_preview_instance()
		if notify:
			controller.notify_listeners()
		else:
			self._refresh_all()

	def menuForEvent_(self, event):
		controller = getattr(self, "controller", None)
		if controller is None or controller.font is None:
			return None
		return build_preview_panel_menu(controller, self)

	def openStandalonePreview_(self, sender):
		plugin = self._plugin()
		if plugin is not None:
			plugin.open_standalone_preview()

	def toggleDrawInEditView_(self, sender):
		self._toggle_pref("drawInEditView")

	def toggleShowPreviewNodes_(self, sender):
		controller = self.controller
		value = 0 if controller.pref("showPreviewPanelNodes") else 1
		controller.set_pref("showPreviewPanelNodes", value)
		controller.notify_listeners()
		self._refresh_all()

	def toggleHideForeground_(self, sender):
		self._toggle_pref("hideForeground")

	def toggleInvolvedMasters_(self, sender):
		self._toggle_pref("showInvolvedMasters")

	def toggleCenterPreview_(self, sender):
		self._toggle_pref("centerPreview")

	def toggleLinkToMaster_(self, sender):
		self._toggle_pref("linkToMaster")

	def toggleRoundValues_(self, sender):
		self._toggle_pref("roundValues")

	def makeInstanceFromPreview_(self, sender):
		controller = self.controller
		if controller is not None:
			controller.make_instance_from_current()
			self._refresh_all()

	def applyMasterOrInstance_(self, sender):
		controller = self.controller
		if controller is None or controller.font is None:
			return
		payload = sender.representedObject()
		if not payload or ":" not in payload:
			return
		kind, identifier = payload.split(":", 1)
		font = controller.font
		if kind == "master":
			for master in font.masters:
				if master.id == identifier:
					controller.apply_master(master)
					break
		elif kind == "instance":
			for instance in exportable_instances(font):
				if instance.name == identifier:
					controller.apply_instance(instance)
					break
		self._refresh_all()

	def current_glyph_layer(self):
		controller = getattr(self, "controller", None)
		if controller is None or controller.font is None:
			return None, None
		font = controller.font
		if font.selectedLayers:
			layer = font.selectedLayers[0]
			if layer is not None and layer.parent is not None:
				return layer, layer.parent
		if font.selection:
			glyph = font.selection[0]
			if glyph is not None:
				master = font.selectedFontMaster
				if master is not None:
					try:
						return glyph.layers[master.id], glyph
					except Exception:
						pass
				try:
					return glyph.layers[0], glyph
				except Exception:
					pass
		return None, None

	def drawRect_(self, rect):
		drawer = getattr(self, "drawer", None)
		if drawer is None:
			return
		self._draw_preview_content(drawer)


class StandalonePreviewWindow(object):
	def __init__(self, controller, drawer):
		self.controller = controller
		self.drawer = drawer
		self.window = None
		self.view = None
		controller.add_listener(self.refresh)

	def open(self):
		if self.window is not None:
			self.window.makeKeyAndOrderFront_(None)
			self.refresh()
			return
		frame = NSMakeRect(120, 120, 520, 420)
		self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
			frame,
			15,
			2,
			False,
		)
		self.window.setTitle_("VF Preview")
		self.view = PreviewCanvasView.alloc().initWithFrame_(frame)
		self.view.setController_(self.controller)
		self.view.drawer = self.drawer
		self.window.setContentView_(self.view)
		self.apply_window_level()
		self.window.makeKeyAndOrderFront_(None)
		self.refresh()

	def close(self):
		if self.window is not None:
			self.window.orderOut_(None)

	def apply_window_level(self):
		if self.window is None:
			return
		if self.controller.pref("alwaysOnTop"):
			self.window.setLevel_(NSFloatingWindowLevel)
		else:
			self.window.setLevel_(0)

	def refresh(self, immediate=False):
		if self.view is not None:
			self.view.setNeedsDisplay_(True)
			if immediate:
				try:
					self.view.displayIfNeeded()
				except Exception:
					pass
		if self.window is not None:
			self.apply_window_level()


class PreviewDrawer(object):
	def __init__(self, controller):
		self.controller = controller
		self._string_layout_key = None
		self._string_layout_positions = None
		self._string_layout_metrics = None
		self._kern_cache_key = None
		self._kern_cache = {}

	def glyph_for_layer(self, font, layer):
		glyph = layer.parent
		if glyph is not None:
			return glyph
		try:
			name = layer.name
			if name:
				return font.glyphs[name]
		except Exception:
			pass
		return None

	def tab_layers(self, font=None):
		if font is None:
			font = self.controller.font
		if font is None:
			return []
		tab = font.currentTab
		if tab is not None:
			try:
				layers = list(tab.layers)
				if layers:
					return layers
			except Exception:
				pass
		try:
			selected = font.selectedLayers
			if selected:
				return list(selected)
		except Exception:
			pass
		return []

	def _interpolated_layer_for_source(self, layer):
		font = self.controller.font
		if font is None or layer is None:
			return None
		glyph = self.glyph_for_layer(font, layer)
		if glyph is None:
			return None
		return self.controller.interpolated_layer(glyph)

	def _interpolated_layer_width(self, layer):
		interpolated = self._interpolated_layer_for_source(layer)
		if interpolated is not None:
			try:
				return float(interpolated.width)
			except Exception:
				pass
		try:
			return float(layer.width)
		except Exception:
			return 0.0

	def _interpolated_kerning(self, left_layer, right_layer):
		font = self.controller.font
		if font is None or left_layer is None or right_layer is None:
			return 0.0
		left_glyph = self.glyph_for_layer(font, left_layer)
		right_glyph = self.glyph_for_layer(font, right_layer)
		if left_glyph is None or right_glyph is None:
			return 0.0
		values_key = self.controller._current_values_key()
		if self._kern_cache_key != values_key:
			self._kern_cache = {}
			self._kern_cache_key = values_key
		pair_key = (left_glyph.name, right_glyph.name)
		if pair_key in self._kern_cache:
			return self._kern_cache[pair_key]
		kern = 0.0
		controller = self.controller
		proxy = controller._proxy()
		if proxy is not None:
			master_id = controller._proxy_master_id(proxy)
			if master_id is not None:
				try:
					value = proxy.kerningForPair(master_id, left_glyph.name, right_glyph.name)
					if value is not None:
						kern = float(value)
						self._kern_cache[pair_key] = kern
						return kern
				except Exception:
					pass
		if controller.preview_instance is not None:
			try:
				interpolated_font = controller.preview_instance.interpolatedFont
				master_id = controller._proxy_master_id(interpolated_font)
				if master_id is None and font.selectedFontMaster is not None:
					master_id = font.selectedFontMaster.id
				if master_id is not None:
					value = interpolated_font.kerningForPair(
						master_id,
						left_glyph.name,
						right_glyph.name,
					)
					if value is not None:
						kern = float(value)
						self._kern_cache[pair_key] = kern
						return kern
			except Exception:
				pass
		master = left_layer.associatedFontMaster()
		if master is None:
			master = font.selectedFontMaster
		if master is not None:
			try:
				value = font.kerningForPair(master.id, left_glyph.name, right_glyph.name)
				if value is not None:
					kern = float(value)
			except Exception:
				pass
		self._kern_cache[pair_key] = kern
		return kern

	def _string_layout_for_layers(self, layers):
		controller = self.controller
		glyph_ids = []
		for layer in layers:
			glyph = self.glyph_for_layer(controller.font, layer)
			if glyph is not None:
				glyph_ids.append((glyph.id, glyph_change_key(glyph)))
			else:
				glyph_ids.append(None)
		cache_key = (controller._current_values_key(), tuple(glyph_ids))
		if self._string_layout_key == cache_key:
			return self._string_layout_positions, self._string_layout_metrics
		controller.prefetch_tab_layers(layers)
		positions = self._layer_x_positions(layers, use_interpolated_metrics=True)
		metrics = self._string_metrics_from_positions(
			layers,
			positions,
			use_interpolated_metrics=True,
		)
		self._string_layout_key = cache_key
		self._string_layout_positions = positions
		self._string_layout_metrics = metrics
		return positions, metrics

	def _layer_x_positions(self, layers, use_interpolated_metrics=False):
		if not layers:
			return []

		if not use_interpolated_metrics:
			tab_x_values = []
			for layer in layers:
				try:
					tab_x_values.append(float(layer.x))
				except Exception:
					tab_x_values = None
					break

			if tab_x_values and len(tab_x_values) > 1:
				increasing = all(
					tab_x_values[index] <= tab_x_values[index + 1]
					for index in range(len(tab_x_values) - 1)
				)
				if increasing and tab_x_values[-1] > tab_x_values[0]:
					return list(zip(layers, tab_x_values))

		positions = []
		cursor_x = 0.0
		for index, layer in enumerate(layers):
			positions.append((layer, cursor_x))
			next_layer = layers[index + 1] if index + 1 < len(layers) else None
			if use_interpolated_metrics:
				cursor_x += self._interpolated_string_advance(layer, next_layer)
			else:
				cursor_x += self._layer_string_advance(layer, next_layer, self.controller.font)
		return positions

	def _interpolated_string_advance(self, layer, next_layer):
		advance = self._interpolated_layer_width(layer)
		if next_layer is not None:
			advance += self._interpolated_kerning(layer, next_layer)
		return advance

	def _layer_string_advance(self, layer, next_layer, font):
		try:
			advance = float(layer.width)
		except Exception:
			advance = 0.0
		if next_layer is None or font is None:
			return advance
		left_glyph = layer.parent
		right_glyph = next_layer.parent
		if left_glyph is None or right_glyph is None:
			return advance
		try:
			master = layer.associatedFontMaster()
			if master is None:
				master = font.selectedFontMaster
			if master is not None:
				kern = font.kerningForPair(master.id, left_glyph.name, right_glyph.name)
				if kern is not None:
					return advance + float(kern)
		except Exception:
			pass
		return advance

	def _string_metrics_from_positions(self, layers, positions, use_interpolated_metrics=False):
		if not layers or not positions:
			return 0.0, 0.0, 800.0, -200.0
		min_x = min(position[1] for position in positions)
		max_x = 0.0
		for layer, layer_x in positions:
			if use_interpolated_metrics:
				width = self._interpolated_layer_width(layer)
			else:
				try:
					width = float(layer.width)
				except Exception:
					width = 0.0
			max_x = max(max_x, layer_x + width)
		master = layers[0].associatedFontMaster()
		if master is None and self.controller.font is not None:
			master = self.controller.font.selectedFontMaster
		ascender = getattr(master, "ascender", 800) or 800
		descender = getattr(master, "descender", -200) or -200
		return min_x, max(max_x - min_x, 1.0), ascender, descender

	def _string_metrics(self, layers):
		if not layers:
			return 0.0, 0.0, 800.0, -200.0
		positions = self._layer_x_positions(layers)
		return self._string_metrics_from_positions(layers, positions)

	def draw_interpolated_layer(self, source_layer, interpolated, scale=1.0, for_panel=False):
		if interpolated is None:
			return
		controller = self.controller
		if for_panel:
			make_color(0.0, 0.0, 0.0, 1.0).set()
		else:
			r, g, b, a = controller.preview_color(controller.is_layer_extrapolated())
			make_color(r, g, b, a).set()
		if interpolated.paths:
			interpolated.bezierPath.fill()
		if interpolated.components:
			for component in interpolated.components:
				component.bezierPath.fill()
		if not for_panel and controller.pref("showPreviewNodes"):
			draw_nodes(interpolated, scale, draw_tangents=True)

	def _show_panel_nodes(self, controller):
		try:
			return bool(int(controller.pref("showPreviewPanelNodes")))
		except Exception:
			return bool(controller.pref("showPreviewPanelNodes"))

	def draw_interpolated_string(
		self,
		bounds,
		layers=None,
		for_panel=False,
		center=False,
	):
		controller = self.controller
		if controller.font is None:
			return False
		if layers is None:
			layers = self.tab_layers(controller.font)
		if not layers:
			selected = controller.font.selectedLayers
			if selected:
				layers = [selected[0]]
			else:
				return False

		layer_positions, (min_x, string_width, ascender, descender) = self._string_layout_for_layers(layers)
		string_height = ascender - descender
		view_width = bounds.size.width
		view_height = bounds.size.height
		padding = 12.0
		scale = min(
			(view_width - padding * 2.0) / string_width,
			(view_height - padding * 2.0) / string_height,
		) * 0.95
		if scale <= 0.0:
			return False

		if center or (for_panel and controller.pref("centerPreview")):
			origin_x = (view_width - string_width * scale) / 2.0 - min_x * scale
		else:
			origin_x = padding - min_x * scale

		if for_panel:
			baseline_y = (view_height - string_height * scale) / 2.0 + ascender * scale
		else:
			baseline_y = padding + (view_height - padding * 2.0 - string_height * scale) / 2.0
			baseline_y += (-descender) * scale

		drawn_count = 0
		panel_points = []
		panel_connections = []
		show_panel_nodes = for_panel and self._show_panel_nodes(controller)
		for source_layer, layer_x in layer_positions:
			glyph = self.glyph_for_layer(controller.font, source_layer)
			if glyph is None:
				continue
			try:
				interpolated = controller.interpolated_layer(glyph)
				if interpolated is None:
					continue
				if show_panel_nodes:
					points, connections = collect_view_node_data(
						interpolated,
						layer_x,
						origin_x,
						baseline_y,
						scale,
					)
					panel_points.extend(points)
					panel_connections.extend(connections)
				NSGraphicsContext.saveGraphicsState()
				transform = NSAffineTransform.transform()
				transform.translateXBy_yBy_(origin_x + layer_x * scale, baseline_y)
				if for_panel:
					transform.scaleXBy_yBy_(scale, -scale)
				else:
					transform.scaleBy_(scale)
				transform.concat()
				self.draw_interpolated_layer(
					source_layer,
					interpolated,
					scale=scale,
					for_panel=for_panel,
				)
				NSGraphicsContext.restoreGraphicsState()
				drawn_count += 1
			except Exception:
				try:
					NSGraphicsContext.restoreGraphicsState()
				except Exception:
					pass
		if show_panel_nodes and panel_points:
			draw_nodes_view_space(panel_points, panel_connections)
		return drawn_count > 0

	def should_draw(self, options=None):
		if options is not None and options.get("OnSpaceDown"):
			return False
		return True

	def draw_preview(self, source_layer, glyph, scale=1.0, is_active=True, for_panel=False):
		if source_layer is None or glyph is None:
			return
		controller = self.controller
		if controller.font is None:
			return

		interpolated = controller.interpolated_layer(glyph)
		if interpolated is None:
			return

		shift_x = 0.0
		if not for_panel:
			shift_x = controller.center_shift_for_layer(source_layer, interpolated)
		elif controller.pref("centerPreview"):
			shift_x = controller.center_shift_for_layer(source_layer, interpolated)

		if abs(shift_x) > 0.001:
			transform = NSAffineTransform.transform()
			transform.translateXBy_yBy_(shift_x, 0.0)
			interpolated = interpolated.copy()
			interpolated.transform_checkForSelection_doComponents_(transform, False, False)

		live_previewing = controller.is_live_previewing()
		show_masters = controller.pref("showInvolvedMasters") and not for_panel and not live_previewing
		if show_masters:
			self.draw_involved_masters(glyph, shift_x, scale)

		r, g, b, a = controller.preview_color(controller.is_layer_extrapolated())
		if for_panel:
			a = max(a, 0.75)
		make_color(r, g, b, a).set()
		if interpolated.paths:
			interpolated.bezierPath.fill()
		if interpolated.components:
			for component in interpolated.components:
				component.bezierPath.fill()

		if controller.pref("showPreviewNodes"):
			draw_nodes(interpolated, scale, draw_tangents=True)

		if controller.pref("showMeasurements") and is_active and not for_panel and not live_previewing:
			draw_measurement(source_layer, scale, center_shift=shift_x)

	def draw_involved_masters(self, glyph, shift_x, scale):
		controller = self.controller
		weights = controller.interpolation_weights()
		if not weights:
			return
		for index, master in enumerate(controller.font.masters):
			weight = abs(weights.get(master.id, 0.0))
			if weight < 0.01:
				continue
			master_layer = controller.master_layer_for_glyph(master, glyph)
			if master_layer is None:
				continue
			r, g, b = controller.master_color(index)
			alpha = min(0.55, 0.15 + weight * 0.45)
			make_color(r, g, b, alpha).set()
			layer = master_layer
			if abs(shift_x) > 0.001:
				layer = master_layer.copy()
				transform = NSAffineTransform.transform()
				transform.translateXBy_yBy_(shift_x, 0.0)
				layer.transform_checkForSelection_doComponents_(transform, False, False)
			if layer.paths:
				layer.bezierPath.fill()
			if controller.pref("showMasterNodes"):
				draw_nodes(layer, scale, color=make_color(r, g, b, 0.95))
