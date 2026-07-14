# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

import re


SS_SUFFIX_RE = re.compile(r"^ss\d+$")
TERMINAL_PUNCTUATION = set(".,;:!?…")
TRAILING_PUNCTUATION = set(".,;:!?…'\"”’)]}")

DIGIT_NAMES = {
	"0": "zero",
	"1": "one",
	"2": "two",
	"3": "three",
	"4": "four",
	"5": "five",
	"6": "six",
	"7": "seven",
	"8": "eight",
	"9": "nine",
}

PUNCTUATION_NAMES = {
	" ": "space",
	"!": "exclam",
	'"': "quotedbl",
	"#": "numbersign",
	"$": "dollar",
	"%": "percent",
	"&": "ampersand",
	"'": "quotesingle",
	"(": "parenleft",
	")": "parenright",
	"*": "asterisk",
	"+": "plus",
	",": "comma",
	"-": "hyphen",
	".": "period",
	"/": "slash",
	":": "colon",
	";": "semicolon",
	"<": "less",
	"=": "equal",
	">": "greater",
	"?": "question",
	"@": "at",
	"[": "bracketleft",
	"\\": "backslash",
	"]": "bracketright",
	"{": "braceleft",
	"|": "bar",
	"}": "braceright",
	"„": "quotedblbase",
	"“": "quotedblleft",
	"”": "quotedblright",
	"‘": "quoteleft",
	"’": "quoteright",
	"–": "endash",
	"—": "emdash",
	"…": "ellipsis",
}


def glyph_names(font):
	names = set()
	try:
		for glyph in font.glyphs:
			name = getattr(glyph, "name", None)
			if name:
				names.add(str(name))
	except Exception:
		pass
	return names


def unicode_to_glyph_name(font):
	mapping = {}
	try:
		glyphs = list(font.glyphs)
	except Exception:
		return mapping

	for glyph in glyphs:
		name = getattr(glyph, "name", None)
		if not name:
			continue

		values = []
		try:
			if glyph.unicode:
				values.append(glyph.unicode)
		except Exception:
			pass
		try:
			values.extend(list(glyph.unicodes or []))
		except Exception:
			pass

		for value in values:
			try:
				key = ("%04X" % int(str(value), 16)).upper()
			except Exception:
				continue
			if key not in mapping:
				mapping[key] = str(name)
	return mapping


def stylistic_suffixes(glyph_name_set):
	suffixes = set()
	for name in glyph_name_set:
		for part in name.split(".")[1:]:
			if SS_SUFFIX_RE.match(part):
				suffixes.add(part)
	return sorted(suffixes, key=lambda suffix: int(suffix[2:]))


def unicode_key(character):
	try:
		return ("%04X" % ord(character)).upper()
	except Exception:
		return None


def fallback_name(character, glyph_name_set):
	if character in DIGIT_NAMES and DIGIT_NAMES[character] in glyph_name_set:
		return DIGIT_NAMES[character]
	if character in PUNCTUATION_NAMES and PUNCTUATION_NAMES[character] in glyph_name_set:
		return PUNCTUATION_NAMES[character]
	if character in glyph_name_set:
		return character
	return None


def base_glyph_name(character, unicode_map, glyph_name_set):
	key = unicode_key(character)
	if key and key in unicode_map:
		return unicode_map[key]
	return fallback_name(character, glyph_name_set)


def slash_name(glyph_name):
	return "/" + glyph_name


def is_letter(character):
	try:
		return character.isalpha()
	except Exception:
		return False


def stylistic_text_for_suffix(text, suffix, unicode_map, glyph_name_set):
	pieces = []
	changed = False

	for character in text:
		base_name = base_glyph_name(character, unicode_map, glyph_name_set)
		if not base_name:
			pieces.append(character)
			continue

		variant_name = base_name + "." + suffix
		if is_letter(character) and variant_name in glyph_name_set:
			pieces.append(slash_name(variant_name))
			changed = True
		else:
			pieces.append(slash_name(base_name))

	return "".join(pieces), changed


def stylistic_suffixes_for_text(text, suffixes, unicode_map, glyph_name_set):
	matching_suffixes = []
	for suffix in suffixes:
		for character in text:
			if not is_letter(character):
				continue
			base_name = base_glyph_name(character, unicode_map, glyph_name_set)
			if base_name and base_name + "." + suffix in glyph_name_set:
				matching_suffixes.append(suffix)
				break
	return matching_suffixes


def terminal_suffix(text):
	index = len(text)
	while index > 0 and text[index - 1] in TRAILING_PUNCTUATION:
		index -= 1
	suffix = text[index:]
	if any(character in TERMINAL_PUNCTUATION for character in suffix):
		return suffix
	return ""


def text_with_stylistic_variants(font, text):
	glyph_name_set = glyph_names(font)
	if not glyph_name_set:
		return text

	unicode_map = unicode_to_glyph_name(font)
	suffixes = stylistic_suffixes(glyph_name_set)
	if not suffixes:
		return text

	pieces = []
	for part in re.split(r"(\s+)", text):
		if not part:
			continue
		if part.isspace():
			pieces.append(part)
			continue

		matching_suffixes = stylistic_suffixes_for_text(
			part, suffixes, unicode_map, glyph_name_set
		)
		if not matching_suffixes:
			pieces.append(part)
			continue

		part_terminal_suffix = terminal_suffix(part)
		if part_terminal_suffix:
			pieces.append(part[: -len(part_terminal_suffix)])
		else:
			pieces.append(part)

		for suffix in matching_suffixes:
			variant_text, changed = stylistic_text_for_suffix(
				part, suffix, unicode_map, glyph_name_set
			)
			if changed:
				pieces.append(" " + variant_text)

	return "".join(pieces)
