"""Programmatic Palette views for Glyph Note."""

from __future__ import annotations

import objc
from AppKit import (
    NSBezelBorder,
    NSBoldFontMask,
    NSButton,
    NSColor,
    NSControlSizeSmall,
    NSEventModifierFlagCommand,
    NSEventModifierFlagControl,
    NSEventModifierFlagDeviceIndependentFlagsMask,
    NSEventModifierFlagOption,
    NSEventModifierFlagShift,
    NSFont,
    NSFontAttributeName,
    NSFontManager,
    NSForegroundColorAttributeName,
    NSItalicFontMask,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSScrollView,
    NSStrikethroughStyleAttributeName,
    NSTextAlignmentLeft,
    NSTextField,
    NSTextView,
    NSUnderlineStyleSingle,
    NSView,
    NSViewHeightSizable,
    NSViewMinYMargin,
    NSViewWidthSizable,
)
from Foundation import NSMakeRange

from glyphnote.markup import (
    FLAG_BOLD,
    FLAG_ITALIC,
    FLAG_STRIKE,
    KIND_BOLD,
    KIND_ITALIC,
    KIND_STRIKE,
    StyleRun,
    python_index_to_utf16,
    toggle_style_runs,
    utf16_index_to_python,
)

try:
    from AppKit import NSButtonTypeSwitch
except ImportError:  # pragma: no cover - older AppKit
    NSButtonTypeSwitch = 3


PALETTE_WIDTH = 180
DEFAULT_HEIGHT = 148
CHECKBOX_HEIGHT = 18
LABEL_HEIGHT = 15
TOP_PADDING = 6
INNER_PADDING = 8
EDITOR_FONT_SIZE = 11
EDITOR_TOOLTIP = "Shortcuts: ⌘B bold, ⌘I italic, ⌘⇧X strikethrough."


class _ClickThroughLabel(NSTextField):
    """Placeholder overlay that must not steal clicks from the text view."""

    def hitTest_(self, point):
        return None


def _markup_kind_for_event(event):
    if event is None:
        return None
    flags = event.modifierFlags() & NSEventModifierFlagDeviceIndependentFlagsMask
    command = bool(flags & NSEventModifierFlagCommand)
    shift = bool(flags & NSEventModifierFlagShift)
    option = bool(flags & NSEventModifierFlagOption)
    control = bool(flags & NSEventModifierFlagControl)
    if not command or option or control:
        return None
    chars = (event.charactersIgnoringModifiers() or "").lower()
    if chars == "b" and not shift:
        return KIND_BOLD
    if chars == "i" and not shift:
        return KIND_ITALIC
    if chars == "x" and shift:
        return KIND_STRIKE
    return None


class GlyphNoteTextView(NSTextView):
    """Note editor that applies bold, italic, and strikethrough in place."""

    def _toggle_markup_kind(self, kind):
        target = getattr(self, "_markup_target", None)
        toggle = getattr(target, "toggleMarkupKind_", None) if target else None
        if callable(toggle):
            toggle(kind)
            return True
        return False

    def performKeyEquivalent_(self, event):
        kind = _markup_kind_for_event(event)
        if kind and self._toggle_markup_kind(kind):
            return True
        return objc.super(GlyphNoteTextView, self).performKeyEquivalent_(event)

    def keyDown_(self, event):
        kind = _markup_kind_for_event(event)
        if kind and self._toggle_markup_kind(kind):
            return
        objc.super(GlyphNoteTextView, self).keyDown_(event)

    def bold_(self, sender):
        if not self._toggle_markup_kind(KIND_BOLD):
            objc.super(GlyphNoteTextView, self).bold_(sender)

    def italic_(self, sender):
        if not self._toggle_markup_kind(KIND_ITALIC):
            objc.super(GlyphNoteTextView, self).italic_(sender)

    def paste_(self, sender):
        if hasattr(self, "pasteAsPlainText_"):
            self.pasteAsPlainText_(sender)
            return
        objc.super(GlyphNoteTextView, self).paste_(sender)


