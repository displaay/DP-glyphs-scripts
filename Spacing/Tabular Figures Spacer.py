#MenuTitle: Tabular Figures Spacer
# -*- coding: utf-8 -*-
__doc__="""
Sets a fixed width for tabular figures (.tf, .tosf, etc.), with options to center, apply metrics keys, and disable component alignment.
"""

import vanilla
import math
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
            print("No tabular figure suffixes found in the font (e.g., .tf, .tosf, .tnum).")
            return
            
        self.suggested_width = self.calculate_widest_tabular()
        
        # --- UI Setup ---
        # Fixed the UI bug: generous base height + dynamic height for suffix checkboxes
        window_height = 230 + (len(self.tabular_suffixes) * 25)
        self.w = vanilla.FloatingWindow((320, window_height), "Tabular Figures Spacer")
        
        y = 15
        self.w.text_1 = vanilla.TextBox((15, y, 120, 20), "Suggested Width:")
        self.w.widthInput = vanilla.EditText((135, y-2, 60, 22), str(self.suggested_width))
        
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
        target_endings = [".tf", ".tosf", ".tnum"]
        
        for glyph in self.font.glyphs:
            parts = glyph.name.split(".")
            if len(parts) > 1:
                suffix = "." + parts[-1]
                if suffix in target_endings:
                    suffixes.add(suffix)
        return sorted(list(suffixes))
        
    def calculate_widest_tabular(self):
        max_width = 0
        for glyph in self.font.glyphs:
            if any(glyph.name.endswith(s) for s in self.tabular_suffixes):
                for layer in glyph.layers:
                    if layer.isMasterLayer or layer.isSpecialLayer:
                        if layer.width > max_width:
                            max_width = layer.width
                            
        return int(math.ceil(max_width))
        
    def applyCallback(self, sender):
        try:
            target_width = float(self.w.widthInput.get())
        except ValueError:
            from AppKit import NSBeep
            NSBeep()
            print("Error: Invalid width value. Please enter a number.")
            return
            
        selected_suffixes = [s for s, chk in self.checkboxes.items() if chk.get()]
        if not selected_suffixes:
            print("No suffixes selected.")
            return
            
        center = self.w.centerGlyphs.get()
        set_key = self.w.setMetricsKey.get()
        disable_align = self.w.disableAutoAlign.get()
        
        self.font.disableUpdateInterface()
        
        count = 0
        for glyph in self.font.glyphs:
            if any(glyph.name.endswith(s) for s in selected_suffixes):
                count += 1
                
                # Apply Metrics Key
                if set_key:
                    glyph.widthMetricsKey = f"=={int(target_width)}"
                else:
                    glyph.widthMetricsKey = None
                
                # Apply to layers
                for layer in glyph.layers:
                    if layer.isMasterLayer or layer.isSpecialLayer:
                        
                        # Disable automatic alignment for components if requested
                        if disable_align and len(layer.components) > 0:
                            for component in layer.components:
                                component.automaticAlignment = False
                        
                        diff = target_width - layer.width
                        
                        if diff != 0:
                            if center:
                                # Distribute the extra space evenly
                                layer.LSB += diff / 2
                            # Enforce the target width
                            layer.width = target_width
                            
        self.font.enableUpdateInterface()
        print(f"Successfully applied width {target_width} to {count} glyphs ({', '.join(selected_suffixes)}).")
        
        self.w.close()

TabularSpacer()