# MenuTitle: DP Swapper
# encoding: utf-8
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__ = """
Performs a two-way swap between suffixed glyph sets in Glyphs 4, preserving
shape groups and hints, with optional metrics, anchors, and Unicode values.
"""

import re
import traceback

from GlyphsApp import CAP, CORNER, GSLTR, GSRTL, GSVertical, Glyphs, Message
from vanilla import (
    Window, List, CheckBox, Button, TextBox,
    HorizontalLine, ProgressBar, PopUpButton,
)

METRIC_KEY_NAMES = ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey")
KERNING_GROUP_NAMES = (
    "leftKerningGroup", "rightKerningGroup", "topKerningGroup", "bottomKerningGroup",
)
SPECIAL_LAYER_ATTRIBUTES = ("coordinates", "axisRules", "colorPalette", "sbixSize", "color", "svg")


def get_suffix_info(font):
    """Return the final suffixes in the font, with available feature labels."""
    suffixes = {g.name.rsplit(".", 1)[1] for g in font.glyphs if "." in g.name}
    feature_map = {}
    for feature in font.features:
        if not feature.name:
            continue
        label = feature.name
        if feature.notes:
            label = feature.notes.strip()
        else:
            match = re.search(r'(?:name|featureNameID)\s+"([^"]+)"', feature.code or "")
            if match:
                label = match.group(1).strip()
        feature_map[feature.name] = label

    common_names = {
        "zero": "Slashed Zero", "alt": "Alternates", "sc": "Small Caps",
        "smcp": "Small Caps", "swsh": "Swashes", "locl": "Localized Forms",
        "sups": "Superscripts", "subs": "Subscripts", "numr": "Numerators",
        "dnom": "Denominators", "frac": "Fractions", "ordn": "Ordinals",
        "lnum": "Lining Figures", "onum": "Oldstyle Figures",
        "pnum": "Proportional Figures", "tnum": "Tabular Figures",
    }
    return [
        {"tag": suffix, "name": feature_map.get(suffix, common_names.get(suffix, suffix))}
        for suffix in sorted(suffixes)
    ]


def glyph_named(font, name):
    # Glyphs' glyph proxy also looks up characters and Unicode strings. A base
    # name must resolve to that exact glyph, even if an alternate is encoded.
    glyph = font.glyphs[name]
    return glyph if glyph is not None and glyph.name == name else None


