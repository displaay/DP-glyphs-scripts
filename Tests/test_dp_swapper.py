"""Regression tests for DP Swapper without modifying an open Glyphs font."""

import copy
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "Tools" / "DP Swapper.py"


class Control:
    def __init__(self, *args, **kwargs):
        self.value = args[1] if len(args) > 1 else kwargs.get("value")
        self.options = kwargs
        self.selection = []
        self.enabled = True

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def getSelection(self):
        return self.selection

    def enable(self, value):
        self.enabled = value

    def open(self):
        pass


def load_script():
    glyphs_app = types.ModuleType("GlyphsApp")
    glyphs_app.Glyphs = types.SimpleNamespace(font=None, fonts=[])
    glyphs_app.Message = lambda *args: None
    for name, value in (("GSLTR", 0), ("GSRTL", 2), ("GSVertical", 4), ("CORNER", 16), ("CAP", 17)):
        setattr(glyphs_app, name, value)
    vanilla = types.ModuleType("vanilla")
    for name in ("Window", "List", "CheckBox", "Button", "TextBox", "HorizontalLine", "ProgressBar", "PopUpButton"):
        setattr(vanilla, name, Control)
    with patch.dict(sys.modules, {"GlyphsApp": glyphs_app, "vanilla": vanilla}):
        spec = importlib.util.spec_from_file_location("dp_swapper", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class Proxy(list):
    def __getitem__(self, index):
        if isinstance(index, str):
            return next((item for item in self if index in (getattr(item, "name", None), getattr(item, "layerId", None))), None)
        return super().__getitem__(index)


class Shape:
    def __init__(self, label, component=None):
        self.label = label
        self.componentName = component
        self.nodes = [types.SimpleNamespace(label=label)]


class Anchor:
    def __init__(self, label):
        self.label = label

    def copy(self):
        return copy.deepcopy(self)


class Layer:
    def __init__(self, label, master="M1", special=None, width=500):
        self.name = label
        self.layerId = label if special is not None else master
        self.associatedMasterId = master
        self.isMasterLayer = special is None
        self.isSpecialLayer = special is not None
        self.attributes = special or {}
        self.shapes = [Shape(label)]
        self.hints = [types.SimpleNamespace(type=0, originNode=self.shapes[0].nodes[0])]
        self.anchors = [Anchor(label)]
        self.width, self.LSB, self.RSB = width, 50, width - 350
        self.leftMetricsKey = self.rightMetricsKey = self.widthMetricsKey = None
        self.background = None
        self.sync_calls = 0

    @property
    def components(self):
        return [shape for shape in self.shapes if shape.componentName is not None]

    def hasBackground(self):
        return self.background is not None

    def copy(self):
        # Avoid recursively copying the font through layer.parent.
        clone = copy.copy(self)
        clone.shapes, clone.hints, clone.anchors = copy.deepcopy((self.shapes, self.hints, self.anchors))
        return clone

    def getCopyOfContentFromLayer_doSelection_(self, source, selection):
        self.shapes, self.hints, self.anchors = copy.deepcopy((source.shapes, source.hints, source.anchors))

    def setNeedUpdateMetrics(self):
        pass

    def updateMetrics(self):
        pass

    def syncMetrics(self):
        self.sync_calls += 1


class Glyph:
    def __init__(self, name, layers=None):
        self.name, self.id = name, name + "-ID"
        self.layers = Proxy(layers or [Layer(name)])
        for layer in self.layers:
            layer.parent = self
        self.leftKerningGroup = self.rightKerningGroup = None
        self.topKerningGroup = self.bottomKerningGroup = None
        self.leftMetricsKey = self.rightMetricsKey = self.widthMetricsKey = None
        self.productionName = name
        self.storeProductionName = False
        self.unicodes = []
        self.undo_depth = 0

    def beginUndo(self):
        self.undo_depth += 1

    def endUndo(self):
        self.undo_depth -= 1


class Font:
    def __init__(self, glyphs):
        self.glyphs = Proxy(glyphs)
        self.masters = [types.SimpleNamespace(id="M1")]
        self.features = []
        self.kerningLTR = {}
        self.kerningRTL = {}
        self.kerningVertical = {}
        self.interface_disabled = False
        self.fail_once = False
        self.pair_calls = []

    def _kerning(self, direction):
        return {0: self.kerningLTR, 2: self.kerningRTL, 4: self.kerningVertical}[direction]

    def _key(self, name):
        return name if name.startswith("@") else self.glyphs[name].id

    def removeKerningForPair(self, master, left, right, direction):
        self.pair_calls.append(("remove", master, left, right, direction))
        pairs = self._kerning(direction).get(master, {})
        right_values = pairs.get(self._key(left), {})
        right_values.pop(self._key(right), None)
        if not right_values:
            pairs.pop(self._key(left), None)

    def setKerningForPair(self, master, left, right, value, direction):
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("Injected kerning write failure")
        self.pair_calls.append(("set", master, left, right, value, direction))
        self._kerning(direction).setdefault(master, {}).setdefault(self._key(left), {})[self._key(right)] = value

    def disableUpdateInterface(self):
        self.interface_disabled = True

    def enableUpdateInterface(self):
        self.interface_disabled = False


class SwapperTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.source, self.target, self.partner = Glyph("a.ss01"), Glyph("a"), Glyph("V")
        self.font = Font([self.source, self.target, self.partner])

    def swap(self, **options):
        return self.module.execute_swaps(self.font, [(self.source, self.target.name)], **options)

    def test_script_compiles_and_import_does_not_open_a_window(self):
        source = SCRIPT_PATH.read_text()
        self.assertEqual(source.splitlines()[0], "# MenuTitle: DP Swapper")
        compile(source, str(SCRIPT_PATH), "exec")
        self.assertIsNone(self.module.Glyphs.font)

    def test_character_lookup_cannot_substitute_an_encoded_alternate_for_a_missing_base(self):
        class CharacterLookup:
            def __getitem__(inner, key):
                return self.source

        font = types.SimpleNamespace(glyphs=CharacterLookup())
        self.assertIsNone(self.module.glyph_named(font, "a"))
        self.assertIs(self.module.glyph_named(font, "a.ss01"), self.source)

    def test_numeric_metric_keys_keep_subunit_precision(self):
        self.assertEqual(self.module.updated_metric_key(None, 12.123456, {}), "==12.123456")
        self.assertEqual(self.module.updated_metric_key(None, 12.00009, {}), "==12.00009")

    def test_complete_content_copy_preserves_shape_order_and_hint_links(self):
        layer = self.source.layers[0]
        layer.shapes.append(Shape("group"))
        layer.shapes.append(Shape("component", "V"))
        layer.shapes.append(Shape("last path"))
        self.swap(deep_swap=False)
        result = self.target.layers[0]
        self.assertEqual([shape.label for shape in result.shapes], ["a.ss01", "group", "component", "last path"])
        self.assertIs(result.hints[0].originNode, result.shapes[0].nodes[0])
        self.assertIsNot(result.shapes[0], layer.shapes[0])

    def test_shallow_swap_keeps_widths_anchors_keys_and_unicode(self):
        self.source.layers[0].width = 600
        self.target.layers[0].width = 450
        self.target.layers[0].leftMetricsKey = "=V"
        self.target.unicodes = ["0061", "0101"]
        self.swap(deep_swap=False)
        self.assertEqual(self.source.layers[0].width, 600)
        self.assertEqual(self.target.layers[0].width, 450)
        self.assertEqual(self.target.layers[0].anchors[0].label, "a")
        self.assertEqual(self.target.layers[0].leftMetricsKey, "=V")
        self.assertEqual(self.target.unicodes, ["0061", "0101"])
        self.assertEqual(self.target.layers[0].sync_calls, 0)

    def test_deep_swap_captures_both_sides_before_any_synchronization(self):
        self.source.layers[0].width = 600
        self.source.layers[0].leftMetricsKey = "=a+10"
        self.target.layers[0].width = 450
        self.target.layers[0].leftMetricsKey = "=V-5"
        self.swap()
        self.assertEqual(self.target.layers[0].width, 600)
        self.assertEqual(self.source.layers[0].width, 450)
        self.assertEqual(self.target.layers[0].leftMetricsKey, "==a.ss01+10")
        self.assertEqual(self.source.layers[0].leftMetricsKey, "==V-5")
        self.assertEqual(self.target.layers[0].anchors[0].label, "a.ss01")
        self.assertEqual(self.target.layers[0].sync_calls, 1)

    def test_inherited_glyph_keys_and_external_references_follow_the_design(self):
        self.source.leftMetricsKey = "=V"
        self.partner.leftMetricsKey = "=a-10"
        self.partner.layers[0].rightMetricsKey = "==a.ss01"
        self.swap()
        self.assertEqual(self.target.leftMetricsKey, "=V")
        self.assertEqual(self.target.layers[0].leftMetricsKey, "==V")
        self.assertEqual(self.partner.leftMetricsKey, "=a.ss01-10")
        self.assertEqual(self.partner.layers[0].rightMetricsKey, "==a")

    def test_unicode_swap_preserves_all_values_including_unencoded_glyph(self):
        self.target.unicodes = ["0061", "0101"]
        self.swap(swap_unicode=True)
        self.assertEqual(self.source.unicodes, ["0061", "0101"])
        self.assertEqual(self.target.unicodes, [])

    def test_kerning_swaps_cross_pairs_fractional_and_zero_values_in_all_directions(self):
        for attribute in ("kerningLTR", "kerningRTL", "kerningVertical"):
            setattr(self.font, attribute, {"M1": {
                self.source.id: {self.target.id: -12.5, self.partner.id: 0},
                self.target.id: {self.source.id: -30, self.partner.id: -40},
                "@MMK_L_test": {self.source.id: -15},
                self.partner.id: {self.partner.id: -7},
            }})
        self.source.topKerningGroup = "source top"
        self.target.topKerningGroup = "target top"
        self.swap()
        for attribute in ("kerningLTR", "kerningRTL", "kerningVertical"):
            pairs = getattr(self.font, attribute)["M1"]
            self.assertEqual(pairs[self.target.id][self.source.id], -12.5)
            self.assertEqual(pairs[self.target.id][self.partner.id], 0)
            self.assertEqual(pairs[self.source.id][self.target.id], -30)
            self.assertEqual(pairs["@MMK_L_test"][self.target.id], -15)
            self.assertEqual(pairs[self.partner.id][self.partner.id], -7)
        self.assertEqual(self.source.topKerningGroup, "target top")

    def test_batch_remaps_both_glyphs_in_a_pair_once(self):
        other_source, other_target = Glyph("b.ss01"), Glyph("b")
        self.font.glyphs.extend([other_source, other_target])
        self.font.kerningLTR = {"M1": {self.source.id: {other_source.id: -22.5}}}
        self.module.execute_swaps(self.font, [(self.source, "a"), (other_source, "b")])
        self.assertEqual(self.font.kerningLTR, {"M1": {self.target.id: {other_target.id: -22.5}}})

    def test_orphaned_kerning_ids_are_left_untouched(self):
        self.font.kerningLTR = {"M1": {self.source.id: {"MISSING-ID": -5, self.partner.id: -20}}}
        self.swap()
        self.assertEqual(self.font.kerningLTR["M1"][self.source.id]["MISSING-ID"], -5)
        self.assertEqual(self.font.kerningLTR["M1"][self.target.id][self.partner.id], -20)

    def test_components_in_foregrounds_backgrounds_and_corner_hints_retarget_once(self):
        layer = self.partner.layers[0]
        layer.shapes = [Shape("component", "a"), Shape("component", "a.ss01")]
        layer.background = Layer("backup")
        layer.background.isMasterLayer = False
        layer.background.shapes = [Shape("background", "a")]
        layer.hints = [types.SimpleNamespace(type=self.module.CORNER, name="a.ss01")]
        count, references = self.swap(deep_swap=False)
        self.assertEqual((count, references), (1, 4))
        self.assertEqual([shape.componentName for shape in layer.shapes], ["a.ss01", "a"])
        self.assertEqual(layer.background.shapes[0].componentName, "a.ss01")
        self.assertEqual(layer.hints[0].name, "a")
        self.assertIsNone(self.source.layers[0].background)

    def test_production_storage_flag_moves_with_custom_name(self):
        self.source.storeProductionName = True
        self.source.productionName = "a.custom"
        self.swap()
        self.assertTrue(self.target.storeProductionName)
        self.assertEqual(self.target.productionName, "a.custom")
        self.assertFalse(self.source.storeProductionName)

    def test_special_layers_match_attributes_rather_than_labels_or_ids(self):
        self.source.layers.append(Layer("source intermediate", special={"coordinates": {"wght": 500}}))
        self.target.layers.append(Layer("target intermediate", special={"coordinates": {"wght": 500}}))
        self.swap()
        self.assertEqual(self.target.layers[1].shapes[0].label, "source intermediate")
        self.assertEqual(self.target.layers[1].name, "target intermediate")
        self.assertEqual(self.target.layers[1].layerId, "target intermediate")

    def test_special_layer_mismatch_rejects_entire_batch_before_changes(self):
        self.target.layers.append(Layer("intermediate", special={"coordinates": {"wght": 500}}))
        with self.assertRaisesRegex(ValueError, "layers do not match"):
            self.swap()
        self.assertEqual(self.target.layers[0].shapes[0].label, "a")
        self.assertFalse(self.font.interface_disabled)

    def test_ambiguous_special_layers_are_rejected(self):
        for name in ("one", "two"):
            self.source.layers.append(Layer(name, special={"axisRules": {"wght": {"min": 500}}}))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            self.swap()

    def test_overlapping_pairs_and_same_glyph_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "more than one"):
            self.module.execute_swaps(self.font, [(self.source, "a"), (self.target, "V")])
        with self.assertRaisesRegex(ValueError, "same glyph"):
            self.module.execute_swaps(self.font, [(self.source, self.source.name)])

    def test_failure_restores_layers_references_metadata_unicode_and_kerning(self):
        self.font.kerningLTR = {"M1": {self.source.id: {self.partner.id: -22.5}}}
        self.source.layers[0].leftMetricsKey = "=V"
        self.source.unicodes = ["0061", "0101"]
        self.source.productionName = "a.custom"
        self.source.storeProductionName = True
        self.partner.layers[0].shapes = [Shape("dependent", "a")]
        before = copy.deepcopy(self.font.kerningLTR)
        self.font.fail_once = True
        with self.assertRaisesRegex(RuntimeError, "original data restored"):
            self.swap(swap_unicode=True)
        self.assertEqual(self.font.kerningLTR, before)
        self.assertEqual(self.source.layers[0].shapes[0].label, "a.ss01")
        self.assertEqual(self.target.layers[0].shapes[0].label, "a")
        self.assertEqual(self.partner.layers[0].shapes[0].componentName, "a")
        self.assertEqual(self.source.layers[0].leftMetricsKey, "=V")
        self.assertEqual(self.source.unicodes, ["0061", "0101"])
        self.assertEqual(self.source.productionName, "a.custom")
        self.assertTrue(self.source.storeProductionName)
        self.assertFalse(self.font.interface_disabled)
        self.assertTrue(all(glyph.undo_depth == 0 for glyph in self.font.glyphs))

    def test_name_replacement_is_simultaneous_and_respects_suffixes_and_offsets(self):
        names = {"a": "a.ss01", "a.ss01": "a", "A-cy": "A-cy.ss01", "A-cy.ss01": "A-cy"}
        self.assertEqual(self.module.text_with_swapped_names("=a-10+a.ss01", names), "=a.ss01-10+a")
        self.assertEqual(self.module.text_with_swapped_names("=a.ss010", names), "=a.ss010")
        self.assertEqual(self.module.text_with_swapped_names("=A-cy-10", names), "=A-cy.ss01-10")
        self.assertEqual(self.module.text_with_swapped_names("=a-cy", names), "=a-cy")

    def test_source_list_cannot_sort_suffix_indices_out_of_sync(self):
        self.module.Glyphs.font = self.font
        dialog = self.module.DPSwapperDialog()
        self.assertFalse(dialog.w.sourceList.options["allowsSorting"])
        self.assertFalse(dialog.w.glyphList.options["allowsSorting"])


if __name__ == "__main__":
    unittest.main()
