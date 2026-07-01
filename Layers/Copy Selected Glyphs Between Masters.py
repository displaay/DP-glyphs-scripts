# MenuTitle: Copy Selected Glyphs Between Masters
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

"""
Batch-copy selected glyphs from one master to another:
outlines, metrics, and master-specific kerning pair values.

Note: kerning group names (left/right) are stored on the glyph and shared
across all masters in a font, so they are not master-specific.
"""

from __future__ import annotations

import traceback

from GlyphsApp import Glyphs, LTR
from vanilla import Button, CheckBox, PopUpButton, TextBox, Window


def safe_string(value):
    if value is None:
        return ""
    return str(value)


def unique_glyphs(glyphs):
    seen = set()
    result = []
    for glyph in glyphs:
        key = safe_string(getattr(glyph, "id", None)) or safe_string(getattr(glyph, "name", None))
        if key in seen:
            continue
        seen.add(key)
        result.append(glyph)
    return result


def get_selected_glyphs(font):
    glyphs = []
    try:
        glyphs = list(font.selection or [])
    except Exception:
        glyphs = []

    if not glyphs:
        glyphs = [glyph for glyph in font.glyphs if getattr(glyph, "selected", False)]

    if not glyphs:
        seen = set()
        for layer in font.selectedLayers or []:
            parent = getattr(layer, "parent", None)
            if parent is None:
                continue
            name = safe_string(getattr(parent, "name", None))
            if not name or name in seen:
                continue
            seen.add(name)
            glyphs.append(parent)

    return unique_glyphs(glyphs)


def master_layer(glyph, master):
    try:
        return glyph.layers[master.id]
    except Exception:
        return None


def replace_layer_strokes(target_layer, source_layer):
    paths = [path.copy() for path in source_layer.paths]
    components = [component.copy() for component in source_layer.components]
    target_layer.shapes = paths + components
    target_layer.hints = [hint.copy() for hint in source_layer.hints]


def copy_layer_metrics(target_layer, source_layer):
    target_layer.LSB = source_layer.LSB
    target_layer.RSB = source_layer.RSB
    target_layer.width = source_layer.width

    for key_name in ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey"):
        try:
            setattr(target_layer, key_name, getattr(source_layer, key_name))
        except Exception:
            pass


def build_glyph_id_name_map(font):
    mapping = {}
    for glyph in font.glyphs:
        mapping[safe_string(glyph.id)] = safe_string(glyph.name)
    return mapping


def normalize_kerning_key(key, glyph_id_name_map):
    key_text = safe_string(key)
    if key_text.startswith("@"):
        return key_text
    return glyph_id_name_map.get(key_text, key_text)


def build_kerning_keys_for_glyphs(glyphs):
    left_keys = set()
    right_keys = set()

    for glyph in glyphs:
        glyph_name = safe_string(getattr(glyph, "name", ""))
        if not glyph_name:
            continue

        left_group = safe_string(getattr(glyph, "leftKerningGroup", None))
        right_group = safe_string(getattr(glyph, "rightKerningGroup", None))

        left_key = safe_string(getattr(glyph, "leftKerningKey", None) or glyph_name)
        right_key = safe_string(getattr(glyph, "rightKerningKey", None) or glyph_name)

        left_keys.add(glyph_name)
        right_keys.add(glyph_name)
        if left_group:
            left_keys.add(left_group)
            left_keys.add("@MMK_R_%s" % left_group)
        if right_group:
            right_keys.add(right_group)
            right_keys.add("@MMK_L_%s" % right_group)
        left_keys.add(left_key)
        right_keys.add(right_key)

    return left_keys, right_keys


def get_ltr_kerning_container(font):
    return getattr(font, "kerningLTR", getattr(font, "kerning", {}))


def iter_kerning_pairs_for_master(font, master_id):
    kerning_container = get_ltr_kerning_container(font)
    try:
        master_kerning = kerning_container[master_id]
    except Exception:
        master_kerning = None

    if not master_kerning:
        return []

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
                value = float(right_dict[right_key])
            except Exception:
                continue
            pairs.append((left_key, right_key, value))

    return pairs


def pair_touches_scope(normal_left_key, normal_right_key, left_keys, right_keys):
    return normal_left_key in left_keys or normal_right_key in right_keys


def copy_kerning_pairs_for_glyphs(font, source_master_id, target_master_id, glyphs, glyph_id_name_map):
    left_keys, right_keys = build_kerning_keys_for_glyphs(glyphs)
    copied = 0

    for left_key, right_key, value in iter_kerning_pairs_for_master(font, source_master_id):
        normal_left = normalize_kerning_key(left_key, glyph_id_name_map)
        normal_right = normalize_kerning_key(right_key, glyph_id_name_map)

        if not pair_touches_scope(normal_left, normal_right, left_keys, right_keys):
            continue

        font.setKerningForPair(target_master_id, normal_left, normal_right, int(round(value)), LTR)
        copied += 1

    return copied