def format_metric_value(value):
    numeric_value = float(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return ("%.12f" % numeric_value).rstrip("0").rstrip(".")


def text_with_swapped_names(text, name_map):
    """Replace whole glyph references simultaneously, including hyphenated names."""
    if not text or not name_map:
        return text
    names = "|".join(re.escape(name) for name in sorted(name_map, key=len, reverse=True))
    # A minus followed by a number is a metric offset; -cy is part of a name.
    pattern = r"(?<![A-Za-z0-9_.-])(?:%s)(?![A-Za-z0-9_.]|-[A-Za-z_])" % names
    return re.sub(pattern, lambda match: name_map[match.group(0)], str(text))


def updated_metric_key(metric_key, fallback_value, name_map):
    """Keep metric expressions, retarget references, and use layer-local == keys."""
    if metric_key:
        return "==" + text_with_swapped_names(str(metric_key).lstrip("="), name_map)
    return "==" + format_metric_value(fallback_value)


def capture_metric_state(layer):
    state = {"width": layer.width, "LSB": layer.LSB, "RSB": layer.RSB}
    state.update({key: getattr(layer, key) for key in METRIC_KEY_NAMES})
    return state


def notify_layer_metrics(layer, sync=False):
    layer.setNeedUpdateMetrics()
    if sync:
        layer.syncMetrics()
    layer.updateMetrics()


def restore_metric_state(layer, state):
    for key in METRIC_KEY_NAMES:
        setattr(layer, key, None)
    layer.LSB = state["LSB"]
    layer.RSB = state["RSB"]
    layer.width = state["width"]
    for key in METRIC_KEY_NAMES:
        setattr(layer, key, state[key])
    notify_layer_metrics(layer)


def apply_metric_state(layer, state, name_map):
    restore_metric_state(layer, state)
    for key, value in zip(METRIC_KEY_NAMES, (state["LSB"], state["RSB"], state["width"])):
        setattr(layer, key, updated_metric_key(state[key], value, name_map))
    # Sync only after the whole batch and its component references are in place.


def replace_layer_content(target, source, copy_anchors=True):
    """Let Glyphs copy shape groups and reconnect copied hint nodes."""
    anchors = None if copy_anchors else [anchor.copy() for anchor in target.anchors]
    width = target.width
    target.getCopyOfContentFromLayer_doSelection_(source, False)
    if anchors is not None:
        target.anchors = anchors
    target.width = width


def frozen_attribute(value):
    if hasattr(value, "keys"):
        return tuple(sorted((str(key), frozen_attribute(value[key])) for key in value.keys()))
    if not isinstance(value, str) and hasattr(value, "__iter__"):
        return tuple(frozen_attribute(item) for item in value)
    return value


def layer_signature(layer):
    if layer.isMasterLayer:
        return ("master", layer.associatedMasterId or layer.layerId)
    if layer.isSpecialLayer:
        attributes = layer.attributes
        settings = tuple(
            (key, frozen_attribute(attributes[key]))
            for key in SPECIAL_LAYER_ATTRIBUTES if key in attributes and attributes[key] is not None
        )
        # Names are display labels in Glyphs 4; coordinates/rules identify layers.
        return ("special", layer.associatedMasterId, settings or (("name", layer.name),))
    return None


def matching_layer_pairs(font, source, target):
    """Require complete, unambiguous master and special-layer matches."""
    source_layers, target_layers = {}, {}
    for glyph, indexed in ((source, source_layers), (target, target_layers)):
        for layer in glyph.layers:
            signature = layer_signature(layer)
            if signature is None:
                continue
            if signature in indexed:
                raise ValueError("Ambiguous layers in '%s'." % glyph.name)
            indexed[signature] = layer
    expected = {("master", master.id) for master in font.masters}
    if not expected.issubset(source_layers) or not expected.issubset(target_layers):
        raise ValueError("Missing master layer.")
    if not source_layers or source_layers.keys() != target_layers.keys():
        raise ValueError("Master/special layers do not match.")
    return [(layer, target_layers[signature]) for signature, layer in source_layers.items()]


def build_swap_plan(font, pair_list):
    name_map, plan = {}, []
    for source, target_name in pair_list:
        current_source = glyph_named(font, source.name)
        target = glyph_named(font, target_name)
        if current_source is None or current_source.id != source.id:
            raise ValueError("Source '%s' changed; refresh the preview." % source.name)
        if target is None:
            raise ValueError("Target '%s' not found." % target_name)
        if source.name == target_name:
            raise ValueError("Source and target are the same glyph.")
        if source.name in name_map or target_name in name_map:
            raise ValueError("A glyph occurs in more than one swap pair.")
        layers = matching_layer_pairs(font, source, target)
        name_map[source.name], name_map[target_name] = target_name, source.name
        plan.append((source, target, layers))
    if not plan:
        raise ValueError("No pairs to swap.")
    return plan, name_map


def build_kerning_plan(font, name_map):
    """Snapshot all directions once and remap explicit exceptions as one batch."""
    id_names = {str(glyph.id): glyph.name for glyph in font.glyphs}
    id_names.update({glyph.name: glyph.name for glyph in font.glyphs})
    plan = []
    for attribute, direction in (
        ("kerningLTR", GSLTR), ("kerningRTL", GSRTL), ("kerningVertical", GSVertical),
    ):
        container = getattr(font, attribute, None)
        if container is None and direction == GSLTR:
            container = getattr(font, "kerning", None)
        if not container:
            continue
        for master in font.masters:
            master_pairs = container.get(master.id, {})
            before, after = [], []
            for left, right_values in master_pairs.items():
                for right, value in right_values.items():
                    left_name = str(left) if str(left).startswith("@") else id_names.get(str(left))
                    right_name = str(right) if str(right).startswith("@") else id_names.get(str(right))
                    # Orphaned IDs cannot be passed to Glyphs' public pair API.
                    if left_name is None or right_name is None:
                        continue
                    if left_name not in name_map and right_name not in name_map:
                        continue
                    before.append((left_name, right_name, value))
                    after.append((name_map.get(left_name, left_name), name_map.get(right_name, right_name), value))
            if before:
                plan.append((master.id, direction, before, after))
    return plan


def write_kerning_plan(font, plan, restore=False):
    for master_id, direction, before, after in plan:
        # Removing the union is also needed after an interrupted write/rollback.
        for left, right in {(left, right) for left, right, _ in before + after}:
            font.removeKerningForPair(master_id, left, right, direction)
        for left, right, value in (before if restore else after):
            font.setKerningForPair(master_id, left, right, value, direction)


def layers_with_backgrounds(glyph):
    for layer in glyph.layers:
        yield layer
        # Reading background unconditionally would create new background layers.
        if layer.hasBackground():
            yield layer.background


def component_references(layer):
    for component in layer.components or []:
        yield component, "componentName"
    for hint in layer.hints:
        if hint.type in (CORNER, CAP):
            yield hint, "name"


def capture_glyph_state(glyph):
    state = {key: getattr(glyph, key) for key in KERNING_GROUP_NAMES + METRIC_KEY_NAMES}
    state["productionName"] = glyph.productionName
    state["storeProductionName"] = glyph.storeProductionName
    state["unicodes"] = list(glyph.unicodes or [])
    return state


def set_production_state(glyph, state):
    # Enable storage before assigning a custom production name.
    glyph.storeProductionName = True
    glyph.productionName = state["productionName"]
    glyph.storeProductionName = state["storeProductionName"]


def execute_swaps(font, pair_list, deep_swap=True, swap_unicode=False, progress=None):
    """Preflight a batch, snapshot affected data, and restore it on failure."""
    plan, name_map = build_swap_plan(font, pair_list)
    kerning_plan = build_kerning_plan(font, name_map)
    swapped_layers = {id(layer) for _, _, pairs in plan for pair in pairs for layer in pair}
    layer_states, glyph_states = [], []
    # Include external references so their metrics and geometry can be restored.
    for glyph in font.glyphs:
        affected = glyph.name in name_map
        glyph_keys_changed = deep_swap and any(
            text_with_swapped_names(getattr(glyph, key), name_map) != getattr(glyph, key)
            for key in METRIC_KEY_NAMES
        )
        for layer in layers_with_backgrounds(glyph):
            references_changed = any(getattr(ref, attr) in name_map for ref, attr in component_references(layer))
            keys_changed = deep_swap and any(
                text_with_swapped_names(getattr(layer, key), name_map) != getattr(layer, key)
                for key in METRIC_KEY_NAMES
            )
            if id(layer) in swapped_layers or references_changed or keys_changed or glyph_keys_changed:
                state = capture_metric_state(layer)
                effective = dict(state)
                for key in METRIC_KEY_NAMES:
                    effective[key] = state[key] or getattr(glyph, key)
                layer_states.append((layer, layer.copy(), state, effective))
                affected = True
        if affected or glyph_keys_changed:
            glyph_states.append((glyph, capture_glyph_state(glyph)))
    by_layer = {id(layer): (backup, state, effective) for layer, backup, state, effective in layer_states}
    by_name = {glyph.name: state for glyph, state in glyph_states}
    undo_glyphs = []
    component_count = 0
    font.disableUpdateInterface()
    try:
        for glyph, _ in glyph_states:
            glyph.beginUndo()
            undo_glyphs.append(glyph)
        for index, (source, target, pairs) in enumerate(plan):
            for source_layer, target_layer in pairs:
                source_backup, _, _ = by_layer[id(source_layer)]
                target_backup, _, _ = by_layer[id(target_layer)]
                replace_layer_content(target_layer, source_backup, copy_anchors=deep_swap)
                replace_layer_content(source_layer, target_backup, copy_anchors=deep_swap)
            for glyph, state in ((source, by_name[target.name]), (target, by_name[source.name])):
                for key in KERNING_GROUP_NAMES:
                    setattr(glyph, key, state[key])
                set_production_state(glyph, state)
                if deep_swap:
                    for key in METRIC_KEY_NAMES:
                        setattr(glyph, key, state[key])
            if swap_unicode:
                source.unicodes = []
                target.unicodes = []
                source.unicodes = by_name[target.name]["unicodes"]
                target.unicodes = by_name[source.name]["unicodes"]
            if progress:
                progress(index + 1, len(plan), source.name)

        for glyph, _ in glyph_states:
            if deep_swap:
                for key in METRIC_KEY_NAMES:
                    setattr(glyph, key, text_with_swapped_names(getattr(glyph, key), name_map))
        for layer, _, _, _ in layer_states:
            for ref, attr in component_references(layer):
                name = getattr(ref, attr)
                if name in name_map:
                    setattr(ref, attr, name_map[name])
                    component_count += 1
            if deep_swap and id(layer) not in swapped_layers:
                for key in METRIC_KEY_NAMES:
                    setattr(layer, key, text_with_swapped_names(getattr(layer, key), name_map))
        if deep_swap:
            # A copied alternate can temporarily reference itself until all
            # components are retargeted. Measure only after that graph is ready.
            for _, _, pairs in plan:
                for source_layer, target_layer in pairs:
                    apply_metric_state(target_layer, by_layer[id(source_layer)][2], name_map)
                    apply_metric_state(source_layer, by_layer[id(target_layer)][2], name_map)
        write_kerning_plan(font, kerning_plan)
        for layer, _, _, _ in layer_states:
            notify_layer_metrics(layer, sync=deep_swap and (layer.isMasterLayer or layer.isSpecialLayer))
    except Exception as error:
        rollback_errors = []
        # Continue restoring independent objects if one native setter fails.
        for glyph, state in glyph_states:
            try:
                for key in KERNING_GROUP_NAMES + METRIC_KEY_NAMES:
                    setattr(glyph, key, state[key])
                set_production_state(glyph, state)
                if swap_unicode:
                    glyph.unicodes = []
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        if swap_unicode:
            for glyph, state in glyph_states:
                try:
                    glyph.unicodes = state["unicodes"]
                except Exception as rollback_error:
                    rollback_errors.append(str(rollback_error))
        for layer, backup, metrics, _ in layer_states:
            try:
                replace_layer_content(layer, backup)
                restore_metric_state(layer, metrics)
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        try:
            write_kerning_plan(font, kerning_plan, restore=True)
        except Exception as rollback_error:
            rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise RuntimeError("Swap failed; restoration incomplete: " + "; ".join(rollback_errors)) from error
        raise RuntimeError("Swap failed; original data restored: %s" % error) from error
    finally:
        try:
            for glyph in reversed(undo_glyphs):
                glyph.endUndo()
        finally:
            font.enableUpdateInterface()
    return len(plan), component_count


# ─────────────────────────────────────────────────────────────────────────────
# DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class DPSwapperDialog:

    def __init__(self):
        self.font = Glyphs.font
        if not self.font:
            Message("No font open.", "Please open a font first.")
            return

        self.suffix_info = get_suffix_info(self.font)
        if not self.suffix_info:
            Message("No Suffixes found.", "The font has no suffixed glyphs.")
            return

        # Prepare target options: Base Glyph + all suffixes
        self.target_tags = ["<Base Glyph>"] + ["." + d["tag"] for d in self.suffix_info]

        self.w = Window((900, 620), "DP Swapper", minSize=(820, 520))
        self._build_ui()
        self.w.open()
        self._populate_source_list()

    def _build_ui(self):
        w = self.w
        
        # Left Panel -- Source
        w.sourceLabel = TextBox((12, 12, 220, 16), "1. Source suffix", sizeStyle="small")
        w.sourceHelp = TextBox((12, 30, 230, 28), "Choose the suffixed glyph set you want to swap from.", sizeStyle="small")
        w.sourceList  = List(
            (12, 64, 230, -44),
            [],
            columnDescriptions=[
                {"title": "Suffix", "width": 60},
                {"title": "Description", "width": 144},
            ],
            selectionCallback=self._update_preview,
            allowsMultipleSelection=False,
            allowsEmptySelection=True,
            allowsSorting=False,
        )

        # Right Panel -- Target & Preview
        w.targetLabel = TextBox((254, 12, 90, 16), "2. Target set", sizeStyle="small")
        w.targetPopup = PopUpButton(
            (344, 10, 180, 20),
            self.target_tags,
            callback=self._update_preview,
            sizeStyle="small"
        )
        w.targetHelp = TextBox((534, 12, -12, 16), "<Base Glyph> uses the unsuffixed glyph name.", sizeStyle="small")

        w.glyphLabel = TextBox((254, 48, -12, 16), "3. Review swap pairs", sizeStyle="small")
        w.glyphList  = List(
            (254, 68, -12, -190),
            [],
            columnDescriptions=[
                {"title": "From",   "width": 170},
                {"title": "To",     "width": 170},
                {"title": "Result", "width": 160},
            ],
            allowsMultipleSelection=True,
            allowsEmptySelection=True,
            allowsSorting=False,
        )

        w.rightDivider = HorizontalLine((254, -180, -12, 1))

        w.alwaysLabel = TextBox((254, -168, 140, 16), "Always swapped", sizeStyle="small")
        w.alwaysText = TextBox(
            (254, -148, -12, 32),
            "Outlines, shape groups, hints, dependent references, kerning groups,\nkerning values (LTR, RTL, vertical), and custom production names",
            sizeStyle="small",
        )

        w.optionsLabel = TextBox((254, -112, 140, 16), "Optional", sizeStyle="small")

        w.deepCheck = CheckBox(
            (254, -94, 190, 20),
            "Metrics and anchors",
            value=True,
            sizeStyle="small",
        )
        w.unicodeCheck = CheckBox(
            (454, -94, -12, 20),
            "Unicode values",
            value=False,
            sizeStyle="small",
        )

        w.swapSelBtn = Button((254, -68, 190, 24), "Swap Selected Valid", callback=self._swap_selected)
        w.swapAllBtn = Button((454, -68, 190, 24), "Swap All Valid", callback=self._swap_all)

        w.progress      = ProgressBar((254, -44, 250, 16), isIndeterminate=False)
        w.progressLabel = TextBox((514, -44, -12, 16), "", sizeStyle="small")

        w.mainDivider = HorizontalLine((10, -28, -10, 1))
        w.statusText  = TextBox((12, -22, -12, 18), "Choose a source suffix to preview swaps.", sizeStyle="small")


    # ─────────────────────────────────────────────────────────────────────
    # LOGIC
    # ─────────────────────────────────────────────────────────────────────

    def _populate_source_list(self):
        rows = [{"Suffix": "." + d["tag"], "Description": d["name"]} for d in self.suffix_info]
        self.w.sourceList.set(rows)

    def _get_current_target_suffix(self):
        idx = self.w.targetPopup.get()
        if idx == 0:
            return ""
        return self.target_tags[idx]

    def _update_preview(self, sender=None):
        sel = self.w.sourceList.getSelection()
        if not sel:
            self.w.glyphList.set([])
            self._set_status("Choose a source suffix to preview swaps.")
            return

        source_tag = self.suffix_info[sel[0]]["tag"]
        target_suffix = self._get_current_target_suffix()
        target_label = target_suffix if target_suffix else "<Base Glyph>"

        rows = []
        # Find all glyphs carrying the source suffix
        for g in self.font.glyphs:
            if g.name.endswith("." + source_tag):
                base_name = g.name.rsplit("." + source_tag, 1)[0]
                target_name = base_name + target_suffix

                if g.name == target_name:
                    status = "Same glyph"
                else:
                    target = glyph_named(self.font, target_name)
                    status = "Missing target"
                    if target is not None:
                        try:
                            matching_layer_pairs(self.font, g, target)
                            status = "Ready"
                        except ValueError as error:
                            status = str(error)

                rows.append({
                    "From": g.name,
                    "To": target_name,
                    "Result": status,
                    "_valid": status == "Ready",
                })

        self.w.glyphList.set(rows)
        valid_count = sum(1 for r in rows if r["_valid"])
        skipped_count = len(rows) - valid_count
        self._set_status(
            f"Previewing .{source_tag} -> {target_label}: {valid_count} ready, {skipped_count} skipped."
        )

    def _swap_selected(self, sender):
        self._trigger_swap(only_selected=True)

    def _swap_all(self, sender):
        self._trigger_swap(only_selected=False)

    def _trigger_swap(self, only_selected):
        if self.font not in Glyphs.fonts:
            self._set_status("This font was closed. Reopen DP Swapper for the font you want to edit.")
            return
        rows = self.w.glyphList.get()
        if only_selected:
            sel_idxs = self.w.glyphList.getSelection()
            if not sel_idxs:
                self._set_status("Select at least one valid row in the preview list.")
                return
            rows = [rows[i] for i in sel_idxs]

        # Filter out invalid rows (missing targets, or source=target)
        valid_pairs = []
        for row in rows:
            if not row["_valid"]:
                continue
            source = glyph_named(self.font, row["From"])
            if source is None:
                self._update_preview()
                self._set_status("A source glyph changed. Review the refreshed preview.")
                return
            valid_pairs.append((source, row["To"]))

        if not valid_pairs:
            self._set_status("No valid pairs to swap. Check the Result column.")
            return

        self._do_swap(valid_pairs, self.w.deepCheck.get(), self.w.unicodeCheck.get())

    def _do_swap(self, pair_list, deep, swap_unicode):
        self.w.progress.set(0)
        self.w.progressLabel.set("")
        self.w.swapSelBtn.enable(False)
        self.w.swapAllBtn.enable(False)

        def show_progress(done, total, source_name):
            self.w.progress.set(int(done / total * 100))
            self.w.progressLabel.set(f"{done} / {total}: {source_name}")

        try:
            count, component_updates = execute_swaps(
                self.font, pair_list, deep_swap=deep,
                swap_unicode=swap_unicode, progress=show_progress,
            )
            result = f"Swapped {count} pair(s). Updated {component_updates} component reference(s)."
        except Exception as error:
            print("DP Swapper:", traceback.format_exc())
            result = f"{error} See Macro window."
            self.w.progress.set(0)
        finally:
            self.w.swapSelBtn.enable(True)
            self.w.swapAllBtn.enable(True)
            self.w.progressLabel.set("")
        self._update_preview()
        self._set_status(result)

    def _set_status(self, msg):
        self.w.statusText.set(msg)


if __name__ == "__main__":
    DPSwapperDialog()
