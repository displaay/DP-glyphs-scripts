"""Decision-rule tests for the Glyphs-only derivative setup script."""

import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "Spacing" / "Space basics.py"
SPEC = importlib.util.spec_from_file_location("derivative_groups", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Master:
    id = "m1"


class Component:
    def __init__(self, name, aligned=False, transform=None):
        self.componentName = name
        self.automaticAlignment = aligned
        self.transform = transform


class Layer:
    def __init__(self, paths=1, components=None):
        self.paths = [object()] * paths
        self.components = components or []
        self.leftMetricsKey = None
        self.rightMetricsKey = None
        self.widthMetricsKey = None
        self.LSB = 40
        self.RSB = 40
        self.width = 600
        self.isMasterLayer = True
        self.isSpecialLayer = False

    def syncMetrics(self):
        pass

    @property
    def bounds(self):
        return types.SimpleNamespace(
            origin=types.SimpleNamespace(y=0),
            size=types.SimpleNamespace(height=500),
        )

    def intersectionsBetweenPoints(self, start, end, components):
        return [start, types.SimpleNamespace(x=100), types.SimpleNamespace(x=300), end]


class Layers(dict):
    def __iter__(self):
        return iter(self.values())


class Glyph:
    def __init__(self, name, layer=None, category="Letter", script="latin"):
        self.name = name
        self.category = category
        self.script = script
        self.export = True
        self.layers = Layers({"m1": layer or Layer()})
        self.leftMetricsKey = None
        self.rightMetricsKey = None
        self.widthMetricsKey = None
        self.leftKerningGroup = None
        self.rightKerningGroup = None

    def beginUndo(self):
        pass

    def endUndo(self):
        pass


class Font:
    def __init__(self, *glyphs):
        self.glyphs = list(glyphs)
        self.masters = [Master()]
        self.selectedLayers = []
        self.updates_disabled = False

    def disableUpdateInterface(self):
        self.updates_disabled = True

    def enableUpdateInterface(self):
        self.updates_disabled = False


class InfoItem:
    def __init__(self, name, category="Letter"):
        self.name = name
        self.category = category


class Info:
    def __init__(self, *components):
        self.components = list(components)


def by_id(proposals):
    return {proposal["id"]: proposal for proposal in proposals}


class DerivativeRulesTests(unittest.TestCase):
    def test_glyphs_empty_smart_values_proxy_does_not_crash_preview(self):
        class GlyphsProxy:
            def values(self):
                return None

            def __len__(self):
                return len(self.values())  # The behavior reported by Glyphs 4.

        a = Glyph("A")
        accent = Glyph("Aacute", Layer(paths=0, components=[Component("A")]))
        accent.layers["m1"].components[0].smartComponentValues = GlyphsProxy()
        proposals, _ = module.build_proposals(Font(a, accent), {})
        self.assertEqual(by_id(proposals)[("Aacute", "leftKerningGroup")]["after"], "A")

    def test_populated_smart_component_is_not_assumed_to_preserve_side_shape(self):
        class GlyphsProxy:
            def values(self):
                return [42]

        component = Component("A")
        component.smartComponentValues = GlyphsProxy()
        self.assertFalse(module.component_preserves_side_shape(component))

    def test_every_behavior_option_has_a_ui_control(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        ui_keys = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"popup", "check"} and node.args
            and isinstance(node.args[0], ast.Constant)
        }
        self.assertEqual(ui_keys, set(module.DEFAULT_OPTIONS))

    def test_auto_aligned_accent_gets_groups_but_no_metrics_keys(self):
        base = Glyph("A")
        accent = Glyph("Aacute", Layer(paths=0, components=[Component("A", True), Component("acutecomb", True)]))
        mark = Glyph("acutecomb", category="Mark")
        proposals, notes = module.build_proposals(Font(base, accent, mark), {}, None)
        planned = by_id(proposals)
        self.assertEqual(planned[("Aacute", "leftKerningGroup")]["after"], "A")
        self.assertEqual(planned[("Aacute", "rightKerningGroup")]["after"], "A")
        self.assertNotIn(("Aacute", "leftMetricsKey"), planned)
        self.assertTrue(any("Auto-aligned" in message for _, message in notes))

    def test_asymmetric_ligature_uses_outer_sides_only(self):
        a, e = Glyph("a"), Glyph("e")
        ae = Glyph("ae", Layer(paths=0, components=[Component("a"), Component("e")]))
        proposals, _ = module.build_proposals(Font(a, e, ae), {}, None)
        planned = by_id(proposals)
        self.assertEqual(planned[("ae", "leftMetricsKey")]["after"], "=a")
        self.assertEqual(planned[("ae", "rightMetricsKey")]["after"], "=e")
        self.assertEqual(planned[("ae", "leftKerningGroup")]["after"], "a")
        self.assertEqual(planned[("ae", "rightKerningGroup")]["after"], "e")
        self.assertNotIn(("ae", "widthMetricsKey"), planned)

    def test_database_recipe_and_chained_derivative(self):
        a, aring, aringacute = Glyph("A"), Glyph("Aring"), Glyph("Aringacute")
        recipe = {
            "Aring": Info(InfoItem("A"), InfoItem("ringcomb", "Mark")),
            "Aringacute": Info(InfoItem("Aring"), InfoItem("acutecomb", "Mark")),
        }
        options = {"confidence": "Medium"}
        proposals, _ = module.build_proposals(Font(a, aring, aringacute), options, recipe.get)
        planned = by_id(proposals)
        self.assertEqual(planned[("Aringacute", "leftKerningGroup")]["after"], "A")
        self.assertEqual(planned[("Aringacute", "leftMetricsKey")]["after"], "=Aring")

    def test_preview_is_read_only_and_apply_is_idempotent(self):
        a = Glyph("A")
        accent = Glyph("Aacute", Layer(paths=0, components=[Component("A")]))
        font = Font(a, accent)
        proposals, _ = module.build_proposals(font, {})
        self.assertIsNone(a.leftKerningGroup)
        self.assertIsNone(accent.leftMetricsKey)
        module.apply_proposals(font, proposals, module.normalized_options({}))
        self.assertEqual(a.leftKerningGroup, "A")
        self.assertEqual(accent.leftMetricsKey, "=A")
        self.assertFalse(font.updates_disabled)
        again, _ = module.build_proposals(font, {})
        self.assertEqual(again, [])

    def test_preserves_existing_and_detects_metric_cycles(self):
        a = Glyph("A")
        accent = Glyph("Aacute", Layer(paths=0, components=[Component("A")]))
        accent.leftKerningGroup = "custom"
        a.leftMetricsKey = "=Aacute"
        proposals, notes = module.build_proposals(Font(a, accent), {})
        planned = by_id(proposals)
        self.assertFalse(planned[("Aacute", "leftKerningGroup")]["include"])
        self.assertNotIn(("Aacute", "leftMetricsKey"), planned)
        self.assertTrue(any("cycle" in message for _, message in notes))

    def test_empty_and_tabular_are_excluded_by_default(self):
        zero = Glyph("zero", category="Number")
        tabular = Glyph("zero.tf", category="Number")
        empty = Glyph("A", Layer(paths=0))
        proposals, notes = module.build_proposals(Font(zero, tabular, empty), {})
        self.assertEqual(proposals, [])
        self.assertEqual(len(notes), 3)

    def test_user_can_enable_empty_database_derivatives(self):
        a = Glyph("A", Layer(paths=0))
        accent = Glyph("Aacute", Layer(paths=0))
        recipe = {"Aacute": Info(InfoItem("A"), InfoItem("acutecomb", "Mark"))}
        options = {"include_empty": True, "confidence": "Medium", "metric_width": True}
        proposals, _ = module.build_proposals(Font(a, accent), options, recipe.get)
        planned = by_id(proposals)
        self.assertEqual(planned[("Aacute", "leftMetricsKey")]["after"], "=A")
        self.assertEqual(planned[("Aacute", "widthMetricsKey")]["after"], "=A")

    def test_contour_supported_family_group_is_side_specific(self):
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            font = Font(Glyph("n"), Glyph("h"))
            proposals, _ = module.build_proposals(font, {"confidence": "Medium"})
        planned = by_id(proposals)
        self.assertEqual(planned[("h", "leftKerningGroup")]["after"], "n")
        self.assertEqual(planned[("h", "rightKerningGroup")]["after"], "n")
        self.assertEqual(planned[("n", "leftKerningGroup")]["after"], "n")

    def test_g_left_links_to_o_when_contours_match(self):
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(Font(Glyph("O"), Glyph("G")), {})
        planned = by_id(proposals)
        self.assertEqual(planned[("G", "leftMetricsKey")]["after"], "=O")
        self.assertEqual(planned[("G", "leftMetricsKey")]["confidence"], "High")
        self.assertTrue(planned[("G", "leftMetricsKey")]["include"])
        self.assertNotIn(("G", "rightMetricsKey"), planned)

    def test_g_left_kerning_group_can_share_o_without_changing_right_group(self):
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(Glyph("O"), Glyph("G")), {"confidence": "Medium"})
        planned = by_id(proposals)
        self.assertEqual(planned[("G", "leftKerningGroup")]["after"], "O")
        self.assertEqual(planned[("G", "rightKerningGroup")]["after"], "G")

    def test_g_left_metric_link_is_review_only_without_contour_evidence(self):
        with patch.dict(sys.modules, {"Foundation": None}):
            proposals, _ = module.build_proposals(Font(Glyph("O"), Glyph("G")), {})
        link = by_id(proposals)[("G", "leftMetricsKey")]
        self.assertEqual(link["confidence"], "Medium")
        self.assertFalse(link["include"])

    def test_geometry_api_failure_leaves_g_link_available_for_review(self):
        class BrokenLayer(Layer):
            def intersectionsBetweenPoints(self, start, end, components):
                raise TypeError("unsupported geometry")

        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(Glyph("O"), Glyph("G", BrokenLayer())), {})
        link = by_id(proposals)[("G", "leftMetricsKey")]
        self.assertEqual(link["confidence"], "Medium")
        self.assertFalse(link["include"])

    def test_different_g_left_contour_is_not_selected(self):
        class DifferentLayer(Layer):
            def intersectionsBetweenPoints(self, start, end, components):
                return [start, types.SimpleNamespace(x=100 + end.y * .15),
                        types.SimpleNamespace(x=300), end]

        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, notes = module.build_proposals(
                Font(Glyph("O"), Glyph("G", DifferentLayer())), {})
        link = by_id(proposals)[("G", "leftMetricsKey")]
        self.assertFalse(link["include"])
        self.assertIn("contour differs", link["warning"])
        self.assertTrue(any("G" == name and "contour differs" in note for name, note in notes))

    def test_metric_cycle_detection_stays_on_referenced_side(self):
        o, g = Glyph("O"), Glyph("G")
        o.rightMetricsKey = "=G"
        glyphs = module.exact_glyph_map(Font(o, g))
        self.assertFalse(module.creates_cycle("G", "O", "leftMetricsKey", glyphs, {}))
        o.leftMetricsKey = "=G"
        self.assertTrue(module.creates_cycle("G", "O", "leftMetricsKey", glyphs, {}))

    def test_checked_conflict_cannot_bypass_fill_empty_policy(self):
        a = Glyph("A")
        accent = Glyph("Aacute", Layer(paths=0, components=[Component("A")]))
        accent.leftKerningGroup = "custom"
        font = Font(a, accent)
        proposals, _ = module.build_proposals(font, {})
        conflict = by_id(proposals)[("Aacute", "leftKerningGroup")]
        conflict["include"] = True
        with self.assertRaisesRegex(ValueError, "Allow overwrite"):
            module.apply_proposals(font, proposals, module.normalized_options({}))
        self.assertEqual(accent.leftKerningGroup, "custom")

    def test_flipped_component_is_not_treated_as_same_side_shape(self):
        six = Glyph("six", category="Number")
        nine = Glyph("nine", Layer(paths=0, components=[Component(
            "six", transform=(-1, 0, 0, 1, 0, 0))]), category="Number")
        proposals, _ = module.build_proposals(
            Font(six, nine), {"include_figures": True})
        self.assertNotIn(("nine", "leftMetricsKey"), by_id(proposals))

    def test_empty_source_is_skipped_unless_placeholder_mode_is_enabled(self):
        base = Glyph("A", Layer(paths=0))
        accent = Glyph("Aacute", Layer(paths=0, components=[Component("A")]))
        font = Font(base, accent)
        proposals, notes = module.build_proposals(font, {})
        self.assertNotIn(("Aacute", "leftMetricsKey"), by_id(proposals))
        self.assertTrue(any("source A is empty" in message for _, message in notes))
        proposals, _ = module.build_proposals(font, {"include_empty": True})
        self.assertIn(("Aacute", "leftMetricsKey"), by_id(proposals))

    def test_sync_failure_restores_keys_and_interface(self):
        class FailingLayer(Layer):
            def syncMetrics(self):
                self.LSB = 100
                raise RuntimeError("sync failed")

        a = Glyph("A")
        accent = Glyph("Aacute", FailingLayer(paths=0, components=[Component("A")]))
        font = Font(a, accent)
        options = module.normalized_options({"sync_metrics": True})
        proposals, _ = module.build_proposals(font, options)
        with self.assertRaisesRegex(RuntimeError, "sync failed"):
            module.apply_proposals(font, proposals, options)
        self.assertIsNone(accent.leftMetricsKey)
        self.assertIsNone(a.leftKerningGroup)
        self.assertEqual(accent.layers["m1"].LSB, 40)
        self.assertFalse(font.updates_disabled)


if __name__ == "__main__":
    unittest.main()
