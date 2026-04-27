#MenuTitle: Tabular Figures Spacer
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__="""
Sets a fixed width for tabular figures (.tf, .tosf, etc.), with options to center, apply metrics keys, and disable component alignment.
"""

import vanilla
import math
from collections import Counter
from GlyphsApp import Glyphs


class TabularSpacer(object):
    def __init__(self):
        self.font = Glyphs.font
        if not self.font:
            from AppKit import NSBeep
            NSBeep()
            print("Error: Please open a font first.")
            return

        self.tabular_suffixes = self.get_tabular_suffixes()
        if not self.tabular_suffixes:
            from AppKit import NSBeep
            NSBeep()
            print("No tabular figure suffixes found in the font (e.g., .tf, .tosf, .tnum, .osf).")
            return

        self.mono_axis_index = self.get_mono_axis_index()
        self.has_positive_mono_masters = any(self.is_positive_mono_master(master) for master in self.font.masters)
        self.suggested_width = self.calculate_widest_tabular(exclude_positive_mono=self.has_positive_mono_masters)
        if self.suggested_width == 0:
            self.suggested_width = self.calculate_widest_tabular()
        self.suggested_mono_width = self.calculate_common_mono_width()
        if self.suggested_mono_width is None:
            self.suggested_mono_width = self.suggested_width

        # --- UI Setup ---
        # Fixed the UI bug: generous base height + dynamic height for suffix checkboxes
        window_height = 280 + (len(self.tabular_suffixes) * 25)
        self.w = vanilla.FloatingWindow((320, window_height), "Tabular Figures Spacer")

        y = 15
        self.w.text_1 = vanilla.TextBox((15, y, 120, 20), "Suggested Width:")
        self.w.widthInput = vanilla.EditText((135, y - 2, 60, 22), str(self.suggested_width))

        y += 30
        self.w.monoWidthText = vanilla.TextBox((15, y, 120, 20), "MONO Width:")
        self.w.monoWidthInput = vanilla.EditText((135, y - 2, 60, 22), str(self.suggested_mono_width))
        if not self.has_positive_mono_masters:
            self.w.monoWidthText.enable(False)
            self.w.monoWidthInput.enable(False)

        y += 35
        self.w.text_2 = vanilla.TextBox((15, y, -15, 20), "Apply to Suffixes:")
        y += 25

        # Dynamically create checkboxes for found suffixes
        self.checkboxes = {}
        for suffix in self.tabular_suffixes:
            chk = vanilla.CheckBox((25, y, -15, 20), suffix, value=True)
            setattr(self.w, "chk_" + suffix.replace(".", ""), chk)
            self.checkboxes[suffix] = chk
            y += 25

        y += 10
        self.w.centerGlyphs = vanilla.CheckBox((15, y, -15, 20), "Center glyphs (adjust LSB/RSB equally)", value=True)
        y += 25
        self.w.setMetricsKey = vanilla.CheckBox((15, y, -15, 20), "Set absolute Width Metrics Key (==val)", value=True)
        y += 25
        self.w.disableAutoAlign = vanilla.CheckBox((15, y, -15, 20), "Disable auto-alignment for components", value=True)

        y += 35
        self.w.applyBtn = vanilla.Button((15, y, -15, 20), "Apply Fixed Width", callback=self.applyCallback)

        self.w.open()

    def get_tabular_suffixes(self):
        suffixes = set()
        target_suffixes = [".tf", ".tosf", ".tnum", ".osf"]

        for glyph in self.font.glyphs:
            for suffix in self.glyph_suffixes(glyph):
                if suffix in target_suffixes:
                    suffixes.add(suffix)
        return sorted(list(suffixes))

    def glyph_suffixes(self, glyph):
        parts = glyph.name.split(".")
        return ["." + part for part in parts[1:]]

    def glyph_has_any_suffix(self, glyph, suffixes):
        glyph_suffixes = self.glyph_suffixes(glyph)
        return any(suffix in glyph_suffixes for suffix in suffixes)

    def calculate_widest_tabular(self, exclude_positive_mono=False):
        max_width = 0
        for glyph in self.font.glyphs:
            if self.glyph_has_any_suffix(glyph, self.tabular_suffixes):
                for layer in glyph.layers:
                    if layer.isMasterLayer or layer.isSpecialLayer:
                        if self.should_exclude_layer(layer, exclude_positive_mono):
                            continue
                        if layer.width > max_width:
                            max_width = layer.width

        return int(math.ceil(max_width))

    def calculate_common_mono_width(self):
        widths = []
        for glyph in self.font.glyphs:
            if self.glyph_has_any_suffix(glyph, self.tabular_suffixes):
                for layer in glyph.layers:
                    if layer.isMasterLayer or layer.isSpecialLayer:
                        if self.is_positive_mono_master(self.master_for_layer(layer)):
                            widths.append(int(round(layer.width)))

        if not widths:
            return None

        counts = Counter(widths)
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    def get_mono_axis_index(self):
        for i, axis in enumerate(self.font.axes):
            axis_tag = getattr(axis, "axisTag", None) or getattr(axis, "tag", None)
            if axis_tag == "MONO":
                return i
        return None

    def master_for_layer(self, layer):
        master_id = self.layer_master_id(layer)
        for master in self.font.masters:
            if master.id == master_id:
                return master
        return None

    def layer_master_id(self, layer):
        return getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None)

    def is_positive_mono_master(self, master):
        if master is None or self.mono_axis_index is None:
            return False
        try:
            return float(master.axes[self.mono_axis_index]) > 0
        except Exception:
            return False

    def should_exclude_layer(self, layer, exclude_positive_mono):
        if not exclude_positive_mono:
            return False
        return self.is_positive_mono_master(self.master_for_layer(layer))

    def disable_component_alignment(self, component):
        try:
            component.automaticAlignment = False
        except Exception:
            pass
        try:
            component.alignment = -1
        except Exception:
            pass

    def move_position_object(self, item, amount):
        try:
            position = item.position
            item.position = (position.x + amount, position.y)
            return True
        except Exception:
            pass

        try:
            x, y = item.position
            item.position = (x + amount, y)
            return True
        except Exception:
            pass

        try:
            item.x += amount
            return True
        except Exception:
            return False

    def move_layer_content(self, layer, amount):
        for path in layer.paths:
            for node in path.nodes:
                self.move_position_object(node, amount)

        for component in layer.components:
            self.move_position_object(component, amount)

        for anchor in layer.anchors:
            self.move_position_object(anchor, amount)

    def component_uses_layer_master(self, component, layer_master_id):
        component_master_id = getattr(component, "componentMasterId", None)
        return not component_master_id or component_master_id == layer_master_id

    def compensate_dependent_components(self, target_items, source_glyph, source_layer, amount):
        source_name = getattr(source_glyph, "name", None)
        source_master_id = self.layer_master_id(source_layer)
        if not source_name or not source_master_id:
            return

        for item in target_items:
            if item["glyph"] is source_glyph:
                continue
            for layer in item["layers"]:
                if self.layer_master_id(layer) != source_master_id:
                    continue
                for component in layer.components:
                    if self.component_base_name(component) == source_name and self.component_uses_layer_master(component, source_master_id):
                        self.disable_component_alignment(component)
                        self.move_position_object(component, -amount)

    def move_target_layer_content(self, item, layer, amount, target_items):
        self.move_layer_content(layer, amount)
        self.compensate_dependent_components(target_items, item["glyph"], layer, amount)

    def layer_centering_offset(self, layer, target_width):
        try:
            bounds = layer.bounds
            if bounds.size.width > 0:
                current_center = bounds.origin.x + (bounds.size.width / 2)
                return (target_width / 2) - current_center
        except Exception:
            pass

        return (target_width - layer.width) / 2

    def component_base_name(self, component):
        return getattr(component, "componentName", None) or getattr(component, "name", None)

    def target_dependencies(self, layers, target_names):
        dependencies = set()
        for layer in layers:
            for component in layer.components:
                base_name = self.component_base_name(component)
                if base_name in target_names:
                    dependencies.add(base_name)
        return dependencies

    def collect_target_glyphs(self, selected_suffixes):
        items = []
        for glyph in self.font.glyphs:
            if self.glyph_has_any_suffix(glyph, selected_suffixes):
                layers_to_process = []
                for layer in glyph.layers:
                    if layer.isMasterLayer or layer.isSpecialLayer:
                        layers_to_process.append(layer)

                if layers_to_process:
                    items.append({"glyph": glyph, "layers": layers_to_process, "dependencies": set()})

        target_names = set(item["glyph"].name for item in items)
        for item in items:
            item["dependencies"] = self.target_dependencies(item["layers"], target_names)
            item["dependencies"].discard(item["glyph"].name)

        return self.sort_target_glyphs(items)

    def sort_target_glyphs(self, items):
        sorted_items = []
        remaining = list(items)
        processed_names = set()

        while remaining:
            emitted_item = False
            for item in list(remaining):
                if item["dependencies"].issubset(processed_names):
                    sorted_items.append(item)
                    processed_names.add(item["glyph"].name)
                    remaining.remove(item)
                    emitted_item = True

            if not emitted_item:
                sorted_items.extend(remaining)
                break

        return sorted_items

    def target_width_for_layer(self, layer, target_width, mono_width):
        if self.is_positive_mono_master(self.master_for_layer(layer)):
            return mono_width
        return target_width

    def recenter_target_items(self, target_items, target_width, mono_width):
        for item in target_items:
            for layer in item["layers"]:
                layer_target_width = self.target_width_for_layer(layer, target_width, mono_width)
                offset = self.layer_centering_offset(layer, layer_target_width)
                if abs(offset) > 0.001:
                    self.move_target_layer_content(item, layer, offset, target_items)

    def applyCallback(self, sender):
        try:
            target_width = float(self.w.widthInput.get())
        except ValueError:
            from AppKit import NSBeep
            NSBeep()
            print("Error: Invalid width value. Please enter a number.")
            return

        try:
            mono_width = float(self.w.monoWidthInput.get())
        except ValueError:
            from AppKit import NSBeep
            NSBeep()
            print("Error: Invalid MONO width value. Please enter a number.")
            return

        selected_suffixes = [s for s, chk in self.checkboxes.items() if chk.get()]
        if not selected_suffixes:
            print("No suffixes selected.")
            return

        center = self.w.centerGlyphs.get()
        set_key = self.w.setMetricsKey.get()
        disable_align = self.w.disableAutoAlign.get()
        use_layer_width_keys = self.has_positive_mono_masters

        self.font.disableUpdateInterface()

        glyph_count = 0
        layer_count = 0
        mono_layer_count = 0
        try:
            target_items = self.collect_target_glyphs(selected_suffixes)
            for item in target_items:
                glyph = item["glyph"]
                glyph_count += 1

                for layer in item["layers"]:
                    layer_target_width = self.target_width_for_layer(layer, target_width, mono_width)
                    width_key = f"=={int(layer_target_width)}"
                    is_mono_layer = self.is_positive_mono_master(self.master_for_layer(layer))
                    if is_mono_layer:
                        mono_layer_count += 1

                    # Components must be unaligned before their positions can be shifted.
                    if len(layer.components) > 0 and (disable_align or center):
                        for component in layer.components:
                            self.disable_component_alignment(component)

                    offset = self.layer_centering_offset(layer, layer_target_width)

                    if center and abs(offset) > 0.001:
                        self.move_target_layer_content(item, layer, offset, target_items)
                    # Enforce the target width
                    layer.width = layer_target_width
                    layer_count += 1

                    # Use layer-local width keys when MONO masters need a different value,
                    # so a glyph-wide key cannot overwrite their dedicated width.
                    if use_layer_width_keys:
                        layer.widthMetricsKey = width_key if set_key else None

                if use_layer_width_keys:
                    glyph.widthMetricsKey = None
                else:
                    glyph.widthMetricsKey = f"=={int(target_width)}" if set_key else None

            if center:
                self.recenter_target_items(target_items, target_width, mono_width)
        finally:
            self.font.enableUpdateInterface()

        message = f"Successfully applied width {target_width} to {glyph_count} glyphs / {layer_count} layers ({', '.join(selected_suffixes)})."
        if mono_layer_count:
            message += f" Applied MONO width {mono_width} to {mono_layer_count} MONO layers."
        print(message)

        self.w.close()


TabularSpacer()
