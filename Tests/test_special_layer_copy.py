"""Regression tests for copy planning, identity, and failure recovery."""

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


RESOURCES = Path(__file__).parents[1] / "Plugins/SpecialLayerCopy.glyphsPlugin/Contents/Resources"
sys.path.insert(0, str(RESOURCES))
from speciallayercopy.core import build_plan, execute_plan, selected_glyphs, special_kind
from speciallayercopy.clipboard import build_paste_plan, snapshot_layers


class Layer:
    def __init__(self, layer_id, master_id, attributes=None, name="Special", master=False):
        self.layerId = layer_id
        self.associatedMasterId = master_id
        self.attributes = attributes or {}
        self.name = name
        self.isMasterLayer = master
        self.parent = None
        self.width = 540
        self.content = {"paths": [[(10, 0), (300, 700)]], "anchors": {"top": (150, 700)}}
        self.selection = [1]

    @property
    def isBraceLayer(self):
        return "coordinates" in self.attributes

    @property
    def isBracketLayer(self):
        return "axisRules" in self.attributes

    @property
    def isSpecialLayer(self):
        return bool(self.attributes)

    @property
    def smartComponentPoleMapping(self):
        raise NotImplementedError("Removed in Glyphs 4")

    def copy(self):
        layer = copy.copy(self)
        layer.parent = None
        layer.attributes = copy.deepcopy(self.attributes)
        layer.content = copy.deepcopy(self.content)
        layer.selection = list(self.selection)
        return layer

    def clearSelection(self):
        self.selection = []

    def getCopyOfContentFromLayer_doSelection_(self, source, selection):
        self.content = copy.deepcopy(source.content)


class Layers:
    def __init__(self, glyph):
        self.glyph = glyph
        self.data = {}
        self.fail_next = False

    def __iter__(self):
        return iter(self.data.values())

    def __getitem__(self, key):
        return self.data.get(key)

    def __setitem__(self, key, layer):
        self.data[key] = layer
        layer.parent = self.glyph
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("Injected write failure after mutation")

    def __delitem__(self, key):
        del self.data[key]


class Glyph:
    def __init__(self, name, font):
        self.name = name
        self.parent = font
        self.layers = Layers(self)
        self.undo_depth = 0

    def beginUndo(self):
        self.undo_depth += 1

    def endUndo(self):
        self.undo_depth -= 1


class Font:
    def __init__(self):
        self.axes = [SimpleNamespace(axisId="weight", axisTag="wght"), SimpleNamespace(axisId="italic", axisTag="ital")]
        self.masters = [
            SimpleNamespace(id="M1", name="Light Upright", axes=[100, 0]),
            SimpleNamespace(id="M2", name="Light Italic", axes=[100, 1]),
            SimpleNamespace(id="M3", name="Bold Italic", axes=[900, 1]),
        ]
        self.glyphs = []
        self.selectedLayers = []
        self.updates_disabled = False

    def disableUpdateInterface(self):
        self.updates_disabled = True

    def enableUpdateInterface(self):
        self.updates_disabled = False


