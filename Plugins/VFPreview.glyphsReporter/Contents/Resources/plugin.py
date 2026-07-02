# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import os
import sys

import objc
from GlyphsApp import Glyphs
from GlyphsApp.plugins import ReporterPlugin

try:
	from GlyphsApp import UPDATEINTERFACE
except Exception:
	UPDATEINTERFACE = None

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if PLUGIN_DIR not in sys.path:
	sys.path.insert(0, PLUGIN_DIR)

from controller import PreviewController
from preview_view import PreviewDrawer, StandalonePreviewWindow
from split_panel import SplitVFPanel
from axis_utils import exportable_instances
from fast_interpolator import glyph_change_key
from font_resolver import resolve_font


class VFPreview(ReporterPlugin):
	dock_panel = None
	preview_controller = None
	drawer = None
	standalone_preview = None
	_update_callback_registered = False
	_last_update_key = None

	@objc.python_method
	def settings(self):
		self.menuName = Glyphs.localize({
			"en": "VF Preview",
			"de": "VF Vorschau",
		})
		self.preview_controller = PreviewController(self)
		self.preview_controller.register_defaults()
		self.drawer = PreviewDrawer(self.preview_controller)
		self.dock_panel = SplitVFPanel(self.preview_controller, self.drawer)
		self.keyEquivalent = "^~@v"

	@objc.python_method
	def start(self):
		if self.preview_controller is None:
			self.preview_controller = PreviewController(self)
		self.preview_controller.register_defaults()

	@objc.python_method
	def _ensure_ready(self):
		if self.preview_controller is None:
			self.preview_controller = PreviewController(self)
			self.drawer = PreviewDrawer(self.preview_controller)
		if self.dock_panel is None:
			self.dock_panel = SplitVFPanel(self.preview_controller, self.drawer)
		font = resolve_font(self)
		if font is not None:
			if self.preview_controller.font != font:
				self.preview_controller.bind_font(font)
			elif self.preview_controller.font is None:
				self.preview_controller.bind_font(font)

	@objc.python_method
	def _refresh_dock(self):
		if self.dock_panel is not None:
			self.dock_panel.refresh()

	@objc.python_method
	def open_standalone_preview(self):
		self._ensure_ready()
		if self.standalone_preview is None:
			self.standalone_preview = StandalonePreviewWindow(self.preview_controller, self.drawer)
		self.standalone_preview.open()

	@objc.python_method
	def toggleLinkToMaster_(self, sender):
		value = 0 if self.preview_controller.pref("linkToMaster") else 1
		self.preview_controller.set_pref("linkToMaster", value)
		self.preview_controller.sync_preview_instance()
		self.preview_controller.notify_listeners()
		self._refresh_dock()
		self.refreshViews()

	@objc.python_method
	def toggleRoundValues_(self, sender):
		value = 0 if self.preview_controller.pref("roundValues") else 1
		self.preview_controller.set_pref("roundValues", value)
		if value:
			rounded = {
				axis_id: self.preview_controller._coerce_axis_value(axis_value)
				for axis_id, axis_value in self.preview_controller.axis_values.items()
			}
			self.preview_controller.set_axis_values(rounded)
		else:
			self.preview_controller.notify_listeners()

	def willActivate(self):
		self._ensure_ready()
		self.register_update_callback()
		if self.dock_panel is not None:
			if (
				self.dock_panel.preview_w is not None
				and self.dock_panel.axes_w is not None
			):
				self.dock_panel.reposition()
				self.dock_panel.refresh()
			else:
				self.dock_panel.open()

	def willDeactivate(self):
		if self.preview_controller is not None:
			self.preview_controller.save_current_values()
		self.unregister_update_callback()
		if self.dock_panel is not None:
			self.dock_panel.close()

	@objc.python_method
	def _ensure_font_bound(self, layer=None):
		self._ensure_ready()
		if self.preview_controller is None:
			return
		font = resolve_font(self, layer)
		if font is None:
			return
		if self.preview_controller.font != font:
			self.preview_controller.bind_font(font)
			self._refresh_dock()

	@objc.python_method
	def register_update_callback(self):
		if UPDATEINTERFACE is None or self._update_callback_registered:
			return
		Glyphs.addCallback(self.updateCallback, UPDATEINTERFACE)
		self._update_callback_registered = True

	@objc.python_method
	def unregister_update_callback(self):
		if UPDATEINTERFACE is None or not self._update_callback_registered:
			return
		Glyphs.removeCallback(self.updateCallback)
		self._update_callback_registered = False

	@objc.python_method
	def updateCallback(self, notification=None):
		font = resolve_font(self)
		if font is None:
			return
		if self.preview_controller is None:
			return
		if self.preview_controller.font != font:
			self.preview_controller.bind_font(font)
			self._last_update_key = None
		if self.preview_controller.pref("linkToMaster"):
			self.preview_controller.sync_preview_instance()
		if self.preview_controller._defer_ui_sync:
			return
		font_id = id(self.preview_controller.font)
		values_key = self.preview_controller._current_values_key()
		source_key = self._current_source_key(font)
		update_key = (font_id, values_key, source_key)
		if update_key == self._last_update_key:
			return
		previous_key = self._last_update_key
		self._last_update_key = update_key
		if (
			previous_key is not None
			and previous_key[0] == font_id
			and previous_key[1] == values_key
			and previous_key[2] != source_key
		):
			self.preview_controller._invalidate_layer_cache()
			self.preview_controller._invalidate_proxy_cache()
			self.preview_controller._refresh_preview_panels(immediate=False)
		else:
			self._refresh_dock()
		self.refreshViews()

	@objc.python_method
	def _current_source_key(self, font):
		if font is None or self.drawer is None:
			return ()
		source = []
		try:
			layers = self.drawer.tab_layers(font)
		except Exception:
			layers = []
		for layer in layers or []:
			try:
				glyph = self.drawer.glyph_for_layer(font, layer)
			except Exception:
				glyph = None
			if glyph is not None:
				source.append((glyph.id, glyph_change_key(glyph)))
		return tuple(source)

	@objc.python_method
	def _object_value(self, obj, name):
		if obj is None:
			return None
		try:
			value = getattr(obj, name, None)
			if callable(value):
				return value()
			return value
		except Exception:
			return None

	@objc.python_method
	def _edit_view_controller(self):
		for owner in (self, getattr(self, "preview_controller", None)):
			for name in ("controller", "viewController", "editViewController"):
				controller = self._object_value(owner, name)
				if controller is not None:
					return controller
		try:
			font = self.preview_controller.font if self.preview_controller is not None else Glyphs.font
			document = getattr(font, "parent", None) if font is not None else None
			window_controller = document.windowController() if document is not None else None
			for name in ("activeEditViewController", "editViewController", "tabViewController"):
				controller = self._object_value(window_controller, name)
				if controller is not None:
					return controller
		except Exception:
			pass
		return None

	@objc.python_method
	def _edit_graphic_view(self):
		controller = self._edit_view_controller()
		for name in ("graphicView", "view"):
			view = self._object_value(controller, name)
			if view is not None:
				return view
		return None

	@objc.python_method
	def _display_view_now(self, view):
		if view is None:
			return False
		try:
			view.setNeedsDisplay_(True)
		except Exception:
			pass
		try:
			view.display()
			return True
		except Exception:
			pass
		try:
			view.displayIfNeeded()
			return True
		except Exception:
			pass
		try:
			window = view.window()
			if window is not None:
				window.displayIfNeeded()
				return True
		except Exception:
			pass
		return False

	@objc.python_method
	def refreshViews(self, immediate=False):
		try:
			if self.preview_controller is not None:
				font = self.preview_controller.font or Glyphs.font
				tab = getattr(font, "currentTab", None) if font is not None else None
				view = self._edit_graphic_view()
				if view is not None:
					try:
						view.setNeedsDisplay_(True)
					except Exception:
						pass
				if tab is not None:
					tab.redraw()
				else:
					Glyphs.redraw()
				if immediate and self._display_view_now(view):
					return
		except Exception:
			pass

	def needsExtraMainOutlineDrawingForActiveLayer_(self, layer):
		if self.preview_controller is None:
			return True
		if not self.preview_controller.pref("hideForeground"):
			return True
		return False

	def drawBackgroundForLayer_options_(self, layer, options):
		self._scale = options.get("Scale", 1.0)
		self._draw_options = options
		self._ensure_font_bound(layer)
		if not self._should_draw_in_edit_view(options):
			return
		if layer is None:
			return
		glyph = layer.parent
		if glyph is None:
			return
		mode = self.preview_controller.pref("previewMode") or "glyph"
		if mode != "glyph":
			return
		scale = self.getScale()
		try:
			self.drawer.draw_preview(layer, glyph, scale=scale, is_active=True)
		except Exception:
			pass

	def drawBackgroundForInactiveLayer_options_(self, layer, options):
		self._scale = options.get("Scale", 1.0)
		self._draw_options = options
		self._ensure_font_bound(layer)
		if not self._should_draw_in_edit_view(options):
			return
		if layer is None:
			return
		glyph = layer.parent
		if glyph is None:
			return
		mode = self.preview_controller.pref("previewMode") or "glyph"
		if mode == "glyph":
			return
		scale = self.getScale()
		try:
			self.drawer.draw_preview(layer, glyph, scale=scale, is_active=False)
		except Exception:
			pass

	@objc.python_method
	def _should_draw_in_edit_view(self, options=None):
		if self.preview_controller is None or self.preview_controller.font is None:
			return False
		if not self.preview_controller.pref("drawInEditView"):
			return False
		if options is not None and options.get("OnSpaceDown"):
			return False
		return True

	@objc.python_method
	def conditionalContextMenus(self):
		contextMenus = []
		font = Glyphs.font
		if font is None or self.preview_controller is None:
			return contextMenus

		for master in font.masters:
			contextMenus.append({
				"name": "VF Preview: Master %s" % master.name,
				"action": self.jumpFromContextMenu_,
			})

		for instance in exportable_instances(font):
			contextMenus.append({
				"name": "VF Preview: Instance %s" % instance.name,
				"action": self.jumpFromContextMenu_,
			})

		contextMenus.extend([
			{
				"name": "VF Preview: Make Instance from Sliders",
				"action": self.makeInstanceFromSliders_,
			},
			{
				"name": "VF Preview: Toggle Center Preview",
				"action": self.toggleCenterPreview_,
				"state": self.preview_controller.pref("centerPreview"),
			},
			{
				"name": "VF Preview: Toggle Hide Foreground",
				"action": self.toggleHideForeground_,
				"state": self.preview_controller.pref("hideForeground"),
			},
			{
				"name": "VF Preview: Toggle Involved Masters",
				"action": self.toggleInvolvedMasters_,
				"state": self.preview_controller.pref("showInvolvedMasters"),
			},
			{
				"name": "VF Preview: Toggle Preview Nodes",
				"action": self.toggleShowPreviewNodes_,
				"state": self.preview_controller.pref("showPreviewPanelNodes"),
			},
			{
				"name": "VF Preview: Toggle Edit View Nodes",
				"action": self.toggleShowEditViewNodes_,
				"state": self.preview_controller.pref("showPreviewNodes"),
			},
			{
				"name": "VF Preview: Toggle Link Selected Master",
				"action": self.toggleLinkToMaster_,
				"state": self.preview_controller.pref("linkToMaster"),
			},
			{
				"name": "VF Preview: Toggle Round Values",
				"action": self.toggleRoundValues_,
				"state": self.preview_controller.pref("roundValues"),
			},
			{
				"name": "VF Preview: Toggle Measurements",
				"action": self.toggleMeasurements_,
				"state": self.preview_controller.pref("showMeasurements"),
			},
		])
		return contextMenus

	def jumpFromContextMenu_(self, sender):
		title = sender.title()
		font = Glyphs.font
		if font is None:
			return
		prefix = "VF Preview: Master "
		if title.startswith(prefix):
			name = title[len(prefix):]
			for master in font.masters:
				if master.name == name:
					self.preview_controller.apply_master(master)
					break
		prefix = "VF Preview: Instance "
		if title.startswith(prefix):
			name = title[len(prefix):]
			for instance in exportable_instances(font):
				if instance.name == name:
					self.preview_controller.apply_instance(instance)
					break
		self._refresh_dock()
		self.refreshViews()

	def makeInstanceFromSliders_(self, sender):
		self.preview_controller.make_instance_from_current()
		self._refresh_dock()

	def toggleCenterPreview_(self, sender):
		value = 0 if self.preview_controller.pref("centerPreview") else 1
		self.preview_controller.set_pref("centerPreview", value)
		self._refresh_dock()
		self.refreshViews()

	def toggleHideForeground_(self, sender):
		value = 0 if self.preview_controller.pref("hideForeground") else 1
		self.preview_controller.set_pref("hideForeground", value)
		self.refreshViews()

	def toggleInvolvedMasters_(self, sender):
		value = 0 if self.preview_controller.pref("showInvolvedMasters") else 1
		self.preview_controller.set_pref("showInvolvedMasters", value)
		self.refreshViews()

	def toggleShowPreviewNodes_(self, sender):
		value = 0 if self.preview_controller.pref("showPreviewPanelNodes") else 1
		self.preview_controller.set_pref("showPreviewPanelNodes", value)
		self._refresh_dock()
		self.refreshViews()

	def toggleShowEditViewNodes_(self, sender):
		value = 0 if self.preview_controller.pref("showPreviewNodes") else 1
		self.preview_controller.set_pref("showPreviewNodes", value)
		self.refreshViews()

	def toggleMeasurements_(self, sender):
		value = 0 if self.preview_controller.pref("showMeasurements") else 1
		self.preview_controller.set_pref("showMeasurements", value)
		self.refreshViews()

	@objc.python_method
	def __file__(self):
		return __file__
