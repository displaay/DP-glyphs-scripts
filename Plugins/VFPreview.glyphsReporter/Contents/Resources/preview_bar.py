# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

import objc
import vanilla
from vanilla.vanillaGroup import Group

from AppKit import NSBezierPath, NSColor, NSMakeRect, NSView

try:
	InspectorGroupBase = type(
		"PatchedGroup",
		(Group,),
		{"nsViewClass": objc.lookUpClass("GSInspectorView")},
	)
except Exception:
	InspectorGroupBase = Group


class TextPreviewBarView(NSView):
	def isFlipped(self):
		return True

	def setController_(self, controller):
		self.controller = controller

	def setDrawer_(self, drawer):
		self.drawer = drawer

	def resizeSubviewsWithOldSize_(self, oldSize):
		self.setNeedsDisplay_(True)

	def drawRect_(self, rect):
		NSColor.whiteColor().setFill()
		NSBezierPath.fillRect_(self.bounds())
		drawer = getattr(self, "drawer", None)
		if drawer is None:
			return
		drawer.draw_interpolated_string(self.bounds(), for_panel=True, center=False)


class PreviewBarPanel(object):
	DEFAULT_HEIGHT = 88
	MIN_HEIGHT = 48
	MAX_HEIGHT = 200
	PADDING = 8

	def __init__(self, controller, drawer):
		self.controller = controller
		self.drawer = drawer
		self.shell = None
		self.group = None
		self.preview_view = None
		self._build_once()
		controller.add_listener(self.refresh)

	def preferred_height(self):
		try:
			height = int(self.controller.pref("previewBarHeight") or self.DEFAULT_HEIGHT)
		except Exception:
			height = self.DEFAULT_HEIGHT
		return max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, height))

	def ns_view(self):
		if self.group is None:
			self._build_once()
		return self.group.getNSView()

	def _build_once(self):
		if self.group is not None:
			return

		width = 800
		height = self.preferred_height()
		self.shell = vanilla.Window((width, height), "")
		self.group = InspectorGroupBase((0, 0, width, height))
		self.shell.group = self.group

		self.group.previewBar = vanilla.Group("auto")
		self.preview_view = TextPreviewBarView.alloc().initWithFrame_(
			NSMakeRect(0, 0, width, height)
		)
		self.preview_view.setController_(self.controller)
		self.preview_view.setDrawer_(self.drawer)
		self.group.previewBar.getNSView().addSubview_(self.preview_view)

		self.group.addAutoPosSizeRules([
			"H:|-%i-[previewBar]-%i-|" % (self.PADDING, self.PADDING),
			"V:|-%i-[previewBar]-%i-|" % (self.PADDING, self.PADDING),
		], {})

	def refresh(self):
		if self.preview_view is not None:
			self.preview_view.setNeedsDisplay_(True)


class PreviewBarInspectorController(object):
	def __init__(self, panel):
		self.panel = panel

	def view(self):
		return self.panel.ns_view()

	def preferredMinimumHeight(self):
		return self.panel.preferred_height()

	def preferredMaximumHeight(self):
		return self.preferredMinimumHeight()
