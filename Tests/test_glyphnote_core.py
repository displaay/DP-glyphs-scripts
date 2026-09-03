import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(
    ROOT, "Plugins", "GlyphNote.glyphsPalette", "Contents", "Resources"
)
sys.path.insert(0, RESOURCES)

from glyphnote.core import (  # noqa: E402
    LAYER_NOTE_KEY,
    LOCKED_KEY,
    MASTER_NOTES_KEY,
    PLACEHOLDER_EMPTY_NOTE,
    PLACEHOLDER_EMPTY_NOTES,
    PLACEHOLDER_MULTIPLE,
    PLACEHOLDER_NO_SELECTION,
    GlyphNoteState,
    apply_lock_to_states,
    apply_note_to_states,
    clean_note,
    clear_active_master_note,
    clear_all_notes,
    empty_state,
    get_display_note,
    has_any_note,
    has_visible_note,
    is_locked,
    layer_has_note,
    native_note,
    read_glyph_state,
    selection_display,
    set_display_note,
    set_locked,
    write_glyph_state,
)


LIGHT = "light"
BOLD = "bold"
MASTERS = (LIGHT, BOLD)


class FakeLayer:
    def __init__(self, layer_id, note="", layer_note=None, parent=None):
        self.layerId = layer_id
        self.associatedMasterId = layer_id
        self.note = note
        self.parent = parent
        self.userData = {}
        if layer_note:
            self.userData[LAYER_NOTE_KEY] = layer_note


class FakeGlyph:
    def __init__(self, note="", locked=None, master_notes=None, layer_notes=None):
        self.note = note
        self.userData = {}
        if locked is not None:
            self.userData[LOCKED_KEY] = locked
        if master_notes:
            self.userData[MASTER_NOTES_KEY] = dict(master_notes)
        self.layers = {
            LIGHT: FakeLayer(LIGHT, parent=self),
            BOLD: FakeLayer(BOLD, parent=self),
        }
        for master_id, text in (layer_notes or {}).items():
            self.layers[master_id].userData[LAYER_NOTE_KEY] = text


class CleanNoteTests(unittest.TestCase):
    def test_strips_and_coerces_empty_values(self):
        self.assertEqual(clean_note(None), "")
        self.assertEqual(clean_note("  hello  "), "hello")
        self.assertEqual(clean_note(b"note"), "note")


class LockDefaultTests(unittest.TestCase):
    def test_missing_lock_flag_is_locked(self):
        self.assertTrue(is_locked(empty_state()))
        self.assertTrue(is_locked(GlyphNoteState(note="legacy")))

    def test_explicit_false_is_unlocked(self):
        self.assertFalse(is_locked(GlyphNoteState(locked=False)))
        self.assertFalse(is_locked(GlyphNoteState(locked=0)))


class DisplayNoteTests(unittest.TestCase):
    def test_locked_uses_glyph_note(self):
        state = GlyphNoteState(note="shared", locked=True)
        self.assertEqual(get_display_note(state, LIGHT), "shared")

    def test_unlocked_uses_master_then_layer_then_glyph(self):
        state = GlyphNoteState(
            note="fallback",
            locked=False,
            master_notes={LIGHT: "light note"},
            layer_notes={BOLD: "bold layer"},
        )
        self.assertEqual(get_display_note(state, LIGHT), "light note")
        self.assertEqual(get_display_note(state, BOLD), "bold layer")
        self.assertEqual(
            get_display_note(GlyphNoteState(note="only glyph", locked=False), LIGHT),
            "only glyph",
        )

    def test_set_locked_note_writes_every_master(self):
        state = set_display_note(empty_state(), "one", LIGHT, MASTERS)
        self.assertTrue(is_locked(state))
        self.assertEqual(state.note, "one")
        self.assertEqual(state.master_notes[BOLD], "one")
        self.assertEqual(state.layer_notes[LIGHT], "one")

    def test_set_unlocked_note_writes_only_that_master(self):
        unlocked = set_locked(empty_state(), False, MASTERS, LIGHT)
        state = set_display_note(unlocked, "light only", LIGHT, MASTERS)
        self.assertEqual(get_display_note(state, LIGHT), "light only")
        self.assertEqual(get_display_note(state, BOLD), "")
        self.assertEqual(state.note, "light only")


