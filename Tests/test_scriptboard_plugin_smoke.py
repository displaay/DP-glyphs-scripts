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


if __name__ == "__main__":
    unittest.main()
