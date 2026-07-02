# -*- encoding: utf-8 -*-
from __future__ import division, print_function, unicode_literals


import re
import io
import os
import platform
import objc
from AppKit import (
    NSButton,
    NSButtonCell,
    NSFont,
    NSMiniControlSize,
    NSShadowlessSquareBezelStyle,
    NSCircularBezelStyle,
    NSTextFieldCell,
    NSLayoutConstraint,
    NSLayoutAttributeHeight,
    NSLayoutAttributeWidth,
    NSLayoutAttributeTop,
    NSLayoutAttributeLeading,
    NSLayoutAttributeTrailing,
    NSLayoutAttributeBottom,
    NSLayoutRelationEqual,
    NSLineBreakByTruncatingTail,
    NSLayoutConstraintOrientationHorizontal,
    NSBezierPath,
    NSColor,
    NSImage,
    NSView,
    NSNotificationCenter,
    NSMakeRect,
    NSMakeSize,
    NSTableColumn,
    NSTableView,
    NSTableViewDropAbove,
    NSDragOperationMove
)
from Foundation import NSIndexSet
try:
    from AppKit import NSPasteboardTypeString
except:
    from AppKit import NSStringPboardType as NSPasteboardTypeString
try:
    from AppKit import NSTableViewSelectionHighlightStyleNone
except:
    NSTableViewSelectionHighlightStyleNone = -1
try:
    from AppKit import NSSmallControlSize
except:
    NSSmallControlSize = NSMiniControlSize
try:
    from AppKit import NSOnState, NSOffState
except:
    NSOnState, NSOffState = 1, 0
try:
    from AppKit import NSBezelStyleRecessed, NSButtonTypeMomentaryLight
    hasRecessedStyleImported = True
except:
    hasRecessedStyleImported = False

from GlyphsApp import Glyphs, GSGlyphsInfo, GetOpenFile, objcObject
from GlyphsApp.plugins import PalettePlugin

if int(Glyphs.versionNumber) == 3:
    GSMouseOverButton = objc.lookUpClass("GSMouseOverButton")
    GSScriptingHandler = objc.lookUpClass("GSScriptingHandler")
else:
    GSMouseOverButton = NSButton
    GSScriptingHandler = objc.lookUpClass("GSMenu")


try:
    scriptsPath = (
        GSGlyphsInfo.applicationSupportPath() + "/Scripts"
    )  # Glyphs 3
except:
    scriptsPath = (
        GSGlyphsInfo.applicationSupportFolder() + "/Scripts"
    )  # Glyphs 2

button_height = 24 if hasRecessedStyleImported else 20
button_gap = 0.24
handle_width = 18
right_margin = 8
icon_button_size = 18
bottom_controls_height = button_height + 10
bottom_button_y = int((bottom_controls_height - icon_button_size) / 2)
defaultsName = "com.ViktorRubenko.FastScripts.button_scripts"
notificationName = "com.ViktorRubenko.FastScripts.reload"


def newButton(frame, title, action, target):
    new_button = NSButton.alloc().initWithFrame_(frame)
    if hasRecessedStyleImported:
        osVersion = int(platform.mac_ver()[0].split(".")[0])
        if osVersion >= 10:  # NSBezelStyleRecessed looks oddly dark in macOS 10.
            new_button.setBezelStyle_(NSBezelStyleRecessed)
            new_button.setButtonType_(NSButtonTypeMomentaryLight)
    else:
        new_button.setBezelStyle_(NSShadowlessSquareBezelStyle)
    new_button.setControlSize_(NSMiniControlSize)
    new_button.setTitle_(title)
    new_button.setFont_(NSFont.systemFontOfSize_(10))
    new_button.setAction_(action)
    new_button.setTarget_(target)
    new_button.setTranslatesAutoresizingMaskIntoConstraints_(False)
    constraint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        new_button,
        NSLayoutAttributeHeight,
        NSLayoutRelationEqual,
        None,
        0,
        1.0,
        button_height,
    )
    new_button.addConstraint_(constraint)
    new_button.setContentCompressionResistancePriority_forOrientation_(100, NSLayoutConstraintOrientationHorizontal)
    return new_button


