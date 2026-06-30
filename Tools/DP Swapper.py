# encoding: utf-8
# MenuTitle: DP Swapper
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

"""
DP Swapper.py - Glyphs 3 Script
Performs a TRUE two-way swap of layers, metrics, and kerning between a source set and a target set.
"""

from __future__ import annotations
import re
import traceback
from GlyphsApp import *
from vanilla import (
    Window, List, CheckBox, Button, TextBox,
    HorizontalLine, ProgressBar, PopUpButton
)

METRIC_KEY_NAMES = ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_suffix_info(font):
    """
    Return a list of dicts: {tag, name} for every suffix in the font.
    """
    suffix_set = set()
    
    for g in font.glyphs:
        if '.' in g.name:
            _, suffix = g.name.rsplit('.', 1)
            suffix_set.add(suffix)

    feature_map = {}
    for f in font.features:
        if not f.name: continue
        label = f.name
        code  = f.code or ""

        if hasattr(f, 'notes') and f.notes:
            label = f.notes.strip()
        else:
            m_name = re.search(r'name\s+"([^"]+)"', code)
            m_feat = re.search(r'featureNameID\s+"([^"]+)"', code)
            if m_name: label = m_name.group(1).strip()
            elif m_feat: label = m_feat.group(1).strip()

        feature_map[f.name] = label

    common_names = {
        'zero': 'Slashed Zero', 'alt': 'Alternates', 'sc': 'Small Caps',
        'smcp': 'Small Caps', 'swsh': 'Swashes', 'locl': 'Localized Forms',
        'sups': 'Superscripts', 'subs': 'Subscripts', 'numr': 'Numerators',
        'dnom': 'Denominators', 'frac': 'Fractions', 'ordn': 'Ordinals',
        'lnum': 'Lining Figures', 'onum': 'Oldstyle Figures',
        'pnum': 'Proportional Figures', 'tnum': 'Tabular Figures'
    }

    results = []
    for suffix in sorted(suffix_set):
        label = suffix
        if suffix in feature_map:
            label = feature_map[suffix]
        elif suffix in common_names:
            label = common_names[suffix]

        results.append({"tag": suffix, "name": label})

    return results


def format_metric_value(value):
    try:
        numeric_value = float(value)
    except Exception:
        return str(value)

    rounded_value = round(numeric_value)
    if abs(numeric_value - rounded_value) < 0.0001:
        return str(int(rounded_value))
    return ("%.3f" % numeric_value).rstrip("0").rstrip(".")


def text_with_swapped_names(text, name_map):
    if not text or not name_map:
        return text

    result = str(text)
    placeholders = {}
    for index, old_name in enumerate(sorted(name_map.keys(), key=len, reverse=True)):
        token = "__DP_SWAPPER_NAME_%d__" % index
        pattern = r"(?<![A-Za-z0-9_.])%s(?![A-Za-z0-9_.])" % re.escape(old_name)
        result = re.sub(pattern, token, result)
        placeholders[token] = name_map[old_name]

    for token, new_name in placeholders.items():
        result = result.replace(token, new_name)

    return result


def updated_metric_key(metric_key, fallback_value, name_map):
    """
    Convert metric keys to double-equals form after a metrics swap.
    Existing metric expressions keep their reference, but glyph names inside the
    expression are retargeted through the current swap map.
    """
    if metric_key:
        key_body = str(metric_key).lstrip("=")
        return "==" + text_with_swapped_names(key_body, name_map)
    return "==" + format_metric_value(fallback_value)


def capture_metric_state(layer):
    state = {
        "width": layer.width,
        "LSB": layer.LSB,
        "RSB": layer.RSB,
    }
    for key_name in METRIC_KEY_NAMES:
        try:
            key_value = getattr(layer, key_name)
        except Exception:
            key_value = None
        state[key_name] = str(key_value) if key_value else None
    return state


def notify_layer_metrics(layer, sync=True):
    try:
        layer.setNeedUpdateMetrics()
    except Exception:
        pass
    if sync:
        try:
            layer.syncMetrics()
        except Exception:
            pass
    try:
        layer.updateMetrics()
    except Exception:
        pass