class SpecialLayerCopyTests(unittest.TestCase):
    def setUp(self):
        self.font = Font()
        self.glyph = Glyph("a", self.font)
        self.font.glyphs.append(self.glyph)
        self.source = Layer("S1", "M1", {"coordinates": {"weight": 500, "italic": 0}})
        self.glyph.layers["S1"] = self.source
        for master in self.font.masters:
            self.glyph.layers[master.id] = Layer(master.id, master.id, master=True)

    def plan(self, **kwargs):
        return build_plan(self.font, [self.glyph], "M1", ["M2"], **kwargs)

    def test_coordinate_remapping_preserves_independent_axes(self):
        plan = self.plan()
        self.assertEqual(plan.operations[0].coordinates, {"weight": 500, "italic": 1})
        self.assertEqual(self.source.attributes["coordinates"]["italic"], 0)

    def test_keep_exact_coordinates(self):
        self.assertEqual(self.plan(follow_master=False).operations[0].coordinates, self.source.attributes["coordinates"])

    def test_sparse_coordinates_remain_sparse(self):
        self.source.attributes["coordinates"] = {"weight": 500}
        self.assertEqual(self.plan().operations[0].coordinates, {"weight": 500})

    def test_skip_matches_by_effective_coordinates_and_ignore_labels(self):
        existing = Layer("E1", "M2", {"coordinates": {"weight": 500}}, name="Different label")
        self.glyph.layers["E1"] = existing
        plan = self.plan()
        self.assertEqual((plan.skipped, len(plan.operations)), (1, 0))

    def test_replace_keeps_target_id_and_copies_everything_independently(self):
        existing = Layer("E1", "M2", {"coordinates": {"weight": 500}}, name="Old label")
        self.glyph.layers["E1"] = existing
        plan = self.plan(conflict="replace")
        self.assertEqual(plan.replaced, 1)
        self.assertEqual(execute_plan(plan), 1)
        target = self.glyph.layers["E1"]
        self.assertEqual(target.layerId, "E1")
        self.assertEqual(target.associatedMasterId, "M2")
        self.assertEqual(target.name, self.source.name)
        self.assertEqual(target.width, 540)
        self.assertEqual(target.content, self.source.content)
        self.assertEqual(target.selection, [])
        target.content["anchors"]["top"] = (0, 0)
        self.assertEqual(self.source.content["anchors"]["top"], (150, 700))

    def test_multiple_targets_deduplicate_and_never_replace_master_layers(self):
        plan = build_plan(self.font, [self.glyph, self.glyph], "M1", ["M1", "M2", "M2", "M3"])
        self.assertEqual(execute_plan(plan), 2)
        copies = [layer for layer in self.glyph.layers if not layer.isMasterLayer and layer is not self.source]
        self.assertEqual(len({layer.layerId for layer in copies}), 2)
        self.assertTrue(all(layer.layerId not in ("S1", "M1", "M2", "M3") for layer in copies))
        self.assertTrue(all(self.glyph.layers[master.id].isMasterLayer for master in self.font.masters))

    def test_repeat_operation_is_idempotent_in_skip_mode(self):
        execute_plan(self.plan())
        self.assertEqual(self.plan().skipped, 1)
        self.assertEqual(execute_plan(self.plan()), 0)

    def test_alternate_rules_are_preserved(self):
        rules = {"weight": {"min": 600, "max": 900}}
        self.source.attributes = {"axisRules": rules}
        self.assertIsNone(self.plan().operations[0].coordinates)
        execute_plan(self.plan())
        target = next(layer for layer in self.glyph.layers if layer.associatedMasterId == "M2" and not layer.isMasterLayer)
        self.assertEqual(target.attributes, {"axisRules": rules})

    def test_color_palette_zero_is_a_special_layer(self):
        self.source.attributes = {"colorPalette": 0}
        self.assertEqual(special_kind(self.source), "other")
        self.assertEqual(self.plan(kinds=("other",)).created, 1)

    def test_backups_and_master_layers_are_untouched(self):
        self.glyph.layers["BACKUP"] = Layer("BACKUP", "M1", name="Backup")
        self.assertEqual(self.plan().created, 1)
        self.assertIsNone(special_kind(self.glyph.layers["BACKUP"]))
        self.assertIsNone(special_kind(self.glyph.layers["M1"]))

    def test_type_filter_and_selected_layer_filter(self):
        self.assertEqual(self.plan(kinds=("alternate",)).without_source, 1)
        self.assertEqual(self.plan(selected_layer_ids={"S1"}).created, 1)
        self.assertEqual(self.plan(selected_layer_ids={"M1"}).created, 0)

    def test_distinct_special_settings_do_not_collide(self):
        self.glyph.layers["S2"] = Layer("S2", "M1", {"coordinates": {"weight": 600, "italic": 0}})
        self.assertEqual(self.plan().created, 2)

    def test_duplicate_source_layers_block_batch_before_mutation(self):
        self.glyph.layers["S2"] = self.source.copy()
        self.glyph.layers["S2"].layerId = "S2"
        with self.assertRaisesRegex(ValueError, "multiple source"):
            self.plan()
        self.assertEqual(len(self.glyph.layers.data), 5)

    def test_ambiguous_target_can_be_skipped_but_not_replaced(self):
        for layer_id in ("E1", "E2"):
            self.glyph.layers[layer_id] = Layer(layer_id, "M2", {"coordinates": {"weight": 500}})
        self.assertEqual(self.plan().skipped, 1)
        with self.assertRaisesRegex(ValueError, "multiple matching"):
            self.plan(conflict="replace")

    def test_missing_masters_and_source_only_target_block_batch(self):
        for source, targets in (("missing", ["M2"]), ("M1", ["missing"]), ("M1", ["M1"])):
            with self.subTest(source=source, targets=targets), self.assertRaises(ValueError):
                build_plan(self.font, [self.glyph], source, targets)

    def test_glyph_from_another_font_is_rejected(self):
        self.glyph.parent = Font()
        with self.assertRaisesRegex(ValueError, "no longer belongs"):
            self.plan()

    def test_native_glyph_local_coordinates_are_preserved(self):
        self.source.attributes["coordinates"]["smart-axis"] = 42
        self.assertEqual(self.plan().operations[0].coordinates["smart-axis"], 42)

    def test_copy_failure_does_not_start_mutation(self):
        def fail():
            raise RuntimeError("Injected copy failure")
        self.source.copy = fail
        with self.assertRaisesRegex(RuntimeError, "copy failure"):
            execute_plan(self.plan())
        self.assertEqual(len(self.glyph.layers.data), 4)
        self.assertFalse(self.font.updates_disabled)

    def test_failure_after_write_restores_replacement_and_closes_undo(self):
        existing = Layer("E1", "M2", {"coordinates": {"weight": 500}}, name="Original")
        self.glyph.layers["E1"] = existing
        self.glyph.layers.fail_next = True
        with self.assertRaisesRegex(RuntimeError, "original layers were restored"):
            execute_plan(self.plan(conflict="replace"))
        self.assertEqual(self.glyph.layers["E1"].name, "Original")
        self.assertEqual(self.glyph.undo_depth, 0)
        self.assertFalse(self.font.updates_disabled)

    def test_failed_batch_rolls_back_previously_copied_glyphs(self):
        second = Glyph("b", self.font)
        second.layers["S2"] = Layer("S2", "M1", {"coordinates": {"weight": 500}})
        second.layers.fail_next = True
        plan = build_plan(self.font, [self.glyph, second], "M1", ["M2"])
        with self.assertRaisesRegex(RuntimeError, "original layers were restored"):
            execute_plan(plan)
        self.assertEqual(len(self.glyph.layers.data), 4)
        self.assertEqual(len(second.layers.data), 1)
        self.assertEqual((self.glyph.undo_depth, second.undo_depth), (0, 0))
        self.assertFalse(self.font.updates_disabled)

    def test_selection_is_unique_across_multiple_selected_layers(self):
        self.font.selectedLayers = [self.source, self.glyph.layers["M1"]]
        self.assertEqual(selected_glyphs(self.font), [self.glyph])

    def test_clipboard_captures_content_and_master_coordinates_at_copy_time(self):
        clipboard = snapshot_layers(self.font, [self.source])
        self.source.content["anchors"]["top"] = (0, 0)
        self.source.attributes["coordinates"]["weight"] = 600
        self.font.masters[0].axes[1] = 10
        plan = build_paste_plan(clipboard, self.font, [self.glyph.layers["M2"]])
        execute_plan(plan)
        target = next(layer for layer in self.glyph.layers if not layer.isMasterLayer and layer.associatedMasterId == "M2")
        self.assertEqual(target.content["anchors"]["top"], (150, 700))
        self.assertEqual(target.attributes["coordinates"], {"weight": 500, "italic": 1})

    def test_clipboard_ignores_master_and_backup_rows_and_deduplicates(self):
        backup = Layer("B1", "M1")
        self.glyph.layers["B1"] = backup
        self.assertIsNone(snapshot_layers(self.font, [self.glyph.layers["M1"], backup]))
        clipboard = snapshot_layers(self.font, [self.source, self.source, self.glyph.layers["M1"]])
        self.assertEqual(len(clipboard.layers), 1)

    def test_clipboard_survives_source_layer_and_master_deletion(self):
        clipboard = snapshot_layers(self.font, [self.source])
        del self.glyph.layers["S1"]
        self.font.masters = self.font.masters[1:]
        self.assertEqual(execute_plan(build_paste_plan(clipboard, self.font, [self.glyph.layers["M2"]])), 1)

    def test_clipboard_paste_is_idempotent(self):
        clipboard = snapshot_layers(self.font, [self.source])
        destination = [self.glyph.layers["M2"]]
        execute_plan(build_paste_plan(clipboard, self.font, destination))
        plan = build_paste_plan(clipboard, self.font, destination)
        self.assertEqual((plan.created, plan.skipped), (0, 1))

    def test_clipboard_paste_to_multiple_master_rows_excludes_duplicate_rows(self):
        clipboard = snapshot_layers(self.font, [self.source])
        plan = build_paste_plan(clipboard, self.font, [self.glyph.layers["M2"], self.glyph.layers["M2"], self.glyph.layers["M3"]])
        self.assertEqual(execute_plan(plan), 2)

    def test_clipboard_pasting_on_source_master_skips_original(self):
        clipboard = snapshot_layers(self.font, [self.source])
        plan = build_paste_plan(clipboard, self.font, [self.glyph.layers["M1"]])
        self.assertEqual((plan.created, plan.skipped), (0, 1))

    def test_clipboard_does_not_modify_copied_glyphs_hidden_from_destination_selection(self):
        second = Glyph("b", self.font)
        second.layers["BS"] = Layer("BS", "M1", {"coordinates": {"weight": 500}})
        second.layers["M2"] = Layer("M2", "M2", master=True)
        clipboard = snapshot_layers(self.font, [self.source, second.layers["BS"]])
        plan = build_paste_plan(clipboard, self.font, [second.layers["M2"]])
        self.assertEqual(len(plan.operations), 1)
        self.assertIs(plan.operations[0].glyph, second)
        self.assertEqual(len(self.glyph.layers.data), 4)

    def test_clipboard_rejects_other_fonts_changed_axes_and_unrelated_glyphs(self):
        clipboard = snapshot_layers(self.font, [self.source])
        with self.assertRaisesRegex(ValueError, "same font"):
            build_paste_plan(clipboard, Font(), [])
        with self.assertRaisesRegex(ValueError, "target master"):
            build_paste_plan(clipboard, self.font, [])
        self.font.axes.reverse()
        with self.assertRaisesRegex(ValueError, "axes changed"):
            build_paste_plan(clipboard, self.font, [self.glyph.layers["M2"]])

    def test_clipboard_rejects_duplicate_source_settings_before_paste(self):
        duplicate = self.source.copy()
        duplicate.layerId = "DUPLICATE"
        self.glyph.layers[duplicate.layerId] = duplicate
        clipboard = snapshot_layers(self.font, [self.source, duplicate])
        with self.assertRaisesRegex(ValueError, "multiple copied layers"):
            build_paste_plan(clipboard, self.font, [self.glyph.layers["M2"]])


if __name__ == "__main__":
    unittest.main()
