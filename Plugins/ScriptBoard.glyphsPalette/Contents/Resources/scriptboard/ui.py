"""Small native AppKit controllers shared by the Script Board palette."""

from __future__ import annotations

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApplication,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFont,
    NSLineBreakByTruncatingMiddle,
    NSMakeRect,
    NSScrollView,
    NSSearchField,
    NSTableCellView,
    NSTableColumn,
    NSTableView,
    NSTableViewStylePlain,
    NSTextField,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
)
from Foundation import NSObject, NSString

from .core import filter_catalog


def _first_composed_character(value):
    """Keep a complete emoji, including joined symbols, flags and skin tones."""

    value = value.strip()
    if not value:
        return ""
    text = NSString.stringWithString_(value)
    first_symbol = text.rangeOfComposedCharacterSequenceAtIndex_(0)
    return str(text.substringWithRange_(first_symbol))


def edit_script_emoji(title, current_emoji):
    """Return an optional emoji, or Ellipsis when the editor is cancelled."""

    alert = NSAlert.alloc().init()
    alert.setMessageText_("Emoji for {}".format(title))
    alert.setInformativeText_(
        "Type or paste an emoji, or choose one with the emoji picker. "
        "The first symbol will appear before the script name. Leave blank to remove it."
    )
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 36))
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 2, 90, 30))
    field.setFont_(NSFont.systemFontOfSize_(18))
    field.setStringValue_(current_emoji)
    field.setPlaceholderString_("Emoji")
    field.setAccessibilityLabel_("Script emoji")
    view.addSubview_(field)

    picker_button = NSButton.alloc().initWithFrame_(NSMakeRect(104, 2, 190, 30))
    picker_button.setTitle_("Emoji Picker…")
    picker_button.setBezelStyle_(NSBezelStyleRounded)
    picker_button.setRefusesFirstResponder_(True)
    picker_button.setTarget_(NSApplication.sharedApplication())
    picker_button.setAction_("orderFrontCharacterPalette:")
    view.addSubview_(picker_button)

    alert.setAccessoryView_(view)
    alert.addButtonWithTitle_("Save")
    alert.addButtonWithTitle_("Cancel")
    alert.window().setInitialFirstResponder_(field)
    alert.window().makeFirstResponder_(field)
    if alert.runModal() != NSAlertFirstButtonReturn:
        return ...
    return _first_composed_character(field.stringValue())


class ScriptPickerController(NSObject):
    """Searchable, multiple-selection accessory view for an NSAlert."""

    @objc.python_method
    def configure(self, catalog):
        self.catalog = list(catalog)
        self.filtered = filter_catalog(self.catalog, "")

        self.view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 500, 350))

        self.search = NSSearchField.alloc().initWithFrame_(NSMakeRect(0, 320, 500, 24))
        self.search.setPlaceholderString_("Search installed scripts")
        self.search.setDelegate_(self)
        self.search.setAutoresizingMask_(NSViewWidthSizable)
        self.view.addSubview_(self.search)

        self.table = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, 500, 310))
        self.table.setHeaderView_(None)
        self.table.setRowHeight_(24)
        self.table.setAllowsMultipleSelection_(True)
        self.table.setAllowsEmptySelection_(True)
        self.table.setUsesAlternatingRowBackgroundColors_(False)
        if hasattr(self.table, "setStyle_"):
            self.table.setStyle_(NSTableViewStylePlain)

        column = NSTableColumn.alloc().initWithIdentifier_("script")
        column.setWidth_(500)
        column.setResizingMask_(1)
        self.table.addTableColumn_(column)
        self.table.setDataSource_(self)
        self.table.setDelegate_(self)

        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 500, 310))
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setBorderType_(0)
        scroll.setDocumentView_(self.table)
        scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        self.view.addSubview_(scroll)
        self.scroll = scroll
        return self

    def controlTextDidChange_(self, notification):
        self.filtered = filter_catalog(self.catalog, self.search.stringValue())
        self.table.reloadData()

    def numberOfRowsInTableView_(self, table_view):
        return len(self.filtered)

    def tableView_viewForTableColumn_row_(self, table_view, table_column, row):
        identifier = "ScriptPickerCell"
        cell = table_view.makeViewWithIdentifier_owner_(identifier, self)
        if cell is None:
            cell = NSTableCellView.alloc().initWithFrame_(NSMakeRect(0, 0, 500, 24))
            cell.setIdentifier_(identifier)
            title = NSTextField.labelWithString_("")
            title.setFrame_(NSMakeRect(4, 7, 300, 15))
            title.setFont_(NSFont.systemFontOfSize_(11))
            title.setLineBreakMode_(NSLineBreakByTruncatingMiddle)
            title.setAutoresizingMask_(NSViewWidthSizable)
            title.setTag_(101)
            cell.addSubview_(title)

            location = NSTextField.labelWithString_("")
            location.setFrame_(NSMakeRect(4, 0, 480, 12))
            location.setFont_(NSFont.systemFontOfSize_(9))
            location.setTextColor_(NSColor.secondaryLabelColor())
            location.setLineBreakMode_(NSLineBreakByTruncatingMiddle)
            location.setAutoresizingMask_(NSViewWidthSizable)
            location.setTag_(102)
            cell.addSubview_(location)

        entry = self.filtered[row]
        cell.viewWithTag_(101).setStringValue_(entry["title"])
        folder = entry.get("folder") or entry.get("source") or "Scripts"
        cell.viewWithTag_(102).setStringValue_(folder)
        cell.setToolTip_(entry.get("absolute_path", ""))
        return cell

    @objc.python_method
    def selected_entries(self):
        return [self.filtered[index] for index in self.table.selectedRowIndexes()]
