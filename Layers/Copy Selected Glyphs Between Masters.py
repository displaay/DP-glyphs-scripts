# MenuTitle: Copy Selected Glyphs Between Masters
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__ = """
Batch-copy selected glyphs from one master to one or more other masters:
outlines, metrics, and master-specific kerning pair values. Kerning group names
are shared across masters and are not copied.
"""

import traceback
import sys
import types

from GlyphsApp import GSLTR, Glyphs
from vanilla import Button, CheckBox, FloatingWindow, List, PopUpButton, TextBox


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


def target_masters(masters, source_index, selected_indices, all_others=False):
    """Return unique target masters, always excluding the source master."""
    if all_others:
        indices = range(len(masters))
    else:
        indices = selected_indices

    result = []
    seen = set()
    for index in indices:
        if index == source_index or index in seen:
            continue
        if 0 <= index < len(masters):
            seen.add(index)
            result.append(masters[index])
    return result


def replace_layer_content(target_layer, source_layer, copy_anchors):
    """Copy Glyphs 4 layer content while keeping hint-node links intact."""
    preserved_anchors = None
    if not copy_anchors:
        preserved_anchors = [anchor.copy() for anchor in target_layer.anchors]

    # In Glyphs 4 this is preferable to rebuilding paths and components: it
    # preserves shape order/groups and reconnects copied hints to copied nodes.
    target_layer.getCopyOfContentFromLayer_doSelection_(source_layer, False)

    if preserved_anchors is not None:
        target_layer.anchors = preserved_anchors


def copy_layer_metrics(target_layer, source_layer):
    target_layer.LSB = source_layer.LSB
    target_layer.RSB = source_layer.RSB
    target_layer.width = source_layer.width

    for key_name in ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey"):
        setattr(target_layer, key_name, getattr(source_layer, key_name))


def build_glyph_id_name_map(font):
    mapping = {}
    for glyph in font.glyphs:
        glyph_id = safe_string(glyph.id)
        glyph_name = safe_string(glyph.name)
        if glyph_id and glyph_name:
            mapping[glyph_id] = glyph_name
            mapping[glyph_name] = glyph_name
    return mapping


def normalize_kerning_key(key, glyph_id_name_map):
    key_text = safe_string(key)
    if key_text.startswith("@"):
        return key_text
    return glyph_id_name_map.get(key_text)


def build_kerning_keys_for_glyphs(glyphs):
    left_keys = set()
    right_keys = set()

    for glyph in glyphs:
        glyph_name = safe_string(getattr(glyph, "name", ""))
        if not glyph_name:
            continue

        left_key = safe_string(getattr(glyph, "leftKerningKey", None) or glyph_name)
        right_key = safe_string(getattr(glyph, "rightKerningKey", None) or glyph_name)

        # Glyphs names the keys for the side of the glyph, not its position in
        # the pair: the first glyph uses rightKerningKey and the second uses
        # leftKerningKey.
        left_keys.add(glyph_name)
        left_keys.add(right_key)
        right_keys.add(glyph_name)
        right_keys.add(left_key)

    return left_keys, right_keys


