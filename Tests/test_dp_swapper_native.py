"""Native data tests; run with GlyphsApp and vanilla available in Glyphs Python.

These tests create detached fonts and never change an open document.
"""

import importlib.util
import unittest
from pathlib import Path

try:
    from GlyphsApp import (
        GSAnchor, GSComponent, GSFont, GSFontMaster, GSGlyph, GSHint,
        GSLayer, GSNode, GSPath, GSLTR, GSRTL, GSVertical, LINE, STEM,
    )
    import vanilla
except ImportError:
    GSFont = None


SCRIPT_PATH = Path(__file__).parents[1] / "Tools" / "DP Swapper.py"


@unittest.skipIf(GSFont is None, "Run with the Glyphs 4 Python API and vanilla available.")
class NativeSwapperTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("dp_swapper_native_tests", SCRIPT_PATH)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.font = GSFont()
        self.master = GSFontMaster()
        self.font.masters = [self.master]
        for name, x, width in (("a.ss01", 75, 550), ("a", 50, 500), ("V", 50, 500)):
            glyph = GSGlyph(name)
            self.font.glyphs.append(glyph)
            layer = GSLayer()
            layer.layerId = self.master.id
            layer.associatedMasterId = self.master.id
            glyph.layers[self.master.id] = layer
            path = GSPath()
            path.closed = True
            for position in ((x, 0), (x + 300, 0), (x + 300, 700), (x, 700)):
                path.nodes.append(GSNode(position, type=LINE))
            layer.shapes.append(path)
            layer.width = width
            layer.anchors.append(GSAnchor("top", (x + 150, 700)))
            hint = GSHint()
            hint.type = STEM
            hint.originNode = path.nodes[0]
            hint.targetNode = path.nodes[1]
            layer.hints.append(hint)
        self.source = self.font.glyphs["a.ss01"]
        self.target = self.font.glyphs["a"]

    def test_native_swap_keeps_hint_links_metrics_unicode_and_all_kerning_directions(self):
        self.source.unicodes = ["0061", "0101"]
        target_unicodes = list(self.target.unicodes or [])
        for direction in (GSLTR, GSRTL, GSVertical):
            self.font.setKerningForPair(self.master.id, "a.ss01", "V", -22.5, direction)
        count, _ = self.module.execute_swaps(self.font, [(self.source, "a")], swap_unicode=True)
        source_layer = self.source.layers[self.master.id]
        target_layer = self.target.layers[self.master.id]
        self.assertEqual(count, 1)
        self.assertEqual(source_layer.width, 500)
        self.assertEqual(target_layer.width, 550)
        self.assertEqual(list(self.source.unicodes or []), target_unicodes)
        self.assertEqual(list(self.target.unicodes), ["0061", "0101"])
        self.assertEqual(target_layer.hints[0].originNode, target_layer.paths[0].nodes[0])
        self.assertEqual(target_layer.hints[0].targetNode, target_layer.paths[0].nodes[1])
        for direction in (GSLTR, GSRTL, GSVertical):
            self.assertEqual(self.font.kerningForPair(self.master.id, "a", "V", direction), -22.5)
            self.assertIsNone(self.font.kerningForPair(self.master.id, "a.ss01", "V", direction))

    def test_native_shape_groups_and_component_order_survive(self):
        layer = self.source.layers[self.master.id]
        path = layer.paths[0]
        component = GSComponent("V")
        component.automaticAlignment = False
        layer.shapes.append(component)
        layer.createShapeGroupFromShapes_([path, component])
        before_types = [shape.__class__.__name__ for shape in layer.shapes]
        before_groups = len(layer.shapeGroups())
        self.module.execute_swaps(self.font, [(self.source, "a")], deep_swap=False)
        target = self.target.layers[self.master.id]
        self.assertEqual([shape.__class__.__name__ for shape in target.shapes], before_types)
        self.assertEqual(len(target.shapeGroups()), before_groups)
        self.assertGreater(before_groups, 0)
        self.assertEqual(target.hints[0].originNode, target.paths[0].nodes[0])
        self.assertEqual(target.width, 500)
        self.assertEqual(target.anchors["top"].position.x, 200)

    def test_native_alternate_built_from_base_does_not_become_self_referencing(self):
        source_layer = self.source.layers[self.master.id]
        component = GSComponent("a")
        component.automaticAlignment = False
        source_layer.shapes = [component]
        source_layer.hints = []
        source_layer.width = 550
        self.module.execute_swaps(self.font, [(self.source, "a")])
        target_layer = self.target.layers[self.master.id]
        self.assertEqual(target_layer.components[0].componentName, "a.ss01")
        self.assertEqual(len(source_layer.paths), 1)
        self.assertEqual(target_layer.width, 550)
        self.assertEqual(target_layer.LSB, 50)

    def test_native_special_layer_matching_uses_coordinates(self):
        special_layers = []
        for glyph, label in ((self.source, "source layer"), (self.target, "target layer")):
            layer = glyph.layers[self.master.id].copy()
            layer.associatedMasterId = self.master.id
            layer.attributes["coordinates"] = {"axis-id": 500}
            glyph.layers.append(layer)
            layer.name = label
            special_layers.append(layer)
        self.assertTrue(all(layer.isSpecialLayer for layer in special_layers))
        pairs = self.module.matching_layer_pairs(self.font, self.source, self.target)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[1], tuple(special_layers))

    def test_native_failed_batch_restores_original_data(self):
        self.source.unicodes = ["0061", "0101"]
        before_source = self.source.layers[self.master.id].copy()
        before_target = self.target.layers[self.master.id].copy()
        self.font.setKerningForPair(self.master.id, "a.ss01", "V", -12.5)

        def fail_progress(*args):
            raise RuntimeError("Injected failure")

        with self.assertRaisesRegex(RuntimeError, "original data restored"):
            self.module.execute_swaps(self.font, [(self.source, "a")], swap_unicode=True, progress=fail_progress)
        source_layer = self.source.layers[self.master.id]
        target_layer = self.target.layers[self.master.id]
        self.assertEqual(source_layer.width, before_source.width)
        self.assertEqual(target_layer.width, before_target.width)
        self.assertEqual(source_layer.paths[0].nodes[0].position, before_source.paths[0].nodes[0].position)
        self.assertEqual(target_layer.paths[0].nodes[0].position, before_target.paths[0].nodes[0].position)
        self.assertEqual(source_layer.hints[0].originNode, source_layer.paths[0].nodes[0])
        self.assertEqual(list(self.source.unicodes), ["0061", "0101"])
        self.assertEqual(self.font.kerningForPair(self.master.id, "a.ss01", "V"), -12.5)


if __name__ == "__main__":
    unittest.main()
