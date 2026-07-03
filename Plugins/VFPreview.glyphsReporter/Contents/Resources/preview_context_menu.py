# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

try:
	from AppKit import NSMenu, NSMenuItem, NSOnState
except Exception:
	NSMenu = NSMenuItem = None
	NSOnState = 1

from axis_utils import exportable_instances


def _checked(pref_value):
	return NSOnState if pref_value else 0


def _add_toggle(menu, title, action, target, checked):
	item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
	item.setTarget_(target)
	item.setState_(_checked(checked))
	menu.addItem_(item)


def _add_action(menu, title, action, target):
	item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
	item.setTarget_(target)
	menu.addItem_(item)


def _add_separator(menu):
	menu.addItem_(NSMenuItem.separatorItem())


def _add_submenu(menu, title, entries, action, target):
	submenu = NSMenu.alloc().init()
	for label, represented_object in entries:
		item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, action, "")
		item.setTarget_(target)
		item.setRepresentedObject_(represented_object)
		submenu.addItem_(item)
	parent = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
	parent.setSubmenu_(submenu)
	menu.addItem_(parent)


def build_preview_panel_menu(controller, target):
	if NSMenu is None or controller is None or controller.font is None:
		return None

	font = controller.font
	menu = NSMenu.alloc().init()

	_add_action(menu, "Preview in Separate Window", "openStandalonePreview_", target)
	_add_separator(menu)
	_add_toggle(
		menu,
		"Draw in Edit View",
		"toggleDrawInEditView_",
		target,
		controller.pref("drawInEditView"),
	)
	_add_toggle(
		menu,
		"Show Preview Nodes",
		"toggleShowPreviewNodes_",
		target,
		controller.pref("showPreviewPanelNodes"),
	)
	_add_toggle(
		menu,
		"Hide Current Layer",
		"toggleHideForeground_",
		target,
		controller.pref("hideForeground"),
	)
	_add_toggle(
		menu,
		"Show Involved Masters",
		"toggleInvolvedMasters_",
		target,
		controller.pref("showInvolvedMasters"),
	)
	_add_separator(menu)
	_add_toggle(
		menu,
		"Center Preview Glyph",
		"toggleCenterPreview_",
		target,
		controller.pref("centerPreview"),
	)
	_add_toggle(
		menu,
		"Link Selected Master",
		"toggleLinkToMaster_",
		target,
		controller.pref("linkToMaster"),
	)
	_add_toggle(
		menu,
		"Round Values",
		"toggleRoundValues_",
		target,
		controller.pref("roundValues"),
	)
	_add_separator(menu)
	_add_action(menu, "Make Instance…", "makeInstanceFromPreview_", target)
	_add_separator(menu)

	master_entries = [("Master: %s" % master.name, "master:%s" % master.id) for master in font.masters]
	if master_entries:
		_add_submenu(menu, "Masters", master_entries, "applyMasterOrInstance_", target)

	instance_entries = [
		(instance.name, "instance:%s" % instance.name)
		for instance in exportable_instances(font)
	]
	if instance_entries:
		_add_submenu(menu, "Instances", instance_entries, "applyMasterOrInstance_", target)

	return menu
