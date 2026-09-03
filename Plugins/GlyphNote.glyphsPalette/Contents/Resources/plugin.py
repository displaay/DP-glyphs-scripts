# -*- coding: utf-8 -*-
"""Glyph Note — a native per-glyph / per-master note palette for Glyphs 4."""

from __future__ import annotations

import traceback

import objc
from AppKit import (
    NSBezierPath,
    NSColor,
    NSCompositingOperationSourceOver,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSZeroRect,
)
from Foundation import NSObject, NSUserDefaults
from GlyphsApp import Glyphs, UPDATEINTERFACE
from GlyphsApp.plugins import PalettePlugin

from glyphnote.core import (
    SHOW_BADGES_DEFAULTS_KEY,
    apply_lock_to_states,
    apply_note_to_states,
    clear_active_master_note,
    clear_all_notes,
    layer_has_note,
    read_glyph_state,
    selection_display,
    write_glyph_state,
)
from glyphnote.ui import DEFAULT_HEIGHT, GlyphNotePaletteView


def _system_image(symbol_name, fallback_name, description):
    if hasattr(NSImage, "imageWithSystemSymbolName_accessibilityDescription_"):
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol_name, description
        )
        if image is not None:
            return image
    if fallback_name:
        return NSImage.imageNamed_(fallback_name)
    return None


class GlyphNoteFontViewDrawer(NSObject):
    _shared_drawer = None
    _active_palettes = set()

    @classmethod
    def register_palette(cls, palette):
        cls._active_palettes.add(id(palette))
        if cls._shared_drawer is None:
            try:
                cls._shared_drawer = cls.alloc().init()
                handler = objc.lookUpClass("GSCallbackHandler")
                if handler is not None:
                    handler.addCallback_forOperation_(
                        cls._shared_drawer, "DrawFontView"
                    )
            except Exception:
                pass

    @classmethod
    def unregister_palette(cls, palette):
        cls._active_palettes.discard(id(palette))
        if not cls._active_palettes and cls._shared_drawer is not None:
            drawer = cls._shared_drawer
            cls._shared_drawer = None
            try:
                handler = objc.lookUpClass("GSCallbackHandler")
                if handler is not None:
                    if hasattr(handler, "removeCallback_forOperation_"):
                        handler.removeCallback_forOperation_(
                            drawer, "DrawFontView"
                        )
                    elif hasattr(handler, "removeCallback_"):
                        handler.removeCallback_(drawer)
            except Exception:
                pass

    @objc.signature(b"v@:@{CGRect={CGPoint=dd}{CGSize=dd}}")
    def drawFontViewForegroundForLayer_inFrame_(self, layer, frame):
        try:
            value = Glyphs.defaults[SHOW_BADGES_DEFAULTS_KEY]
            if value is not None and not value:
                return
            if layer is None or not layer_has_note(layer):
                return
            _draw_note_badge(frame)
        except Exception:
            pass


def _draw_note_badge(frame):
    size = 10.0
    inset = 3.0
    dest = NSMakeRect(
        frame.origin.x + inset,
        frame.origin.y + inset,
        size,
        size,
    )
    image = _system_image("note.text", None, "Glyph note")
    if image is not None:
        image.drawInRect_fromRect_operation_fraction_(
            dest, NSZeroRect, NSCompositingOperationSourceOver, 1.0
        )
        return
    NSColor.systemYellowColor().setFill()
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(dest, 2.0, 2.0)
    path.fill()


