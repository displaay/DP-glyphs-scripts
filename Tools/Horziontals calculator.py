# MenuTitle: Calculate horizontals
# -*- coding: utf-8 -*-
import vanilla

class StemCalculator(object):
    def __init__(self):
        # 1. Fetch values specifically from the Dimensions Palette
        initial_v, initial_h = self.get_dimensions_values()

        self.w = vanilla.FloatingWindow((320, 370), "Stem Contrast & Optical")

        # --- SECTION 1: Reference (Auto-filled from Dimensions Palette) ---
        self.w.lbl_ref_v = vanilla.TextBox((15, 15, 150, 22), "H Vertical Stem:")
        self.w.val_ref_v = vanilla.EditText((165, 12, 140, 22), str(initial_v), callback=self.calculate)

        self.w.lbl_ref_h = vanilla.TextBox((15, 45, 150, 22), "H Horizontal Stem:")
        self.w.val_ref_h = vanilla.EditText((165, 42, 140, 22), str(initial_h), callback=self.calculate)

        # Added: Visual representation of current percentage
        self.w.lbl_ref_pct_title = vanilla.TextBox((15, 75, 150, 22), "Current Contrast:")
        self.w.val_ref_pct = vanilla.TextBox((165, 75, 140, 22), "0%", sizeStyle="small")

        self.w.divider1 = vanilla.HorizontalLine((15, 105, -15, 1))

        # --- INPUT: Target ---
        self.w.lbl_tar_v = vanilla.TextBox((15, 120, 150, 22), "Target Vertical Stem:")
        self.w.val_tar_v = vanilla.EditText((165, 117, 140, 22), "85", callback=self.calculate)

        # --- RESULT 1: Contrast-based ---
        self.w.lbl_tar_h = vanilla.TextBox((15, 150, 150, 22), "Target H (Contrast):")
        self.w.val_tar_h = vanilla.TextBox((165, 150, 140, 22), "")

        self.w.divider2 = vanilla.HorizontalLine((15, 180, -15, 1))

        # --- SECTION 2: Optical Compensation Slider ---
        self.w.lbl_opt_set = vanilla.TextBox((15, 195, 150, 22), "Optical Reduction:")
        self.w.slider_opt = vanilla.Slider((165, 195, 100, 22), minValue=5, maxValue=15, value=10, 
                                           tickMarkCount=11, stopOnTickMarks=True, continuous=True, callback=self.calculate)
        self.w.val_opt_pct = vanilla.TextBox((275, 195, 40, 22), "10%")

        # --- RESULT 2: Optical Equilibrium ---
        self.w.lbl_opt_h = vanilla.TextBox((15, 230, 150, 44), "Target H (Optical Eq.):\n*Based on Target V")
        self.w.val_opt_h = vanilla.TextBox((165, 230, 140, 22), "")

        self.w.divider3 = vanilla.HorizontalLine((15, 275, -15, 1))

        # --- INFO BOX ---
        self.w.info_title = vanilla.TextBox((15, 290, -15, 22), "DESIGN GUIDE:")
        guide_text = "• 5-7%: Heavy/Display (Maintains mass)\n• 10%: Regular/Text (Standard balance)\n• 12-15%: Light/Thin (Prevents clunkiness)"
        self.w.info_body = vanilla.TextBox((15, 310, -15, 50), guide_text, sizeStyle="small")

        self.w.open()
        self.w.makeKey()
        self.calculate(None)

    def get_dimensions_values(self):
        """Extracts HV and HH values from the Dimensions Palette notepad"""
        default_v, default_h = 100, 30
        font = Glyphs.font
        if not font: return default_v, default_h
        master_id = font.selectedFontMaster.id
        dim_data = font.userData.get("GSDimensionPlugin.Dimensions")
        if dim_data and master_id in dim_data:
            master_dims = dim_data[master_id]
            h_v = master_dims.get("HV")
            h_h = master_dims.get("HH")
            if h_v is not None and h_h is not None:
                return h_v, h_h
        return default_v, default_h

    def calculate(self, sender):
        try:
            opt_pct_val = int(round(self.w.slider_opt.get()))
            self.w.val_opt_pct.set(f"{opt_pct_val}%")

            ref_v_raw = self.w.val_ref_v.get()
            ref_h_raw = self.w.val_ref_h.get()
            tar_v_raw = self.w.val_tar_v.get()

            if not ref_v_raw or not ref_h_raw:
                return

            ref_v, ref_h = float(ref_v_raw), float(ref_h_raw)
            
            # --- Update Section 1 Percentage ---
            if ref_v != 0:
                current_ratio_pct = (ref_h / ref_v) * 100
                self.w.val_ref_pct.set(f"{round(current_ratio_pct, 1)}%")
            else:
                self.w.val_ref_pct.set("0%")

            if not tar_v_raw:
                return
            
            tar_v = float(tar_v_raw)

            # Calculation 1: Maintaining the H-Ratio (Contrast)
            if ref_v != 0:
                ratio = ref_h / ref_v
                self.w.val_tar_h.set(str(round(tar_v * ratio, 1)))
            else:
                self.w.val_tar_h.set("Error")

            # Calculation 2: Flat Optical Reduction
            opt_reduction = opt_pct_val / 100.0
            opt_h_result = tar_v * (1.0 - opt_reduction)
            self.w.val_opt_h.set(str(round(opt_h_result, 1)))

        except Exception:
            pass

StemCalculator()