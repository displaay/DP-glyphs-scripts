"""Programmatic Palette views for Glyph Note."""

from __future__ import annotations

from AppKit import (
    NSBezelBorder,
    NSButton,
    NSColor,
    NSControlSizeSmall,
    NSFont,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSScrollView,
    NSTextAlignmentLeft,
    NSTextField,
    NSTextView,
    NSView,
    NSViewHeightSizable,
    NSViewMinYMargin,
    NSViewWidthSizable,
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


class _ClickThroughLabel(NSTextField):
    """Placeholder overlay that must not steal clicks from the text view."""

    def hitTest_(self, point):
        return None


class GlyphNotePaletteView:
    """Native Palette chrome: lock checkbox, master label, and note editor."""

    def __init__(self, width=PALETTE_WIDTH, height=DEFAULT_HEIGHT):
        self.dialog = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        self.lock_button = self._make_lock_button(width, height)
        self.master_label = self._make_master_label(width, height)
        self.placeholder = self._make_placeholder(width, height)
        self.text_view = self._make_text_view(width, height)
        self.scroll = self._make_scroll(width, height)
        self.scroll.setDocumentView_(self.text_view)
        self.dialog.addSubview_(self.lock_button)
        self.dialog.addSubview_(self.master_label)
        self.dialog.addSubview_(self.scroll)
        self.dialog.addSubview_(self.placeholder)

    def attach_target(self, target):
        self.lock_button.setTarget_(target)
        self.lock_button.setAction_("toggleLock:")
        self.text_view.setDelegate_(target)

    def set_enabled(self, enabled):
        self.lock_button.setEnabled_(enabled)
        self.text_view.setEditable_(enabled)
        self.text_view.setSelectable_(enabled)

    def set_placeholder_visible(self, visible):
        self.placeholder.setHidden_(not visible)

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
        text_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, frame.size.width, frame.size.height)
        )
        text_view.setRichText_(False)
        text_view.setImportsGraphics_(False)
        text_view.setFont_(NSFont.systemFontOfSize_(11))
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
