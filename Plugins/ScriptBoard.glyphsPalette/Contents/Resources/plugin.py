# -*- coding: utf-8 -*-
"""Script Board — a native favorite-script palette for Glyphs 4."""

from __future__ import annotations

import os
import traceback

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSAlertStyleCritical,
    NSAlertStyleWarning,
    NSApplication,
    NSBezelStyleAccessoryBarAction,
    NSBeep,
    NSButton,
    NSColor,
    NSControlSizeSmall,
    NSEvent,
    NSEventMaskKeyDown,
    NSEventModifierFlagCommand,
    NSEventModifierFlagControl,
    NSEventModifierFlagOption,
    NSEventModifierFlagShift,
    NSFont,
    NSImage,
    NSImageNameAddTemplate,
    NSImageNameRefreshTemplate,
    NSLineBreakByTruncatingMiddle,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSScrollView,
    NSTableCellView,
    NSTableColumn,
    NSTableView,
    NSTableViewDropAbove,
    NSTableViewStylePlain,
    NSTextAlignmentCenter,
    NSTextAlignmentLeft,
    NSTextField,
    NSUserDefaults,
    NSView,
    NSViewHeightSizable,
    NSViewMaxXMargin,
    NSViewMaxYMargin,
    NSViewMinXMargin,
    NSViewMinYMargin,
    NSViewWidthSizable,
    NSWorkspace,
)
from Foundation import NSNotificationCenter
from GlyphsApp import Glyphs
from GlyphsApp.plugins import PalettePlugin

from scriptboard.core import (
    SUPPORTED_MODIFIERS,
    catalog_identity,
    display_shortcut,
    find_shortcut_conflict,
    make_board_item,
    move_items,
    normalize_state,
    resolve_board_item,
    shortcut_signature,
    state_for_preferences,
    validate_shortcut,
)
from scriptboard.ui import ScriptPickerController


DEFAULTS_KEY = "com.displaay.ScriptBoard.state"
BOARD_CHANGED_NOTIFICATION = "com.displaay.ScriptBoard.changed"
SCRIPT_MENU_RELOADED_NOTIFICATION = "GSReloadScriptMenu"
ROW_PASTEBOARD_TYPE = "com.displaay.ScriptBoard.rows"
MIN_HEIGHT = 72
DEFAULT_HEIGHT = 164
MAX_HEIGHT = 520
FOOTER_BUTTON_RESIZING_MASK = NSViewMaxXMargin | NSViewMaxYMargin
FOOTER_LABEL_RESIZING_MASK = NSViewWidthSizable | NSViewMaxYMargin


def _alert(message, informative="", style=None):
    alert = NSAlert.alloc().init()
    alert.setMessageText_(message)
    if informative:
        alert.setInformativeText_(informative)
    if style is not None:
        alert.setAlertStyle_(style)
    alert.addButtonWithTitle_("OK")
    alert.runModal()


def _system_image(symbol_name, fallback_name, description):
    if hasattr(NSImage, "imageWithSystemSymbolName_accessibilityDescription_"):
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol_name, description
        )
        if image is not None:
            return image
    return NSImage.imageNamed_(fallback_name)


def _palette_view_class():
    """Return Glyphs' native resizable Palette container when available."""

    try:
        return objc.lookUpClass("GSPaletteView")
    except Exception:
        # Keeps imports and unit tests independent from a running Glyphs app.
        return NSView