class GlyphNotePaletteView:
    """Native Palette chrome: lock checkbox, master label, and note editor."""

    def __init__(self, width=PALETTE_WIDTH, height=DEFAULT_HEIGHT):
        self.dialog = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        self.lock_button = self._make_lock_button(width, height)
        self.master_label = self._make_master_label(width, height)
        self.placeholder = self._make_placeholder(width, height)
        self.text_view = self._make_text_view(width, height)
        self._style_runs = []
        self._style_text = ""
        self.scroll = self._make_scroll(width, height)
        self.scroll.setDocumentView_(self.text_view)
        self.dialog.addSubview_(self.lock_button)
        self.dialog.addSubview_(self.master_label)
        self.dialog.addSubview_(self.scroll)
        self.dialog.addSubview_(self.placeholder)

    def attach_target(self, target):
        self.lock_button.setTarget_(target)
        self.lock_button.setAction_("toggleLock:")
        self.text_view._markup_target = target
        self.text_view.setDelegate_(target)

    def set_enabled(self, enabled):
        self.lock_button.setEnabled_(enabled)
        self.text_view.setEditable_(enabled)
        self.text_view.setSelectable_(enabled)

    def set_placeholder_visible(self, visible):
        self.placeholder.setHidden_(not visible)

    def apply_style_runs(self, text, runs):
        text_view = self.text_view
        storage = text_view.textStorage()
        if storage is None:
            return
        text = text or ""
        base_font = NSFont.systemFontOfSize_(EDITOR_FONT_SIZE)
        base_attrs = _base_attributes(base_font)
        storage.beginEditing()
        try:
            storage.setAttributes_range_(
                base_attrs, _python_range_to_ns(text, 0, len(text))
            )
            for run in runs or ():
                attrs = _attributes_for_flags(base_font, run.flags)
                if attrs:
                    storage.addAttributes_range_(
                        attrs, _python_range_to_ns(text, run.start, run.end)
                    )
        finally:
            storage.endEditing()
        self._style_runs = list(runs or ())
        caret = utf16_index_to_python(text, text_view.selectedRange().location)
        flags = 0
        for run in runs or ():
            if run.start <= caret < run.end:
                flags = run.flags
                break
            if caret == run.end:
                flags = run.flags
        text_view.setTypingAttributes_(_attributes_for_flags(base_font, flags))

    def read_note_contents(self):
        text_view = self.text_view
        text = str(text_view.string() or "")
        extracted = self._extract_style_runs(text)
        if extracted:
            self._style_runs = extracted
            self._style_text = text
            return text, extracted
        if text == getattr(self, "_style_text", None):
            return text, list(self._style_runs)
        self._style_runs = []
        self._style_text = text
        return text, []

    def _extract_style_runs(self, text):
        storage = self.text_view.textStorage()
        if storage is None or not text:
            return []
        flags = []
        for index in range(len(text)):
            utf16 = python_index_to_utf16(text, index)
            flags.append(_flags_at_index(storage, utf16))
        runs = []
        start = 0
        for index in range(1, len(flags) + 1):
            if index == len(flags) or flags[index] != flags[start]:
                if flags[start]:
                    runs.append(StyleRun(start, index, flags[start]))
                start = index
        return runs

    def toggle_style_kind(self, kind):
        bit = _FLAG_BY_KIND.get(kind)
        if not bit:
            return False
        text_view = self.text_view
        if not text_view.isEditable():
            return False
        text = str(text_view.string() or "")
        selected = text_view.selectedRange()
        start = utf16_index_to_python(text, selected.location)
        end = utf16_index_to_python(text, selected.location + selected.length)
        if end <= start:
            attrs = dict(text_view.typingAttributes() or {})
            flags = _flags_from_attributes(attrs)
            if flags & bit:
                flags &= ~bit
            else:
                flags |= bit
            text_view.setTypingAttributes_(
                _attributes_for_flags(NSFont.systemFontOfSize_(EDITOR_FONT_SIZE), flags)
            )
            return True
        self._style_runs = toggle_style_runs(
            self._style_runs, start, end, bit, len(text)
        )
        self.apply_style_runs(text, self._style_runs)
        text_view.setSelectedRange_(selected)
        text_view.didChangeText()
        return True

    def _make_lock_button(self, width, height):
        button = NSButton.alloc().initWithFrame_(
            NSMakeRect(
                INNER_PADDING,
                height - TOP_PADDING - CHECKBOX_HEIGHT,
                width - INNER_PADDING * 2,
                CHECKBOX_HEIGHT,
            )
        )
        button.setButtonType_(NSButtonTypeSwitch)
        button.setControlSize_(NSControlSizeSmall)
        button.setTitle_("Lock for all masters")
        button.setToolTip_(
            "When checked, the note is identical across all masters. "
            "When unchecked, each master has an independent note."
        )
        button.setFont_(NSFont.systemFontOfSize_(11))
        button.setAllowsMixedState_(True)
        button.setAutoresizingMask_(NSViewWidthSizable | NSViewMinYMargin)
        return button

    def _make_master_label(self, width, height):
        label = NSTextField.labelWithString_("Master: —")
        label.setFrame_(
            NSMakeRect(
                INNER_PADDING,
                height - TOP_PADDING - CHECKBOX_HEIGHT - LABEL_HEIGHT - 2,
                width - INNER_PADDING * 2,
                LABEL_HEIGHT,
            )
        )
        label.setFont_(NSFont.systemFontOfSize_(10))
        label.setTextColor_(NSColor.secondaryLabelColor())
        label.setLineBreakMode_(NSLineBreakByTruncatingTail)
        label.setAutoresizingMask_(NSViewWidthSizable | NSViewMinYMargin)
        return label

    def _editor_frame(self, width, height):
        top = TOP_PADDING + CHECKBOX_HEIGHT + LABEL_HEIGHT + 8
        return NSMakeRect(
            INNER_PADDING,
            INNER_PADDING,
            width - INNER_PADDING * 2,
            max(36, height - top - INNER_PADDING),
        )

    def _make_text_view(self, width, height):
        frame = self._editor_frame(width, height)
        text_view = GlyphNoteTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, frame.size.width, frame.size.height)
        )
        text_view._markup_target = None
        text_view.setRichText_(True)
        text_view.setImportsGraphics_(False)
        if hasattr(text_view, "setUsesFontPanel_"):
            text_view.setUsesFontPanel_(False)
        text_view.setFont_(NSFont.systemFontOfSize_(EDITOR_FONT_SIZE))
        if hasattr(text_view, "setUsesFindBar_"):
            text_view.setUsesFindBar_(True)
        text_view.setAutomaticQuoteSubstitutionEnabled_(False)
        text_view.setAutomaticDashSubstitutionEnabled_(False)
        text_view.setAutomaticTextReplacementEnabled_(False)
        text_view.setVerticallyResizable_(True)
        text_view.setHorizontallyResizable_(False)
        text_view.setAutoresizingMask_(NSViewWidthSizable)
        text_view.setTextContainerInset_((3, 4))
        text_view.setDrawsBackground_(True)
        text_view.setBackgroundColor_(NSColor.textBackgroundColor())
        text_view.setToolTip_(EDITOR_TOOLTIP)
        container = text_view.textContainer()
        if container is not None:
            container.setWidthTracksTextView_(True)
            container.setContainerSize_((frame.size.width, 1.0e7))
        return text_view

    def _make_scroll(self, width, height):
        scroll = NSScrollView.alloc().initWithFrame_(self._editor_frame(width, height))
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setBorderType_(NSBezelBorder)
        scroll.setDrawsBackground_(True)
        scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        return scroll

    def _make_placeholder(self, width, height):
        frame = self._editor_frame(width, height)
        label = _ClickThroughLabel.alloc().initWithFrame_(
            NSMakeRect(
                frame.origin.x + 6,
                frame.origin.y + frame.size.height - 20,
                frame.size.width - 12,
                16,
            )
        )
        label.setBezeled_(False)
        label.setBordered_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setFont_(NSFont.systemFontOfSize_(11))
        label.setTextColor_(NSColor.placeholderTextColor())
        label.setAlignment_(NSTextAlignmentLeft)
        label.setDrawsBackground_(False)
        label.setRefusesFirstResponder_(True)
        label.setAutoresizingMask_(NSViewWidthSizable | NSViewMinYMargin)
        return label