def removeButton(frame, imageName, action, target):
    new_button = GSMouseOverButton.alloc().initWithFrame_(frame)
    new_button.setBezelStyle_(NSCircularBezelStyle)
    new_button.setBordered_(False)
    new_button.setImage_(NSImage.imageNamed_(imageName))
    new_button.setControlSize_(NSMiniControlSize)
    new_button.setTitle_("")
    new_button.setAction_(action)
    new_button.setTarget_(target)
    new_button.setTranslatesAutoresizingMaskIntoConstraints_(False)
    constraint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        new_button,
        NSLayoutAttributeHeight,
        NSLayoutRelationEqual,
        None,
        0,
        1.0,
        icon_button_size,
    )
    new_button.addConstraint_(constraint)
    constraint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
        new_button,
        NSLayoutAttributeWidth,
        NSLayoutRelationEqual,
        None,
        0,
        1.0,
        icon_button_size,
    )
    new_button.addConstraint_(constraint)
    return new_button


class ButtonTableView(NSTableView):
    def highlightSelectionInClipRect_(self, rect):
        pass


class HighlightButtonCell(NSButtonCell):
    def drawWithFrame_inView_(self, cellFrame, controlView):
        if self.state() == NSOnState:
            NSColor.colorWithCalibratedWhite_alpha_(0.82, 1.0).set()
            highlightFrame = NSMakeRect(
                cellFrame.origin.x,
                cellFrame.origin.y + 2,
                cellFrame.size.width,
                cellFrame.size.height - 4,
            )
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                highlightFrame, 5, 5
            ).fill()
        objc.super(HighlightButtonCell, self).drawWithFrame_inView_(
            cellFrame, controlView
        )


