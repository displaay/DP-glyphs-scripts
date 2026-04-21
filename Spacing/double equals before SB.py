# MenuTitle: Set == Sidebearings with Mono Check
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals
import vanilla

class SetDoubleEqualsMetrics(object):
	def __init__(self):
		self.w = vanilla.FloatingWindow((320, 190), "Set == Sidebearings")
		
		# UI Elements
		self.w.allMasters = vanilla.CheckBox((15, 15, -15, 20), "Apply to all masters", value=False)
		self.w.allGlyphs = vanilla.CheckBox((15, 45, -15, 20), "Apply to all glyphs in font", value=False)
		
		# New Mono Checkbox
		self.w.skipMono = vanilla.CheckBox((15, 75, -15, 20), "Skip masters where Mono >= 1", value=True)
		
		self.w.runButton = vanilla.Button((15, -45, -15, 20), "Apply '==' Metrics", callback=self.process)
		self.w.open()

	def is_mono_master(self, font, master):
		"""Checks if the master is considered 'Monospaced' based on the MONO axis."""
		mono_axis_index = -1
		
		# Find the index of the axis with the 'MONO' tag
		for i, axis in enumerate(font.axes):
			if axis.axisTag == "MONO":
				mono_axis_index = i
				break
		
		if mono_axis_index != -1:
			# Check the value of this master on that axis
			mono_value = master.axes[mono_axis_index]
			# Threshold: If 1 or higher (handles 0-1 or 0-100 scales), we call it Mono
			if mono_value >= 1:
				return True
		return False

	def update_metrics(self, layer):
		# Left Sidebearing
		if layer.leftMetricsKey:
			current_key = layer.leftMetricsKey.lstrip("=")
			layer.leftMetricsKey = "==" + current_key
		else:
			layer.leftMetricsKey = "==" + str(int(layer.LSB))
			
		# Right Sidebearing
		if layer.rightMetricsKey:
			current_key = layer.rightMetricsKey.lstrip("=")
			layer.rightMetricsKey = "==" + current_key
		else:
			layer.rightMetricsKey = "==" + str(int(layer.RSB))
			
		layer.syncMetrics()

	def process(self, sender):
		font = Glyphs.font
		if font is None:
			return

		# Determine glyph set
		if self.w.allGlyphs.get():
			glyphs_to_process = font.glyphs
		else:
			glyphs_to_process = [l.parent for l in font.selectedLayers]

		font.disableUpdateInterface()
		if font.parent:
			font.parent.undoManager().beginUndoGrouping()

		try:
			for glyph in glyphs_to_process:
				if self.w.allMasters.get():
					for layer in glyph.layers:
						# Only process if it's a master layer (skip brackets/braces for now)
						master = font.masters[layer.associatedMasterId]
						if self.w.skipMono.get() and self.is_mono_master(font, master):
							continue # Skip this master
						
						# Only update if it's a master layer or a special layer
						if layer.isMasterLayer or layer.isSpecialLayer:
							self.update_metrics(layer)
				else:
					# Active master only
					active_master = font.selectedFontMaster
					if self.w.skipMono.get() and self.is_mono_master(font, active_master):
						print("Skipping active master: Monospaced.")
					else:
						layer = glyph.layers[active_master.id]
						self.update_metrics(layer)
				
		except Exception as e:
			print(e)
		
		finally:
			if font.parent:
				font.parent.undoManager().endUndoGrouping()
			font.enableUpdateInterface()
			
		print("Done.")

SetDoubleEqualsMetrics()