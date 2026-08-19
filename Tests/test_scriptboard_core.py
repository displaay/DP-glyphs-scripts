import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(
    ROOT, "Plugins", "ScriptBoard.glyphsPalette", "Contents", "Resources"
)
sys.path.insert(0, RESOURCES)

from scriptboard.core import (  # noqa: E402
    MODIFIER_COMMAND,
    MODIFIER_SHIFT,
    catalog_identity,
    display_shortcut,
    filter_catalog,
    find_shortcut_conflict,
    make_board_item,
    move_items,
    normalize_state,
    resolve_board_item,
    shortcut_signature,
    state_for_preferences,
    validate_shortcut,
)


def entry(source="Repo", relative="Tools/Test.py", title="Test Script"):
    return {
        "source": source,
        "source_root": "/Scripts/{}".format(source),
        "relative_path": relative,
        "absolute_path": "/Scripts/{}/{}".format(source, relative),
        "title": title,
        "folder": "{} › {}".format(source, os.path.dirname(relative)),
    }


class ShortcutTests(unittest.TestCase):
    def test_printable_key_requires_safe_modifier(self):
        self.assertIsNotNone(validate_shortcut({"key": "a", "modifiers": 0}))
        self.assertIsNotNone(
            validate_shortcut({"key": "a", "modifiers": MODIFIER_SHIFT})
        )
        self.assertIsNone(
            validate_shortcut({"key": "a", "modifiers": MODIFIER_COMMAND})
        )

    def test_function_key_can_be_unmodified(self):
        shortcut = {"key": chr(0xF704), "modifiers": 0}
        self.assertIsNone(validate_shortcut(shortcut))
        self.assertEqual(display_shortcut(shortcut), "F1")

    def test_display_and_signature_are_normalized(self):
        shortcut = {
            "key": "A",
            "modifiers": MODIFIER_SHIFT | MODIFIER_COMMAND,
            "key_code": 0,
        }
        self.assertEqual(display_shortcut(shortcut), "⇧⌘A")
        self.assertEqual(
            shortcut_signature(shortcut),
            ("a", MODIFIER_SHIFT | MODIFIER_COMMAND),
        )


class PersistenceTests(unittest.TestCase):
    def test_migrates_legacy_path_list(self):
        state = normalize_state(["/Scripts/Old.py"])
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["items"][0]["title"], "Old")

    def test_rejects_duplicates_and_duplicate_shortcuts(self):
        one = make_board_item(entry(), {"key": "a", "modifiers": MODIFIER_COMMAND})
        two = dict(one)
        two["id"] = "second"
        state = normalize_state({"schema_version": 1, "items": [one, two]})
        self.assertEqual(len(state["items"]), 1)

        other = make_board_item(
            entry(relative="Other.py", title="Other"),
            {"key": "a", "modifiers": MODIFIER_COMMAND},
        )
        state = normalize_state({"items": [one, other]})
        self.assertIsNone(state["items"][1]["shortcut"])

    def test_resolves_moved_repository_by_source_and_relative_path(self):
        stored = make_board_item(entry())
        moved = entry()
        moved["source_root"] = "/Moved/Repo"
        moved["absolute_path"] = "/Moved/Repo/Tools/Test.py"
        self.assertIs(resolve_board_item(stored, [moved]), moved)

    def test_preference_state_contains_only_property_list_values(self):
        item = make_board_item(entry())
        serialized = state_for_preferences({"items": [item]})
        self.assertNotIn("shortcut", serialized["items"][0])
        self.assertNotIn(None, serialized["items"][0].values())


class CatalogTests(unittest.TestCase):
    def test_searches_title_source_and_folder(self):
        entries = [
            entry(source="Mekkablue", title="Build Small Caps"),
            entry(source="DP", relative="Kerning/Clean.py", title="Clean Pairs"),
        ]
        self.assertEqual(filter_catalog(entries, "small caps"), [entries[0]])
        self.assertEqual(filter_catalog(entries, "dp kerning"), [entries[1]])

    def test_catalog_identity_prefers_source_and_relative_path(self):
        first = entry()
        second = dict(first, absolute_path="/Moved/Repo/Tools/Test.py")
        self.assertEqual(catalog_identity(first), catalog_identity(second))

    def test_finds_shortcut_conflict(self):
        shortcut = {"key": "k", "modifiers": MODIFIER_COMMAND}
        item = make_board_item(entry(), shortcut, item_id="one")
        self.assertIs(find_shortcut_conflict([item], shortcut), item)
        self.assertIsNone(
            find_shortcut_conflict([item], shortcut, excluding_id="one")
        )

    def test_moves_discontiguous_rows(self):
        items = list("ABCDE")
        self.assertEqual(move_items(items, [1, 3], 5), list("ACEBD"))
        self.assertEqual(move_items(items, [3], 1), list("ADBCE"))


if __name__ == "__main__":
    unittest.main()