class ScriptBoard(PalettePlugin):
    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Script Board"})
        self.sortId = 5  # Public GlyphsPalette sort order; Dimensions is 10.
        # A differing min/max plus both currentHeight accessors enables the
        # native Glyphs Palette resize divider.
        self.min = MIN_HEIGHT
        self.max = MAX_HEIGHT
        self._state = normalize_state(Glyphs.defaults[DEFAULTS_KEY])
        self._catalog = []
        self._menu_parent = None
        self._menu_parent_item = None
        self._event_monitor = None
        self._picker = None
        self._build_view()
        self._build_settings_menu()

    @objc.python_method
    def start(self):
        center = NSNotificationCenter.defaultCenter()
        center.addObserver_selector_name_object_(
            self, self.boardStateChanged_, BOARD_CHANGED_NOTIFICATION, None
        )
        center.addObserver_selector_name_object_(
            self,
            self.scriptMenuReloaded_,
            SCRIPT_MENU_RELOADED_NOTIFICATION,
            None,
        )
        self._install_script_board_menu()
        self._refresh_catalog()
        self._reload_table()

    def __del__(self):
        try:
            NSNotificationCenter.defaultCenter().removeObserver_(self)
            if self._event_monitor is not None:
                NSEvent.removeMonitor_(self._event_monitor)
                self._event_monitor = None
            if self._menu_parent is not None and self._menu_parent_item is not None:
                self._menu_parent.removeItem_(self._menu_parent_item)
        except Exception:
            pass

    @objc.typedSelector(b"L@:")
    def currentHeight(self):
        value = NSUserDefaults.standardUserDefaults().integerForKey_(
            self.name + ".ViewHeight"
        )
        value = value or DEFAULT_HEIGHT
        return max(self.min, min(int(value), self.max))

    @objc.typedSelector(b"v@:L")
    def setCurrentHeight_(self, new_height):
        """Persist height changes made with Glyphs' native Palette divider."""

        height = max(self.min, min(int(new_height), self.max))
        NSUserDefaults.standardUserDefaults().setInteger_forKey_(
            height, self.name + ".ViewHeight"
        )

    @objc.typedSelector(b"@@:")
    def settingsMenu(self):
        return self._settings_menu

    @objc.python_method
    def _build_view(self):
        width, height = 180, DEFAULT_HEIGHT
        self.dialog = _palette_view_class().alloc().initWithFrame_(
            NSMakeRect(0, 0, width, height)
        )
        # Glyphs sizes GSPaletteView from its intrinsic height. A translated
        # autoresizing mask would add a fixed-height constraint and prevent
        # the native resize drag from changing the section on screen.
        self.dialog.setTranslatesAutoresizingMaskIntoConstraints_(False)

        table_frame = NSMakeRect(8, 36, width - 16, height - 42)
        self.table = NSTableView.alloc().initWithFrame_(table_frame)
        self.table.setHeaderView_(None)
        self.table.setRowHeight_(25)
        self.table.setIntercellSpacing_((0, 1))
        self.table.setAllowsEmptySelection_(True)
        self.table.setAllowsMultipleSelection_(False)
        self.table.setUsesAlternatingRowBackgroundColors_(False)
        if hasattr(self.table, "setStyle_"):
            self.table.setStyle_(NSTableViewStylePlain)
        column = NSTableColumn.alloc().initWithIdentifier_("script")
        column.setWidth_(width - 18)
        column.setResizingMask_(1)
        self.table.addTableColumn_(column)
        self.table.setDataSource_(self)
        self.table.setDelegate_(self)
        self.table.setTarget_(self)
        self.table.setAction_("runSelectedScript:")
        self.table.registerForDraggedTypes_([ROW_PASTEBOARD_TYPE])
        self.table.setDraggingSourceOperationMask_forLocal_(1 << 4, True)

        self.context_menu = NSMenu.alloc().initWithTitle_("Script Board")
        self.context_menu.setDelegate_(self)
        self.table.setMenu_(self.context_menu)

        self.scroll = NSScrollView.alloc().initWithFrame_(table_frame)
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setAutohidesScrollers_(True)
        self.scroll.setBorderType_(0)
        self.scroll.setDocumentView_(self.table)
        self.scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        self.dialog.addSubview_(self.scroll)

        self.empty_label = NSTextField.labelWithString_(
            "No scripts yet\nAdd your favorites for one-click access."
        )
        self.empty_label.setFrame_(table_frame)
        self.empty_label.setAlignment_(NSTextAlignmentCenter)
        self.empty_label.setFont_(NSFont.systemFontOfSize_(11))
        self.empty_label.setTextColor_(NSColor.secondaryLabelColor())
        self.empty_label.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        self.dialog.addSubview_(self.empty_label)

        self.add_button = self._toolbar_button(
            NSMakeRect(8, 7, 24, 24),
            "plus",
            NSImageNameAddTemplate,
            "Add installed scripts",
            self.addScripts_,
        )
        self.dialog.addSubview_(self.add_button)

        self.refresh_button = self._toolbar_button(
            NSMakeRect(34, 7, 24, 24),
            "arrow.trianglehead.2.clockwise.rotate.90",
            NSImageNameRefreshTemplate,
            "Refresh installed scripts",
            self.refreshScripts_,
        )
        self.dialog.addSubview_(self.refresh_button)

        self.count_label = NSTextField.labelWithString_("")
        self.count_label.setFrame_(NSMakeRect(64, 10, width - 72, 17))
        self.count_label.setAlignment_(NSTextAlignmentLeft)
        self.count_label.setFont_(NSFont.systemFontOfSize_(10))
        self.count_label.setTextColor_(NSColor.secondaryLabelColor())
        # Keep the complete footer attached to the lower edge while the
        # script list absorbs vertical palette resizing.
        self.count_label.setAutoresizingMask_(FOOTER_LABEL_RESIZING_MASK)
        self.dialog.addSubview_(self.count_label)

    @objc.python_method
    def _toolbar_button(self, frame, symbol, fallback, tooltip, action):
        button = NSButton.alloc().initWithFrame_(frame)
        button.setBordered_(False)
        button.setBezelStyle_(NSBezelStyleAccessoryBarAction)
        button.setControlSize_(NSControlSizeSmall)
        button.setImage_(_system_image(symbol, fallback, tooltip))
        button.setTitle_("")
        button.setToolTip_(tooltip)
        button.setAccessibilityLabel_(tooltip)
        button.setTarget_(self)
        button.setAction_(action)
        button.setAutoresizingMask_(FOOTER_BUTTON_RESIZING_MASK)
        return button

    @objc.python_method
    def _build_settings_menu(self):
        menu = NSMenu.alloc().initWithTitle_("Script Board")
        self._add_menu_item(menu, "Add Scripts…", self.addScripts_)
        self._add_menu_item(menu, "Refresh Installed Scripts", self.refreshScripts_)
        menu.addItem_(NSMenuItem.separatorItem())
        self._add_menu_item(menu, "Reset Board…", self.resetBoard_)
        self._settings_menu = menu

    @objc.python_method
    def _add_menu_item(self, menu, title, action, represented=None):
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
        item.setTarget_(self)
        if represented is not None:
            item.setRepresentedObject_(represented)
        menu.addItem_(item)
        return item

    @objc.python_method
    def _install_script_board_menu(self):
        try:
            handler_class = objc.lookUpClass("GSScriptingHandler")
            script_menu = handler_class.alloc().init().scriptMenu()
            if script_menu is None:
                return
            existing = script_menu.itemWithTitle_("Script Board")
            if existing is not None:
                script_menu.removeItem_(existing)
            submenu = NSMenu.alloc().initWithTitle_("Script Board")
            parent = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Script Board", None, ""
            )
            parent.setSubmenu_(submenu)
            insertion = next(
                (
                    index
                    for index, item in enumerate(script_menu.itemArray())
                    if item.isSeparatorItem()
                ),
                script_menu.numberOfItems(),
            )
            script_menu.insertItem_atIndex_(parent, insertion)
            self._menu_parent = script_menu
            self._menu_parent_item = parent
            self._board_menu = submenu
        except Exception:
            self._log_exception("Could not install the Script Board menu")

    @objc.python_method
    def _refresh_catalog(self):
        try:
            handler_class = objc.lookUpClass("GSScriptingHandler")
            menu = handler_class.alloc().init().scriptMenu()
            groups = []
            for top_item in menu.itemArray():
                if not top_item.hasSubmenu() or top_item.title() == "Script Board":
                    continue
                entries = []
                self._walk_script_menu(
                    top_item.submenu(), [top_item.title()], entries
                )
                if entries:
                    groups.append((top_item.title(), entries))

            catalog = []
            seen_paths = set()
            for source, entries in groups:
                parent_paths = [os.path.dirname(entry["absolute_path"]) for entry in entries]
                try:
                    source_root = os.path.commonpath(parent_paths)
                except ValueError:
                    source_root = ""
                for entry in entries:
                    normalized = os.path.normcase(os.path.normpath(entry["absolute_path"]))
                    if normalized in seen_paths:
                        continue
                    seen_paths.add(normalized)
                    entry["source"] = source
                    entry["source_root"] = source_root
                    entry["relative_path"] = (
                        os.path.relpath(entry["absolute_path"], source_root)
                        if source_root
                        else os.path.basename(entry["absolute_path"])
                    )
                    catalog.append(entry)
            self._catalog = sorted(
                catalog,
                key=lambda entry: (
                    entry["title"].casefold(),
                    entry["source"].casefold(),
                    entry["relative_path"].casefold(),
                ),
            )
            self._repair_persisted_paths()
        except Exception:
            self._catalog = []
            self._log_exception("Could not read Glyphs’ Script menu")

    @objc.python_method
    def _walk_script_menu(self, menu, path, output):
        for item in menu.itemArray():
            if item.hasSubmenu():
                self._walk_script_menu(item.submenu(), path + [item.title()], output)
                continue
            represented = item.representedObject()
            action = str(item.action() or "")
            if (
                action != "runScriptMenu:"
                or not isinstance(represented, str)
                or not represented.lower().endswith(".py")
            ):
                continue
            output.append(
                {
                    "title": item.title(),
                    "folder": " › ".join(path),
                    "menu_path": list(path),
                    "absolute_path": represented,
                    "menu_item": item,
                }
            )

    @objc.python_method
    def _repair_persisted_paths(self):
        changed = False
        for item in self._state["items"]:
            entry = resolve_board_item(item, self._catalog)
            if entry is None:
                continue
            for key in ("source", "source_root", "relative_path", "absolute_path", "folder"):
                if item.get(key) != entry.get(key):
                    item[key] = entry.get(key, "")
                    changed = True
            if not item.get("title"):
                item["title"] = entry["title"]
                changed = True
        if changed:
            self._save_state(notify=False)

    @objc.python_method
    def _save_state(self, notify=True):
        normalized = normalize_state(self._state)
        if normalized != self._state:
            self._state = normalized
        preferences_state = state_for_preferences(self._state)
        if Glyphs.defaults[DEFAULTS_KEY] != preferences_state:
            Glyphs.defaults[DEFAULTS_KEY] = preferences_state
        if notify:
            NSNotificationCenter.defaultCenter().postNotificationName_object_(
                BOARD_CHANGED_NOTIFICATION, self
            )
        self._rebuild_board_menu()
        self._reload_table()

    @objc.python_method
    def _reload_table(self):
        self.table.reloadData()
        count = len(self._state["items"])
        self.scroll.setHidden_(count == 0)
        self.empty_label.setHidden_(count != 0)
        self.count_label.setStringValue_(
            "{} script{}".format(count, "" if count == 1 else "s")
        )
        self._rebuild_board_menu()

    @objc.python_method
    def _rebuild_board_menu(self):
        if not hasattr(self, "_board_menu"):
            return
        self._board_menu.removeAllItems()
        if not self._state["items"]:
            empty = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No Scripts Added", None, ""
            )
            empty.setEnabled_(False)
            self._board_menu.addItem_(empty)
            return
        for board_item in self._state["items"]:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                board_item["title"], self.runBoardScript_, ""
            )
            item.setTarget_(self)
            item.setRepresentedObject_(board_item["id"])
            shortcut = board_item.get("shortcut")
            signature = shortcut_signature(shortcut)
            if signature is not None:
                item.setKeyEquivalent_(signature[0])
                item.setKeyEquivalentModifierMask_(signature[1])
            self._board_menu.addItem_(item)

    @objc.python_method
    def _board_item(self, item_id):
        return next(
            (item for item in self._state["items"] if item["id"] == item_id), None
        )

    @objc.python_method
    def _resolved_entry(self, item):
        return resolve_board_item(item, self._catalog)

    @objc.python_method
    def _run_item(self, board_item):
        self._refresh_catalog()
        entry = self._resolved_entry(board_item)
        if entry is None:
            _alert(
                "Script Not Available",
                "Glyphs no longer lists “{}”. Refresh or add the moved script again.".format(
                    board_item["title"]
                ),
                NSAlertStyleWarning,
            )
            return
        menu_item = entry.get("menu_item")
        try:
            sent = NSApplication.sharedApplication().sendAction_to_from_(
                menu_item.action(), menu_item.target(), menu_item
            )
            if not sent:
                raise RuntimeError("Glyphs did not accept the script command")
        except Exception:
            self._log_exception("Could not run {}".format(board_item["title"]))
            _alert(
                "Script Could Not Run",
                "Open the Macro window for the full error.",
                NSAlertStyleCritical,
            )

    @objc.python_method
    def _log_exception(self, message):
        try:
            Glyphs.showMacroWindow()
        except Exception:
            pass
        print("Script Board: {}\n{}".format(message, traceback.format_exc()))

    def numberOfRowsInTableView_(self, table_view):
        return len(self._state["items"])

    def tableView_viewForTableColumn_row_(self, table_view, table_column, row):
        identifier = "ScriptBoardCell"
        cell = table_view.makeViewWithIdentifier_owner_(identifier, self)
        if cell is None:
            cell = NSTableCellView.alloc().initWithFrame_(NSMakeRect(0, 0, 164, 25))
            cell.setIdentifier_(identifier)
            title = NSTextField.labelWithString_("")
            title.setFrame_(NSMakeRect(5, 5, 112, 16))
            title.setFont_(NSFont.systemFontOfSize_(11))
            title.setLineBreakMode_(NSLineBreakByTruncatingMiddle)
            title.setAutoresizingMask_(NSViewWidthSizable)
            title.setTag_(201)
            cell.addSubview_(title)

            shortcut = NSTextField.labelWithString_("")
            shortcut.setFrame_(NSMakeRect(116, 5, 43, 16))
            shortcut.setAlignment_(2)
            shortcut.setFont_(NSFont.monospacedSystemFontOfSize_weight_(9, 0))
            shortcut.setTextColor_(NSColor.secondaryLabelColor())
            shortcut.setAutoresizingMask_(NSViewMinXMargin | NSViewMinYMargin)
            shortcut.setTag_(202)
            cell.addSubview_(shortcut)

        item = self._state["items"][row]
        resolved = self._resolved_entry(item)
        title = item["title"] if resolved is not None else item["title"] + " — Missing"
        cell.viewWithTag_(201).setStringValue_(title)
        cell.viewWithTag_(202).setStringValue_(display_shortcut(item.get("shortcut")))
        cell.setToolTip_(item.get("absolute_path", ""))
        return cell

    def runSelectedScript_(self, sender):
        row = self.table.clickedRow()
        if row < 0:
            row = self.table.selectedRow()
        if 0 <= row < len(self._state["items"]):
            self._run_item(self._state["items"][row])
        self.table.deselectAll_(None)

    def runBoardScript_(self, sender):
        board_item = self._board_item(sender.representedObject())
        if board_item is not None:
            self._run_item(board_item)

    def addScripts_(self, sender):
        self._refresh_catalog()
        existing = {catalog_identity(item) for item in self._state["items"]}
        available = [
            entry for entry in self._catalog if catalog_identity(entry) not in existing
        ]
        if not available:
            _alert(
                "No More Scripts to Add",
                "Every installed script is already on the board, or Glyphs has no scripts loaded.",
            )
            return

        picker = ScriptPickerController.alloc().init()
        picker.configure(available)
        self._picker = picker
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Add Scripts")
        alert.setInformativeText_(
            "Choose one or more scripts already installed in Glyphs."
        )
        alert.setAccessoryView_(picker.view)
        alert.addButtonWithTitle_("Add Selected")
        alert.addButtonWithTitle_("Cancel")
        response = alert.runModal()
        if response != NSAlertFirstButtonReturn:
            return
        selected = picker.selected_entries()
        if not selected:
            return
        self._state["items"].extend(make_board_item(entry) for entry in selected)
        self._save_state()

    def refreshScripts_(self, sender):
        self._refresh_catalog()
        self._reload_table()

    def scriptMenuReloaded_(self, notification):
        self.performSelector_withObject_afterDelay_(self.refreshScripts_, None, 0.0)

    def boardStateChanged_(self, notification):
        if notification.object() is self:
            return
        self._state = normalize_state(Glyphs.defaults[DEFAULTS_KEY])
        self._reload_table()

    def menuNeedsUpdate_(self, menu):
        menu.removeAllItems()
        row = self.table.clickedRow()
        if row < 0 or row >= len(self._state["items"]):
            return
        board_item = self._state["items"][row]
        item_id = board_item["id"]
        self._add_menu_item(menu, "Run", self.runBoardScript_, item_id)
        self._add_menu_item(menu, "Assign Shortcut…", self.assignShortcut_, item_id)
        if board_item.get("shortcut"):
            self._add_menu_item(menu, "Clear Shortcut", self.clearShortcut_, item_id)
        menu.addItem_(NSMenuItem.separatorItem())
        self._add_menu_item(menu, "Reveal Script in Finder", self.revealScript_, item_id)
        self._add_menu_item(menu, "Show Details", self.showDetails_, item_id)
        menu.addItem_(NSMenuItem.separatorItem())
        self._add_menu_item(menu, "Remove from Board", self.removeScript_, item_id)

    def assignShortcut_(self, sender):
        board_item = self._board_item(sender.representedObject())
        if board_item is None:
            return
        shortcut = self._record_shortcut(board_item["title"])
        if shortcut is ...:
            return
        if shortcut is None:
            board_item["shortcut"] = None
            self._save_state()
            return

        conflict = find_shortcut_conflict(
            self._state["items"], shortcut, excluding_id=board_item["id"]
        )
        if conflict is not None:
            _alert(
                "Shortcut Already Used",
                "{} is assigned to “{}”.".format(
                    display_shortcut(shortcut), conflict["title"]
                ),
                NSAlertStyleWarning,
            )
            return
        menu_conflict = self._find_menu_conflict(shortcut)
        if menu_conflict:
            _alert(
                "Shortcut Conflicts with Glyphs",
                "{} is already assigned to “{}”. Choose another shortcut.".format(
                    display_shortcut(shortcut), menu_conflict
                ),
                NSAlertStyleWarning,
            )
            return
        board_item["shortcut"] = shortcut
        self._save_state()

    @objc.python_method
    def _record_shortcut(self, title):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Shortcut for {}".format(title))
        alert.setInformativeText_(
            "Press a shortcut. Printable keys need ⌘, ⌥, or ⌃. "
            "Function keys can be used alone. Press Delete to clear or Escape to cancel."
        )
        alert.addButtonWithTitle_("Cancel")
        state = {"result": ...}
        allowed = (
            NSEventModifierFlagShift
            | NSEventModifierFlagControl
            | NSEventModifierFlagOption
            | NSEventModifierFlagCommand
        )

        def handler(event):
            key = event.charactersIgnoringModifiers() or ""
            modifiers = int(event.modifierFlags() & allowed)
            if key == "\x1b":
                state["result"] = ...
                NSApplication.sharedApplication().abortModal()
                return None
            if key in ("\x08", "\x7f", chr(0xF728)) and modifiers == 0:
                state["result"] = None
                NSApplication.sharedApplication().abortModal()
                return None
            if len(key) != 1:
                NSBeep()
                return None
            shortcut = {
                "key": key.lower() if ord(key) < 0xF700 else key,
                "modifiers": modifiers,
                "key_code": int(event.keyCode()),
            }
            error = validate_shortcut(shortcut)
            if error:
                alert.setInformativeText_(error + " Try another combination.")
                NSBeep()
                return None
            state["result"] = shortcut
            NSApplication.sharedApplication().abortModal()
            return None

        self._event_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, handler
        )
        try:
            alert.runModal()
        finally:
            if self._event_monitor is not None:
                NSEvent.removeMonitor_(self._event_monitor)
                self._event_monitor = None
            alert.window().orderOut_(None)
        return state["result"]

    @objc.python_method
    def _find_menu_conflict(self, shortcut):
        signature = shortcut_signature(shortcut)
        if signature is None:
            return None

        def walk(menu):
            for item in menu.itemArray():
                if item is self._menu_parent_item:
                    continue
                key = item.keyEquivalent()
                if key:
                    item_signature = (
                        key.lower() if ord(key[0]) < 0xF700 else key,
                        int(item.keyEquivalentModifierMask()) & SUPPORTED_MODIFIERS,
                    )
                    if item_signature == signature:
                        return item.title()
                if item.hasSubmenu():
                    conflict = walk(item.submenu())
                    if conflict:
                        return conflict
            return None

        return walk(NSApplication.sharedApplication().mainMenu())

    def clearShortcut_(self, sender):
        board_item = self._board_item(sender.representedObject())
        if board_item is not None:
            board_item["shortcut"] = None
            self._save_state()

    def removeScript_(self, sender):
        item_id = sender.representedObject()
        self._state["items"] = [
            item for item in self._state["items"] if item["id"] != item_id
        ]
        self._save_state()

    def revealScript_(self, sender):
        board_item = self._board_item(sender.representedObject())
        if board_item is None:
            return
        entry = self._resolved_entry(board_item)
        path = (entry or board_item).get("absolute_path", "")
        if path and os.path.exists(path):
            NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_(
                path, ""
            )
        else:
            _alert("Script Not Found", path or board_item["title"], NSAlertStyleWarning)

    def showDetails_(self, sender):
        board_item = self._board_item(sender.representedObject())
        if board_item is None:
            return
        shortcut = display_shortcut(board_item.get("shortcut")) or "None"
        _alert(
            board_item["title"],
            "Location: {}\nShortcut: {}".format(
                board_item.get("absolute_path", "Unknown"), shortcut
            ),
        )

    def resetBoard_(self, sender):
        if not self._state["items"]:
            return
        alert = NSAlert.alloc().init()
        alert.setAlertStyle_(NSAlertStyleWarning)
        alert.setMessageText_("Reset Script Board?")
        alert.setInformativeText_(
            "This removes every board item and shortcut. Installed script files are not changed."
        )
        alert.addButtonWithTitle_("Reset Board")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() == NSAlertFirstButtonReturn:
            self._state = normalize_state(None)
            self._save_state()

    def tableView_writeRowsWithIndexes_toPasteboard_(self, table_view, indexes, pasteboard):
        value = ",".join(str(index) for index in indexes)
        pasteboard.declareTypes_owner_([ROW_PASTEBOARD_TYPE], self)
        pasteboard.setString_forType_(value, ROW_PASTEBOARD_TYPE)
        return True

    def tableView_validateDrop_proposedRow_proposedDropOperation_(
        self, table_view, info, row, operation
    ):
        table_view.setDropRow_dropOperation_(row, NSTableViewDropAbove)
        return 1 << 4

    def tableView_acceptDrop_row_dropOperation_(self, table_view, info, row, operation):
        value = info.draggingPasteboard().stringForType_(ROW_PASTEBOARD_TYPE)
        if not value:
            return False
        try:
            indexes = [int(part) for part in value.split(",") if part]
        except ValueError:
            return False
        self._state["items"] = move_items(self._state["items"], indexes, row)
        self._save_state()
        return True
