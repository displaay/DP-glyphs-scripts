"""Load Glyph Note's PyObjC classes without launching Glyphs."""

import importlib.util
import os
import sys
import types
import unittest

try:
    from Foundation import NSObject
except ImportError:
    NSObject = None


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(
    ROOT, "Plugins", "GlyphNote.glyphsPalette", "Contents", "Resources"
)
sys.path.insert(0, RESOURCES)


if NSObject is None:
    class PluginSmokeTests(unittest.TestCase):
        def test_skipped_without_pyobjc(self):
            raise unittest.SkipTest(
                "PyObjC (Foundation) is not available in this Python environment; run inside Glyphs Python."
            )
else:
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

        @staticmethod
        def addCallback(function, hook):
            pass

        @staticmethod
        def removeCallback(function, hook=None):
            pass

        @staticmethod
        def redraw():
            pass

    class DummyPalettePlugin(NSObject):
        pass

    glyphs_module = types.ModuleType("GlyphsApp")
    glyphs_module.Glyphs = DummyGlyphs
    glyphs_module.UPDATEINTERFACE = "UPDATEINTERFACE"
    plugins_module = types.ModuleType("GlyphsApp.plugins")
    plugins_module.PalettePlugin = DummyPalettePlugin
    sys.modules.setdefault("GlyphsApp", glyphs_module)
    sys.modules.setdefault("GlyphsApp.plugins", plugins_module)

    spec = importlib.util.spec_from_file_location(
        "glyphnote_plugin_smoke", os.path.join(RESOURCES, "plugin.py")
    )
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)

    class PluginSmokeTests(unittest.TestCase):
        def test_module_defines_expected_pyobjc_classes(self):
            self.assertEqual(plugin.GlyphNotePalette.__name__, "GlyphNotePalette")
            self.assertEqual(
                plugin.GlyphNoteFontViewDrawer.__name__, "GlyphNoteFontViewDrawer"
            )


if __name__ == "__main__":
    unittest.main()