def get_ltr_kerning_container(font):
    container = getattr(font, "kerningLTR", None)
    if container is None:
        container = getattr(font, "kerning", {})
    return container


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

        # Ignore orphaned kerning entries whose glyph no longer exists. Passing
        # their IDs as glyph names to Glyphs 4 would raise and stop the batch.
        if normal_left is None or normal_right is None:
            continue

        if not pair_touches_scope(normal_left, normal_right, left_keys, right_keys):
            continue

        font.setKerningForPair(target_master_id, normal_left, normal_right, value, GSLTR)
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

        self.w = FloatingWindow((430, 314), "Copy Selected Glyphs Between Masters", minSize=(430, 314))
        self._build_ui()
        self._validate()
        self.w.open()
        self._bring_to_front()

    def _bring_to_front(self):
        try:
            self.w.getNSWindow().makeKeyAndOrderFront_(None)
        except Exception:
            try:
                self.w.makeKey()
            except Exception:
                pass

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
        w.targetList = List(
            (inset + 95, y - 2, -inset, 72),
            self.master_names,
            allowsMultipleSelection=True,
            showColumnTitles=False,
            selectionCallback=self._validate,
        )
        y += 76

        w.allOtherMastersCheck = CheckBox(
            (inset + 95, y, -inset, 20),
            "All other masters",
            value=False,
            sizeStyle="small",
            callback=self._validate,
        )
        y += 28

        w.strokesCheck = CheckBox(
            (inset, y, -inset, 20),
            "Outlines (shapes, groups, and hints)",
            value=True,
            sizeStyle="small",
        )
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

        # Set the initial target only after every callback dependency exists.
        if len(self.master_names) > 1:
            w.targetList.setSelection([1])

    def _validate(self, sender=None):
        source_index = self.w.sourcePopup.get()
        all_others = bool(self.w.allOtherMastersCheck.get())
        self.w.targetList.enable(not all_others)
        targets = target_masters(
            self.masters,
            source_index,
            self.w.targetList.getSelection(),
            all_others,
        )
        self.w.copyButton.enable(bool(targets))
        if not targets:
            self.w.statusText.set("Select at least one master other than the source.")
        else:
            self.w.statusText.set("Ready to copy into %i master(s)." % len(targets))

    def _copy(self, sender):
        source_index = self.w.sourcePopup.get()
        source_master = self.masters[source_index]
        targets = target_masters(
            self.masters,
            source_index,
            self.w.targetList.getSelection(),
            bool(self.w.allOtherMastersCheck.get()),
        )
        glyphs = get_selected_glyphs(self.font)

        if not targets:
            self.w.statusText.set("Select at least one master other than the source.")
            return

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
        print("Targets: %s" % ", ".join(target.name for target in targets))
        print("Glyphs: %i" % len(glyphs))

        undo_manager = None
        undo_group_open = False
        self.font.disableUpdateInterface()
        try:
            if self.font.parent is not None:
                undo_manager = self.font.parent.undoManager()
                if undo_manager is not None:
                    undo_manager.beginUndoGrouping()
                    undo_group_open = True

            glyph_id_name_map = build_glyph_id_name_map(self.font) if copy_kerning_pairs else None
            for target_master in targets:
                print("Target: %s" % target_master.name)

                if any((copy_strokes, copy_metrics, copy_anchors)):
                    for glyph in glyphs:
                        try:
                            source_layer = master_layer(glyph, source_master)
                            target_layer = master_layer(glyph, target_master)
                            if source_layer is None or target_layer is None:
                                skipped += 1
                                print("  skip %s (missing layer)" % glyph.name)
                                continue

                            if copy_strokes:
                                replace_layer_content(target_layer, source_layer, copy_anchors)
                            elif copy_anchors:
                                target_layer.anchors = [anchor.copy() for anchor in source_layer.anchors]

                            if copy_metrics:
                                copy_layer_metrics(target_layer, source_layer)

                            glyph_count += 1
                            print("  copied %s" % glyph.name)
                        except Exception:
                            skipped += 1
                            errors.append("%s (%s)" % (glyph.name, target_master.name))
                            print("  error in %s" % glyph.name)
                            traceback.print_exc()

                if copy_kerning_pairs:
                    try:
                        copied = copy_kerning_pairs_for_glyphs(
                            self.font,
                            source_master.id,
                            target_master.id,
                            glyphs,
                            glyph_id_name_map,
                        )
                        kerning_pairs_copied += copied
                        print("  kerning pairs copied: %i" % copied)
                    except Exception:
                        errors.append("kerning (%s)" % target_master.name)
                        print("  error while copying kerning")
                        traceback.print_exc()
        finally:
            if undo_group_open:
                undo_manager.endUndoGrouping()
            self.font.enableUpdateInterface()

        summary_parts = []
        if any((copy_strokes, copy_metrics, copy_anchors)):
            summary_parts.append("Copied %i glyph(s)" % glyph_count)
        if copy_kerning_pairs:
            summary_parts.append("%i kerning pair(s)" % kerning_pairs_copied)
        summary = "%s into %i master(s)" % (", ".join(summary_parts), len(targets))
        if skipped:
            summary += ", skipped %i" % skipped
        if errors:
            summary += ". See Macro window for errors."
            Glyphs.showMacroWindow()

        self.w.statusText.set(summary)


# Glyphs 4 disposes the script's execution namespace after the run. Keep the
# controller in a process-wide module so its Vanilla callbacks and window stay
# alive. Re-running the script replaces the previous controller cleanly.
WINDOW_REGISTRY_NAME = "com.displaay.glyphs-scripts.windows"
window_registry = sys.modules.get(WINDOW_REGISTRY_NAME)
if window_registry is None:
    window_registry = types.ModuleType(WINDOW_REGISTRY_NAME)
    sys.modules[WINDOW_REGISTRY_NAME] = window_registry

window_registry.copyGlyphsBetweenMasters = CopyGlyphsBetweenMastersDialog()
