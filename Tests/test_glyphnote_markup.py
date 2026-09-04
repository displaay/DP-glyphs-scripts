import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(
    ROOT, "Plugins", "GlyphNote.glyphsPalette", "Contents", "Resources"
)
sys.path.insert(0, RESOURCES)

from glyphnote.markup import (  # noqa: E402
    KIND_BOLD,
    KIND_ITALIC,
    KIND_STRIKE,
    FLAG_BOLD,
    FLAG_ITALIC,
    FLAG_MARKER,
    FLAG_STRIKE,
    StyleRun,
    display_from_markup,
    markup_style_runs,
    parse_note_markup,
    python_index_to_utf16,
    style_runs_from_plist,
    style_runs_from_storage,
    style_runs_to_plist,
    style_runs_to_storage,
    toggle_style_runs,
    trim_note_styles,
    utf16_index_to_python,
)


class ParseMarkupTests(unittest.TestCase):
    def test_plain_text_has_no_matches(self):
        self.assertEqual(parse_note_markup(""), [])
        self.assertEqual(parse_note_markup("just a note"), [])

    def test_bold_italic_and_strike(self):
        text = "*bold* _italic_ ~~gone~~"
        kinds = [match.kind for match in parse_note_markup(text)]
        self.assertEqual(kinds, [KIND_BOLD, KIND_ITALIC, KIND_STRIKE])
        bold, italic, strike = parse_note_markup(text)
        self.assertEqual(text[bold.inner_start : bold.inner_end], "bold")
        self.assertEqual(text[italic.inner_start : italic.inner_end], "italic")
        self.assertEqual(text[strike.inner_start : strike.inner_end], "gone")

    def test_unmatched_markers_stay_literal(self):
        self.assertEqual(parse_note_markup("*oops"), [])
        self.assertEqual(parse_note_markup("_oops"), [])
        self.assertEqual(parse_note_markup("~~oops"), [])
        self.assertEqual(parse_note_markup("**"), [])

    def test_underscore_in_identifiers_is_not_italic(self):
        self.assertEqual(parse_note_markup("file_name_here"), [])

    def test_italic_still_matches_at_word_edges(self):
        text = "see _italic_ now"
        matches = parse_note_markup(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(text[matches[0].inner_start : matches[0].inner_end], "italic")

    def test_markup_does_not_span_newlines(self):
        self.assertEqual(parse_note_markup("*two\nlines*"), [])
        self.assertEqual(parse_note_markup("~~two\nlines~~"), [])

    def test_overlapping_kinds_are_both_reported(self):
        text = "*~~both~~*"
        kinds = {match.kind for match in parse_note_markup(text)}
        self.assertEqual(kinds, {KIND_BOLD, KIND_STRIKE})

    def test_overlapping_kinds_combine_flags(self):
        runs = markup_style_runs("*~~x~~*")
        inner = [flags for start, end, flags in runs if "x" in "*~~x~~*"[start:end]]
        self.assertTrue(inner)
        self.assertEqual(inner[0] & FLAG_BOLD, FLAG_BOLD)
        self.assertEqual(inner[0] & FLAG_STRIKE, FLAG_STRIKE)
        marker_flags = [flags for _start, _end, flags in runs if flags & FLAG_MARKER]
        self.assertTrue(marker_flags)


class DisplayFromMarkupTests(unittest.TestCase):
    def test_strips_markers_and_keeps_style(self):
        plain, runs = display_from_markup("*bold*")
        self.assertEqual(plain, "bold")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0], StyleRun(0, 4, FLAG_BOLD))

    def test_strips_all_marker_kinds(self):
        plain, runs = display_from_markup("*bold* _italic_ ~~gone~~")
        self.assertEqual(plain, "bold italic gone")
        flags = {plain[run.start : run.end]: run.flags for run in runs}
        self.assertEqual(flags["bold"], FLAG_BOLD)
        self.assertEqual(flags["italic"], FLAG_ITALIC)
        self.assertEqual(flags["gone"], FLAG_STRIKE)

    def test_overlapping_markup_combines_on_plain_text(self):
        plain, runs = display_from_markup("*~~x~~*")
        self.assertEqual(plain, "x")
        self.assertEqual(runs[0].flags, FLAG_BOLD | FLAG_STRIKE)

    def test_unmatched_markers_remain_visible(self):
        plain, runs = display_from_markup("*oops")
        self.assertEqual(plain, "*oops")
        self.assertEqual(runs, [])

    def test_trim_shifts_style_runs(self):
        trimmed, shifted = trim_note_styles(
            "  bold  ", [StyleRun(2, 6, FLAG_BOLD)]
        )
        self.assertEqual(trimmed, "bold")
        self.assertEqual(shifted[0], StyleRun(0, 4, FLAG_BOLD))

    def test_plist_roundtrip(self):
        runs = [StyleRun(0, 4, FLAG_BOLD | FLAG_ITALIC)]
        restored = style_runs_from_plist(style_runs_to_plist(runs))
        self.assertEqual(restored, runs)

    def test_storage_string_roundtrip(self):
        runs = [StyleRun(0, 4, FLAG_BOLD), StyleRun(5, 8, FLAG_ITALIC)]
        token = style_runs_to_storage(runs)
        self.assertEqual(token, "0:4:1;5:8:2")
        self.assertEqual(style_runs_from_storage(token), runs)
        self.assertEqual(style_runs_from_storage(runs), runs)

    def test_toggle_style_runs_is_reversible(self):
        runs = toggle_style_runs([], 0, 4, FLAG_BOLD, 4)
        self.assertEqual(runs, [StyleRun(0, 4, FLAG_BOLD)])
        self.assertEqual(toggle_style_runs(runs, 0, 4, FLAG_BOLD, 4), [])


class Utf16IndexTests(unittest.TestCase):
    def test_bmp_indexes_match(self):
        text = "příliš"
        for index in range(len(text) + 1):
            utf16 = python_index_to_utf16(text, index)
            self.assertEqual(utf16_index_to_python(text, utf16), index)

    def test_emoji_uses_two_utf16_units(self):
        text = "a😀b"
        self.assertEqual(python_index_to_utf16(text, 1), 1)
        self.assertEqual(python_index_to_utf16(text, 2), 3)
        self.assertEqual(utf16_index_to_python(text, 3), 2)


if __name__ == "__main__":
    unittest.main()
