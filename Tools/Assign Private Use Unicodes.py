#MenuTitle: Assign Private Use Unicodes
# -*- coding: utf-8 -*-
__doc__ = """
Assigns consecutive Private Use Area Unicode values to the selected glyphs,
starting at U+E000.
"""

from GlyphsApp import Glyphs, Message
from AppKit import NSAlert, NSAlertFirstButtonReturn

try:
    from AppKit import NSAlertStyleWarning, NSAlertStyleInformational
except ImportError:
    from AppKit import NSWarningAlertStyle as NSAlertStyleWarning
    from AppKit import NSInformationalAlertStyle as NSAlertStyleInformational


START_UNICODE = 0xE000
END_UNICODE = 0xF8FF


def is_private_use(unicode_value):
    if not unicode_value:
        return False

    value = int(str(unicode_value), 16)
    return (
        0xE000 <= value <= 0xF8FF
        or 0xF0000 <= value <= 0xFFFFD
        or 0x100000 <= value <= 0x10FFFD
    )


def format_unicode(unicode_value):
    if not unicode_value:
        return "none"

    return "U+%04X" % int(str(unicode_value), 16)


def confirm(title, message, style=NSAlertStyleInformational):
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(message)
    alert.setAlertStyle_(style)
    alert.addButtonWithTitle_("Overwrite")
    alert.addButtonWithTitle_("Cancel")
    return alert.runModal() == NSAlertFirstButtonReturn


font = Glyphs.font

if not font:
    Message(
        title="No Font Open",
        message="Open a font and select the glyphs you want to encode.",
        OKButton="OK",
    )
else:
    selected_glyphs = []
    seen_glyph_names = set()

    for layer in font.selectedLayers:
        glyph = layer.parent
        if glyph.name not in seen_glyph_names:
            selected_glyphs.append(glyph)
            seen_glyph_names.add(glyph.name)

    if not selected_glyphs:
        Message(
            title="No Glyphs Selected",
            message="Select one or more glyphs and run the script again.",
            OKButton="OK",
        )
    elif START_UNICODE + len(selected_glyphs) - 1 > END_UNICODE:
        Message(
            title="Too Many Glyphs",
            message="The Basic Private Use Area only runs from U+E000 to U+F8FF.",
            OKButton="OK",
        )
    else:
        glyphs_with_pua = []
        glyphs_with_regular_unicode = []

        for glyph in selected_glyphs:
            if glyph.unicode:
                current_unicode = format_unicode(glyph.unicode)
                entry = "%s (%s)" % (glyph.name, current_unicode)

                if is_private_use(glyph.unicode):
                    glyphs_with_pua.append(entry)
                else:
                    glyphs_with_regular_unicode.append(entry)

        should_continue = True

        if glyphs_with_regular_unicode:
            message = (
                "The following selected glyphs already have regular Unicode "
                "values. Overwriting them can change typed text behavior:\n\n%s"
                "\n\nContinue and replace them with Private Use values?"
            ) % "\n".join(glyphs_with_regular_unicode)
            should_continue = confirm(
                "Warning: Regular Unicode Values",
                message,
                NSAlertStyleWarning,
            )

        if should_continue and glyphs_with_pua:
            message = (
                "The following selected glyphs already have Private Use Unicode "
                "values:\n\n%s\n\nContinue and overwrite them?"
            ) % "\n".join(glyphs_with_pua)
            should_continue = confirm(
                "Overwrite Existing Private Use Values",
                message,
                NSAlertStyleInformational,
            )

        if should_continue:
            font.disableUpdateInterface()

            try:
                for index, glyph in enumerate(selected_glyphs):
                    glyph.beginUndo()

                    try:
                        glyph.unicode = "%04X" % (START_UNICODE + index)
                    finally:
                        glyph.endUndo()
            finally:
                font.enableUpdateInterface()

            first_unicode = "U+%04X" % START_UNICODE
            last_unicode = "U+%04X" % (START_UNICODE + len(selected_glyphs) - 1)

            Message(
                title="Private Use Values Assigned",
                message="Assigned %s through %s to %i selected glyphs."
                % (first_unicode, last_unicode, len(selected_glyphs)),
                OKButton="OK",
            )