class FastScripts(PalettePlugin):
    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "FastScripts"})
        self.button_scripts = []
        self.dialog = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 150, 100))
        self.dialog.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.heightConstraint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.dialog,
            NSLayoutAttributeHeight,
            NSLayoutRelationEqual,
            None,
            0,
            1.0,
            0,
        )
        self.dialog.addConstraint_(self.heightConstraint)
        self.buttonContainer = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 15, 150, 85)
        )
        self.buttonContainer.setTranslatesAutoresizingMaskIntoConstraints_(
            False
        )
        self.dialog.addSubview_(self.buttonContainer)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.dialog,
            NSLayoutAttributeTop,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeTop,
            1.0,
            0,
        )
        self.dialog.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.dialog,
            NSLayoutAttributeLeading,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeLeading,
            1.0,
            0,
        )
        self.dialog.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.dialog,
            NSLayoutAttributeTrailing,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeTrailing,
            1.0,
            0,
        )
        self.dialog.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.dialog,
            NSLayoutAttributeBottom,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeBottom,
            1.0,
            bottom_controls_height,
        )
        self.dialog.addConstraint_(constaint)
        self.tableView = ButtonTableView.alloc().initWithFrame_(NSMakeRect(0, 0, 150, 85))
        self.tableView.setHeaderView_(None)
        self.tableView.setRowHeight_(button_height)
        self.tableView.setIntercellSpacing_(NSMakeSize(0, button_gap))
        self.tableView.setUsesAlternatingRowBackgroundColors_(False)
        self.tableView.setAllowsMultipleSelection_(False)
        try:
            self.tableView.setSelectionHighlightStyle_(NSTableViewSelectionHighlightStyleNone)
        except:
            pass
        self.tableView.setTarget_(self)
        self.tableView.setAction_(self.runSelectedScript_)
        self.tableView.setDoubleAction_(self.runSelectedScript_)
        self.tableView.setDataSource_(self)
        self.tableView.setDelegate_(self)
        self.tableView.registerForDraggedTypes_([NSPasteboardTypeString])
        self.tableView.setDraggingSourceOperationMask_forLocal_(NSDragOperationMove, True)
        self.handleColumn = NSTableColumn.alloc().initWithIdentifier_("handle")
        self.handleColumn.setEditable_(False)
        self.handleColumn.setWidth_(handle_width)
        self.handleColumn.setMinWidth_(handle_width)
        self.handleColumn.setMaxWidth_(handle_width)
        handle_cell = NSTextFieldCell.alloc().init()
        handle_cell.setFont_(NSFont.systemFontOfSize_(12))
        handle_cell.setAlignment_(0)
        try:
            handle_cell.setBordered_(False)
            handle_cell.setDrawsBackground_(False)
        except:
            pass
        self.handleColumn.setDataCell_(handle_cell)
        self.tableView.addTableColumn_(self.handleColumn)
        self.tableColumn = NSTableColumn.alloc().initWithIdentifier_("scripts")
        self.tableColumn.setEditable_(False)
        self.tableColumn.setResizingMask_(2)
        button_cell = HighlightButtonCell.alloc().init()
        if hasRecessedStyleImported:
            osVersion = int(platform.mac_ver()[0].split(".")[0])
            if osVersion >= 10:
                button_cell.setBezelStyle_(NSBezelStyleRecessed)
                button_cell.setButtonType_(NSButtonTypeMomentaryLight)
        else:
            button_cell.setBezelStyle_(NSShadowlessSquareBezelStyle)
        button_cell.setControlSize_(NSSmallControlSize)
        button_cell.setFont_(NSFont.systemFontOfSize_(12))
        button_cell.setAlignment_(0)
        button_cell.setLineBreakMode_(NSLineBreakByTruncatingTail)
        self.tableColumn.setDataCell_(button_cell)
        self.tableView.addTableColumn_(self.tableColumn)
        self.tableView.setColumnAutoresizingStyle_(1)
        self.tableView.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.buttonContainer.addSubview_(self.tableView)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.tableView,
            NSLayoutAttributeTop,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeTop,
            1.0,
            0,
        )
        self.buttonContainer.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.tableView,
            NSLayoutAttributeLeading,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeLeading,
            1.0,
            0,
        )
        self.buttonContainer.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.tableView,
            NSLayoutAttributeTrailing,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeTrailing,
            1.0,
            -right_margin,
        )
        self.buttonContainer.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.tableView,
            NSLayoutAttributeBottom,
            NSLayoutRelationEqual,
            self.buttonContainer,
            NSLayoutAttributeBottom,
            1.0,
            0,
        )
        self.buttonContainer.addConstraint_(constaint)
        self.add_button = removeButton(
            NSMakeRect(8, bottom_button_y, icon_button_size, icon_button_size),
            "NSAddTemplate",
            self.addScript_,
            self,
        )
        self.dialog.addSubview_(self.add_button)
        self.remove_button = removeButton(
            NSMakeRect(30, bottom_button_y, icon_button_size, icon_button_size),
            "NSRemoveTemplate",
            self.removeSelectedScript_,
            self,
        )
        self.dialog.addSubview_(self.remove_button)
        self.addBottomButtonConstraints()
        self.setupButtons_()
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, self.setupButtons_, notificationName, None
        )

    def __del__(self):
        NSNotificationCenter.defaultCenter().removeObserver_name_object_(
            self, notificationName, None
        )

    @objc.python_method
    def addBottomButtonConstraints(self):
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.add_button,
            NSLayoutAttributeLeading,
            NSLayoutRelationEqual,
            self.dialog,
            NSLayoutAttributeLeading,
            1.0,
            8,
        )
        self.dialog.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.add_button,
            NSLayoutAttributeBottom,
            NSLayoutRelationEqual,
            self.dialog,
            NSLayoutAttributeBottom,
            1.0,
            -bottom_button_y,
        )
        self.dialog.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.remove_button,
            NSLayoutAttributeLeading,
            NSLayoutRelationEqual,
            self.add_button,
            NSLayoutAttributeTrailing,
            1.0,
            4,
        )
        self.dialog.addConstraint_(constaint)
        constaint = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.remove_button,
            NSLayoutAttributeBottom,
            NSLayoutRelationEqual,
            self.add_button,
            NSLayoutAttributeBottom,
            1.0,
            0,
        )
        self.dialog.addConstraint_(constaint)

    def setupButtons_(self, notification=None):
        self.load_data()
        quantity = len(self.button_scripts)
        height = 0
        if quantity > 0:
            height = quantity * button_height + (quantity - 1) * button_gap
        self.heightConstraint.setConstant_(height + bottom_controls_height)
        self.tableView.setFrame_(NSMakeRect(0, 0, 160 - right_margin, height))
        self.handleColumn.setWidth_(handle_width)
        self.tableColumn.setWidth_(
            max(10, self.tableView.frame().size.width - handle_width)
        )
        self.tableView.reloadData()
        self.dialog.invalidateIntrinsicContentSize()

    def numberOfRowsInTableView_(self, tableView):
        return len(self.button_scripts)

    def tableView_objectValueForTableColumn_row_(self, tableView, tableColumn, row):
        column_id = str(tableColumn.identifier())
        if column_id == "handle":
            return "≡"
        return self.titleForScriptPath_(self.button_scripts[row])

    def tableView_willDisplayCell_forTableColumn_row_(self, tableView, cell, tableColumn, row):
        column_id = str(tableColumn.identifier())
        if column_id == "handle":
            cell.setStringValue_("≡")
        elif column_id == "scripts":
            selected = row == tableView.selectedRow()
            cell.setTitle_(self.titleForScriptPath_(self.button_scripts[row]))
            try:
                cell.setState_(NSOnState if selected else NSOffState)
            except:
                pass

    def tableViewSelectionDidChange_(self, notification):
        self.tableView.reloadData()

    def tableView_writeRowsWithIndexes_toPasteboard_(self, tableView, rowIndexes, pasteboard):
        row = rowIndexes.firstIndex()
        if row < 0:
            return False
        pasteboard.declareTypes_owner_([NSPasteboardTypeString], self)
        pasteboard.setString_forType_(str(row), NSPasteboardTypeString)
        return True

    def tableView_validateDrop_proposedRow_proposedDropOperation_(self, tableView, info, row, operation):
        tableView.setDropRow_dropOperation_(row, NSTableViewDropAbove)
        return NSDragOperationMove

    def tableView_acceptDrop_row_dropOperation_(self, tableView, info, row, operation):
        pasteboard = info.draggingPasteboard()
        source_row_text = pasteboard.stringForType_(NSPasteboardTypeString)
        if source_row_text is None:
            return False
        source_row = int(source_row_text)
        if source_row < 0 or source_row >= len(self.button_scripts):
            return False
        if source_row == row or source_row + 1 == row:
            return False
        script_path = self.button_scripts.pop(source_row)
        if source_row < row:
            row -= 1
        row = min(max(row, 0), len(self.button_scripts))
        self.button_scripts.insert(row, script_path)
        self.save_data()
        tableView.reloadData()
        tableView.selectRowIndexes_byExtendingSelection_(
            NSIndexSet.indexSetWithIndex_(row), False
        )
        return True

    def runSelectedScript_(self, sender):
        clicked_column = self.tableView.clickedColumn()
        clicked_row = self.tableView.clickedRow()
        if clicked_column < 0 or clicked_row < 0 or clicked_row >= len(self.button_scripts):
            return
        column_id = str(self.tableView.tableColumns()[clicked_column].identifier())
        if column_id == "handle":
            return
        self.runScriptPath_(self.button_scripts[clicked_row])

    def removeSelectedScript_(self, sender):
        row = self.tableView.selectedRow()
        if row < 0 or row >= len(self.button_scripts):
            return
        self.removeScriptAtIndex_(row)

    @objc.python_method
    def removeScriptAtIndex_(self, row):
        del self.button_scripts[row]
        self.save_data()
        self.tableView.reloadData()
        if len(self.button_scripts) > 0:
            row = min(row, len(self.button_scripts) - 1)
            self.tableView.selectRowIndexes_byExtendingSelection_(
                NSIndexSet.indexSetWithIndex_(row), False
            )
        self.setupButtons_()

    @objc.python_method
    def titleForScriptPath_(self, script_path):
        try:
            with io.open(script_path, "r", encoding="utf-8") as f:
                code = f.read()
        except:
            return os.path.basename(script_path)
        menu_title = re.findall(
            r"^#\s*MenuTitle:\s*(.*)", code, flags=re.IGNORECASE
        )
        if menu_title:
            return menu_title[0]
        return os.path.basename(script_path)

    @objc.python_method
    def load_data(self):
        if Glyphs.defaults[defaultsName]:
            self.button_scripts = list(
                sp
                for sp in Glyphs.defaults[defaultsName]
                if os.path.exists(sp)
            )
        else:
            self.button_scripts = []

    @objc.python_method
    def save_data(self):
        Glyphs.defaults[defaultsName] = self.button_scripts

    @objc.python_method
    def dataHasChanged(self):
        self.save_data()
        NSNotificationCenter.defaultCenter().postNotificationName_object_(
            notificationName, None
        )

    def runScriptCallback_(self, button):
        self.runScriptPath_(button.representedObject())

    def runScriptPath_(self, scriptPath):
        scriptHandler = GSScriptingHandler.alloc()
        scriptHandler.runMacroFile_(scriptPath)

    def removeScriptCallback_(self, button):
        self.button_scripts.remove(button.representedObject())
        self.dataHasChanged()

    def addScript_(self, sender):
        try:
            filepaths = GetOpenFile(
                path=objcObject(scriptsPath),
                filetypes=["py"],
                allowsMultipleSelection=True,
            )
        except:
            import traceback
            print(traceback.format_exc())

        if not filepaths or len(filepaths) == 0:
            return
        self.button_scripts.extend(filepaths)
        self.dataHasChanged()

    @objc.python_method
    def init_button(self, button, script_path):
        with io.open(script_path, "r", encoding="utf-8") as f:
            code = f.read()

            menu_title = re.findall(
                r"^#\s*MenuTitle:\s*(.*)", code, flags=re.IGNORECASE
            )
            if not menu_title:
                return

            button.setRepresentedObject_(script_path)

            menu_title = menu_title[0]
            button.setTitle_(menu_title)
