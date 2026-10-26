"""Shortcut dispatch tests: layer Copy/Paste must not capture canvas/text edits."""

import importlib.util
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from Tests.test_special_layer_copy import Font, Glyph, Layer, RESOURCES
from speciallayercopy.clipboard import PASTEBOARD_TYPE


COMMAND, SHIFT, CONTROL, OPTION = (1 << n for n in (20, 17, 18, 19))


class Pasteboard:
    def __init__(self):
        self.values = {"public.utf8-plain-text": "Previous clipboard"}

    def declareTypes_owner_(self, types, owner):
        self.values.clear()

    def setString_forType_(self, value, kind):
        self.values[kind] = value
        return True

    def stringForType_(self, kind):
        return self.values.get(kind)


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.font = Font()
        self.glyph = Glyph("a", self.font)
        self.font.glyphs.append(self.glyph)
        self.source = Layer("S1", "M1", {"coordinates": {"weight": 500, "italic": 0}})
        self.glyph.layers["S1"] = self.source
        for master in self.font.masters:
            self.glyph.layers[master.id] = Layer(master.id, master.id, master=True)
        self.rows = {0: [self.source], 1: [self.glyph.layers["M2"]]}
        self.selection = [0]
        self.palette = SimpleNamespace(layersForRow_=lambda row: self.rows[row])
        self.table = SimpleNamespace(
            delegate=lambda: self.palette, dataSource=lambda: None,
            selectedRowIndexes=lambda: self.selection, reloadData=Mock(),
            isKindOfClass_=lambda cls: True,
        )
        self.responder = self.table
        self.board = Pasteboard()
        self.glyphs = SimpleNamespace(font=self.font, versionNumber=4, redraw=Mock())
        self.outline_class = SimpleNamespace(acceptsFirstResponder=SimpleNamespace(signature=b"B@:"))
        self.objc = ModuleType("objc")
        self.objc.python_method = lambda method: method
        self.objc.lookUpClass = Mock(return_value=self.outline_class)
        self.objc.classAddMethods = Mock()
        self.objc.selector = lambda method, **kwargs: (method, kwargs)
        self.objc.nosuchclass_error = type("NoSuchClass", (Exception,), {})
        self.appkit = ModuleType("AppKit")
        self.appkit.NSApplication = SimpleNamespace(sharedApplication=lambda: SimpleNamespace(
            keyWindow=lambda: SimpleNamespace(firstResponder=lambda: self.responder)
        ))
        self.appkit.NSBeep = Mock()
        self.appkit.NSEvent = SimpleNamespace(
            addLocalMonitorForEventsMatchingMask_handler_=Mock(return_value="monitor"),
            removeMonitor_=Mock(),
        )
        self.appkit.NSEventMaskKeyDown = 1 << 10
        self.appkit.NSEventMaskLeftMouseDown = 1 << 1
        self.appkit.NSEventTypeLeftMouseDown = 1
        for name, value in (("Command", COMMAND), ("Shift", SHIFT), ("Control", CONTROL), ("Option", OPTION)):
            setattr(self.appkit, "NSEventModifierFlag" + name, value)
        self.appkit.NSPasteboard = SimpleNamespace(generalPasteboard=lambda: self.board)
        glyphs_module = ModuleType("GlyphsApp")
        glyphs_module.Glyphs, glyphs_module.GSLayer = self.glyphs, Layer
        plugins_module = ModuleType("GlyphsApp.plugins")
        plugins_module.GeneralPlugin = object
        modules = {"objc": self.objc, "AppKit": self.appkit, "GlyphsApp": glyphs_module, "GlyphsApp.plugins": plugins_module}
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        spec = importlib.util.spec_from_file_location("special_layer_copy_shortcut_tests", RESOURCES / "plugin.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.plugin = self.module.DPSpecialLayerCopy()
        self.plugin.settings()

    @staticmethod
    def event(key, modifiers=COMMAND, event_type=10):
        return SimpleNamespace(type=lambda: event_type, modifierFlags=lambda: modifiers,
                               charactersIgnoringModifiers=lambda: key)

    def copy(self):
        self.assertIsNone(self.plugin.handle_event(self.event("c")))

    def test_copy_then_paste_on_master_row_uses_native_clipboard_token(self):
        self.copy()
        self.assertEqual(self.board.values, {PASTEBOARD_TYPE: self.plugin.clipboard.token})
        self.selection = [1]
        self.assertIsNone(self.plugin.handle_event(self.event("v")))
        copies = [layer for layer in self.glyph.layers if layer.associatedMasterId == "M2" and not layer.isMasterLayer]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].attributes["coordinates"], {"weight": 500, "italic": 1})
        self.table.reloadData.assert_called_once()
        self.glyphs.redraw.assert_called_once()

    def test_text_editors_and_canvas_keep_copy_and_paste(self):
        self.copy()
        self.responder = SimpleNamespace(isKindOfClass_=lambda cls: False)
        for key in ("c", "v"):
            event = self.event(key)
            self.assertIs(self.plugin.handle_event(event), event)

    def test_master_layer_copy_keeps_glyphs_behavior_and_clipboard(self):
        self.selection = [1]
        event = self.event("c")
        self.assertIs(self.plugin.handle_event(event), event)
        self.assertEqual(self.board.values["public.utf8-plain-text"], "Previous clipboard")

    def test_changed_system_clipboard_prevents_stale_special_layer_paste(self):
        self.copy()
        self.board.values = {"public.utf8-plain-text": "Something else"}
        event = self.event("v")
        self.assertIs(self.plugin.handle_event(event), event)
        self.assertIsNone(self.plugin.clipboard)

    def test_plain_paste_without_special_layer_clipboard_passes_through(self):
        event = self.event("v")
        self.assertIs(self.plugin.handle_event(event), event)

    def test_modified_shortcuts_and_other_keys_pass_through(self):
        for key, flags in (("c", COMMAND | SHIFT), ("v", COMMAND | OPTION), ("c", CONTROL), ("c", 0), ("x", COMMAND)):
            event = self.event(key, flags)
            self.assertIs(self.plugin.handle_event(event), event)

    def test_copy_ignores_caps_lock_modifier(self):
        self.assertIsNone(self.plugin.handle_event(self.event("C", COMMAND | (1 << 16))))

    def test_other_font_paste_is_consumed_without_mutation_or_window(self):
        self.copy()
        self.glyphs.font = Font()
        with patch("builtins.print"):
            self.assertIsNone(self.plugin.handle_event(self.event("v")))
        self.appkit.NSBeep.assert_called_once()
        self.assertEqual(len(self.glyph.layers.data), 4)

    def test_repeat_paste_does_not_duplicate_layers(self):
        self.copy()
        self.selection = [1]
        self.plugin.handle_event(self.event("v"))
        self.plugin.handle_event(self.event("v"))
        self.assertEqual(len(self.glyph.layers.data), 5)
        self.appkit.NSBeep.assert_called_once()

    def test_palette_row_resolution_handles_multiple_glyphs_and_duplicate_layers(self):
        self.rows[0] = [self.source, self.source, object()]
        self.selection = [0, 0]
        self.assertEqual(self.plugin.selected_palette_layers(self.table), [self.source])

    def test_focus_hook_is_installed_once_and_monitor_is_replaced_on_restart(self):
        self.plugin.start()
        self.plugin.start()
        self.objc.classAddMethods.assert_called_once()
        self.appkit.NSEvent.removeMonitor_.assert_called_once_with("monitor")
        self.assertIsNotNone(self.plugin._event_handler)

    def test_click_installs_focus_support_before_normal_appkit_dispatch(self):
        event = self.event("", event_type=1)
        self.assertIs(self.plugin.handle_event(event), event)
        self.objc.classAddMethods.assert_called_once()

    def test_no_font_or_no_layers_palette_passes_through(self):
        event = self.event("c")
        self.responder = None
        self.assertIs(self.plugin.handle_event(event), event)
        self.responder = self.table
        self.glyphs.font = None
        self.assertIs(self.plugin.handle_event(event), event)


if __name__ == "__main__":
    unittest.main()
