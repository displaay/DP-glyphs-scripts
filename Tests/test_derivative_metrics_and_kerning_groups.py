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


class ProfileLayer(Layer):
    def __init__(self, left, right, height=500):
        super().__init__()
        self.left_edge = left
        self.right_edge = right
        self.height = height

    @property
    def bounds(self):
        return types.SimpleNamespace(
            origin=types.SimpleNamespace(y=0),
            size=types.SimpleNamespace(height=self.height),
        )

    def intersectionsBetweenPoints(self, start, end, components):
        return [start, types.SimpleNamespace(x=self.left_edge(end.y)),
                types.SimpleNamespace(x=self.right_edge(end.y)), end]


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
    def test_font_specific_checks_are_off_by_default(self):
        self.assertFalse(module.DEFAULT_OPTIONS["font_specific_checks"])

    def test_single_storey_a_uses_o_on_both_matching_sides(self):
        round_left = lambda y: 100 + 40 * ((y - 250) / 250) ** 2
        round_right = lambda y: 300 - 40 * ((y - 250) / 250) ** 2
        flat_left = lambda y: 100
        flat_right = lambda y: 300
        font = Font(Glyph("n", ProfileLayer(flat_left, flat_right)),
                    Glyph("o", ProfileLayer(round_left, round_right)),
                    Glyph("a", ProfileLayer(round_left, round_right)))
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            ordinary, _ = module.build_proposals(font, {})
            smart, _ = module.build_proposals(font, {"font_specific_checks": True})
        self.assertNotIn(("a", "leftMetricsKey"), by_id(ordinary))
        self.assertEqual(by_id(smart)[("a", "leftMetricsKey")]["after"], "=o")
        self.assertEqual(by_id(smart)[("a", "rightMetricsKey")]["after"], "=o")
        self.assertTrue(by_id(smart)[("a", "rightMetricsKey")]["include"])

    def test_font_specific_checks_scan_unselected_glyphs_and_new_shape_matches(self):
        round_edge = lambda y: 100 + 40 * ((y - 250) / 250) ** 2
        n = Glyph("n", ProfileLayer(lambda y: 100, lambda y: 300))
        o = Glyph("o", ProfileLayer(round_edge, lambda y: 300))
        z = Glyph("z", ProfileLayer(round_edge, lambda y: 300))
        font = Font(n, o, z)
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(font, {
                "scope": "Selected glyphs", "font_specific_checks": True})
        self.assertEqual(by_id(proposals)[("z", "leftMetricsKey")]["after"], "=o")
        self.assertNotIn(("z", "leftKerningGroup"), by_id(proposals))

    def test_descender_or_ascender_outward_shape_blocks_false_link(self):
        n = Glyph("n", ProfileLayer(lambda y: 100, lambda y: 300))
        f = Glyph("f", ProfileLayer(lambda y: 50 if y > 500 else 100,
                                    lambda y: 300, height=700))
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(n, f), {"font_specific_checks": True})
        self.assertNotIn(("f", "leftMetricsKey"), by_id(proposals))

    def test_conventional_link_changes_when_other_reference_fits(self):
        flat = lambda y: 100
        rounded = lambda y: 100 + 40 * ((y - 250) / 250) ** 2
        h = Glyph("H", ProfileLayer(flat, lambda y: 300))
        o = Glyph("O", ProfileLayer(rounded, lambda y: 300))
        m = Glyph("M", ProfileLayer(rounded, lambda y: 300))
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(h, o, m), {"font_specific_checks": True})
        self.assertEqual(by_id(proposals)[("M", "leftMetricsKey")]["after"], "=O")

    def test_unusual_g_right_side_can_match_o(self):
        flat = lambda y: 100
        rounded = lambda y: 300 - 40 * ((y - 250) / 250) ** 2
        n = Glyph("n", ProfileLayer(flat, lambda y: 300))
        o = Glyph("o", ProfileLayer(flat, rounded))
        g = Glyph("g", ProfileLayer(flat, rounded))
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(n, o, g), {"font_specific_checks": True})
        self.assertEqual(by_id(proposals)[("g", "rightMetricsKey")]["after"], "=o")

    def test_single_storey_alternate_can_link_to_o_instead_of_a(self):
        flat = lambda y: 100
        round_left = lambda y: 100 + 40 * ((y - 250) / 250) ** 2
        round_right = lambda y: 300 - 40 * ((y - 250) / 250) ** 2
        n = Glyph("n", ProfileLayer(flat, lambda y: 300))
        o = Glyph("o", ProfileLayer(round_left, round_right))
        a = Glyph("a", ProfileLayer(flat, lambda y: 300))
        alternate = Glyph("a.ss01", ProfileLayer(round_left, round_right))
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(n, o, a, alternate), {"font_specific_checks": True,
                                           "include_alternates": True})
        self.assertEqual(by_id(proposals)[("a.ss01", "leftMetricsKey")]["after"], "=o")
        self.assertEqual(by_id(proposals)[("a.ss01", "rightMetricsKey")]["after"], "=o")

    def test_missing_anchor_outline_does_not_invalidate_existing_key(self):
        h = Glyph("H", Layer(paths=0))
        o = Glyph("O", ProfileLayer(lambda y: 100 + y * .2,
                                     lambda y: 300 - y * .2))
        m = Glyph("M", ProfileLayer(lambda y: 100, lambda y: 300))
        m.leftMetricsKey = "=H"
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(h, o, m), {"font_specific_checks": True,
                                "existing": "Allow overwrite"})
        self.assertNotIn(("M", "leftMetricsKey"), by_id(proposals))

    def test_local_metrics_exception_is_preserved(self):
        h = Glyph("H", ProfileLayer(lambda y: 100, lambda y: 300))
        m = Glyph("M", ProfileLayer(lambda y: 100 + y * .2,
                                     lambda y: 300))
        m.leftMetricsKey = "==H"
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(
                Font(h, m), {"font_specific_checks": True,
                             "existing": "Allow overwrite"})
        self.assertNotIn(("M", "leftMetricsKey"), by_id(proposals))

    def test_slanted_m_clears_wrong_h_link_for_review(self):
        flat_left = lambda y: 100
        flat_right = lambda y: 300
        slant_left = lambda y: 100 + y * .25
        slant_right = lambda y: 300 - y * .25
        h = Glyph("H", ProfileLayer(flat_left, flat_right))
        m = Glyph("M", ProfileLayer(slant_left, slant_right))
        m.leftMetricsKey = "=H"
        font = Font(h, m)
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        options = {"font_specific_checks": True, "existing": "Allow overwrite"}
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(font, options)
        planned = by_id(proposals)
        clear = planned[("M", "leftMetricsKey")]
        self.assertIsNone(clear["after"])
        self.assertFalse(clear["include"])
        self.assertNotIn(("M", "rightMetricsKey"), planned)
        for item in proposals:
            item["include"] = item is clear
        module.apply_proposals(font, proposals, module.normalized_options(options))
        self.assertIsNone(m.leftMetricsKey)

    def test_different_outline_derivative_loses_incorrect_source_link(self):
        base = Glyph("A", ProfileLayer(lambda y: 100, lambda y: 300))
        derivative = Glyph("Aacute", ProfileLayer(lambda y: 100 + y * .2,
                                                   lambda y: 300))
        recipe = {"Aacute": Info(InfoItem("A"), InfoItem("acutecomb", "Mark"))}
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, notes = module.build_proposals(
                Font(base, derivative), {"font_specific_checks": True,
                                         "confidence": "Medium"}, recipe.get)
        planned = by_id(proposals)
        self.assertNotIn(("Aacute", "leftMetricsKey"), planned)
        self.assertEqual(planned[("Aacute", "rightMetricsKey")]["after"], "=A")
        self.assertTrue(any(name == "Aacute" and "differs from derivative" in note
                            for name, note in notes))

    def test_font_specific_checks_require_every_master_to_match(self):
        round_left = lambda y: 100 + 40 * ((y - 250) / 250) ** 2
        round_right = lambda y: 300 - 40 * ((y - 250) / 250) ** 2
        flat_left = lambda y: 100
        flat_right = lambda y: 300
        n = Glyph("n", ProfileLayer(flat_left, flat_right))
        o = Glyph("o", ProfileLayer(round_left, round_right))
        a = Glyph("a", ProfileLayer(round_left, round_right))
        font = Font(n, o, a)
        font.masters.append(types.SimpleNamespace(id="m2"))
        n.layers["m2"] = ProfileLayer(flat_left, flat_right)
        o.layers["m2"] = ProfileLayer(round_left, round_right)
        a.layers["m2"] = ProfileLayer(flat_left, flat_right)
        foundation = types.SimpleNamespace(
            NSMakePoint=lambda x, y: types.SimpleNamespace(x=x, y=y))
        with patch.dict(sys.modules, {"Foundation": foundation}):
            proposals, _ = module.build_proposals(font, {"font_specific_checks": True})
        self.assertNotIn(("a", "leftMetricsKey"), by_id(proposals))
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
        self.assertEqual(set(module.OPTION_HELP), set(module.DEFAULT_OPTIONS))
        self.assertTrue(all(module.OPTION_HELP.values()))

    def test_tabbed_ui_opens_with_tooltips_on_every_option(self):
        class Control:
            def __init__(self, *args, **kwargs):
                self.tooltip = None
                self.value = kwargs.get("value")

            def setToolTip(self, message):
                self.tooltip = message

            def set(self, value):
                self.value = value

            def get(self):
                return self.value

            def enable(self, value):
                pass

            def setImage(self, **kwargs):
                pass

            def open(self):
                pass

        class Tabs(Control):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.pages = [Control() for _ in args[1]]

            def __getitem__(self, index):
                return self.pages[index]

        class Image:
            @classmethod
            def alloc(cls):
                return cls()

            def initWithSize_(self, size):
                return self

            def lockFocus(self):
                pass

            def unlockFocus(self):
                pass

        class Path:
            @classmethod
            def bezierPath(cls):
                return cls()

            def moveToPoint_(self, point):
                pass

            def lineToPoint_(self, point):
                pass

            def closePath(self):
                pass

            def fill(self):
                pass

        class Color:
            @classmethod
            def colorWithCalibratedHue_saturation_brightness_alpha_(cls, *args):
                return cls()

            def set(self):
                pass

        vanilla = types.SimpleNamespace(**{name: Control for name in (
            "Window", "TextBox", "PopUpButton", "CheckBox", "ImageView", "Button",
            "HorizontalLine", "List", "CheckBoxListCell")})
        vanilla.Tabs = Tabs
        appkit = types.SimpleNamespace(NSBezierPath=Path, NSColor=Color, NSImage=Image)
        foundation = types.SimpleNamespace(NSMakePoint=lambda x, y: (x, y),
                                           NSMakeSize=lambda w, h: (w, h))
        glyphs = types.SimpleNamespace(font=Font(Glyph("n")), defaults={})
        glyphs_app = types.SimpleNamespace(Glyphs=glyphs, Message=lambda *args, **kwargs: None)
        with patch.dict(sys.modules, {"vanilla": vanilla, "AppKit": appkit,
                                      "Foundation": foundation, "GlyphsApp": glyphs_app}):
            module.launch()
        manager = module.DERIVATIVE_MANAGER_WINDOW
        self.assertEqual(len(manager.w.settingsTabs.pages), 3)
        self.assertEqual(set(manager.controls), set(module.DEFAULT_OPTIONS))
        for key, entry in manager.controls.items():
            control = entry[0] if isinstance(entry, tuple) else entry
            self.assertEqual(control.tooltip, module.OPTION_HELP[key])
        self.assertEqual(manager.w.settingsTabs[0].smartIcon.tooltip,
                         module.OPTION_HELP["font_specific_checks"])

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

    def test_dotless_i_and_j_remain_bases_for_dotted_auto_composites(self):
        for base_name, dotted_name in (("idotless", "i"), ("jdotless", "j")):
            with self.subTest(base=base_name):
                base = Glyph(base_name)
                dotted = Glyph(dotted_name, Layer(paths=0, components=[
                    Component(base_name, True), Component("dotaccentcomb", True)]))
                recipe = {base_name: Info(InfoItem(dotted_name))}
                proposals, notes = module.build_proposals(
                    Font(base, dotted), {"confidence": "Medium", "metric_width": True}, recipe.get)
                planned = by_id(proposals)
                self.assertEqual(planned[(base_name, "leftKerningGroup")]["after"], base_name)
                self.assertEqual(planned[(dotted_name, "leftKerningGroup")]["after"], base_name)
                self.assertNotIn((base_name, "leftMetricsKey"), planned)
                self.assertNotIn((base_name, "rightMetricsKey"), planned)
                self.assertNotIn((base_name, "widthMetricsKey"), planned)
                self.assertTrue(any(name == base_name and "independent base" in note
                                    for name, note in notes))

    def test_reverse_component_dependency_is_rejected_transitively(self):
        root = Glyph("root")
        middle = Glyph("middle", Layer(paths=0, components=[Component("root", True)]))
        decorated = Glyph("decorated", Layer(paths=0, components=[Component("middle", True)]))
        recipe = {"root": Info(InfoItem("decorated"))}
        proposals, notes = module.build_proposals(
            Font(root, middle, decorated), {"confidence": "Medium"}, recipe.get)
        planned = by_id(proposals)
        self.assertNotIn(("root", "leftMetricsKey"), planned)
        self.assertEqual(planned[("root", "leftKerningGroup")]["after"], "root")
        self.assertEqual(planned[("decorated", "leftKerningGroup")]["after"], "root")
        self.assertTrue(any(name == "root" and "source uses this glyph" in note
                            for name, note in notes))

    def test_auto_aligned_source_is_not_used_for_metrics_keys(self):
        base = Glyph("roundBase")
        source = Glyph("O", Layer(paths=0, components=[Component("roundBase", True)]))
        target = Glyph("G")
        composite = Glyph("C", Layer(paths=0, components=[Component("O")]))
        proposals, notes = module.build_proposals(
            Font(base, source, target, composite), {"metric_width": True})
        planned = by_id(proposals)
        self.assertNotIn(("G", "leftMetricsKey"), planned)
        self.assertNotIn(("C", "leftMetricsKey"), planned)
        self.assertNotIn(("C", "widthMetricsKey"), planned)
        self.assertEqual(planned[("C", "leftKerningGroup")]["after"], "roundBase")
        self.assertTrue(any(name == "G" and "auto-aligned" in note for name, note in notes))

    def test_layer_alignment_state_also_protects_metrics_sources(self):
        source = Glyph("O")
        source.layers["m1"].hasAlignedSideBearings = lambda: True
        proposals, _ = module.build_proposals(Font(source, Glyph("G")), {})
        self.assertNotIn(("G", "leftMetricsKey"), by_id(proposals))

    def test_auto_alignment_in_one_master_blocks_font_wide_metrics_link(self):
        base, source, target = Glyph("roundBase"), Glyph("O"), Glyph("G")
        font = Font(base, source, target)
        font.masters.append(types.SimpleNamespace(id="m2"))
        base.layers["m2"] = Layer()
        source.layers["m2"] = Layer(paths=0, components=[Component("roundBase", True)])
        target.layers["m2"] = Layer()
        proposals, _ = module.build_proposals(font, {})
        self.assertNotIn(("G", "leftMetricsKey"), by_id(proposals))

    def test_single_side_metrics_hint_keeps_other_side_as_independent_group(self):
        source, target = Glyph("source"), Glyph("target")
        target.leftMetricsKey = "=source"
        proposals, _ = module.build_proposals(
            Font(source, target), {"metrics_hints": True, "confidence": "Low"})
        planned = by_id(proposals)
        self.assertEqual(planned[("target", "rightKerningGroup")]["after"], "target")

    def test_apply_rejects_source_that_became_auto_aligned_after_preview(self):
        base = Glyph("A")
        target = Glyph("Aacute", Layer(paths=0, components=[Component("A")]))
        underlying = Glyph("underlying")
        font = Font(base, target, underlying)
        proposals, _ = module.build_proposals(font, {})
        for item in proposals:
            item["include"] = item["id"] == ("Aacute", "leftMetricsKey")
        base.layers["m1"] = Layer(paths=0, components=[Component("underlying", True)])
        with self.assertRaisesRegex(ValueError, "auto-aligned"):
            module.apply_proposals(font, proposals, module.normalized_options({}))
        self.assertIsNone(target.leftMetricsKey)

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
