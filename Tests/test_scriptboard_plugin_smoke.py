"""Load Script Board's PyObjC classes without launching Glyphs."""

import importlib.util
import os
import sys
import types
import unittest

from Foundation import NSObject


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(
    ROOT, "Plugins", "ScriptBoard.glyphsPalette", "Contents", "Resources"
)
sys.path.insert(0, RESOURCES)


class Defaults(dict):
    def __getitem__(self, key):
        return self.get(key)


class DummyGlyphs:
    defaults = Defaults()

    @staticmethod
    def localize(value):
        return value.get("en", next(iter(value.values())))

    @staticmethod
    def showMacroWindow():
        pass


class DummyPalettePlugin(NSObject):
    pass


glyphs_module = types.ModuleType("GlyphsApp")
glyphs_module.Glyphs = DummyGlyphs
plugins_module = types.ModuleType("GlyphsApp.plugins")
plugins_module.PalettePlugin = DummyPalettePlugin
sys.modules.setdefault("GlyphsApp", glyphs_module)
sys.modules.setdefault("GlyphsApp.plugins", plugins_module)

spec = importlib.util.spec_from_file_location(
    "scriptboard_plugin_smoke", os.path.join(RESOURCES, "plugin.py")
)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class PluginSmokeTests(unittest.TestCase):
    def test_module_defines_expected_pyobjc_classes(self):
        self.assertEqual(plugin.ScriptBoard.__name__, "ScriptBoard")
        self.assertEqual(
            plugin.ScriptPickerController.__name__, "ScriptPickerController"
        )

    def test_palette_view_has_safe_non_glyphs_fallback(self):
        self.assertTrue(issubclass(plugin._palette_view_class(), NSObject))

    def test_script_title_font_prefers_condensed_system_width(self):
        class CondensedFont:
            @classmethod
            def systemFontOfSize_weight_width_(cls, size, weight, width):
                return ("condensed", size, weight, width)

        original = plugin.NSFont
        plugin.NSFont = CondensedFont
        try:
            font = plugin._script_title_font()
            self.assertEqual(font[0], "condensed")
            self.assertEqual(font[1], 11)
            self.assertEqual(font[3], plugin.NSFontWidthCondensed)
        finally:
            plugin.NSFont = original

    def test_script_title_font_has_regular_system_fallback(self):
        class RegularFont:
            @classmethod
            def systemFontOfSize_(cls, size):
                return ("regular", size)

        original = plugin.NSFont
        plugin.NSFont = RegularFont
        try:
            self.assertEqual(plugin._script_title_font(), ("regular", 11))
        finally:
            plugin.NSFont = original

    def test_palette_height_is_resizable_and_persistent(self):
        class UserDefaultsStore:
            def __init__(self):
                self.values = {}

            def integerForKey_(self, key):
                return self.values.get(key, 0)

            def setInteger_forKey_(self, value, key):
                self.values[key] = value

        class UserDefaults:
            store = UserDefaultsStore()

            @classmethod
            def standardUserDefaults(cls):
                return cls.store

        original = plugin.NSUserDefaults
        plugin.NSUserDefaults = UserDefaults
        try:
            board = plugin.ScriptBoard.alloc().init()
            board.name = "Script Board"
            board.min = plugin.MIN_HEIGHT
            board.max = plugin.MAX_HEIGHT

            self.assertLess(board.min, board.max)
            self.assertEqual(board.currentHeight(), plugin.DEFAULT_HEIGHT)

            board.setCurrentHeight_(360)
            self.assertEqual(board.currentHeight(), 360)

            board.setCurrentHeight_(10_000)
            self.assertEqual(board.currentHeight(), plugin.MAX_HEIGHT)
        finally:
            plugin.NSUserDefaults = original

    def test_palette_footer_stays_on_lower_edge_when_resized(self):
        self.assertTrue(
            plugin.FOOTER_BUTTON_RESIZING_MASK & plugin.NSViewMaxYMargin
        )
        self.assertTrue(
            plugin.FOOTER_LABEL_RESIZING_MASK & plugin.NSViewMaxYMargin
        )
        self.assertFalse(
            plugin.FOOTER_BUTTON_RESIZING_MASK & plugin.NSViewMinYMargin
        )
        self.assertFalse(
            plugin.FOOTER_LABEL_RESIZING_MASK & plugin.NSViewMinYMargin
        )


if __name__ == "__main__":
    unittest.main()