def apply_metric_state(layer, state, name_map):
    for key_name in METRIC_KEY_NAMES:
        try:
            setattr(layer, key_name, None)
        except Exception:
            pass

    layer.width = state["width"]
    layer.LSB = state["LSB"]
    layer.RSB = state["RSB"]

    layer.leftMetricsKey = updated_metric_key(state["leftMetricsKey"], state["LSB"], name_map)
    layer.rightMetricsKey = updated_metric_key(state["rightMetricsKey"], state["RSB"], name_map)
    layer.widthMetricsKey = updated_metric_key(state["widthMetricsKey"], state["width"], name_map)
    notify_layer_metrics(layer, sync=True)


def component_base_name(component):
    return getattr(component, "componentName", None) or getattr(component, "name", None)


def set_component_base_name(component, new_name):
    changed = False
    try:
        component.componentName = new_name
        changed = True
    except Exception:
        pass
    try:
        component.name = new_name
        changed = True
    except Exception:
        pass
    return changed


def retarget_components_for_swapped_glyphs(font, name_map):
    component_count = 0
    if not name_map:
        return component_count

    for glyph in font.glyphs:
        for layer in glyph.layers:
            layer_changed = False
            for component in getattr(layer, "components", []) or []:
                base_name = component_base_name(component)
                if base_name in name_map and set_component_base_name(component, name_map[base_name]):
                    component_count += 1
                    layer_changed = True
            if layer_changed:
                notify_layer_metrics(layer, sync=True)

    return component_count


def sync_metrics_for_glyph_names(font, glyph_names):
    for glyph_name in glyph_names:
        glyph = font.glyphs[glyph_name]
        if glyph is None:
            continue
        for layer in glyph.layers:
            if layer.isMasterLayer or layer.isSpecialLayer:
                notify_layer_metrics(layer, sync=True)