class GlyphNotePalette(PalettePlugin):
    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Glyph Note"})
        self.sortId = 6  # After Script Board (5), before Dimensions (10).
        self.min = 80
        self.max = 420
        self._updating = False
        self._palette = GlyphNotePaletteView()
        self._palette.attach_target(self)
        self.dialog = self._palette.dialog
        self.lock_button = self._palette.lock_button
        self.master_label = self._palette.master_label
        self.text_view = self._palette.text_view
        self.placeholder = self._palette.placeholder
        self._settings_menu = NSMenu.alloc().initWithTitle_("Glyph Note")

    @objc.python_method
    def start(self):
        Glyphs.addCallback(self.update, UPDATEINTERFACE)
        GlyphNoteFontViewDrawer.register_palette(self)
        self.update(None)

    def __del__(self):
        try:
            Glyphs.removeCallback(self.update, UPDATEINTERFACE)
        except Exception:
            pass
        GlyphNoteFontViewDrawer.unregister_palette(self)

    @objc.typedSelector(b"L@:")
    def currentHeight(self):
        value = NSUserDefaults.standardUserDefaults().integerForKey_(
            self.name + ".ViewHeight"
        )
        return value or DEFAULT_HEIGHT

    @objc.typedSelector(b"@@:")
    def settingsMenu(self):
        self._rebuild_settings_menu()
        return self._settings_menu

    @objc.python_method
    def _rebuild_settings_menu(self):
        menu = self._settings_menu
        menu.removeAllItems()
        self._add_menu_item(menu, "Lock Notes for Selection", self.lockSelection_)
        self._add_menu_item(menu, "Unlock Notes for Selection", self.unlockSelection_)
        menu.addItem_(NSMenuItem.separatorItem())
        self._add_menu_item(
            menu, "Clear Note in Active Master", self.clearActiveMaster_
        )
        self._add_menu_item(
            menu, "Clear All Notes in Selection", self.clearAllNotes_
        )
        menu.addItem_(NSMenuItem.separatorItem())
        badges = self._add_menu_item(
            menu, "Show Badges in Font View", self.toggleBadges_
        )
        badges.setState_(1 if self._badges_enabled() else 0)

    @objc.python_method
    def _add_menu_item(self, menu, title, action):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
        item.setTarget_(self)
        menu.addItem_(item)
        return item

    @objc.python_method
    def _font(self):
        try:
            controller = self.windowController()
            if controller is not None:
                document = controller.document()
                if document is not None:
                    font = getattr(document, "font", None)
                    return font() if callable(font) else font
        except Exception:
            pass
        return Glyphs.font

    @objc.python_method
    def _is_edit_view(self, font):
        controller = None
        try:
            controller = self.windowController()
        except Exception:
            pass
        if controller is None and font is not None:
            try:
                parent = getattr(font, "parent", None)
                if parent is not None:
                    ctrl = getattr(parent, "windowController", None)
                    if callable(ctrl):
                        controller = ctrl()
                    elif ctrl is not None:
                        controller = ctrl
            except Exception:
                pass
        if controller is not None:
            active_edit = getattr(controller, "activeEditViewController", None)
            if callable(active_edit):
                try:
                    return active_edit() is not None
                except Exception:
                    pass
            elif active_edit is not None:
                return True
            return False

        if font is not None:
            try:
                if font.selection:
                    return False
            except Exception:
                pass
            return bool(getattr(font, "currentTab", None))
        return False

    @objc.python_method
    def _selected_glyphs(self, font):
        if font is None:
            return []
        if self._is_edit_view(font):
            layers = getattr(font, "selectedLayers", None) or []
            glyphs = []
            seen = set()
            for layer in layers:
                glyph = getattr(layer, "parent", None)
                if glyph is None:
                    continue
                key = id(glyph)
                if key in seen:
                    continue
                seen.add(key)
                glyphs.append(glyph)
            return glyphs
        return list(getattr(font, "selection", None) or [])

    @objc.python_method
    def _master_ids(self, font):
        if font is None:
            return []
        return [master.id for master in font.masters]

    @objc.python_method
    def _active_master(self, font):
        if font is None:
            return None, "", ""
        master = font.selectedFontMaster
        if master is None and font.masters:
            master = font.masters[0]
        if master is None:
            return None, "", ""
        return master, master.id, master.name or ""

    @objc.python_method
    def _states_for_glyphs(self, glyphs, master_ids):
        return [read_glyph_state(glyph, master_ids) for glyph in glyphs]

    @objc.python_method
    def _write_states(self, font, glyphs, states, master_ids, active_master_id):
        if font is None:
            return
        disable = getattr(font, "disableUpdateInterface", None)
        enable = getattr(font, "enableUpdateInterface", None)
        if callable(disable):
            disable()
        self._updating = True
        try:
            for glyph, state in zip(glyphs, states):
                write_glyph_state(glyph, state, master_ids, active_master_id)
        finally:
            self._updating = False
            if callable(enable):
                enable()
        self._refresh_font_view(font)

    @objc.python_method
    def _refresh_font_view(self, font):
        try:
            Glyphs.redraw()
        except Exception:
            pass
        try:
            controller = self.windowController()
            if controller is None:
                return
            font_view = None
            if hasattr(controller, "fontView"):
                font_view = controller.fontView()
            elif hasattr(controller, "fontViewController"):
                view_controller = controller.fontViewController()
                if view_controller is not None and hasattr(view_controller, "collectionView"):
                    font_view = view_controller.collectionView()
            if font_view is not None:
                font_view.setNeedsDisplay_(True)
        except Exception:
            pass

    @objc.python_method
    def _log_exception(self, message):
        try:
            Glyphs.showMacroWindow()
        except Exception:
            pass
        print("Glyph Note: {}\n{}".format(message, traceback.format_exc()))

    @objc.python_method
    def _badges_enabled(self):
        value = Glyphs.defaults[SHOW_BADGES_DEFAULTS_KEY]
        if value is None:
            return True
        return bool(value)

    @objc.python_method
    def update(self, sender):
        if self._updating:
            return
        font = self._font()
        glyphs = self._selected_glyphs(font)
        master_ids = self._master_ids(font)
        _master, master_id, master_name = self._active_master(font)
        display = selection_display(
            self._states_for_glyphs(glyphs, master_ids),
            master_id,
            master_name,
        )
        self._apply_display(display)

    @objc.python_method
    def _apply_display(self, display):
        self._updating = True
        try:
            if display.mixed_lock:
                self.lock_button.setState_(-1)
            else:
                self.lock_button.setState_(1 if display.locked else 0)
            if display.master_name:
                self.master_label.setStringValue_("Master: {}".format(display.master_name))
            else:
                self.master_label.setStringValue_("Master: —")
            self.placeholder.setStringValue_(display.placeholder)
            editing = False
            window = self.dialog.window()
            if window is not None:
                editing = window.firstResponder() == self.text_view
            if not editing:
                current = self.text_view.string()
                if current != display.text:
                    self.text_view.setString_(display.text)
            show_placeholder = not bool(self.text_view.string()) and not editing
            self._palette.set_placeholder_visible(show_placeholder)
            self._palette.set_enabled(display.has_selection)
        finally:
            self._updating = False

    def toggleLock_(self, sender):
        font = self._font()
        glyphs = self._selected_glyphs(font)
        if not glyphs:
            return
        master_ids = self._master_ids(font)
        _master, master_id, master_name = self._active_master(font)
        current = selection_display(
            self._states_for_glyphs(glyphs, master_ids),
            master_id,
            master_name,
        )
        locked = True if current.mixed_lock else not current.locked
        self._apply_lock(locked)

    def lockSelection_(self, sender):
        self._apply_lock(True)

    def unlockSelection_(self, sender):
        self._apply_lock(False)

    @objc.python_method
    def _apply_lock(self, locked):
        font = self._font()
        glyphs = self._selected_glyphs(font)
        if not glyphs:
            return
        master_ids = self._master_ids(font)
        _master, master_id, _name = self._active_master(font)
        states = apply_lock_to_states(
            self._states_for_glyphs(glyphs, master_ids),
            locked,
            master_ids,
            master_id,
        )
        self._write_states(font, glyphs, states, master_ids, master_id)
        self.update(None)

    def textDidChange_(self, notification):
        if self._updating:
            return
        if notification.object() is not self.text_view:
            return
        self._apply_note(self.text_view.string())
        self._palette.set_placeholder_visible(not bool(self.text_view.string()))

    @objc.python_method
    def _apply_note(self, text):
        font = self._font()
        glyphs = self._selected_glyphs(font)
        if not glyphs:
            return
        master_ids = self._master_ids(font)
        _master, master_id, _name = self._active_master(font)
        states = apply_note_to_states(
            self._states_for_glyphs(glyphs, master_ids),
            text,
            master_id,
            master_ids,
        )
        self._write_states(font, glyphs, states, master_ids, master_id)

    def clearActiveMaster_(self, sender):
        font = self._font()
        glyphs = self._selected_glyphs(font)
        if not glyphs:
            return
        master_ids = self._master_ids(font)
        _master, master_id, _name = self._active_master(font)
        states = [
            clear_active_master_note(state, master_id, master_ids)
            for state in self._states_for_glyphs(glyphs, master_ids)
        ]
        self._write_states(font, glyphs, states, master_ids, master_id)
        self.update(None)

    def clearAllNotes_(self, sender):
        font = self._font()
        glyphs = self._selected_glyphs(font)
        if not glyphs:
            return
        master_ids = self._master_ids(font)
        _master, master_id, _name = self._active_master(font)
        states = [
            clear_all_notes(state, master_ids)
            for state in self._states_for_glyphs(glyphs, master_ids)
        ]
        self._write_states(font, glyphs, states, master_ids, master_id)
        self.update(None)

    def toggleBadges_(self, sender):
        Glyphs.defaults[SHOW_BADGES_DEFAULTS_KEY] = not self._badges_enabled()
        self._refresh_font_view(self._font())
