#MenuTitle: Optical Center in Width
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Centers selected glyphs inside their current advance width.

The script estimates the horizontal center of ink by sampling filled
horizontal slices through each layer. In mono workflows it keeps geometric
centering as the priority and uses the sampled ink center only as a small
optional nudge.
"""

import vanilla
from GlyphsApp import Glyphs


class OpticalCenterInWidth(object):
	MAX_OPTICAL_NUDGE = 8.0

	def __init__(self):
		self.font = Glyphs.font
		if not self.font:
			self.beep()
			print("Optical Center in Width: Please open a font first.")
			return

		self.has_mono_axis = self.get_mono_axis_index() is not None

		self.w = vanilla.FloatingWindow((420, 510), "Optical Center in Width")

		y = 15
		self.w.glyphScopeLabel = vanilla.TextBox((15, y, -15, 18), "Glyphs")
		y += 22
		self.w.glyphScope = vanilla.RadioGroup((25, y, -15, 44), ["Selected glyphs", "All glyphs"])
		self.w.glyphScope.set(0)

		y += 58
		self.w.masterScopeLabel = vanilla.TextBox((15, y, -15, 18), "Masters")
		y += 22
		self.master_scope_items = ["Current master", "All masters", "MONO masters only"]
		self.w.masterScope = vanilla.RadioGroup((25, y, -15, 66), self.master_scope_items)
		self.w.masterScope.set(2 if self.has_mono_axis else 0)

		y += 82
		self.w.processSpecialLayers = vanilla.CheckBox((15, y, -15, 20), "Include special layers", value=True)
		y += 25
		self.w.disableAutoAlignment = vanilla.CheckBox((15, y, -15, 20), "Disable component auto-alignment", value=False)
		y += 25
		self.w.flattenMetrics = vanilla.CheckBox((15, y, -15, 20), "Flatten LSB/RSB metrics on processed layers", value=False)
		y += 25
		self.w.keepMonoSidebearingsPositive = vanilla.CheckBox((15, y, -15, 20), "Avoid negative sidebearings in MONO masters", value=True)

		y += 36
		self.w.strengthLabel = vanilla.TextBox((15, y, 155, 20), "Optical strength:")
		self.w.strengthInput = vanilla.EditText((175, y - 2, 55, 22), "0")
		self.w.strengthSuffix = vanilla.TextBox((235, y, 50, 20), "%")

		y += 30
		self.w.samplesLabel = vanilla.TextBox((15, y, 155, 20), "Vertical samples:")
		self.w.samplesInput = vanilla.EditText((175, y - 2, 55, 22), "80")

		y += 30
		self.w.maxShiftLabel = vanilla.TextBox((15, y, 155, 20), "Max shift:")
		self.w.maxShiftInput = vanilla.EditText((175, y - 2, 55, 22), "120")
		self.w.maxShiftSuffix = vanilla.TextBox((235, y, 70, 20), "units")

		y += 30
		self.w.minShiftLabel = vanilla.TextBox((15, y, 155, 20), "Ignore shifts below:")
		self.w.minShiftInput = vanilla.EditText((175, y - 2, 55, 22), "0.5")
		self.w.minShiftSuffix = vanilla.TextBox((235, y, 70, 20), "units")

		y += 34
		self.w.roundShifts = vanilla.CheckBox((15, y, -15, 20), "Round shifts to whole units", value=True)
		y += 25
		self.w.dryRun = vanilla.CheckBox((15, y, -15, 20), "Report only", value=False)

		self.w.runButton = vanilla.Button((15, -42, -15, 22), "Center Optically", callback=self.runCallback)
		self.w.setDefaultButton(self.w.runButton)

		self.w.open()
		self.w.makeKey()

	def beep(self):
		try:
			from AppKit import NSBeep
			NSBeep()
		except Exception:
			pass

	def get_mono_axis_index(self):
		for i, axis in enumerate(self.font.axes):
			axis_tag = getattr(axis, "axisTag", None) or getattr(axis, "tag", None)
			if axis_tag == "MONO":
				return i
		return None

	def layer_master_id(self, layer):
		return getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None)

	def master_for_layer(self, layer):
		master_id = self.layer_master_id(layer)
		if not master_id:
			return None
		for master in self.font.masters:
			if master.id == master_id:
				return master
		return None

	def is_mono_master(self, master):
		mono_axis_index = self.get_mono_axis_index()
		if master is None or mono_axis_index is None:
			return False
		try:
			return float(master.axes[mono_axis_index]) > 0
		except Exception:
			return False

	def is_mono_layer(self, layer):
		return self.is_mono_master(self.master_for_layer(layer))

	def selected_glyphs(self):
		selected_layers = list(self.font.selectedLayers or [])
		glyphs = []
		seen = set()
		for layer in selected_layers:
			glyph = layer.parent
			if glyph is not None and glyph.name not in seen:
				glyphs.append(glyph)
				seen.add(glyph.name)
		return glyphs

	def target_glyphs(self):
		if self.w.glyphScope.get() == 1:
			return list(self.font.glyphs)
		return self.selected_glyphs()

	def target_layers_for_glyph(self, glyph):
		master_scope = self.w.masterScope.get()
		include_special = self.w.processSpecialLayers.get()
		layers = []

		if master_scope == 0:
			layer = glyph.layers[self.font.selectedFontMaster.id]
			if layer is not None:
				layers.append(layer)
			if include_special:
				for candidate in glyph.layers:
					if candidate.isSpecialLayer and self.layer_master_id(candidate) == self.font.selectedFontMaster.id:
						layers.append(candidate)
			return layers

		for layer in glyph.layers:
			if not layer.isMasterLayer and not (include_special and layer.isSpecialLayer):
				continue
			master = self.master_for_layer(layer)
			if master_scope == 2 and not self.is_mono_master(master):
				continue
			layers.append(layer)
		return layers

	def point_x(self, point):
		try:
			return float(point.x)
		except Exception:
			pass
		try:
			return float(point.pointValue().x)
		except Exception:
			pass
		try:
			return float(point[0])
		except Exception:
			return None

	def unique_sorted_xs(self, intersections, x_min, x_max):
		xs = []
		for point in intersections:
			x = self.point_x(point)
			if x is None:
				continue
			if x_min - 1.0 <= x <= x_max + 1.0:
				xs.append(x)

		xs.sort()
		unique_xs = []
		for x in xs:
			if not unique_xs or abs(x - unique_xs[-1]) > 0.01:
				unique_xs.append(x)
		return unique_xs

	def intersections_at_y(self, layer, start_x, end_x, y):
		try:
			return layer.intersectionsBetweenPoints((start_x, y), (end_x, y), True)
		except TypeError:
			pass
		try:
			return layer.intersectionsBetweenPoints((start_x, y), (end_x, y), components=True)
		except TypeError:
			pass
		return layer.intersectionsBetweenPoints((start_x, y), (end_x, y))

	def ink_center_x(self, layer, sample_count):
		bounds = layer.bounds
		if bounds is None or bounds.size.width <= 0 or bounds.size.height <= 0:
			return None

		x_min = float(bounds.origin.x)
		x_max = x_min + float(bounds.size.width)
		y_min = float(bounds.origin.y)
		step = float(bounds.size.height) / sample_count
		start_x = x_min - max(100.0, bounds.size.width)
		end_x = x_max + max(100.0, bounds.size.width)

		total_length = 0.0
		total_moment = 0.0

		for i in range(sample_count):
			y = y_min + (i + 0.5) * step
			try:
				intersections = self.intersections_at_y(layer, start_x, end_x, y)
			except Exception:
				continue

			xs = self.unique_sorted_xs(intersections, x_min, x_max)
			if len(xs) < 2:
				continue
			if len(xs) % 2:
				xs = xs[:-1]

			for j in range(0, len(xs), 2):
				left = xs[j]
				right = xs[j + 1]
				if right <= left:
					continue
				segment_length = right - left
				total_length += segment_length
				total_moment += ((left + right) * 0.5) * segment_length

		if total_length <= 0:
			return x_min + (float(bounds.size.width) * 0.5)

		return total_moment / total_length

	def sidebearing_center_shift(self, layer):
		return (float(layer.RSB) - float(layer.LSB)) * 0.5

	def clamp_to_positive_sidebearings(self, layer, shift):
		left_limit = -float(layer.LSB)
		right_limit = float(layer.RSB)
		if left_limit > right_limit:
			return shift
		return max(left_limit, min(right_limit, shift))

	def clamped_optical_correction(self, layer, strength, sample_count):
		if strength <= 0:
			return 0.0

		bounds = layer.bounds
		if bounds is None or bounds.size.width <= 0:
			return 0.0
		bounds_center = float(bounds.origin.x) + (float(bounds.size.width) * 0.5)
		ink_center = self.ink_center_x(layer, sample_count)
		if ink_center is None:
			return 0.0

		optical_correction = (bounds_center - ink_center) * strength
		return max(-self.MAX_OPTICAL_NUDGE, min(self.MAX_OPTICAL_NUDGE, optical_correction))

	def optical_shift_for_layer(self, layer, strength, sample_count, max_shift, keep_positive_sidebearings, force_sidebearing_guard):
		bounds = layer.bounds
		if bounds is None or bounds.size.width <= 0:
			return None

		shift = self.sidebearing_center_shift(layer)
		shift += self.clamped_optical_correction(layer, strength, sample_count)

		if max_shift > 0:
			shift = max(-max_shift, min(max_shift, shift))
		if keep_positive_sidebearings and (force_sidebearing_guard or self.is_mono_layer(layer)):
			shift = self.clamp_to_positive_sidebearings(layer, shift)
		return shift

	def disable_component_alignment(self, layer):
		for component in layer.components:
			try:
				component.automaticAlignment = False
			except Exception:
				pass
			try:
				component.alignment = -1
			except Exception:
				pass

	def flatten_layer_metrics(self, layer):
		current_width = layer.width
		current_lsb = layer.LSB
		current_rsb = layer.RSB
		try:
			layer.leftMetricsKey = None
		except Exception:
			pass
		try:
			layer.rightMetricsKey = None
		except Exception:
			pass
		try:
			layer.LSB = current_lsb
			layer.width = current_width
			layer.RSB = current_rsb
		except Exception:
			pass

	def apply_shift(self, layer, shift):
		layer.applyTransform((1, 0, 0, 1, shift, 0))

	def float_from_input(self, control, label):
		try:
			return float(control.get())
		except Exception:
			self.beep()
			raise ValueError("Invalid %s value." % label)

	def int_from_input(self, control, label):
		value = self.float_from_input(control, label)
		return int(max(1, round(value)))

	def runCallback(self, sender):
		try:
			strength = self.float_from_input(self.w.strengthInput, "optical strength") / 100.0
			sample_count = self.int_from_input(self.w.samplesInput, "vertical samples")
			max_shift = abs(self.float_from_input(self.w.maxShiftInput, "max shift"))
			min_shift = abs(self.float_from_input(self.w.minShiftInput, "minimum shift"))
		except ValueError as error:
			print("Optical Center in Width:", error)
			return

		if self.w.masterScope.get() == 2 and not self.has_mono_axis:
			self.beep()
			print("Optical Center in Width: No MONO axis found. Choose Current master or All masters.")
			return

		glyphs = self.target_glyphs()
		if not glyphs:
			self.beep()
			print("Optical Center in Width: Please select at least one glyph.")
			return

		round_shifts = self.w.roundShifts.get()
		dry_run = self.w.dryRun.get()
		flatten_metrics = self.w.flattenMetrics.get()
		disable_alignment = self.w.disableAutoAlignment.get()
		keep_positive_sidebearings = self.w.keepMonoSidebearingsPositive.get()
		force_sidebearing_guard = self.w.masterScope.get() == 2

		processed_layers = 0
		shifted_layers = 0
		skipped_layers = 0
		report_lines = []

		self.font.disableUpdateInterface()
		if self.font.parent:
			self.font.parent.undoManager().beginUndoGrouping()

		try:
			for glyph in glyphs:
				for layer in self.target_layers_for_glyph(glyph):
					if layer is None:
						continue
					processed_layers += 1
					shift = self.optical_shift_for_layer(layer, strength, sample_count, max_shift, keep_positive_sidebearings, force_sidebearing_guard)
					if shift is None:
						skipped_layers += 1
						continue
					if round_shifts:
						shift = round(shift)
					if keep_positive_sidebearings and (force_sidebearing_guard or self.is_mono_layer(layer)):
						shift = self.clamp_to_positive_sidebearings(layer, shift)
					if abs(shift) < min_shift:
						continue

					layer_name = getattr(layer, "name", "") or self.layer_master_id(layer) or ""
					report_lines.append("%s / %s: %+0.2f" % (glyph.name, layer_name, shift))

					if not dry_run:
						if disable_alignment:
							self.disable_component_alignment(layer)
						self.apply_shift(layer, shift)
						if flatten_metrics:
							self.flatten_layer_metrics(layer)

					shifted_layers += 1
		finally:
			if self.font.parent:
				self.font.parent.undoManager().endUndoGrouping()
			self.font.enableUpdateInterface()

		if report_lines:
			print("Optical Center in Width shifts:")
			for line in report_lines:
				print(line)

		action = "Would shift" if dry_run else "Shifted"
		message = "%s %i of %i processed layers. Skipped %i empty/unmeasurable layers." % (
			action,
			shifted_layers,
			processed_layers,
			skipped_layers,
		)
		print("Optical Center in Width:", message)
		try:
			Glyphs.showNotification("Optical Center in Width", message)
		except Exception:
			pass

		if not dry_run:
			self.w.close()


OpticalCenterInWidth()
