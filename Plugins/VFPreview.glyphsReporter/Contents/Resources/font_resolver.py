# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals

from GlyphsApp import Glyphs


def resolve_font(plugin, layer=None):
	font = Glyphs.font
	if font is not None:
		return font

	if layer is not None:
		try:
			glyph = layer.parent
			if glyph is not None:
				font = glyph.parent
				if font is not None:
					return font
		except Exception:
			pass

	controller = getattr(plugin, "controller", None)
	if controller is not None:
		for accessor in ("font", "font_"):
			try:
				candidate = getattr(controller, accessor, None)
				if callable(candidate):
					font = candidate()
				else:
					font = candidate
				if font is not None:
					return font
			except Exception:
				pass

	return None


def font_storage_key(font):
	if font is None:
		return None
	for attr in ("filepath", "filePath", "path"):
		try:
			value = getattr(font, attr, None)
			if value:
				return str(value)
		except Exception:
			pass
	try:
		parent = getattr(font, "parent", None)
		if parent is not None:
			for attr in ("filePath", "filepath", "path"):
				value = getattr(parent, attr, None)
				if value:
					return str(value)
	except Exception:
		pass
	try:
		name = font.familyName
		if name:
			return str(name)
	except Exception:
		pass
	try:
		return str(font.masters[0].id)
	except Exception:
		return str(id(font))
