# -*- coding: utf-8 -*-
"""Native ⌘C / ⌘V for special layers in Glyphs 4's Layers palette."""
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

import traceback

import objc
from AppKit import (
    NSApplication, NSBeep, NSEvent, NSEventMaskKeyDown, NSEventMaskLeftMouseDown,
    NSEventTypeLeftMouseDown,
    NSEventModifierFlagCommand, NSEventModifierFlagControl,
    NSEventModifierFlagOption, NSEventModifierFlagShift, NSPasteboard,
)
from GlyphsApp import GSLayer, Glyphs
from GlyphsApp.plugins import GeneralPlugin

from speciallayercopy.clipboard import PASTEBOARD_TYPE, build_paste_plan, snapshot_layers
from speciallayercopy.core import execute_plan


SHORTCUT_MODIFIERS = (
    NSEventModifierFlagCommand | NSEventModifierFlagControl
    | NSEventModifierFlagOption | NSEventModifierFlagShift
)


def _palette_accepts_first_responder(view):
    return True


class DPSpecialLayerCopy(GeneralPlugin):
    @objc.python_method
    def settings(self):
        self.name = "Copy Special Layers"
        self.clipboard = None
        self._event_monitor = None
        self._event_handler = None
        self._focus_hook_installed = False

    @objc.python_method
    def start(self):
        if Glyphs.versionNumber < 4:
            return
        if self._event_monitor is not None:
            NSEvent.removeMonitor_(self._event_monitor)
        self.enable_palette_focus()
        self._event_handler = self.handle_event
        self._event_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown | NSEventMaskLeftMouseDown, self._event_handler
        )

    @objc.python_method
    def enable_palette_focus(self):
        if self._focus_hook_installed:
            return
        try:
            outline_class = objc.lookUpClass("GSLayerOutlineView")
        except objc.nosuchclass_error:
            return
        # Glyphs 4's Layers outline explicitly refuses first-responder status.
        # Enable keyboard focus for this one control so a click can establish
        # an unambiguous layer-copy context without stealing canvas commands.
        method = objc.selector(
            _palette_accepts_first_responder, selector=b"acceptsFirstResponder",
            signature=outline_class.acceptsFirstResponder.signature,
        )
        objc.classAddMethods(outline_class, [method])
        self._focus_hook_installed = True

    @objc.python_method
    def focused_layers_table(self):
        window = NSApplication.sharedApplication().keyWindow()
        if window is None:
            return None
        responder = window.firstResponder()
        try:
            outline_class = objc.lookUpClass("GSLayerOutlineView")
        except objc.nosuchclass_error:
            return None
        # Do not walk up from a field editor: copying a layer name must copy
        # text, and copying on the drawing canvas must still copy outlines.
        if responder is not None and responder.isKindOfClass_(outline_class):
            return responder
        return None

    @objc.python_method
    def selected_palette_layers(self, table):
        # Glyphs 4's outline rows may represent layers for several glyphs.
        # Resolve the rows through the palette rather than Font.selectedLayers,
        # which describes the drawing selection and can miss palette selections.
        palette = None
        for candidate in (table.delegate(), table.dataSource()):
            if candidate is not None and hasattr(candidate, "layersForRow_"):
                palette = candidate
                break
        if palette is None:
            return []
        layers, seen = [], set()
        for row in table.selectedRowIndexes():
            for layer in palette.layersForRow_(int(row)) or []:
                if not isinstance(layer, GSLayer) or layer.parent is None:
                    continue
                key = (layer.parent.name, layer.layerId)
                if key not in seen:
                    seen.add(key)
                    layers.append(layer)
        return layers

    @objc.python_method
    def handle_event(self, event):
        if event.type() == NSEventTypeLeftMouseDown:
            # The native Layers bundle can be loaded after general plug-ins.
            # Install before the click is dispatched, then let AppKit focus it.
            self.enable_palette_focus()
            return event
        if int(event.modifierFlags()) & SHORTCUT_MODIFIERS != NSEventModifierFlagCommand:
            return event
        key = (event.charactersIgnoringModifiers() or "").lower()
        if key not in ("c", "v"):
            return event
        table = self.focused_layers_table()
        if table is None or Glyphs.font is None:
            return event
        handled = False
        try:
            pasteboard = NSPasteboard.generalPasteboard()
            layers = self.selected_palette_layers(table)
            if key == "c":
                snapshot = snapshot_layers(Glyphs.font, layers)
                if snapshot is None:
                    return event
                handled = True
                pasteboard.declareTypes_owner_([PASTEBOARD_TYPE], None)
                if not pasteboard.setString_forType_(snapshot.token, PASTEBOARD_TYPE):
                    raise RuntimeError("The special layers could not be copied to the clipboard.")
                self.clipboard = snapshot
            else:
                if self.clipboard is None:
                    return event
                if pasteboard.stringForType_(PASTEBOARD_TYPE) != self.clipboard.token:
                    self.clipboard = None
                    return event
                handled = True
                plan = build_paste_plan(self.clipboard, Glyphs.font, layers)
                if execute_plan(plan):
                    table.reloadData()
                    Glyphs.redraw()
                else:
                    NSBeep()
            return None
        except Exception:
            # No modal UI or auxiliary windows. Consume only a command already
            # claimed by this plug-in; otherwise let Glyphs handle it normally.
            print("Copy Special Layers: " + traceback.format_exc())
            NSBeep()
            return None if handled else event

    @objc.python_method
    def __file__(self):
        return __file__
