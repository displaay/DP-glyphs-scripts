# MenuTitle: AbCs
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens a compact Latin proofing set in the current Edit tab, or in a new tab if
no Edit tab is open.
"""

import os
import sys

from GlyphsApp import Glyphs, Message

try:
	SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
	if SCRIPT_DIR not in sys.path:
		sys.path.insert(0, SCRIPT_DIR)
except Exception:
	pass

from _stylistic_variants import text_with_stylistic_variants


SCRIPT_NAME = "AbCs"

UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
NUMBERS = "0123456789"

MIXED_CASE = " ".join([letter + letter.lower() for letter in UPPERCASE])
REVERSE_CASE = " ".join([letter.lower() + letter for letter in UPPERCASE])

PROOF_LINES = [
	UPPERCASE,
	LOWERCASE,
	NUMBERS,
	MIXED_CASE,
	REVERSE_CASE,
	"0123456789 00 11 22 33 44 55 66 77 88 99",
	"00 01 02 03 04 05 06 07 08 09 10 11 12",
	"HHH HHO HOH HOO OHH OHO OOH OOO",
	"NNN NNO NON NOO ONN ONO OON OOO",
	"nnn nno non noo onn ono oon ooo",
	"mmm mmo mom moo omm omo oom ooo",
	"AV AW AY AT TA TO Te Ty Va Vo Wa Wo Ya Yo",
	"FA LT LY PA RT RV Ta Te Ti To Tu Ty T. T, T:",
	"ov av aw ay va ve vo wa we wo ya ye yo",
	"ro ry rn rm nm nn mm il li ij ji fj ff fi fl ffi ffl",
	"ace age ago are arm art ear eel eye ice ill ion ore our",
	"AVA TAT VAV WAW YAY OAO HAH NON OHO",
	"Ta. Te, To: Va? Wa! Ya' Fo\" P, F. L'",
	"(Aa) [Bb] {Cc} -Dd- /Ee/ \\Ff\\",
	"'Aa' \"Bb\" Aa-Bb Aa/Bb Aa&Bb Aa@Bb",
	"Áá Àà Ââ Ää Ãã Åå Āā Ąą Ææ Çç Ćć Čč",
	"Ďď Éé Èè Êê Ëë Ěě Ēē Ęę Íí Ìì Îî Ïï",
	"Ĺĺ Ľľ Łł Ńń Ňň Óó Òò Ôô Öö Õõ Őő Øø Œœ",
	"Ŕŕ Řř Śś Šš Ťť Úú Ùù Ûû Üü Ůů Űű Ýý Žž",
	"The quick brown fox jumps over the lazy dog.",
	"Sphinx of black quartz, judge my vow.",
	"Pack my box with five dozen liquor jugs.",
]

PROOF_TEXT = "\n".join(PROOF_LINES)


def current_tab(font):
	tab = getattr(font, "currentTab", None)
	if callable(tab):
		try:
			tab = tab()
		except Exception:
			tab = None
	return tab


def show_text(font, text):
	tab = current_tab(font)
	if tab is not None:
		try:
			tab.text = text
			return
		except Exception:
			pass
		try:
			tab.setText_(text)
			return
		except Exception:
			pass
	font.newTab(text)


def main():
	font = Glyphs.font
	if font is None:
		Message(title=SCRIPT_NAME, message="Open a font and run the script again.")
		return
	show_text(font, text_with_stylistic_variants(font, PROOF_TEXT))


main()
