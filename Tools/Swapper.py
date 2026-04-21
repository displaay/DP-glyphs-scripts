# encoding: utf-8
# MenuTitle: Swapper

"""
Swapper.py — Glyphs 3 Script
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


def execute_swap(font, source_glyph, target_name, deep_swap=True):
    """
    Perform a true two-way swap of data between source_glyph and target_name.
    """
    target_glyph = font.glyphs[target_name]
    if target_glyph is None:
        return False, f"Target '{target_name}' not found."

    for src_layer in source_glyph.layers:
        master_id = src_layer.associatedMasterId
        target_layer = target_glyph.layers[master_id]
        if target_layer is None:
            continue

        # 1. BACKUP Target Data
        tgt_shapes_backup = [s.copy() for s in target_layer.shapes]
        tgt_width_backup  = target_layer.width
        if deep_swap:
            tgt_LSB_backup     = target_layer.LSB
            tgt_RSB_backup     = target_layer.RSB
            tgt_anchors_backup = [a.copy() for a in target_layer.anchors]

        # 2. SOURCE -> TARGET
        target_layer.shapes = [s.copy() for s in src_layer.shapes]
        target_layer.width  = src_layer.width
        if deep_swap:
            target_layer.LSB     = src_layer.LSB
            target_layer.RSB     = src_layer.RSB
            target_layer.anchors = [a.copy() for a in src_layer.anchors]

        # 3. TARGET BACKUP -> SOURCE
        src_layer.shapes = tgt_shapes_backup
        src_layer.width  = tgt_width_backup
        if deep_swap:
            src_layer.LSB     = tgt_LSB_backup
            src_layer.RSB     = tgt_RSB_backup
            src_layer.anchors = tgt_anchors_backup

    # 4. Swap Glyph-level attributes (Kerning & Unicode)
    if deep_swap:
        # Backup source kerning & unicode
        src_left_kern  = source_glyph.leftKerningGroup
        src_right_kern = source_glyph.rightKerningGroup
        src_unicode    = source_glyph.unicode

        # Target -> Source
        source_glyph.leftKerningGroup  = target_glyph.leftKerningGroup
        source_glyph.rightKerningGroup = target_glyph.rightKerningGroup
        source_glyph.unicode           = target_glyph.unicode

        # Source Backup -> Target
        target_glyph.leftKerningGroup  = src_left_kern
        target_glyph.rightKerningGroup = src_right_kern
        target_glyph.unicode           = src_unicode

    return True, f"SWAPPED: {source_glyph.name} <-> {target_name}"


# ─────────────────────────────────────────────────────────────────────────────
# DIALOG
# ─────────────────────────────────────────────────────────────────────────────

class SwapperDialog:

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

        self.w = Window((900, 600), "Swapper", minSize=(750, 450))
        self._build_ui()
        self.w.open()
        self._populate_source_list()

    def _build_ui(self):
        w = self.w
        
        # Left Panel -- Source
        w.sourceLabel = TextBox((12, 12, 200, 16), "1. Select Source Suffix", sizeStyle="small")
        w.sourceList  = List(
            (12, 30, 230, -44),
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
        w.targetLabel = TextBox((254, 12, 120, 16), "2. Select Target:", sizeStyle="small")
        w.targetPopup = PopUpButton(
            (364, 10, 160, 20),
            self.target_tags,
            callback=self._update_preview,
            sizeStyle="small"
        )

        w.glyphLabel = TextBox((254, 40, -12, 16), "3. Preview Swaps", sizeStyle="small")
        w.glyphList  = List(
            (254, 58, -12, -130),
            [],
            columnDescriptions=[
                {"title": "Source Glyph", "width": 140},
                {"title": "Target Glyph", "width": 140},
                {"title": "Status",       "width": 140},
            ],
            allowsMultipleSelection=True,
            allowsEmptySelection=True,
        )

        w.rightDivider = HorizontalLine((254, -120, -12, 1))

        w.deepCheck = CheckBox(
            (254, -110, -12, 20),
            "Include metrics (LSB/RSB/width), kerning groups, anchors, and Unicode",
            value=True,
            sizeStyle="small",
        )

        w.swapSelBtn = Button((254, -80, 190, 24), "Swap Selected", callback=self._swap_selected)
        w.swapAllBtn = Button((454, -80, 190, 24), "Swap ALL Valid", callback=self._swap_all)

        w.progress      = ProgressBar((254, -46, 250, 16), isIndeterminate=False)
        w.progressLabel = TextBox((514, -46, -12, 16), "", sizeStyle="small")

        w.mainDivider = HorizontalLine((10, -32, -10, 1))
        w.statusText  = TextBox((12, -24, -12, 18), "Ready.", sizeStyle="small")


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
            return

        source_tag = self.suffix_info[sel[0]]["tag"]
        target_suffix = self._get_current_target_suffix()

        rows = []
        # Find all glyphs carrying the source suffix
        for g in self.font.glyphs:
            if g.name.endswith("." + source_tag):
                base_name = g.name.rsplit("." + source_tag, 1)[0]
                target_name = base_name + target_suffix
                
                if g.name == target_name:
                    status = "⚠️ Source = Target"
                else:
                    target_exists = self.font.glyphs[target_name] is not None
                    status = "✅ Ready" if target_exists else "❌ Target Missing"

                rows.append({
                    "Source Glyph": g.name,
                    "Target Glyph": target_name,
                    "Status": status,
                    "_valid": status == "✅ Ready",
                    "_source": g,
                    "_target_name": target_name
                })
        
        self.w.glyphList.set(rows)
        valid_count = sum(1 for r in rows if r["_valid"])
        self._set_status(f"Found {len(rows)} glyphs. {valid_count} have valid targets.")

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
            self._set_status("No valid targets to swap. Check the Status column.")
            return

        self._do_swap(valid_pairs, self.w.deepCheck.get())

    def _do_swap(self, pair_list, deep):
        total  = len(pair_list)
        errors = []

        self.w.progress.set(0)
        self.w.progressLabel.set("")
        self.font.disableUpdateInterface()

        try:
            for i, (src_g, target_name) in enumerate(pair_list):
                ok, msg = execute_swap(self.font, src_g, target_name, deep_swap=deep)
                if not ok:
                    errors.append(msg)
                    print("Swapper:", msg)
                    
                self.w.progress.set(int((i + 1) / total * 100))
                self.w.progressLabel.set(f"{i + 1} / {total} : {src_g.name}")
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
            self._set_status(f"Success! Swapped {total} pair(s).")

    def _set_status(self, msg):
        self.w.statusText.set(msg)

SwapperDialog()