def execute_swap(font, source_glyph, target_name, deep_swap=True, swap_unicode=False, name_map=None):
    """
    Perform a true two-way swap of data between source_glyph and target_name.
    """
    target_glyph = font.glyphs[target_name]
    if target_glyph is None:
        return False, f"Target '{target_name}' not found."

    if name_map is None:
        name_map = {source_glyph.name: target_glyph.name, target_glyph.name: source_glyph.name}

    def replace_layer_geometry(layer, new_paths, new_components):
        """
        Replace outlines/components by reassigning `shapes`.
        GSLayer path/component proxies can be read-only for delete/clear.
        """
        layer.shapes = [p.copy() for p in new_paths] + [c.copy() for c in new_components]

    def glyph_id_name_map():
        mapping = {}
        for glyph in font.glyphs:
            name = getattr(glyph, "name", None)
            if not name:
                continue
            for attr_name in ("id", "glyphId"):
                glyph_id = getattr(glyph, attr_name, None)
                if glyph_id:
                    mapping[str(glyph_id)] = name
        return mapping

    def normalize_kerning_key(key, id_name_map):
        key_text = str(key)
        if key_text.startswith("@"):
            return key_text
        return id_name_map.get(key_text, key_text)

    def iter_master_kerning_pairs(master_id):
        kerning_container = getattr(font, "kerningLTR", getattr(font, "kerning", {}))
        try:
            master_kerning = kerning_container[master_id]
        except Exception:
            master_kerning = None

        if not master_kerning:
            return []

        id_name_map = glyph_id_name_map()
        pairs = []
        try:
            left_keys = list(master_kerning.keys())
        except Exception:
            left_keys = list(master_kerning)

        for left_key in left_keys:
            try:
                right_dict = master_kerning[left_key]
            except Exception:
                continue

            try:
                right_keys = list(right_dict.keys())
            except Exception:
                right_keys = list(right_dict)

            for right_key in right_keys:
                try:
                    value = right_dict[right_key]
                except Exception:
                    continue
                pairs.append((
                    normalize_kerning_key(left_key, id_name_map),
                    normalize_kerning_key(right_key, id_name_map),
                    value,
                ))

        return pairs

    def remove_kerning_pair(master_id, left_key, right_key):
        try:
            font.removeKerningForPair(master_id, left_key, right_key, LTR)
            return
        except (NameError, TypeError):
            pass
        except Exception:
            return

        try:
            font.removeKerningForPair(master_id, left_key, right_key)
        except Exception:
            pass

    def set_kerning_pair(master_id, left_key, right_key, value):
        try:
            font.setKerningForPair(master_id, left_key, right_key, value, LTR)
            return
        except (NameError, TypeError):
            pass

        font.setKerningForPair(master_id, left_key, right_key, value)

    def swap_kerning_values():
        source_name = source_glyph.name
        target_name_local = target_glyph.name

        def swapped_key(key):
            if key == source_name:
                return target_name_local
            if key == target_name_local:
                return source_name
            return key

        pair_count = 0
        for master in font.masters:
            master_id = master.id
            affected_pairs = []
            for left_key, right_key, value in iter_master_kerning_pairs(master_id):
                if left_key in (source_name, target_name_local) or right_key in (source_name, target_name_local):
                    affected_pairs.append((left_key, right_key, value))

            if not affected_pairs:
                continue

            pairs_to_remove = set()
            pairs_to_write = {}
            for left_key, right_key, value in affected_pairs:
                swapped_left = swapped_key(left_key)
                swapped_right = swapped_key(right_key)
                pairs_to_remove.add((left_key, right_key))
                pairs_to_remove.add((swapped_left, swapped_right))
                pairs_to_write[(swapped_left, swapped_right)] = value

            for left_key, right_key in pairs_to_remove:
                remove_kerning_pair(master_id, left_key, right_key)

            for (left_key, right_key), value in pairs_to_write.items():
                set_kerning_pair(master_id, left_key, right_key, value)
                pair_count += 1

        return pair_count

    def swap_always_glyph_attributes():
        src_left_kern = source_glyph.leftKerningGroup
        src_right_kern = source_glyph.rightKerningGroup
        src_production_name = getattr(source_glyph, "productionName", None)

        source_glyph.leftKerningGroup = target_glyph.leftKerningGroup
        source_glyph.rightKerningGroup = target_glyph.rightKerningGroup
        if hasattr(source_glyph, "productionName") and hasattr(target_glyph, "productionName"):
            source_glyph.productionName = getattr(target_glyph, "productionName", None)

        target_glyph.leftKerningGroup = src_left_kern
        target_glyph.rightKerningGroup = src_right_kern
        if hasattr(source_glyph, "productionName") and hasattr(target_glyph, "productionName"):
            target_glyph.productionName = src_production_name

        swap_kerning_values()

    def find_matching_target_layer(src_layer, used_target_layer_ids):
        # Ignore background/temp layers that do not represent editable glyph data.
        if not (src_layer.isMasterLayer or src_layer.isSpecialLayer):
            return None

        # Master layers share IDs across glyphs.
        if src_layer.isMasterLayer:
            master_id = src_layer.associatedMasterId or src_layer.layerId
            if not master_id:
                return None
            layer = target_glyph.layers[master_id]
            if layer is None or layer.layerId in used_target_layer_ids:
                return None
            return layer

        # Special layers have per-glyph IDs; match by (name, associated master).
        for candidate in target_glyph.layers:
            if not candidate.isSpecialLayer:
                continue
            if candidate.layerId in used_target_layer_ids:
                continue
            if candidate.associatedMasterId != src_layer.associatedMasterId:
                continue
            if candidate.name != src_layer.name:
                continue
            return candidate

        return None

    used_target_layer_ids = set()
    for src_layer in source_glyph.layers:
        target_layer = find_matching_target_layer(src_layer, used_target_layer_ids)
        if target_layer is None:
            continue
        used_target_layer_ids.add(target_layer.layerId)

        # 1. BACKUP Target outline/component data
        tgt_paths_backup      = [p.copy() for p in target_layer.paths]
        tgt_components_backup = [c.copy() for c in target_layer.components]
        if deep_swap:
            src_metric_state   = capture_metric_state(src_layer)
            tgt_metric_state   = capture_metric_state(target_layer)
            tgt_anchors_backup = [a.copy() for a in target_layer.anchors]

        # 2. SOURCE -> TARGET
        replace_layer_geometry(target_layer, src_layer.paths, src_layer.components)
        if deep_swap:
            target_layer.anchors = [a.copy() for a in src_layer.anchors]
            apply_metric_state(target_layer, src_metric_state, name_map)

        # 3. TARGET BACKUP -> SOURCE
        replace_layer_geometry(src_layer, tgt_paths_backup, tgt_components_backup)
        if deep_swap:
            src_layer.anchors = tgt_anchors_backup
            apply_metric_state(src_layer, tgt_metric_state, name_map)

    # 4. Glyph-level metadata that should follow the swapped design.
    swap_always_glyph_attributes()

    if swap_unicode:
        src_unicode = source_glyph.unicode
        source_glyph.unicode = target_glyph.unicode
        target_glyph.unicode = src_unicode

    return True, f"SWAPPED: {source_glyph.name} <-> {target_name}"


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
        )

        w.rightDivider = HorizontalLine((254, -180, -12, 1))

        w.alwaysLabel = TextBox((254, -168, 140, 16), "Always swapped", sizeStyle="small")
        w.alwaysText = TextBox(
            (254, -148, -12, 32),
            "Outlines, components, dependent component references, kerning groups,\nkerning values, and production names",
            sizeStyle="small",
        )

        w.optionsLabel = TextBox((254, -112, 140, 16), "Optional", sizeStyle="small")

        w.deepCheck = CheckBox(
            (254, -94, 300, 20),
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
        if idx == 0: return "" # Base glyph
        return self.target_tags[idx] # Returns ".tag"

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
                    target_exists = self.font.glyphs[target_name] is not None
                    status = "Ready" if target_exists else "Missing target"

                rows.append({
                    "From": g.name,
                    "To": target_name,
                    "Result": status,
                    "_valid": status == "Ready",
                    "_source": g,
                    "_target_name": target_name
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
        rows = self.w.glyphList.get()
        if only_selected:
            sel_idxs = self.w.glyphList.getSelection()
            if not sel_idxs:
                self._set_status("Select at least one valid row in the preview list.")
                return
            rows = [rows[i] for i in sel_idxs]

        # Filter out invalid rows (missing targets, or source=target)
        valid_pairs = [(r["_source"], r["_target_name"]) for r in rows if r["_valid"]]

        if not valid_pairs:
            self._set_status("No valid pairs to swap. Check the Result column.")
            return

        self._do_swap(valid_pairs, self.w.deepCheck.get(), self.w.unicodeCheck.get())

    def _do_swap(self, pair_list, deep, swap_unicode):
        total  = len(pair_list)
        errors = []
        component_updates = 0
        name_map = {}
        for src_g, target_name in pair_list:
            name_map[src_g.name] = target_name
            name_map[target_name] = src_g.name

        self.w.progress.set(0)
        self.w.progressLabel.set("")
        self.font.disableUpdateInterface()

        try:
            for i, (src_g, target_name) in enumerate(pair_list):
                ok, msg = execute_swap(
                    self.font,
                    src_g,
                    target_name,
                    deep_swap=deep,
                    swap_unicode=swap_unicode,
                    name_map=name_map,
                )
                if not ok:
                    errors.append(msg)
                    print("DP Swapper:", msg)
                    
                self.w.progress.set(int((i + 1) / total * 100))
                self.w.progressLabel.set(f"{i + 1} / {total} : {src_g.name}")

            component_updates = retarget_components_for_swapped_glyphs(self.font, name_map)
            if deep:
                sync_metrics_for_glyph_names(self.font, name_map.keys())
        except Exception:
            tb = traceback.format_exc()
            errors.append(tb)
            print(tb)
        finally:
            self.font.enableUpdateInterface()

        self.w.progressLabel.set("")
        self._update_preview() # Refresh statuses

        if errors:
            self._set_status(f"Done: {total - len(errors)} swapped, {len(errors)} error(s). See Macro window.")
        else:
            self._set_status(f"Success! Swapped {total} pair(s). Updated {component_updates} component reference(s).")

    def _set_status(self, msg):
        self.w.statusText.set(msg)

DPSwapperDialog()