def _python_range_to_ns(text, start, end):
    location = python_index_to_utf16(text, start)
    length = python_index_to_utf16(text, end) - location
    return NSMakeRange(location, max(0, length))


_FLAG_BY_KIND = {
    KIND_BOLD: FLAG_BOLD,
    KIND_ITALIC: FLAG_ITALIC,
    KIND_STRIKE: FLAG_STRIKE,
}


def _base_attributes(font):
    return {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: NSColor.textColor(),
        NSStrikethroughStyleAttributeName: 0,
    }


def _attributes_for_flags(base_font, flags):
    attrs = _base_attributes(base_font)
    traits = 0
    if flags & FLAG_BOLD:
        traits |= NSBoldFontMask
    if flags & FLAG_ITALIC:
        traits |= NSItalicFontMask
    if traits:
        converted = NSFontManager.sharedFontManager().convertFont_toHaveTrait_(
            base_font, traits
        )
        attrs[NSFontAttributeName] = converted or base_font
    if flags & FLAG_STRIKE:
        attrs[NSStrikethroughStyleAttributeName] = NSUnderlineStyleSingle
    return attrs


def _attribute_at(storage, name, utf16_index):
    try:
        result = storage.attribute_atIndex_effectiveRange_(name, utf16_index, None)
        if isinstance(result, tuple):
            return result[0]
        return result
    except Exception:
        return None


