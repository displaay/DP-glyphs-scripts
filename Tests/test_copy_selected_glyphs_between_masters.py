import importlib.util
import sys
import types
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "Layers" / "Copy Selected Glyphs Between Masters.py"


class DummyControl:
    def __init__(self, *args, **kwargs):
        pass


def load_script_module():
    glyphs_app = types.ModuleType("GlyphsApp")
    glyphs_app.GSLTR = 0
    glyphs_app.Glyphs = types.SimpleNamespace(font=None)

    vanilla = types.ModuleType("vanilla")
    for name in ("Button", "CheckBox", "FloatingWindow", "List", "PopUpButton", "TextBox"):
        setattr(vanilla, name, DummyControl)

    old_glyphs_app = sys.modules.get("GlyphsApp")
    old_vanilla = sys.modules.get("vanilla")
    sys.modules["GlyphsApp"] = glyphs_app
    sys.modules["vanilla"] = vanilla
    try:
        spec = importlib.util.spec_from_file_location("copy_glyphs_between_masters", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_glyphs_app is None:
            del sys.modules["GlyphsApp"]
        else:
            sys.modules["GlyphsApp"] = old_glyphs_app
        if old_vanilla is None:
            del sys.modules["vanilla"]
        else:
            sys.modules["vanilla"] = old_vanilla


class CopyGlyphsBetweenMastersTests(unittest.TestCase):
    def test_target_masters_supports_multiple_targets_and_excludes_source(self):
        module = load_script_module()
        masters = ["Regular", "Medium", "Bold", "Black"]

        result = module.target_masters(masters, 1, [0, 1, 3, 3])

        self.assertEqual(result, ["Regular", "Black"])

    def test_target_masters_can_select_all_other_masters(self):
        module = load_script_module()
        masters = ["Regular", "Medium", "Bold", "Black"]

        result = module.target_masters(masters, 2, [], all_others=True)

        self.assertEqual(result, ["Regular", "Medium", "Black"])

    def test_kerning_scope_uses_correct_glyph_sides(self):
        module = load_script_module()
        glyph = types.SimpleNamespace(
            name="A",
            leftKerningKey="@MMK_R_A",
            rightKerningKey="@MMK_L_A",
        )

        left_keys, right_keys = module.build_kerning_keys_for_glyphs([glyph])

        self.assertEqual(left_keys, {"A", "@MMK_L_A"})
        self.assertEqual(right_keys, {"A", "@MMK_R_A"})

    def test_copy_kerning_preserves_fractional_values_and_normalizes_ids(self):
        module = load_script_module()
        glyph = types.SimpleNamespace(
            name="A",
            leftKerningKey="@MMK_R_A",
            rightKerningKey="@MMK_L_A",
        )

        class Font:
            kerningLTR = {"source": {"A-ID": {"V-ID": -12.5}}}

            def __init__(self):
                self.calls = []

            def setKerningForPair(self, *args):
                self.calls.append(args)

        font = Font()
        count = module.copy_kerning_pairs_for_glyphs(
            font,
            "source",
            "target",
            [glyph],
            {"A-ID": "A", "V-ID": "V"},
        )

        self.assertEqual(count, 1)
        self.assertEqual(font.calls, [("target", "A", "V", -12.5, module.GSLTR)])

    def test_copy_kerning_skips_orphaned_glyph_ids(self):
        module = load_script_module()
        glyph = types.SimpleNamespace(
            name="A",
            leftKerningKey="@MMK_R_A",
            rightKerningKey="@MMK_L_A",
        )

        class Font:
            kerningLTR = {"source": {"@MMK_L_A": {"MISSING-ID": -20}}}

            def __init__(self):
                self.calls = []

            def setKerningForPair(self, *args):
                self.calls.append(args)

        font = Font()
        count = module.copy_kerning_pairs_for_glyphs(
            font,
            "source",
            "target",
            [glyph],
            {"A-ID": "A", "A": "A"},
        )

        self.assertEqual(count, 0)
        self.assertEqual(font.calls, [])

    def test_layer_content_copy_preserves_target_anchors_when_not_requested(self):
        module = load_script_module()

        class Copyable:
            def __init__(self, value):
                self.value = value

            def copy(self):
                return Copyable(self.value)

        class Layer:
            def __init__(self, anchors):
                self.anchors = anchors
                self.copy_calls = []

            def getCopyOfContentFromLayer_doSelection_(self, source, selection):
                self.copy_calls.append((source, selection))
                self.anchors = [Copyable("source")]

        source = Layer([Copyable("source")])
        target = Layer([Copyable("target")])

        module.replace_layer_content(target, source, copy_anchors=False)

        self.assertEqual(target.copy_calls, [(source, False)])
        self.assertEqual([anchor.value for anchor in target.anchors], ["target"])
        self.assertIsNot(target.anchors[0], source.anchors[0])

    def test_ltr_kerning_does_not_require_legacy_kerning_property(self):
        module = load_script_module()
        expected = {"master": {}}
        font = types.SimpleNamespace(kerningLTR=expected)

        self.assertIs(module.get_ltr_kerning_container(font), expected)
