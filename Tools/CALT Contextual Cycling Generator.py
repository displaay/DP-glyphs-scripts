# MenuTitle: CALT Contextual Cycling Generator
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.
"""
CALT Contextual Cycling Generator for Glyphs 3 & 4
Based on Rainer Erich Scheichelbauer's tutorial:
https://glyphsapp.com/learn/features-part-3-advanced-contextual-alternates
"""

import vanilla
from GlyphsApp import Glyphs, GSClass, GSFeature, Message


class ContextualCyclingGenerator:
    def __init__(self):
        self.w = vanilla.FloatingWindow((420, 520), "CALT Contextual Cycling Generator")

        y = 15
        self.w.labelSuffix = vanilla.TextBox((15, y, -15, 20), "Alternate Suffixes (comma-separated):")
        y += 22
        self.w.suffixes = vanilla.EditText((15, y, -15, 22), ".ss01, .ss02, .ss03")

        y += 35
        self.w.labelMode = vanilla.TextBox((15, y, -15, 20), "Randomization / Cycling Algorithm:")
        y += 25
        self.w.mode = vanilla.RadioGroup((15, y, -15, 80), [
            "1. Simple Sequential Cycling (Consecutive)",
            "2. Consonant / Vowel Gap Cycling (Tutorial Method)",
            "3. Quantum Offset Chaining (Multi-lookup)"
        ], callback=self.modeChanged)
        self.w.mode.set(1) # Default to Mode 2 (Tutorial Method)

        y += 90
        self.w.labelGap = vanilla.TextBox((15, y, -60, 20), "Max Interrupting Letters to Skip (Mode 2):")
        self.w.gapValue = vanilla.TextBox((-45, y, -15, 20), "3")
        y += 22
        self.w.gapSlider = vanilla.Slider((15, y, -15, 20), minValue=1, maxValue=4, value=3, tickMarkCount=4, stopOnTickMarks=True, callback=self.sliderChanged)

        y += 35
        self.w.syncMissing = vanilla.CheckBox((15, y, -15, 20), "Auto-sync missing alternates (Fallback to base)", value=True)

        y += 28
        self.w.createClasses = vanilla.CheckBox((15, y, -15, 20), "Generate OpenType Classes (@DEFAULT, @ALT1, etc.)", value=True)

        y += 28
        self.w.createFeature = vanilla.CheckBox((15, y, -15, 20), "Generate or Replace 'calt' Feature", value=True)

        y += 35
        self.w.status = vanilla.TextBox((15, y, -15, 45), "Ready. Click below to scan font and generate feature code.", sizeStyle="small")

        y += 50
        self.w.generateButton = vanilla.Button((15, -45, -15, 28), "Generate Contextual Cycling", callback=self.generateCallback)

        self.modeChanged(self.w.mode)
        self.w.open()

    def sliderChanged(self, sender):
        self.w.gapValue.set(str(int(sender.get())))

    def modeChanged(self, sender):
        is_mode_2 = (sender.get() == 1)
        self.w.gapSlider.enable(is_mode_2)
        self.w.labelGap.enable(is_mode_2)
        self.w.gapValue.enable(is_mode_2)

    def is_vowel(self, glyph_name):
        clean = glyph_name.split('.')[0].split('_')[0].lower()
        vowels = ('a', 'e', 'i', 'o', 'u', 'y', 'ae', 'oe', 'alpha', 'epsilon', 'eta', 'iota', 'omicron', 'upsilon', 'omega')
        return any(clean == v or clean.startswith(v) for v in vowels)

    def scan_font(self, font, suffix_list, sync_missing):
        base_glyphs = []
        for glyph in font.glyphs:
            if not glyph.export or not glyph.name:
                continue
            if any(glyph.name.endswith(s) for s in suffix_list):
                continue

            alternate_glyphs = [font.glyphs[glyph.name + suffix] for suffix in suffix_list]
            exported_alternates = [alternate and alternate.export for alternate in alternate_glyphs]

            # With fallback enabled, include any family that has an alternate.
            # Without fallback, only complete families produce equal-length classes.
            if any(exported_alternates) and (sync_missing or all(exported_alternates)):
                base_glyphs.append(glyph.name)

        base_glyphs.sort()
        if not base_glyphs:
            return None, None

        # Build synchronized class lists
        class_lists = {0: []}
        for i in range(1, len(suffix_list) + 1):
            class_lists[i] = []

        for base_name in base_glyphs:
            class_lists[0].append(base_name)
            for i, s in enumerate(suffix_list, 1):
                alt_glyph = font.glyphs[base_name + s]
                if alt_glyph and alt_glyph.export:
                    class_lists[i].append(alt_glyph.name)
                else:
                    # scan_font excludes incomplete families when fallback is off.
                    class_lists[i].append(base_name)

        return base_glyphs, class_lists

    def add_or_update_class(self, font, class_name, glyph_names):
        code_str = " ".join([g for g in glyph_names if g])
        existing_class = font.classes[class_name]
        if existing_class:
            existing_class.code = code_str
        else:
            font.classes.append(GSClass(class_name, code_str))

    def add_or_update_feature(self, font, tag, code):
        existing_feature = font.features[tag]
        if existing_feature:
            existing_feature.code = code
        else:
            font.features.append(GSFeature(tag, code))

    def generateCallback(self, sender):
        font = Glyphs.font
        if not font:
            Message("No Font Open", "Please open a font project in Glyphs before running this script.")
            return

        raw_suffixes = self.w.suffixes.get()
        suffix_list = [s.strip() for s in raw_suffixes.split(",") if s.strip()]
        if not suffix_list:
            Message("Invalid Suffixes", "Please enter at least one alternate suffix (e.g. .ss01).")
            return

        sync_missing = self.w.syncMissing.get()
        base_glyphs, class_lists = self.scan_font(font, suffix_list, sync_missing)

        if not base_glyphs:
            detail = "any matching alternates" if sync_missing else "any complete alternate families"
            Message(
                "No Alternates Found",
                f"Could not find {detail} for the suffixes: {', '.join(suffix_list)}",
            )
            return

        mode = self.w.mode.get()
        num_alts = len(suffix_list)
        feature_code = []

        # ==========================================================
        # MODE 0: Simple Sequential Cycling
        # ==========================================================
        if mode == 0:
            if self.w.createClasses.get():
                self.add_or_update_class(font, "DEFAULT", class_lists[0])
                for i in range(1, num_alts + 1):
                    self.add_or_update_class(font, f"ALT{i}", class_lists[i])

            feature_code.append("# Simple Sequential Cycling")
            feature_code.append("sub @DEFAULT @DEFAULT' by @ALT1;")
            for i in range(1, num_alts):
                feature_code.append(f"sub @ALT{i} @DEFAULT' by @ALT{i+1};")

        # ==========================================================
        # MODE 1: Consonant / Vowel Gap Cycling (Tutorial Method)
        # ==========================================================
        elif mode == 1:
            con_indices = [idx for idx, name in enumerate(base_glyphs) if not self.is_vowel(name)]
            voc_indices = [idx for idx, name in enumerate(base_glyphs) if self.is_vowel(name)]

            all_cycling = {name for tier in class_lists.values() for name in tier}
            etc_glyphs = [
                glyph.name
                for glyph in font.glyphs
                if glyph.export and glyph.name and glyph.name not in all_cycling
            ]

            if self.w.createClasses.get():
                # Build Consonant Classes
                if con_indices:
                    for tier in range(num_alts + 1):
                        names = [class_lists[tier][idx] for idx in con_indices]
                        self.add_or_update_class(font, f"Con{tier}", names)

                # Build Vowel Classes
                if voc_indices:
                    for tier in range(num_alts + 1):
                        names = [class_lists[tier][idx] for idx in voc_indices]
                        self.add_or_update_class(font, f"Voc{tier}", names)

                # Build @Etc Class (All remaining export glyphs)
                if etc_glyphs:
                    self.add_or_update_class(font, "Etc", etc_glyphs)

            max_gap = int(self.w.gapSlider.get())
            voc_group_parts = [f"@Voc{i}" for i in range(num_alts + 1)] if voc_indices else []
            con_group_parts = [f"@Con{i}" for i in range(num_alts + 1)] if con_indices else []
            if etc_glyphs:
                voc_group_parts.append("@Etc")
                con_group_parts.append("@Etc")

            # Consonant Rules
            if con_indices:
                feature_code.append("# Consonant Cycling")
                feature_code.append("sub @Con0 @Con0' by @Con1;")
                for i in range(1, num_alts):
                    feature_code.append(f"sub @Con{i} @Con0' by @Con{i+1};")

                if voc_group_parts:
                    voc_group = " ".join(voc_group_parts)
                    for gap in range(1, max_gap + 1):
                        interfering = " ".join([f"[{voc_group}]"] * gap)
                        feature_code.append(f"# Consonant across {gap} interrupting glyphs")
                        feature_code.append(f"sub @Con0 {interfering} @Con0' by @Con1;")
                        for i in range(1, num_alts):
                            feature_code.append(f"sub @Con{i} {interfering} @Con0' by @Con{i+1};")

            # Vowel Rules
            if voc_indices:
                if feature_code:
                    feature_code.append("")
                feature_code.append("# Vowel Cycling")
                feature_code.append("sub @Voc0 @Voc0' by @Voc1;")
                for i in range(1, num_alts):
                    feature_code.append(f"sub @Voc{i} @Voc0' by @Voc{i+1};")

                if con_group_parts:
                    con_group = " ".join(con_group_parts)
                    for gap in range(1, max_gap + 1):
                        interfering = " ".join([f"[{con_group}]"] * gap)
                        feature_code.append(f"# Vowel across {gap} interrupting glyphs")
                        feature_code.append(f"sub @Voc0 {interfering} @Voc0' by @Voc1;")
                        for i in range(1, num_alts):
                            feature_code.append(f"sub @Voc{i} {interfering} @Voc0' by @Voc{i+1};")

        # ==========================================================
        # MODE 2: Quantum Offset Chaining
        # ==========================================================
        elif mode == 2:
            if self.w.createClasses.get():
                self.add_or_update_class(font, "DEFAULT", class_lists[0])
                for i in range(1, num_alts + 1):
                    self.add_or_update_class(font, f"ALT{i}", class_lists[i])

            feature_code.append("# Quantum Offset Chaining (Pass 1: Forward Loop)")
            feature_code.append("lookup CALT_PASS_1 {")
            feature_code.append("    sub @DEFAULT @DEFAULT' by @ALT1;")
            for i in range(1, num_alts):
                feature_code.append(f"    sub @ALT{i} @DEFAULT' by @ALT{i+1};")
            feature_code.append("} CALT_PASS_1;\n")

            if num_alts >= 2:
                feature_code.append("# Quantum Offset Chaining (Pass 2: Pairwise Phase Shift)")
                feature_code.append("lookup CALT_PASS_2 {")
                feature_code.append("    sub @ALT1 @ALT1' by @ALT2;")
                feature_code.append("    sub @ALT2 @ALT2' by @DEFAULT;")
                feature_code.append("} CALT_PASS_2;")

        # Inject into Font
        full_code = "\n".join(feature_code)
        if self.w.createFeature.get():
            self.add_or_update_feature(font, "calt", full_code)

        self.w.status.set(f"Success! Processed {len(base_glyphs)} base glyphs across {num_alts} alternate tiers.")
        print(f"--- CALT Feature Generated Successfully ---\n{full_code}")

ContextualCyclingGenerator()
