"""Load Script Board's PyObjC classes without launching Glyphs."""

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import patch

try:
    from Foundation import NSObject
except ImportError:
    NSObject = None


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = os.path.join(
    ROOT, "Plugins", "ScriptBoard.glyphsPalette", "Contents", "Resources"
)
sys.path.insert(0, RESOURCES)


if NSObject is None:
    class PluginSmokeTests(unittest.TestCase):
        def test_skipped_without_pyobjc(self):
            raise unittest.SkipTest(
                "PyObjC (Foundation) is not available in this Python environment; run inside Glyphs Python."
            )
else:
    class Defaults(dict):
        def __getitem__(self, key):
            return self.get(key)

    class DummyGlyphs:
        defaults = Defaults()

        @staticmethod
        def localize(value):
            return value.get("en", next(iter(value.values())))

        @staticmethod
        def showMacroWindow():
            pass

    class DummyPalettePlugin(NSObject):
        pass

    glyphs_module = types.ModuleType("GlyphsApp")
    glyphs_module.Glyphs = DummyGlyphs
    plugins_module = types.ModuleType("GlyphsApp.plugins")
    plugins_module.PalettePlugin = DummyPalettePlugin
    sys.modules.setdefault("GlyphsApp", glyphs_module)
    sys.modules.setdefault("GlyphsApp.plugins", plugins_module)

    spec = importlib.util.spec_from_file_location(
        "scriptboard_plugin_smoke", os.path.join(RESOURCES, "plugin.py")
    )
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    import scriptboard.ui as scriptboard_ui
    from scriptboard.ui import _first_composed_character

    class PluginSmokeTests(unittest.TestCase):
        def test_emoji_editor_preserves_complete_unicode_symbols(self):
            for emoji in ("🎨", "👩🏽‍💻", "🇨🇿", "❤️", "1️⃣", "👨‍👩‍👧‍👦"):
                with self.subTest(emoji=emoji):
                    self.assertEqual(_first_composed_character(" " + emoji + " ⭐ "), emoji)
            self.assertEqual(_first_composed_character(" \n "), "")

        def test_emoji_reserves_space_without_moving_shortcut(self):
            plain = plugin._script_row_layout(164, "⌘A")
            decorated = plugin._script_row_layout(164, "⌘A", "👩🏽‍💻")
            self.assertEqual(decorated[0], plain[0] - plugin.SCRIPT_EMOJI_WIDTH)
            self.assertEqual(decorated[1:], plain[1:])
            self.assertGreaterEqual(plugin._script_row_layout(40, "⌘A", "🎨")[0], 0)

        def test_module_defines_expected_pyobjc_classes(self):
            self.assertEqual(plugin.ScriptBoard.__name__, "ScriptBoard")
            self.assertEqual(
                plugin.ScriptPickerController.__name__, "ScriptPickerController"
            )

        def test_palette_view_has_safe_non_glyphs_fallback(self):
            self.assertTrue(issubclass(plugin._palette_view_class(), NSObject))

        def test_script_title_font_uses_requested_system_width(self):
            class VariableFont:
                @classmethod
                def systemFontOfSize_weight_width_(cls, size, weight, width):
                    return ("variable", size, weight, width)

            original = plugin.NSFont
            plugin.NSFont = VariableFont
            try:
                font = plugin._script_title_font(width=-0.125)
                self.assertEqual(font[0], "variable")
                self.assertEqual(font[1], 11)
                self.assertEqual(font[3], -0.125)
            finally:
                plugin.NSFont = original

        def test_script_title_font_has_regular_system_fallback(self):
            class RegularFont:
                @classmethod
                def systemFontOfSize_(cls, size):
                    return ("regular", size)

            original = plugin.NSFont
            plugin.NSFont = RegularFont
            try:
                self.assertEqual(plugin._script_title_font(), ("regular", 11))
            finally:
                plugin.NSFont = original

        def test_short_script_name_keeps_standard_width(self):
            font = plugin._fitted_script_title_font(
                "Short Name",
                120,
                font_factory=lambda size, width: width,
                measure=lambda text, width: 100 * (1 + width),
            )
            self.assertEqual(font, plugin.NSFontWidthStandard)

        def test_overflowing_script_name_uses_only_the_width_needed(self):
            font = plugin._fitted_script_title_font(
                "Moderately Long Name",
                85,
                font_factory=lambda size, width: width,
                measure=lambda text, width: 100 * (1 + width),
            )
            self.assertAlmostEqual(font, -0.15, places=2)
            self.assertGreater(font, plugin.NSFontWidthCompressed)

        def test_extremely_long_script_name_stops_at_readable_width(self):
            font = plugin._fitted_script_title_font(
                "Extremely Long Script Name",
                50,
                font_factory=lambda size, width: width,
                measure=lambda text, width: 100 * (1 + width),
            )
            self.assertEqual(font, plugin.NSFontWidthCompressed)

        def test_script_row_title_uses_full_width_without_shortcut(self):
            title_width, shortcut_x, shortcut_width = plugin._script_row_layout(164, "")
            self.assertEqual(title_width, 154)
            self.assertEqual(shortcut_x, 159)
            self.assertEqual(shortcut_width, 0)

        def test_script_row_reserves_space_only_for_visible_shortcut(self):
            title_width, shortcut_x, shortcut_width = plugin._script_row_layout(
                164, "⇧⌘A"
            )
            self.assertEqual(title_width, 107)
            self.assertEqual(shortcut_x, 116)
            self.assertEqual(shortcut_width, 43)

        def test_script_title_is_configured_as_nonwrapping_single_line(self):
            class Cell:
                def setWraps_(self, value):
                    self.wraps = value

                def setScrollable_(self, value):
                    self.scrollable = value

                def setUsesSingleLineMode_(self, value):
                    self.single_line = value

            class Title:
                def __init__(self):
                    self.text_cell = Cell()

                def setLineBreakMode_(self, value):
                    self.line_break = value

                def setMaximumNumberOfLines_(self, value):
                    self.maximum_lines = value

                def cell(self):
                    return self.text_cell

            title = Title()
            plugin._configure_script_title_field(title)

            self.assertEqual(title.line_break, plugin.NSLineBreakByTruncatingTail)
            self.assertEqual(title.maximum_lines, 1)
            self.assertFalse(title.text_cell.wraps)
            self.assertTrue(title.text_cell.scrollable)
            self.assertTrue(title.text_cell.single_line)

        def test_palette_height_is_resizable_and_persistent(self):
            class UserDefaultsStore:
                def __init__(self):
                    self.values = {}

                def integerForKey_(self, key):
                    return self.values.get(key, 0)

                def setInteger_forKey_(self, value, key):
                    self.values[key] = value

            class UserDefaults:
                store = UserDefaultsStore()

                @classmethod
                def standardUserDefaults(cls):
                    return cls.store

            original = plugin.NSUserDefaults
            plugin.NSUserDefaults = UserDefaults
            try:
                board = plugin.ScriptBoard.alloc().init()
                board.name = "Script Board"
                board.min = plugin.MIN_HEIGHT
                board.max = plugin.MAX_HEIGHT

                self.assertLess(board.min, board.max)
                self.assertEqual(board.currentHeight(), plugin.DEFAULT_HEIGHT)

                board.setCurrentHeight_(360)
                self.assertEqual(board.currentHeight(), 360)

                board.setCurrentHeight_(10_000)
                self.assertEqual(board.currentHeight(), plugin.MAX_HEIGHT)
            finally:
                plugin.NSUserDefaults = original

        def test_palette_footer_stays_on_lower_edge_when_resized(self):
            self.assertTrue(
                plugin.FOOTER_BUTTON_RESIZING_MASK & plugin.NSViewMaxYMargin
            )
            self.assertTrue(
                plugin.FOOTER_LABEL_RESIZING_MASK & plugin.NSViewMaxYMargin
            )
            self.assertFalse(
                plugin.FOOTER_BUTTON_RESIZING_MASK & plugin.NSViewMinYMargin
            )
            self.assertFalse(
                plugin.FOOTER_LABEL_RESIZING_MASK & plugin.NSViewMinYMargin
            )

    class NativeAppearanceTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            plugin.NSApplication.sharedApplication()

        def setUp(self):
            DummyGlyphs.defaults.clear()
            self.board = plugin.ScriptBoard.alloc().init()
            self.board.settings()
            self.board._board_menu = plugin.NSMenu.alloc().initWithTitle_("Test Board")
            self.entry = {
                "title": "Test Script", "source": "Tests", "relative_path": "Test.py",
                "absolute_path": "/Scripts/Test.py",
            }
            self.board._state = plugin.normalize_state({"items": [self.entry]})
            self.board._catalog = [self.entry]
            self.item_id = self.board._state["items"][0]["id"]

        def tearDown(self):
            self.board.table.setDelegate_(None)
            self.board.table.setDataSource_(None)
            self.board.context_menu.setDelegate_(None)

        def sender(self, value):
            item = plugin.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Test", None, "")
            item.setRepresentedObject_(value)
            return item

        def test_color_and_emoji_actions_persist_and_rebuild_menu(self):
            self.board.setScriptColor_(self.sender({"id": self.item_id, "color": "purple"}))
            with patch.object(plugin, "edit_script_emoji", return_value="👩🏽‍💻"):
                self.board.editScriptEmoji_(self.sender(self.item_id))
            saved = DummyGlyphs.defaults[plugin.DEFAULTS_KEY]["items"][0]
            self.assertEqual((saved["color"], saved["emoji"]), ("purple", "👩🏽‍💻"))
            item = self.board._board_menu.itemAtIndex_(0)
            self.assertEqual(item.title(), "👩🏽‍💻 Test Script")
            self.assertIsNotNone(item.image())

            with patch.object(plugin, "edit_script_emoji", return_value=...):
                self.board.editScriptEmoji_(self.sender(self.item_id))
            self.assertEqual(self.board._state["items"][0]["emoji"], "👩🏽‍💻")

            self.board.clearScriptEmoji_(self.sender(self.item_id))
            self.board.setScriptColor_(self.sender({"id": self.item_id, "color": ""}))
            saved = DummyGlyphs.defaults[plugin.DEFAULTS_KEY]["items"][0]
            self.assertEqual((saved["color"], saved["emoji"]), ("", ""))
            self.assertEqual(self.board._board_menu.itemAtIndex_(0).title(), "Test Script")
            self.assertIsNone(self.board._board_menu.itemAtIndex_(0).image())

        def test_native_emoji_editor_saves_clears_and_cancels(self):
            for response, text, expected in (
                (plugin.NSAlertFirstButtonReturn, "👩🏽‍💻 ⭐", "👩🏽‍💻"),
                (plugin.NSAlertFirstButtonReturn, " ", ""),
                (plugin.NSAlertFirstButtonReturn + 1, "⭐", ...),
            ):
                with self.subTest(expected=expected):
                    native_alert = plugin.NSAlert.alloc().init()

                    class Alert:
                        def __getattr__(self, name):
                            return getattr(native_alert, name)

                        def runModal(self):
                            native_alert.accessoryView().subviews()[0].setStringValue_(text)
                            return response

                    with patch.object(scriptboard_ui, "NSAlert") as factory:
                        factory.alloc.return_value.init.return_value = Alert()
                        result = scriptboard_ui.edit_script_emoji("Test Script", "🎨")
                    self.assertEqual(result, expected)
                    picker = native_alert.accessoryView().subviews()[1]
                    self.assertEqual(str(picker.action()), "orderFrontCharacterPalette:")
                    self.assertEqual(picker.target(), plugin.NSApplication.sharedApplication())

        def test_context_menu_offers_checked_colors_and_optional_emoji_actions(self):
            class ClickedTable:
                def clickedRow(self):
                    return 0

            self.board._state["items"][0].update(color="blue", emoji="🎨")
            with patch.object(self.board, "table", ClickedTable()):
                self.board.menuNeedsUpdate_(self.board.context_menu)
            menu = self.board.context_menu
            color_menu = menu.itemWithTitle_("Color").submenu()
            self.assertEqual(color_menu.numberOfItems(), len(plugin.SCRIPT_COLORS) + 1)
            self.assertEqual(color_menu.itemWithTitle_("Blue").state(), 1)
            self.assertEqual(color_menu.itemWithTitle_("None").state(), 0)
            self.assertIsNotNone(menu.itemWithTitle_("Edit Emoji…"))
            self.assertIsNotNone(menu.itemWithTitle_("Remove Emoji"))

            # Menu actions target the stored item ID, even if rows are reordered.
            self.board._state["items"].insert(0, plugin.make_board_item({
                "title": "Other", "relative_path": "Other.py",
            }))
            self.board.setScriptColor_(color_menu.itemWithTitle_("Green"))
            self.assertEqual(self.board._state["items"][0]["color"], "")
            self.assertEqual(self.board._state["items"][1]["color"], "green")

        def test_reused_row_clears_appearance_and_restores_name_width(self):
            item = self.board._state["items"][0]
            item.update(color="blue", emoji="👩🏽‍💻")
            column = self.board.table.tableColumns()[0]
            cell = self.board.tableView_viewForTableColumn_row_(self.board.table, column, 0)
            title = cell.viewWithTag_(201)
            emoji = cell.viewWithTag_(203)
            decorated_width = title.frame().size.width
            self.assertEqual(title.textColor(), plugin.NSColor.systemBlueColor())
            self.assertEqual(emoji.stringValue(), "👩🏽‍💻")
            self.assertFalse(emoji.isHidden())
            self.assertEqual(self.board.table.rowHeight() + self.board.table.intercellSpacing().height
                             - title.frame().size.height, 5)

            class ReusingTable:
                def makeViewWithIdentifier_owner_(self, identifier, owner):
                    return cell

            item.update(color="", emoji="")
            self.board.tableView_viewForTableColumn_row_(ReusingTable(), column, 0)
            self.assertEqual(title.textColor(), plugin.NSColor.labelColor())
            self.assertTrue(emoji.isHidden())
            self.assertEqual(emoji.stringValue(), "")
            self.assertEqual(title.frame().size.width, decorated_width + plugin.SCRIPT_EMOJI_WIDTH)


if __name__ == "__main__":
    unittest.main()
