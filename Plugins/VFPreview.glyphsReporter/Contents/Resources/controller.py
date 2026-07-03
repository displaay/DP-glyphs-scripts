# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import json

from GlyphsApp import GSInstance

from axis_utils import (
	default_axis_values,
	instance_axis_values,
	master_axis_values,
	selected_master_axis_values,
	set_instance_axis_values,
)
from font_resolver import font_storage_key
from fast_interpolator import direct_interpolated_layer, glyph_change_key


PREFS_PREFIX = "com.displaay.VFPreview"

MASTER_COLORS = [
	(0.20, 0.55, 0.95),
	(0.95, 0.35, 0.25),
	(0.30, 0.78, 0.45),
	(0.92, 0.62, 0.15),
	(0.62, 0.35, 0.88),
	(0.15, 0.72, 0.78),
	(0.88, 0.42, 0.62),
	(0.45, 0.45, 0.45),
]


class PreviewController(object):
	def __init__(self, plugin):
		self.plugin = plugin
		self.font = None
		self.preview_instance = None
		self.axis_values = {}
		self._proxy_cache = None
		self._proxy_font_id = None
		self._values_key = None
		self._layer_cache = {}
		self._layer_cache_key = None
		self._fast_layer_cache = {}
		self._fast_layer_cache_key = None
		self.listeners = []
		self._ui_flush_timer = None
		self._ui_flush_target = None
		self._defer_ui_sync = False
		self._live_preview_timer = None
		self._live_preview_target = None
		self._live_previewing = False
		self._edit_redraw_timer = None
		self._edit_redraw_target = None
		self._extrapolated_cache_key = None
		self._extrapolated_cache_value = False
		self._weights_cache_key = None
		self._weights_cache_value = {}

	def _current_values_key(self):
		return tuple(sorted(self.axis_values.items()))

	def _invalidate_layer_cache(self):
		self._layer_cache = {}
		self._layer_cache_key = None
		self._fast_layer_cache = {}
		self._fast_layer_cache_key = None

	def _invalidate_proxy_cache(self):
		self._proxy_cache = None
		self._proxy_font_id = None
		self._values_key = None

	def _on_axis_values_changed(self):
		self._invalidate_layer_cache()
		self._extrapolated_cache_key = None
		self._weights_cache_key = None

	def _invalidate_preview_caches(self):
		if self.plugin is not None:
			dock_panel = self.plugin.dock_panel
			if dock_panel is not None:
				try:
					dock_panel.invalidate_preview_cache()
				except Exception:
					pass
			standalone = getattr(self.plugin, "standalone_preview", None)
			if standalone is not None:
				try:
					standalone.invalidate_preview_cache()
				except Exception:
					pass

	def _refresh_preview_panels(self, immediate=False):
		if self.plugin is not None:
			dock_panel = self.plugin.dock_panel
			if dock_panel is not None:
				try:
					dock_panel.refresh_preview_only(immediate=immediate)
				except Exception:
					pass
			standalone = getattr(self.plugin, "standalone_preview", None)
			if standalone is not None:
				try:
					standalone.refresh(immediate=immediate)
				except Exception:
					pass

	def _should_redraw_edit_view(self):
		if self.plugin is None:
			return False
		try:
			return bool(int(self.pref("drawInEditView")))
		except Exception:
			return bool(self.pref("drawInEditView"))

	def notify_preview(self):
		self._refresh_preview_panels(immediate=not self._live_previewing)
		if self.plugin is not None and self._should_redraw_edit_view():
			if self._live_previewing:
				self.plugin.refreshViews(immediate=True)
			else:
				self.plugin.refreshViews()

	def register_defaults(self):
		from GlyphsApp import Glyphs

		defaults = {
			"drawInEditView": 1,
			"standaloneWindow": 0,
			"alwaysOnTop": 0,
			"centerPreview": 0,
			"hideForeground": 0,
			"linkToMaster": 0,
			"showInvolvedMasters": 0,
			"showPreviewNodes": 1,
			"showPreviewPanelNodes": 0,
			"showMasterNodes": 0,
			"showMeasurements": 1,
			"roundValues": 1,
			"previewMode": "glyph",
			"showBarChart": 1,
			"showRadarChart": 1,
			"previewScale": 1.0,
			"previewBarHeight": 88,
			"savedValues": "{}",
		}
		for key, value in defaults.items():
			Glyphs.registerDefault("%s.%s" % (PREFS_PREFIX, key), value)

	def pref(self, key):
		from GlyphsApp import Glyphs

		return Glyphs.defaults["%s.%s" % (PREFS_PREFIX, key)]

	def set_pref(self, key, value):
		from GlyphsApp import Glyphs

		Glyphs.defaults["%s.%s" % (PREFS_PREFIX, key)] = value

	def add_listener(self, callback):
		if callback not in self.listeners:
			self.listeners.append(callback)

	def remove_listener(self, callback):
		if callback in self.listeners:
			self.listeners.remove(callback)

	def notify_ui(self):
		for callback in list(self.listeners):
			try:
				callback()
			except Exception:
				pass

	def notify_listeners(self):
		self.notify_ui()
		self.notify_preview()

	def _cancel_ui_flush(self):
		if self._ui_flush_timer is not None:
			try:
				self._ui_flush_timer.invalidate()
			except Exception:
				pass
			self._ui_flush_timer = None

	def schedule_ui_flush(self, delay=0.016):
		try:
			from Foundation import NSTimer, NSObject

			if self._ui_flush_timer is not None:
				try:
					self._ui_flush_timer.invalidate()
				except Exception:
					pass
				self._ui_flush_timer = None

			if self._ui_flush_target is None:

				class UIFlushTarget(NSObject):
					controller = None

					def fire_(self, timer):
						if UIFlushTarget.controller is not None:
							UIFlushTarget.controller._run_ui_flush()

				self._ui_flush_target = UIFlushTarget.alloc().init()
				UIFlushTarget.controller = self

			self._ui_flush_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
				delay,
				self._ui_flush_target,
				"fire:",
				None,
				False,
			)
		except Exception:
			self.notify_ui()

	def _run_ui_flush(self):
		self._ui_flush_timer = None
		self._defer_ui_sync = False
		if self.plugin is not None and self._should_redraw_edit_view():
			self.plugin.refreshViews()
		self.notify_ui()

	def _mark_live_preview(self, delay=0.12):
		self._live_previewing = True
		try:
			from Foundation import NSTimer, NSObject

			if self._live_preview_timer is not None:
				try:
					self._live_preview_timer.invalidate()
				except Exception:
					pass
				self._live_preview_timer = None

			if self._live_preview_target is None:

				class LivePreviewTarget(NSObject):
					controller = None

					def fire_(self, timer):
						if LivePreviewTarget.controller is not None:
							LivePreviewTarget.controller._clear_live_preview()

				self._live_preview_target = LivePreviewTarget.alloc().init()
				LivePreviewTarget.controller = self

			self._live_preview_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
				delay,
				self._live_preview_target,
				"fire:",
				None,
				False,
			)
		except Exception:
			pass

	def _clear_live_preview(self):
		self._live_preview_timer = None
		self._live_previewing = False
		self._invalidate_layer_cache()
		if self.plugin is not None and self._should_redraw_edit_view():
			self.plugin.refreshViews()
		self._refresh_preview_panels(immediate=False)

	def is_live_previewing(self):
		return bool(self._live_previewing)

	def schedule_edit_redraw(self, delay=0.016):
		if self.plugin is None:
			return
		try:
			from Foundation import NSTimer, NSObject

			if self._edit_redraw_timer is not None:
				return

			if self._edit_redraw_target is None:

				class EditRedrawTarget(NSObject):
					controller = None

					def fire_(self, timer):
						if EditRedrawTarget.controller is not None:
							EditRedrawTarget.controller._run_edit_redraw()

				self._edit_redraw_target = EditRedrawTarget.alloc().init()
				EditRedrawTarget.controller = self

			self._edit_redraw_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
				delay,
				self._edit_redraw_target,
				"fire:",
				None,
				False,
			)
		except Exception:
			if self.plugin is not None:
				self.plugin.refreshViews()

	def _run_edit_redraw(self):
		self._edit_redraw_timer = None
		if self.plugin is not None:
			self.plugin.refreshViews()

	def bind_font(self, font):
		if font is None:
			self.font = None
			self.preview_instance = None
			self._invalidate_proxy_cache()
			self._invalidate_layer_cache()
			self._values_key = None
			self._invalidate_preview_caches()
			return

		font_changed = self.font is None or self.font != font
		self.font = font

		if self.preview_instance is None:
			self.preview_instance = GSInstance()
		self.preview_instance.font = font
		self.preview_instance.active = False
		self.preview_instance.name = "__VFPreview__"

		if font_changed:
			try:
				self.axis_values = self.load_saved_values(font) or default_axis_values(font)
			except Exception:
				self.axis_values = default_axis_values(font)
		self._coerce_all_axis_values()
		self.sync_preview_instance()
		self._invalidate_proxy_cache()
		self._invalidate_layer_cache()
		self._invalidate_preview_caches()

	def load_saved_values(self, font):
		try:
			data = json.loads(self.pref("savedValues") or "{}")
		except Exception:
			return None
		font_key = font_storage_key(font)
		if not font_key:
			return None
		saved = data.get(font_key)
		if not saved:
			return None
		values = {}
		for axis in font.axes:
			if axis.axisId in saved:
				values[axis.axisId] = float(saved[axis.axisId])
		return values or None

	def save_current_values(self):
		if self.font is None:
			return
		try:
			data = json.loads(self.pref("savedValues") or "{}")
		except Exception:
			data = {}
		font_key = font_storage_key(self.font)
		if not font_key:
			return
		data[font_key] = dict(self.axis_values)
		self.set_pref("savedValues", json.dumps(data))

	def _coerce_axis_value(self, value):
		value = float(value)
		try:
			round_values = bool(int(self.pref("roundValues")))
		except Exception:
			round_values = bool(self.pref("roundValues"))
		if round_values:
			return float(int(round(value)))
		return value

	def _coerce_all_axis_values(self):
		self.axis_values = {
			axis_id: self._coerce_axis_value(axis_value)
			for axis_id, axis_value in self.axis_values.items()
		}

	def sync_preview_instance(self):
		if self.font is None or self.preview_instance is None:
			return
		if self.pref("linkToMaster"):
			self.axis_values = selected_master_axis_values(self.font)
		self._coerce_all_axis_values()
		set_instance_axis_values(self.preview_instance, self.font, self.axis_values)
		self._on_axis_values_changed()
		self._invalidate_proxy_cache()

	def set_axis_value(self, axis_id, value, notify=True):
		coerced = self._coerce_axis_value(value)
		if self.axis_values.get(axis_id) == coerced:
			if notify == "preview":
				return
			if notify is True and not self._defer_ui_sync:
				return
		self.axis_values[axis_id] = coerced
		set_instance_axis_values(self.preview_instance, self.font, self.axis_values)
		self._on_axis_values_changed()
		self._invalidate_proxy_cache()
		if notify is True:
			self._cancel_ui_flush()
			self._defer_ui_sync = False
			self.notify_listeners()
		elif notify == "preview":
			self._defer_ui_sync = True
			self._mark_live_preview()
			self.notify_preview()

	def set_axis_values(self, values, notify=True):
		for axis_id, value in values.items():
			self.axis_values[axis_id] = self._coerce_axis_value(value)
		set_instance_axis_values(self.preview_instance, self.font, self.axis_values)
		self._on_axis_values_changed()
		self._invalidate_proxy_cache()
		if notify is True:
			self.notify_listeners()
		elif notify == "preview":
			self._mark_live_preview()
			self.notify_preview()

	def apply_master(self, master):
		self.set_axis_values(master_axis_values(self.font, master))

	def apply_instance(self, instance):
		self.set_axis_values(instance_axis_values(self.font, instance))

	def interpolation_weights(self):
		if self.preview_instance is None:
			return {}
		values_key = self._current_values_key()
		if self._weights_cache_key == values_key:
			return dict(self._weights_cache_value)
		try:
			weights = self.preview_instance.instanceInterpolations
			if weights is None:
				result = {}
			else:
				result = dict(weights)
		except Exception:
			result = {}
		self._weights_cache_key = values_key
		self._weights_cache_value = result
		return dict(result)

	def prefetch_tab_layers(self, layers):
		if not layers or self.font is None:
			return
		font = self.font
		for layer in layers:
			glyph = layer.parent
			if glyph is None:
				try:
					name = layer.name
					if name:
						glyph = font.glyphs[name]
				except Exception:
					glyph = None
			if glyph is not None:
				try:
					self.interpolated_layer(glyph)
				except Exception:
					pass

	def master_color(self, master_index):
		return MASTER_COLORS[master_index % len(MASTER_COLORS)]

	def _proxy_master_id(self, proxy):
		for name in ("fontMasterID", "fontMasterId"):
			try:
				value = getattr(proxy, name, None)
				if value is None:
					continue
				return value() if callable(value) else value
			except Exception:
				pass
		try:
			return proxy.masters[0].id
		except Exception:
			return None

	def _layer_from_proxy_glyph(self, proxy, proxy_glyph):
		if proxy_glyph is None:
			return None
		master_id = self._proxy_master_id(proxy)
		if master_id is not None:
			try:
				layer = proxy_glyph.layers[master_id]
				if layer is not None:
					return layer
			except Exception:
				pass
		try:
			return proxy_glyph.layers[0]
		except Exception:
			return None

	def _prepare_layer_for_draw(self, layer):
		if layer is None:
			return None
		if layer.components:
			layer = layer.copy()
			layer.decomposeComponents()
		return layer

	def _fetch_interpolated_layer(self, glyph):
		try:
			proxy = self._proxy()
			if proxy is None:
				return None
			proxy_glyph = proxy.glyphs[glyph.name]
			layer = self._layer_from_proxy_glyph(proxy, proxy_glyph)
			return self._prepare_layer_for_draw(layer)
		except Exception:
			try:
				font = self.preview_instance.interpolatedFont
				proxy_glyph = font.glyphs[glyph.name]
				layer = self._layer_from_proxy_glyph(font, proxy_glyph)
				return self._prepare_layer_for_draw(layer)
			except Exception:
				return None

	def _fetch_fast_interpolated_layer(self, glyph):
		try:
			return direct_interpolated_layer(self, glyph)
		except Exception:
			return None

	def interpolated_layer(self, glyph):
		if self.font is None or self.preview_instance is None or glyph is None:
			return None
		values_key = self._current_values_key()
		if self._fast_layer_cache_key != values_key:
			self._fast_layer_cache = {}
			self._fast_layer_cache_key = values_key
		glyph_id = glyph.id
		change_key = glyph_change_key(glyph)
		cached = self._fast_layer_cache.get(glyph_id)
		if cached is not None and cached[0] == change_key:
			return cached[1]
		layer = self._fetch_fast_interpolated_layer(glyph)
		if layer is not None:
			self._fast_layer_cache[glyph_id] = (change_key, layer)
			return layer

		if self._layer_cache_key != values_key:
			self._layer_cache = {}
			self._layer_cache_key = values_key
		cached = self._layer_cache.get(glyph_id)
		if cached is not None and cached[0] == change_key:
			return cached[1]
		layer = self._fetch_interpolated_layer(glyph)
		if layer is not None:
			self._layer_cache[glyph_id] = (change_key, layer)
		return layer

	def _proxy(self):
		if self.preview_instance is None:
			return None
		font_id = id(self.font)
		values_key = self._current_values_key()
		if (
			self._proxy_cache is not None
			and self._proxy_font_id == font_id
			and self._values_key == values_key
		):
			self._values_key = self._current_values_key()
			return self._proxy_cache
		try:
			self._proxy_cache = self.preview_instance.interpolatedFontProxy
		except Exception:
			try:
				self._proxy_cache = self.preview_instance.pyobjc_instanceMethods.interpolatedFontProxy()
			except Exception:
				self._proxy_cache = None
		self._proxy_font_id = font_id
		self._values_key = values_key
		return self._proxy_cache

	def master_layer_for_glyph(self, master, glyph):
		try:
			return glyph.layers[master.id]
		except Exception:
			return None

	def upm_scale(self):
		if self.font is None:
			return 1.0
		return 1000.0 / float(self.font.upm or 1000)

	def preview_color(self, extrapolated=False):
		if extrapolated:
			return (0.55, 0.55, 0.55, 0.35)
		return (0.18, 0.42, 0.88, 0.40)

	def is_layer_extrapolated(self):
		from axis_utils import SYNTHETIC_AXIS_ID, is_extrapolated, synthetic_axis_limits, uses_synthetic_axis

		if self.font is None:
			return False
		values_key = self._current_values_key()
		if self._extrapolated_cache_key == values_key:
			return self._extrapolated_cache_value
		if uses_synthetic_axis(self.font):
			minimum, maximum = synthetic_axis_limits(self.font)
			value = self.axis_values.get(SYNTHETIC_AXIS_ID, (minimum + maximum) / 2.0)
			result = value < minimum - 0.0001 or value > maximum + 0.0001
		else:
			result = False
			for index, axis in enumerate(self.font.axes):
				value = self.axis_values.get(axis.axisId, 0.0)
				if is_extrapolated(self.font, index, value):
					result = True
					break
		self._extrapolated_cache_key = values_key
		self._extrapolated_cache_value = result
		return result

	def make_instance_from_current(self, name=None):
		from GlyphsApp import GSInstance

		if self.font is None:
			return None
		instance = GSInstance()
		instance.font = self.font
		instance.active = True
		if name is None:
			name = "VF Preview %i" % (len(self.font.instances) + 1)
		instance.name = name
		set_instance_axis_values(instance, self.font, self.axis_values)
		self.font.instances.append(instance)
		return instance

	def axis_rows(self):
		from axis_utils import (
			SYNTHETIC_AXIS_ID,
			axis_limits,
			is_extrapolated,
			synthetic_axis_limits,
			uses_synthetic_axis,
		)

		if self.font is None:
			return []
		if uses_synthetic_axis(self.font):
			minimum, maximum = synthetic_axis_limits(self.font)
			value = self.axis_values.get(SYNTHETIC_AXIS_ID, (minimum + maximum) / 2.0)
			return [{
				"index": 0,
				"axisId": SYNTHETIC_AXIS_ID,
				"tag": "axis",
				"name": "Interpolation",
				"minimum": minimum,
				"maximum": maximum,
				"value": value,
				"extrapolated": value < minimum - 0.0001 or value > maximum + 0.0001,
				"binary": (maximum - minimum) <= 1.0,
				"ticks": (maximum - minimum) <= 10.0 and (maximum - minimum) > 1.0,
			}]
		rows = []
		for index, axis in enumerate(self.font.axes):
			minimum, maximum = axis_limits(self.font, index)
			value = self.axis_values.get(axis.axisId, minimum)
			rows.append({
				"index": index,
				"axisId": axis.axisId,
				"tag": axis.axisTag,
				"name": axis.name,
				"minimum": minimum,
				"maximum": maximum,
				"value": value,
				"extrapolated": is_extrapolated(self.font, index, value),
				"binary": (maximum - minimum) <= 1.0,
				"ticks": (maximum - minimum) <= 10.0 and (maximum - minimum) > 1.0,
			})
		return rows

	def weight_entries(self):
		weights = self.interpolation_weights()
		if not weights:
			return []
		total = sum(abs(value) for value in weights.values()) or 1.0
		entries = []
		for index, master in enumerate(self.font.masters):
			weight = abs(weights.get(master.id, 0.0))
			entries.append({
				"master": master,
				"index": index,
				"name": master.name,
				"weight": weight,
				"percent": 100.0 * weight / total,
				"color": self.master_color(index),
			})
		entries.sort(key=lambda item: item["percent"], reverse=True)
		return entries

	def center_shift_for_layer(self, source_layer, interpolated_layer):
		if not self.pref("centerPreview"):
			return 0.0
		source_center = source_layer.bounds.origin.x + source_layer.bounds.size.width / 2.0
		interp_center = interpolated_layer.bounds.origin.x + interpolated_layer.bounds.size.width / 2.0
		return source_center - interp_center