class CopyGlyphsBetweenMastersDialog:
    def __init__(self):
        self.font = Glyphs.font
        if self.font is None:
            self._message("No font open", "Open a font and run the script again.")
            return

        self.masters = list(self.font.masters)
        if len(self.masters) < 2:
            self._message("Not enough masters", "This font needs at least two masters.")
            return

        self.master_names = [safe_string(master.name) or safe_string(master.id) for master in self.masters]

        self.w = Window((430, 228), "Copy Selected Glyphs Between Masters", minSize=(430, 228))
        self._build_ui()
        self._validate()
        self.w.open()

    def _message(self, title, text):
        try:
            from vanilla.dialogs import message

            message(text, title)
        except Exception:
            print("%s: %s" % (title, text))

    def _build_ui(self):
        w = self.w
        inset = 15
        line_height = 28
        y = 12

        w.sourceLabel = TextBox((inset, y, 90, 18), "Copy from", sizeStyle="small")
        w.sourcePopup = PopUpButton((inset + 95, y - 2, -inset, 22), self.master_names, callback=self._validate)
        y += line_height

        w.targetLabel = TextBox((inset, y, 90, 18), "Paste into", sizeStyle="small")
        w.targetPopup = PopUpButton((inset + 95, y - 2, -inset, 22), self.master_names, callback=self._validate)
        if len(self.master_names) > 1:
            w.targetPopup.set(1)
        y += line_height + 6

        w.strokesCheck = CheckBox((inset, y, -inset, 20), "Strokes (paths, components, hints)", value=True, sizeStyle="small")
        y += 22
        w.metricsCheck = CheckBox((inset, y, -inset, 20), "Metrics (LSB, RSB, width, metric keys)", value=True, sizeStyle="small")
        y += 22
        w.anchorsCheck = CheckBox((inset, y, -inset, 20), "Anchors", value=True, sizeStyle="small")
        y += 22
        w.kerningPairsCheck = CheckBox(
            (inset, y, -inset, 20),
            "Kerning pairs for selected glyphs and their groups",
            value=True,
            sizeStyle="small",
        )

        w.statusText = TextBox((inset, -52, -inset, 18), "Select glyphs in Font View or Edit View.", sizeStyle="small")
        w.copyButton = Button((-110, -28, -inset, 24), "Copy", callback=self._copy)
        w.setDefaultButton(w.copyButton)

    def _validate(self, sender=None):
        same_master = self.w.sourcePopup.get() == self.w.targetPopup.get()
        self.w.copyButton.enable(not same_master)
        if same_master:
            self.w.statusText.set("Choose two different masters.")
        else:
            self.w.statusText.set("Select glyphs in Font View or Edit View.")

    def _copy(self, sender):
        source_master = self.masters[self.w.sourcePopup.get()]
        target_master = self.masters[self.w.targetPopup.get()]
        glyphs = get_selected_glyphs(self.font)

        if not glyphs:
            self.w.statusText.set("No glyphs selected.")
            return

        copy_strokes = self.w.strokesCheck.get()
        copy_metrics = self.w.metricsCheck.get()
        copy_anchors = self.w.anchorsCheck.get()
        copy_kerning_pairs = self.w.kerningPairsCheck.get()

        if not any((copy_strokes, copy_metrics, copy_anchors, copy_kerning_pairs)):
            self.w.statusText.set("Enable at least one copy option.")
            return

        glyph_count = 0
        skipped = 0
        kerning_pairs_copied = 0
        errors = []

        Glyphs.clearLog()
        print("Copy Selected Glyphs Between Masters")
        print("Source: %s" % source_master.name)
        print("Target: %s" % target_master.name)
        print("Glyphs: %i" % len(glyphs))

        self.font.disableUpdateInterface()
        try:
            for glyph in glyphs:
                try:
                    source_layer = master_layer(glyph, source_master)
                    target_layer = master_layer(glyph, target_master)
                    if source_layer is None or target_layer is None:
                        skipped += 1
                        print("  skip %s (missing layer)" % glyph.name)
                        continue

                    if copy_strokes:
                        replace_layer_strokes(target_layer, source_layer)

                    if copy_metrics:
                        copy_layer_metrics(target_layer, source_layer)

                    if copy_anchors:
                        target_layer.anchors = [anchor.copy() for anchor in source_layer.anchors]

                    glyph_count += 1
                    print("  copied %s" % glyph.name)
                except Exception:
                    skipped += 1
                    errors.append(glyph.name)
                    print("  error in %s" % glyph.name)
                    traceback.print_exc()

            if copy_kerning_pairs:
                glyph_id_name_map = build_glyph_id_name_map(self.font)
                kerning_pairs_copied = copy_kerning_pairs_for_glyphs(
                    self.font,
                    source_master.id,
                    target_master.id,
                    glyphs,
                    glyph_id_name_map,
                )
                print("  kerning pairs copied: %i" % kerning_pairs_copied)
        finally:
            self.font.enableUpdateInterface()

        summary = "Copied %i glyph(s)" % glyph_count
        if kerning_pairs_copied:
            summary += ", %i kerning pair(s)" % kerning_pairs_copied
        if skipped:
            summary += ", skipped %i" % skipped
        if errors:
            summary += ". See Macro window for errors."
            Glyphs.showMacroWindow()

        self.w.statusText.set(summary)


CopyGlyphsBetweenMastersDialog()
