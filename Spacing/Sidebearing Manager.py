#MenuTitle: Sidebearing manager Displaay
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__="""
Sidebearing manager Displaay - Manages sidebearings, flattens derivative metrics, and handles auto-alignment.
"""

import vanilla
from GlyphsApp import Glyphs

class SidebearingManagerDisplaay:
	def __init__(self):
		self.w = vanilla.FloatingWindow((320, 260), "Sidebearing manager Displaay")

		y = 15
		self.w.allGlyphs = vanilla.CheckBox((15, y, -15, 20), "Apply to All Glyphs (Unchecked = Selected)", value=False)
		y += 25
		self.w.allMasters = vanilla.CheckBox((15, y, -15, 20), "Apply to All Masters (Unchecked = Current)", value=False)

		y += 35
		self.w.lblMod = vanilla.TextBox((15, y, 55, 20), "Modify:")
		self.w.modLSB = vanilla.CheckBox((70, y, 50, 20), "LSB", value=True)
		self.w.modWidth = vanilla.CheckBox((130, y, 60, 20), "Width", value=False)
		self.w.modRSB = vanilla.CheckBox((200, y, 50, 20), "RSB", value=True)

		y += 35
		self.w.delDerivatives = vanilla.CheckBox((15, y, -15, 20), "Delete derivative values (calculate formulas)", value=True)

		y += 25
		self.w.disableAutoAlign = vanilla.CheckBox((15, y, -15, 20), "Disable auto alignment", value=False)

		y += 35
		self.w.runBtn = vanilla.Button((15, y, -15, 20), "Apply Changes", callback=self.runCallback)
		self.w.setDefaultButton(self.w.runBtn)

		self.w.open()

	def runCallback(self, sender):
		font = Glyphs.font
		if not font:
			Glyphs.showNotification("Sidebearing Manager Displaay", "Please open a font first.")
			return

		all_glyphs = self.w.allGlyphs.get()
		all_masters = self.w.allMasters.get()

		mod_lsb = self.w.modLSB.get()
		mod_width = self.w.modWidth.get()
		mod_rsb = self.w.modRSB.get()

		del_derivatives = self.w.delDerivatives.get()
		disable_auto = self.w.disableAutoAlign.get()

		# Determine glyphs to process
		if all_glyphs:
			glyphs = font.glyphs
		else:
			if not font.selectedLayers:
				Glyphs.showNotification("Sidebearing Manager Displaay", "Please select at least one glyph.")
				return
			glyphs = [layer.parent for layer in font.selectedLayers]

		glyphs = list(set(glyphs)) # Remove duplicates

		# Determine masters to process
		if all_masters:
			master_ids = [m.id for m in font.masters]
		else:
			master_ids = [font.selectedFontMaster.id]

		font.disableUpdateInterface()
		try:
			for glyph in glyphs:
				for layer in glyph.layers:
					# Process only the selected masters (this also covers associated special layers)
					if layer.associatedMasterId not in master_ids:
						continue

					# Handle Auto Alignment
					if disable_auto:
						for comp in layer.components:
							comp.alignment = -1 # Disables alignment in Glyphs 3

						# Handle Derivative Sidebearings
					if del_derivatives:
						# Capture the mathematical output before removing the keys
						calc_lsb = layer.LSB
						calc_rsb = layer.RSB
						calc_width = layer.width

						if mod_lsb:
							if glyph.leftMetricsKey:
								glyph.leftMetricsKey = None
							if layer.leftMetricsKey:
								layer.leftMetricsKey = None
							layer.LSB = calc_lsb

						if mod_width:
							if glyph.widthMetricsKey:
								glyph.widthMetricsKey = None
							if layer.widthMetricsKey:
								layer.widthMetricsKey = None
							layer.width = calc_width

						if mod_rsb:
							if glyph.rightMetricsKey:
								glyph.rightMetricsKey = None
							if layer.rightMetricsKey:
								layer.rightMetricsKey = None
							layer.RSB = calc_rsb
		finally:
			font.enableUpdateInterface()
			Glyphs.showNotification("Sidebearing Manager Displaay", "Changes applied successfully!")

SidebearingManagerDisplaay()