def _attributes_at(storage, utf16_index):
    result = storage.attributesAtIndex_effectiveRange_(utf16_index, None)
    if isinstance(result, tuple):
        return result[0]
    return result


def _flags_at_index(storage, utf16_index):
    attrs = _attributes_at(storage, utf16_index)
    flags = _flags_from_attributes(attrs)
    if flags:
        return flags
    font = _attribute_at(storage, NSFontAttributeName, utf16_index)
    strike = _attribute_at(storage, NSStrikethroughStyleAttributeName, utf16_index)
    return _flags_from_font(font, strike)


def _flags_from_attributes(attrs):
    if not attrs:
        return 0
    font = None
    strike = 0
    try:
        font = attrs.objectForKey_(NSFontAttributeName)
        strike = attrs.objectForKey_(NSStrikethroughStyleAttributeName)
    except Exception:
        try:
            font = attrs.get(NSFontAttributeName)
            strike = attrs.get(NSStrikethroughStyleAttributeName)
        except Exception:
            pass
    return _flags_from_font(font, strike)


def _flags_from_font(font, strike=0):
    flags = 0
    if font is not None:
        try:
            traits = NSFontManager.sharedFontManager().traitsOfFont_(font)
            if traits & NSBoldFontMask:
                flags |= FLAG_BOLD
            if traits & NSItalicFontMask:
                flags |= FLAG_ITALIC
        except Exception:
            pass
        try:
            symbolic = font.fontDescriptor().symbolicTraits()
            if symbolic & 2:  # NSFontDescriptorTraitBold
                flags |= FLAG_BOLD
            if symbolic & 1:  # NSFontDescriptorTraitItalic
                flags |= FLAG_ITALIC
        except Exception:
            pass
        try:
            name = (font.fontName() or "").lower()
            if "bold" in name:
                flags |= FLAG_BOLD
            if "italic" in name or "oblique" in name:
                flags |= FLAG_ITALIC
        except Exception:
            pass
    try:
        if int(strike or 0):
            flags |= FLAG_STRIKE
    except (TypeError, ValueError):
        if strike:
            flags |= FLAG_STRIKE
    return flags
