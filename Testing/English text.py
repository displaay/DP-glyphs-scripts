# MenuTitle: English text
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from __future__ import division, print_function, unicode_literals

__doc__ = """
Opens random English proofing text in the current Edit tab, or in a new tab if
no Edit tab is open. Each sample includes varied English text for quick text
testing.
"""

import random

from GlyphsApp import Glyphs, Message


SCRIPT_NAME = "English text"
DEFAULTS_KEY = "com.displaay.testing.EnglishText.lastIndex"

OPENERS = [
	"After a bright morning, the editor packed a quick note for every branch office",
	"Before the quiet lecture began, six curious students fixed the projector",
	"During the yearly market, an agile baker sold warm rolls beside the river",
	"Every careful designer checked the awkward spacing before the final review",
	"From the upper balcony, visitors noticed a hazy skyline and moving traffic",
	"In a narrow studio, the printer hummed while fresh proofs covered the table",
	"Just beyond the old station, a velvet banner marked the public garden",
	"Many honest workers gathered early, carrying boxes, charts, and coffee",
	"On Tuesday evening, a local writer mailed a lively column to the paper",
	"Quietly, the young archivist labeled folders, journals, tickets, and maps",
	"Several musicians adjusted brass, wood, and nylon parts before rehearsal",
	"The brave pilot watched a golden horizon above clouds and empty fields",
	"Under a glass roof, people compared colors, weights, prices, and dates",
	"With exact timing, the host welcomed every guest and answered quick questions",
	"Yesterday the museum opened a compact exhibit about machines and memory",
	"A friendly judge explained the rule, then invited both teams to continue",
	"Because the workshop was full, extra chairs appeared along the side wall",
	"Calm voices filled the room while a blue notebook passed from hand to hand",
	"Downstairs, the cafe served orange cake, black tea, and sparkling water",
	"Each weekend, families crossed the square to visit the library and cinema",
]

MIDDLES = [
	"Numbers like 12, 48, and 305 were circled in red ink",
	"Someone asked, \"Will the final copy arrive before 6:30?\"",
	"The answer was simple: adjust, compare, print, and repeat",
	"A small note said, 'Keep the margins even, but leave room for captions'",
	"The headline used capitals, lowercase text, figures, and sharp punctuation",
	"A second paragraph tested commas, periods, quotes, and question marks",
	"The sample included quick words such as jazz, voxel, glyph, and quiz",
	"Proofs moved from table to table; everyone marked one or two details",
	"The final page needed balance, rhythm, texture, and a little patience",
	"An invoice listed $24.50, 18%, and reference code AX-719",
	"Several names appeared together: Alice, Omar, Vivian, Xavier, and Zoe",
	"The room became quiet when the first clean print rolled out",
	"An old sign read: Open daily, 9-5, rain or shine",
	"The layout changed again, but the message stayed clear and useful",
	"Each line mixed narrow forms, round letters, diagonals, and terminals",
	"The visitor wrote a note on page 7, paragraph 3, line 12",
	"A careful proof can reveal color, fit, rhythm, and spacing at once",
	"Fresh paper, dark ink, and patient eyes made the difference",
	"The team checked email, labels, captions, menus, and small print",
	"Even the shortest words helped expose awkward joins and uneven gaps",
]

DETAILS = [
	"because the page needed a steady texture at several different sizes",
	"while the team compared the dark spots, open counters, and loose spaces",
	"so the proof would show how ordinary words behave in a longer paragraph",
	"as the afternoon light changed across the table and the notes",
	"before anyone decided which small corrections were actually worth keeping",
	"although the first version already looked calm from a comfortable distance",
	"because narrow letters, round letters, and diagonal strokes needed equal attention",
	"while the same sentence was read aloud, marked, and checked again",
	"so every change could be judged inside a believable piece of text",
	"as several quiet details began to stand out between familiar words",
]

CLOSERS = [
	"Finally, everyone signed off with a quick smile.",
	"Nothing felt rushed, and the page remained easy to read.",
	"The next revision was cleaner, warmer, and more confident.",
	"By noon, the whole set was ready for another careful pass.",
	"Such ordinary sentences are useful when the alphabet needs exercise.",
	"The result looked balanced across wide, narrow, dark, and light shapes.",
	"One more printout proved that the changes were worth keeping.",
	"The proof stayed plain enough to judge without distraction.",
	"A good text sample should feel natural, not merely mechanical.",
	"That small routine saved the team from several late surprises.",
	"Line by line, the texture became steadier and easier to trust.",
	"Good spacing made the paragraph feel calm at every size.",
	"Even quick checks became clearer with varied words and punctuation.",
	"The work ended with notes for tomorrow and a tidy stack of pages.",
	"After that, the editor chose tea, silence, and one last look.",
	"The story was simple, but the letters had plenty to do.",
	"Across the page, ascenders, descenders, bowls, and diagonals all appeared.",
	"A useful specimen asks the typeface to solve many small problems.",
	"The best proof is ordinary enough to show extraordinary details.",
	"Every run should offer a new voice and a different texture.",
]

ENDING_DETAILS = [
	"with enough length to reveal spacing that shorter samples often hide",
	"while still feeling like something a person might actually read",
	"and the paragraph gave the letters more room to settle into rhythm",
	"so the final impression depended on texture rather than isolated characters",
	"with punctuation and word shapes appearing naturally inside the sentence",
	"and every line carried a slightly different balance of width and color",
	"while the proof remained simple enough for quick decisions",
	"so the reader could judge comfort, density, and pace together",
	"and the ordinary language made awkward details easier to notice",
	"with a longer sentence giving the typeface a fairer little workout",
]


def build_text_variants():
	texts = []
	for index in range(100):
		opener = OPENERS[index % len(OPENERS)]
		middle = MIDDLES[(index * 7) % len(MIDDLES)]
		closer = CLOSERS[(index * 13) % len(CLOSERS)]
		second_middle = MIDDLES[(index * 11 + 3) % len(MIDDLES)]
		detail = DETAILS[(index * 5) % len(DETAILS)]
		ending_detail = ENDING_DETAILS[(index * 3) % len(ENDING_DETAILS)]
		title = "Proof %03i" % (index + 1)
		texts.append(
			"%s\n%s, %s. %s. %s. %s, %s."
			% (title, opener, detail, middle, second_middle, closer.rstrip("."), ending_detail)
		)
	return texts


TEXT_VARIANTS = build_text_variants()


def stored_last_index():
	try:
		return int(Glyphs.defaults[DEFAULTS_KEY])
	except Exception:
		return None


def store_last_index(index):
	try:
		Glyphs.defaults[DEFAULTS_KEY] = index
	except Exception:
		pass


def random_variant():
	indexes = list(range(len(TEXT_VARIANTS)))
	last_index = stored_last_index()
	if last_index in indexes and len(indexes) > 1:
		indexes.remove(last_index)
	index = random.choice(indexes)
	store_last_index(index)
	return TEXT_VARIANTS[index]


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
	show_text(font, random_variant())


main()