class LockTransitionTests(unittest.TestCase):
    def test_unlock_copies_shared_note_to_empty_masters(self):
        locked = GlyphNoteState(note="shared", locked=True)
        unlocked = set_locked(locked, False, MASTERS, LIGHT)
        self.assertFalse(is_locked(unlocked))
        self.assertEqual(get_display_note(unlocked, LIGHT), "shared")
        self.assertEqual(get_display_note(unlocked, BOLD), "shared")

    def test_unlock_preserves_existing_master_notes(self):
        state = GlyphNoteState(
            note="shared",
            locked=True,
            master_notes={LIGHT: "light kept", BOLD: "bold kept"},
            layer_notes={LIGHT: "light kept", BOLD: "bold kept"},
        )
        unlocked = set_locked(state, False, MASTERS, LIGHT)
        self.assertEqual(get_display_note(unlocked, LIGHT), "light kept")
        self.assertEqual(get_display_note(unlocked, BOLD), "bold kept")

    def test_lock_uses_active_master_note_for_all(self):
        unlocked = GlyphNoteState(
            locked=False,
            master_notes={LIGHT: "light", BOLD: "bold"},
            layer_notes={LIGHT: "light", BOLD: "bold"},
        )
        locked = set_locked(unlocked, True, MASTERS, BOLD)
        self.assertTrue(is_locked(locked))
        self.assertEqual(locked.note, "bold")
        self.assertEqual(get_display_note(locked, LIGHT), "bold")

    def test_legacy_glyph_note_unlocks_without_data_loss(self):
        legacy = GlyphNoteState(note="imported")
        unlocked = set_locked(legacy, False, MASTERS, LIGHT)
        self.assertEqual(get_display_note(unlocked, LIGHT), "imported")
        self.assertEqual(get_display_note(unlocked, BOLD), "imported")

    def test_lock_from_empty_master_preserves_other_master_note(self):
        unlocked = GlyphNoteState(
            locked=False,
            master_notes={LIGHT: "", BOLD: "bold note"},
            layer_notes={LIGHT: "", BOLD: "bold note"},
        )
        locked = set_locked(unlocked, True, MASTERS, LIGHT)
        self.assertTrue(is_locked(locked))
        self.assertEqual(locked.note, "bold note")
        self.assertEqual(get_display_note(locked, LIGHT), "bold note")
        self.assertEqual(get_display_note(locked, BOLD), "bold note")
        # Unlocking without editing retains the original master notes
        restored = set_locked(locked, False, MASTERS, LIGHT)
        self.assertEqual(get_display_note(restored, BOLD), "bold note")


class ClearNoteTests(unittest.TestCase):
    def test_clear_active_master_clears_all_when_locked(self):
        state = set_display_note(empty_state(), "keep", LIGHT, MASTERS)
        cleared = clear_active_master_note(state, LIGHT, MASTERS)
        self.assertFalse(has_any_note(cleared))

    def test_clear_active_master_clears_one_when_unlocked(self):
        unlocked = set_locked(empty_state(), False, MASTERS, LIGHT)
        with_notes = set_display_note(
            set_display_note(unlocked, "L", LIGHT, MASTERS), "B", BOLD, MASTERS
        )
        cleared = clear_active_master_note(with_notes, LIGHT, MASTERS)
        self.assertEqual(get_display_note(cleared, LIGHT), "")
        self.assertEqual(get_display_note(cleared, BOLD), "B")
        self.assertEqual(native_note(cleared, LIGHT, MASTERS), "B")

    def test_clear_all_notes_removes_everything(self):
        state = set_display_note(empty_state(), "keep", LIGHT, MASTERS)
        cleared = clear_all_notes(state, MASTERS)
        self.assertEqual(cleared.note, "")
        self.assertEqual(cleared.master_notes, {})
        self.assertFalse(has_visible_note(cleared, LIGHT))


class NativeNoteTests(unittest.TestCase):
    def test_unlocked_native_note_falls_back_to_other_master(self):
        unlocked = set_locked(empty_state(), False, MASTERS, LIGHT)
        state = set_display_note(unlocked, "bold only", BOLD, MASTERS)
        self.assertEqual(native_note(state, LIGHT, MASTERS), "bold only")
        self.assertTrue(has_any_note(state))
        self.assertFalse(has_visible_note(state, LIGHT))


