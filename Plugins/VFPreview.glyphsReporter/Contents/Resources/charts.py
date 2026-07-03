# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import math

try:
	from AppKit import (
		NSAttributedString,
		NSBezierPath,
		NSColor,
		NSFont,
		NSFontAttributeName,
		NSForegroundColorAttributeName,
		NSMakeRect,
		NSView,
	)
except Exception:
	NSView = object
	NSAttributedString = None


def make_color(red, green, blue, alpha=1.0):
	return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, alpha)


def draw_text(text, point, font, color):
	if NSAttributedString is None:
		return
	attrs = {
		NSFontAttributeName: font,
		NSForegroundColorAttributeName: color,
	}
	label = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
	label.drawAtPoint_(point)


class MasterChartView(NSView):
	def isFlipped(self):
		return True

	def setEntries_(self, entries):
		self.entries = entries or []
		self.setNeedsDisplay_(True)

	def setMode_(self, mode):
		self.mode = mode or "bar"
		self.setNeedsDisplay_(True)

	def drawRect_(self, rect):
		entries = getattr(self, "entries", [])
		if not entries:
			return
		if getattr(self, "mode", "bar") == "radar":
			self.draw_radar(entries)
		else:
			self.draw_bars(entries)

	def draw_bars(self, entries):
		width = self.bounds().size.width
		height = self.bounds().size.height
		label_width = min(90.0, width * 0.35)
		bar_left = label_width + 8.0
		bar_width = max(10.0, width - bar_left - 36.0)
		row_height = max(16.0, height / max(len(entries), 1))

		NSColor.colorWithCalibratedWhite_alpha_(0.92, 1.0).setFill()
		NSBezierPath.fillRect_(NSMakeRect(0, 0, width, height))

		font = NSFont.systemFontOfSize_(10)
		for index, entry in enumerate(entries):
			y = index * row_height + 2.0
			name = entry.get("name", "")
			percent = entry.get("percent", 0.0)
			color = entry.get("color", (0.5, 0.5, 0.5))

			draw_text(name, (4, y + 2), font, NSColor.darkGrayColor())

			track = NSMakeRect(bar_left, y + 4, bar_width, row_height - 8)
			NSColor.colorWithCalibratedWhite_alpha_(0.82, 1.0).setFill()
			NSBezierPath.fillRect_(track)

			fill_width = bar_width * max(0.0, min(100.0, percent)) / 100.0
			fill = NSMakeRect(bar_left, y + 4, fill_width, row_height - 8)
			make_color(color[0], color[1], color[2], 0.85).setFill()
			NSBezierPath.fillRect_(fill)

			label = "%i%%" % int(round(percent))
			draw_text(label, (bar_left + bar_width + 4, y + 2), font, NSColor.blackColor())

	def draw_radar(self, entries):
		width = self.bounds().size.width
		height = self.bounds().size.height
		center_x = width / 2.0
		center_y = height / 2.0
		radius = min(width, height) * 0.34
		count = len(entries)

		NSColor.colorWithCalibratedWhite_alpha_(0.95, 1.0).setFill()
		NSBezierPath.fillRect_(NSMakeRect(0, 0, width, height))

		for ring in (0.25, 0.5, 0.75, 1.0):
			path = NSBezierPath.bezierPath()
			for index in range(count + 1):
				angle = (math.pi * 2.0 * index / count) - math.pi / 2.0
				x = center_x + math.cos(angle) * radius * ring
				y = center_y + math.sin(angle) * radius * ring
				if index == 0:
					path.moveToPoint_((x, y))
				else:
					path.lineToPoint_((x, y))
			NSColor.colorWithCalibratedWhite_alpha_(0.82, 1.0).setStroke()
			path.stroke()

		polygon = NSBezierPath.bezierPath()
		for index, entry in enumerate(entries):
			percent = entry.get("percent", 0.0) / 100.0
			angle = (math.pi * 2.0 * index / count) - math.pi / 2.0
			x = center_x + math.cos(angle) * radius * percent
			y = center_y + math.sin(angle) * radius * percent
			if index == 0:
				polygon.moveToPoint_((x, y))
			else:
				polygon.lineToPoint_((x, y))
		polygon.closePath()
		NSColor.colorWithCalibratedRed_green_blue_alpha_(0.18, 0.42, 0.88, 0.25).setFill()
		polygon.fill()
		NSColor.colorWithCalibratedRed_green_blue_alpha_(0.18, 0.42, 0.88, 0.8).setStroke()
		polygon.setLineWidth_(1.2)
		polygon.stroke()

		font = NSFont.systemFontOfSize_(9)
		for index, entry in enumerate(entries):
			angle = (math.pi * 2.0 * index / count) - math.pi / 2.0
			x = center_x + math.cos(angle) * (radius + 12)
			y = center_y + math.sin(angle) * (radius + 12)
			color = entry.get("color", (0.3, 0.3, 0.3))
			name = entry.get("name", "")
			draw_text(name, (x - 20, y - 5), font, make_color(color[0], color[1], color[2], 1.0))
