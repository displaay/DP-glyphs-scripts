"""Exercise real Glyphs 4 layer objects without touching an open document.

Run with Glyphs-managed Python (PyObjC required). Thin facades expose the
Python wrapper's property conventions over GlyphsCore Objective-C objects.
"""

import unittest
from pathlib import Path

from Tests.test_special_layer_copy import Font
from speciallayercopy.core import build_plan, execute_plan
from speciallayercopy.clipboard import build_paste_plan, snapshot_layers

try:
    import objc
    from Foundation import NSBundle
    framework = Path("/Applications/Glyphs 4.app/Contents/Frameworks/GlyphsCore.framework")
    NATIVE_AVAILABLE = framework.exists() and NSBundle.bundleWithPath_(str(framework)).load()
except ImportError:
    NATIVE_AVAILABLE = False


def native(class_name):
    return objc.lookUpClass(class_name).alloc().init()


def native_property(name):
    setter = "set" + name[0].upper() + name[1:] + "_"
    return property(lambda self: getattr(self.raw, name)(),
                    lambda self, value: getattr(self.raw, setter)(value))


class NativeLayer:
    layerId = native_property("layerId")
    associatedMasterId = native_property("associatedMasterId")
    name = native_property("name")
    width = native_property("width")
    attributes = native_property("attributes")
    isMasterLayer = native_property("isMasterLayer")
    isSpecialLayer = native_property("isSpecialLayer")
    isBraceLayer = native_property("isBraceLayer")
    isBracketLayer = native_property("isBracketLayer")

    def __init__(self, raw=None):
        self.raw = native("GSLayer") if raw is None else raw

    def copy(self):
        return NativeLayer(self.raw.copy())

    def clearSelection(self):
        self.raw.clearSelection()

    def getCopyOfContentFromLayer_doSelection_(self, source, selection):
        self.raw.getCopyOfContentFromLayer_doSelection_(source.raw, selection)


class NativeLayers:
    def __init__(self, glyph):
        self.glyph = glyph
        self.fail_next = False

    def __iter__(self):
        return iter([NativeLayer(raw) for raw in self.glyph.layers().allValues()])

    def __getitem__(self, key):
        raw = self.glyph.layerForId_(key)
        return NativeLayer(raw) if raw is not None else None

    def __setitem__(self, key, layer):
        self.glyph.setLayer_forId_(layer.raw, key)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("Injected native write failure")

    def __delitem__(self, key):
        self.glyph.removeLayerForId_(key)


class NativeGlyph:
    def __init__(self, font):
        self.name = "a"
        self.parent = font
        self.raw = native("GSGlyph")
        self.raw.setName_("a")
        self.layers = NativeLayers(self.raw)
        self.undo_depth = 0

    def beginUndo(self):
        self.undo_depth += 1

    def endUndo(self):
        self.undo_depth -= 1


@unittest.skipUnless(NATIVE_AVAILABLE, "Requires Glyphs 4 GlyphsCore and PyObjC.")
class NativeSpecialLayerCopyTests(unittest.TestCase):
    def setUp(self):
        self.font = Font()
        self.glyph = NativeGlyph(self.font)
        self.source = NativeLayer()
        self.source.associatedMasterId = "M1"
        self.source.attributes = {"coordinates": {"weight": 500, "italic": 0}}
        self.source.width = 540
        path = native("GSPath")
        for point in ((0, 0), (300, 0), (300, 700), (0, 700)):
            node = native("GSNode")
            node.setPosition_(point)
            node.setType_(1)
            path.addNode_(node)
        path.setClosed_(True)
        self.source.raw.addShape_(path)
        hint = native("GSHint")
        hint.setType_(0)
        hint.setOriginNode_(path.nodes()[0])
        hint.setTargetNode_(path.nodes()[1])
        self.source.raw.addHint_(hint)
        anchor = native("GSAnchor")
        anchor.setName_("top")
        anchor.setPosition_((150, 700))
        self.source.raw.addAnchor_(anchor)
        self.source.raw.setLeftMetricsKey_("=H")
        self.glyph.layers["S1"] = self.source

    def plan(self, **kwargs):
        return build_plan(self.font, [self.glyph], "M1", ["M2"], **kwargs)

    def target(self):
        return next(layer for layer in self.glyph.layers if layer.associatedMasterId == "M2")

    def assert_hint_links(self, layer):
        hint = layer.raw.hints()[0]
        path = layer.raw.shapes()[0]
        self.assertEqual(hint.originNode(), path.nodes()[0])
        self.assertEqual(hint.targetNode(), path.nodes()[1])

    def test_native_copy_preserves_hint_links_anchors_metrics_and_attributes(self):
        execute_plan(self.plan())
        target = self.target()
        self.assert_hint_links(target)
        self.assert_hint_links(self.source)
        self.assertEqual(target.width, 540)
        self.assertEqual(target.raw.leftMetricsKey(), self.source.raw.leftMetricsKey())
        self.assertEqual(target.raw.anchors()["top"].name(), "top")
        self.assertEqual(dict(target.attributes["coordinates"]), {"weight": 500, "italic": 1})
        self.assertEqual(dict(self.source.attributes["coordinates"]), {"weight": 500, "italic": 0})
        self.assertNotEqual(target.layerId, self.source.layerId)
        self.assertEqual(self.plan().skipped, 1)

    def test_native_shape_groups_components_and_order_survive(self):
        component = native("GSComponent")
        component.setComponentName_("acute")
        component.setDisableAlignment_(True)
        self.source.raw.addShape_(component)
        self.source.raw.createShapeGroupFromShapes_(list(self.source.raw.shapes()))
        execute_plan(self.plan())
        target = self.target()
        self.assertEqual(len(target.raw.shapeGroups()), len(self.source.raw.shapeGroups()))
        self.assertGreater(len(target.raw.shapeGroups()), 0)
        self.assertEqual([type(shape).__name__ for shape in target.raw.shapes()],
                         [type(shape).__name__ for shape in self.source.raw.shapes()])
        self.assertEqual(target.raw.shapes()[1].componentName(), "acute")
        self.assert_hint_links(target)

    def test_native_rollback_preserves_target_layer_id_and_hint_links(self):
        execute_plan(self.plan())
        target_id = self.target().layerId
        self.glyph.layers.fail_next = True
        with self.assertRaisesRegex(RuntimeError, "original layers were restored"):
            execute_plan(self.plan(conflict="replace"))
        self.assertEqual(self.target().layerId, target_id)
        self.assert_hint_links(self.target())
        self.assertEqual(self.glyph.undo_depth, 0)
        self.assertFalse(self.font.updates_disabled)

    def test_native_clipboard_snapshot_survives_source_edits_and_keeps_hint_links(self):
        self.source.parent = self.glyph
        clipboard = snapshot_layers(self.font, [self.source])
        self.source.raw.hints()[0].setOriginNode_(self.source.raw.shapes()[0].nodes()[2])
        self.source.attributes["coordinates"] = {"weight": 600, "italic": 0}
        destination = NativeLayer()
        destination.associatedMasterId = "M2"
        destination.parent = self.glyph
        self.glyph.layers["M2"] = destination
        plan = build_paste_plan(clipboard, self.font, [destination])
        self.assertEqual(execute_plan(plan), 1)
        target = next(layer for layer in self.glyph.layers if layer.associatedMasterId == "M2" and not layer.isMasterLayer)
        self.assert_hint_links(target)
        self.assertEqual(dict(target.attributes["coordinates"]), {"weight": 500, "italic": 1})


if __name__ == "__main__":
    unittest.main()