class SelectionDisplayTests(unittest.TestCase):
    def test_no_selection(self):
        display = selection_display([], LIGHT, "Light")
        self.assertFalse(display.has_selection)
        self.assertEqual(display.placeholder, PLACEHOLDER_NO_SELECTION)
        self.assertEqual(display.master_name, "Light")

    def test_same_notes(self):
        states = [
            set_display_note(empty_state(), "same", LIGHT, MASTERS),
            set_display_note(empty_state(), "same", LIGHT, MASTERS),
        ]
        display = selection_display(states, LIGHT)
        self.assertEqual(display.text, "same")
        self.assertFalse(display.mixed_notes)
        self.assertTrue(display.locked)

    def test_multiple_values(self):
        states = [
            set_display_note(empty_state(), "A", LIGHT, MASTERS),
            set_display_note(empty_state(), "B", LIGHT, MASTERS),
        ]
        display = selection_display(states, LIGHT)
        self.assertEqual(display.text, "")
        self.assertTrue(display.mixed_notes)
        self.assertEqual(display.placeholder, PLACEHOLDER_MULTIPLE)

    def test_mixed_lock(self):
        locked = set_display_note(empty_state(), "A", LIGHT, MASTERS)
        unlocked = set_locked(locked, False, MASTERS, LIGHT)
        display = selection_display([locked, unlocked], LIGHT)
        self.assertTrue(display.mixed_lock)
        self.assertFalse(display.locked)

    def test_empty_placeholders(self):
        one = selection_display([empty_state()], LIGHT)
        many = selection_display([empty_state(), empty_state()], LIGHT)
        self.assertEqual(one.placeholder, PLACEHOLDER_EMPTY_NOTE)
        self.assertEqual(many.placeholder, PLACEHOLDER_EMPTY_NOTES)


class BatchApplyTests(unittest.TestCase):
    def test_apply_note_and_lock_to_states(self):
        states = [empty_state(), empty_state()]
        noted = apply_note_to_states(states, "batch", LIGHT, MASTERS)
        self.assertEqual(noted[1].note, "batch")
        unlocked = apply_lock_to_states(noted, False, MASTERS, LIGHT)
        self.assertFalse(is_locked(unlocked[0]))
        self.assertEqual(get_display_note(unlocked[1], BOLD), "batch")


class GlyphRoundTripTests(unittest.TestCase):
    def test_reads_legacy_glyph_note(self):
        glyph = FakeGlyph(note="from list view")
        state = read_glyph_state(glyph, MASTERS)
        self.assertTrue(is_locked(state))
        self.assertEqual(get_display_note(state, LIGHT), "from list view")

    def test_write_then_read_roundtrip(self):
        glyph = FakeGlyph()
        unlocked = set_locked(empty_state(), False, MASTERS, LIGHT)
        state = set_display_note(
            set_display_note(unlocked, "L", LIGHT, MASTERS), "B", BOLD, MASTERS
        )
        write_glyph_state(glyph, state, MASTERS)
        loaded = read_glyph_state(glyph, MASTERS)
        self.assertFalse(is_locked(loaded))
        self.assertEqual(get_display_note(loaded, LIGHT), "L")
        self.assertEqual(get_display_note(loaded, BOLD), "B")
        self.assertEqual(glyph.layers[LIGHT].userData[LAYER_NOTE_KEY], "L")
        self.assertEqual(glyph.userData[LOCKED_KEY], False)

    def test_empty_note_clears_native_glyph_note(self):
        glyph = FakeGlyph(note="old")
        write_glyph_state(glyph, empty_state(), MASTERS)
        self.assertIsNone(glyph.note)
        self.assertNotIn(MASTER_NOTES_KEY, glyph.userData)
        self.assertNotIn(LAYER_NOTE_KEY, glyph.layers[LIGHT].userData)

    def test_layer_has_note_follows_lock_and_master(self):
        glyph = FakeGlyph()
        unlocked = set_locked(empty_state(), False, MASTERS, LIGHT)
        state = set_display_note(unlocked, "only light", LIGHT, MASTERS)
        write_glyph_state(glyph, state, MASTERS)
        self.assertTrue(layer_has_note(glyph.layers[LIGHT], glyph))
        self.assertFalse(layer_has_note(glyph.layers[BOLD], glyph))

        locked = set_locked(state, True, MASTERS, LIGHT)
        write_glyph_state(glyph, locked, MASTERS)
        self.assertTrue(layer_has_note(glyph.layers[BOLD], glyph))


if __name__ == "__main__":
    unittest.main()
