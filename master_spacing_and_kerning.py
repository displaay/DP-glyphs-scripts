# MenuTitle: Master Spacing and Kerning Adjuster
# -*- coding: utf-8 -*-

import traceback

import objc
import AppKit
from Foundation import NSObject, NSMakeRect, NSMakeSize, NSNotificationCenter
from AppKit import (
    NSAlert,
    NSBackingStoreBuffered,
    NSBox,
    NSButton,
    NSButtonCell,
    NSFont,
    NSPopUpButton,
    NSScrollView,
    NSTableColumn,
    NSTableView,
    NSTextField,
    NSTextFieldCell,
    NSWindow,
)
from GlyphsApp import Glyphs, LTR

SOURCE_MODES = ["Percent", "Fixed value", "InDesign", "Figma", "Web"]
SCOPE_MODES = ["Spacing only", "Spacing and kerning"]
GLYPH_SCOPES = ["All glyphs", "Selected glyphs only", "Exporting glyphs only"]
FIGMA_UNITS = ["px", "%"]
WEB_UNITS = ["em", "px"]

WINDOW_WIDTH = 796
WINDOW_MIN_WIDTH = 796

OUTER_MARGIN = 14
SECTION_GAP = 10
SETTINGS_BOX_HEIGHT = 116
BULK_BOX_HEIGHT = 60
FOOTER_HEIGHT = 40
TABLE_ROW_HEIGHT = 24
TABLE_HEADER_HEIGHT = 26
TABLE_PADDING = 10
MAX_VISIBLE_MASTER_ROWS = 8

STYLE_MASK_TITLED = getattr(AppKit, "NSWindowStyleMaskTitled", AppKit.NSTitledWindowMask)
STYLE_MASK_CLOSABLE = getattr(AppKit, "NSWindowStyleMaskClosable", AppKit.NSClosableWindowMask)
STYLE_MASK_MINIATURIZABLE = getattr(AppKit, "NSWindowStyleMaskMiniaturizable", AppKit.NSMiniaturizableWindowMask)

STATE_ON = getattr(AppKit, "NSControlStateValueOn", 1)
STATE_OFF = getattr(AppKit, "NSControlStateValueOff", 0)
SWITCH_BUTTON = getattr(AppKit, "NSSwitchButton", 3)
ALIGN_LEFT = getattr(AppKit, "NSTextAlignmentLeft", 0)
ALIGN_RIGHT = getattr(AppKit, "NSTextAlignmentRight", 2)
SMALL_CONTROL_SIZE = getattr(AppKit, "NSSmallControlSize", 1)
REGULAR_SQUARE_BEZEL = getattr(AppKit, "NSRegularSquareBezelStyle", 2)
ROUNDED_BEZEL = getattr(AppKit, "NSRoundedBezelStyle", 1)
TABLE_LAST_COLUMN_AUTOSIZE = getattr(AppKit, "NSTableViewLastColumnOnlyAutoresizingStyle", 3)
CHANGE_DONE = getattr(AppKit, "NSChangeDone", 1)

TOOL_INSTANCE_KEY = "_DP_MASTER_SPACING_KERNING_TOOL_INSTANCE"


def get_font_and_masters():
    font = Glyphs.font
    if font is None:
        return None, []
    return font, list(font.masters)


def make_label(frame, text, font=None, alignment=ALIGN_LEFT):
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setEditable_(False)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setSelectable_(False)
    label.setAlignment_(alignment)
    if font is not None:
        label.setFont_(font)
    return label


def make_text_field(frame, text="", editable=True, alignment=ALIGN_LEFT, placeholder=None):
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text)
    field.setEditable_(editable)
    field.setAlignment_(alignment)
    if editable:
        field.setBezeled_(True)
        field.setDrawsBackground_(True)
        try:
            if placeholder:
                field.setPlaceholderString_(placeholder)
        except Exception:
            pass
    else:
        field.setBezeled_(False)
        field.setDrawsBackground_(False)
        field.setSelectable_(False)
    set_small_control(field)
    return field


def make_button(frame, title, target=None, action=None, bezel_style=ROUNDED_BEZEL):
    button = NSButton.alloc().initWithFrame_(frame)
    button.setTitle_(title)
    button.setBezelStyle_(bezel_style)
    if target is not None:
        button.setTarget_(target)
    if action is not None:
        button.setAction_(action)
    set_small_control(button)
    return button


def make_popup(frame, items, selected_title=None, target=None, action=None):
    popup = NSPopUpButton.alloc().initWithFrame_(frame)
    popup.addItemsWithTitles_(items)
    if selected_title in items:
        popup.selectItemWithTitle_(selected_title)
    if target is not None:
        popup.setTarget_(target)
    if action is not None:
        popup.setAction_(action)
    set_small_control(popup)
    return popup


def make_box(frame, title):
    box = NSBox.alloc().initWithFrame_(frame)
    box.setTitle_(title)
    return box


def set_small_control(control):
    try:
        control.setControlSize_(SMALL_CONTROL_SIZE)
    except Exception:
        pass
    try:
        control.cell().setControlSize_(SMALL_CONTROL_SIZE)
    except Exception:
        pass
    return control


def set_hidden(views, hidden):
    for view in views:
        try:
            view.setHidden_(hidden)
        except Exception:
            pass


def safe_string(value):
    if value is None:
        return ""
    return str(value)


def parse_numeric_input(raw_value, allowed_suffixes=None):
    text = safe_string(raw_value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    lower_text = text.lower()
    for suffix in allowed_suffixes or []:
        suffix = suffix.lower()
        if lower_text.endswith(suffix):
            text = text[: len(text) - len(suffix)].strip()
            break
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def format_number(value, decimals=2):
    rounded = round(float(value), decimals)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    text = ("%%.%df" % decimals) % rounded
    return text.rstrip("0").rstrip(".")


def format_signed_number(value, decimals=2):
    prefix = "+" if float(value) >= 0 else ""
    return "%s%s" % (prefix, format_number(value, decimals))


def pluralize(count, singular, plural=None):
    if count == 1:
        return singular
    return plural if plural is not None else singular + "s"


def show_alert(title, message):
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(message)
    alert.addButtonWithTitle_("OK")
    alert.runModal()


def get_selected_source_mode(controller):
    return controller.sourcePopup.titleOfSelectedItem()


def get_selected_scope_mode(controller):
    return controller.scopePopup.titleOfSelectedItem()


def get_glyph_scope(controller):
    return controller.glyphScopePopup.titleOfSelectedItem()


def needs_reference_size(source_mode, figma_unit, web_unit):
    return (source_mode == "Figma" and figma_unit == "px") or (source_mode == "Web" and web_unit == "px")


def get_reference_size_state(source_mode, figma_unit, web_unit, reference_text):
    if not needs_reference_size(source_mode, figma_unit, web_unit):
        return False, True, ""

    if not safe_string(reference_text).strip():
        return True, False, "Reference text size is required for px conversion."

    reference_value = parse_reference_px(reference_text)
    if reference_value is None:
        return True, False, "Reference text size must be numeric."
    if reference_value <= 0:
        return True, False, "Reference text size must be greater than 0."

    return True, True, ""


def describe_source_mode(source_mode, figma_unit, web_unit):
    if source_mode == "Figma":
        return "Figma (%s)" % figma_unit
    if source_mode == "Web":
        return "Web (%s)" % web_unit
    return source_mode


def describe_glyph_scope(glyph_scope):
    return glyph_scope.lower()


def get_bulk_placeholder(source_mode, figma_unit, web_unit):
    if source_mode == "Percent":
        return "e.g. +5%"
    if source_mode == "Fixed value":
        return "e.g. +5"
    if source_mode == "InDesign":
        return "e.g. +10"
    if source_mode == "Figma" and figma_unit == "%":
        return "e.g. +2%"
    if source_mode == "Figma" and figma_unit == "px":
        return "e.g. +2px"
    if source_mode == "Web" and web_unit == "em":
        return "e.g. +0.02em"
    if source_mode == "Web" and web_unit == "px":
        return "e.g. +1px"
    return "Enter value"


def get_preset_definitions(source_mode, figma_unit, web_unit):
    """
    Presets stay intentionally lightweight. They insert values in the currently visible source
    system so the shortcuts feel native to the selected mode without adding another conversion
    layer on top of the real one.
    """
    if source_mode == "Percent":
        return [
            {"label": "+2%", "value": "+2%"},
            {"label": "+5%", "value": "+5%"},
            {"label": "+10%", "value": "+10%"},
        ]

    if source_mode == "Fixed value":
        return [
            {"label": "+5", "value": "+5"},
            {"label": "+10", "value": "+10"},
            {"label": "+20", "value": "+20"},
        ]

    if source_mode == "InDesign":
        return [
            {"label": "+5", "value": "+5"},
            {"label": "+10", "value": "+10"},
            {"label": "+20", "value": "+20"},
        ]

    if source_mode == "Figma" and figma_unit == "%":
        return [
            {"label": "+2%", "value": "+2%"},
            {"label": "+5%", "value": "+5%"},
            {"label": "+10%", "value": "+10%"},
        ]

    if source_mode == "Figma" and figma_unit == "px":
        return [
            {"label": "+1px", "value": "+1px"},
            {"label": "+2px", "value": "+2px"},
            {"label": "+4px", "value": "+4px"},
        ]

    if source_mode == "Web" and web_unit == "em":
        return [
            {"label": "+0.01em", "value": "+0.01em"},
            {"label": "+0.02em", "value": "+0.02em"},
            {"label": "+0.04em", "value": "+0.04em"},
        ]

    if source_mode == "Web" and web_unit == "px":
        return [
            {"label": "+1px", "value": "+1px"},
            {"label": "+2px", "value": "+2px"},
            {"label": "+4px", "value": "+4px"},
        ]

    return [
        {"label": "+5", "value": "+5"},
        {"label": "+10", "value": "+10"},
        {"label": "+20", "value": "+20"},
    ]


def unique_glyphs(glyphs):
    seen = set()
    unique = []
    for glyph in glyphs:
        glyph_id = safe_string(getattr(glyph, "id", None)) or safe_string(getattr(glyph, "name", None))
        if glyph_id in seen:
            continue
        seen.add(glyph_id)
        unique.append(glyph)
    return unique


def get_target_glyphs(font, glyph_scope):
    if glyph_scope == "All glyphs":
        return list(font.glyphs)

    if glyph_scope == "Selected glyphs only":
        selected = []
        try:
            selected = list(font.selection or [])
        except Exception:
            selected = []
        if not selected:
            selected = [glyph for glyph in font.glyphs if getattr(glyph, "selected", False)]
        return unique_glyphs(selected)

    if glyph_scope == "Exporting glyphs only":
        return [glyph for glyph in font.glyphs if getattr(glyph, "export", False)]

    return list(font.glyphs)


def parse_reference_px(reference_text):
    return parse_numeric_input(reference_text, ["px"])


def convert_fixed_value_to_glyphs_delta(input_value):
    # Fixed value formula:
    # glyphs_delta = input
    return float(input_value)


def percent_input_to_scale_factor(input_value):
    # Percent scale formula:
    # scale_factor = 1 + input / 100.0
    return 1.0 + (float(input_value) / 100.0)


def convert_indesign_to_glyphs_delta(input_value, upm):
    # InDesign tracking/kerning is treated as 1/1000 em in version 1.
    # Formula:
    # glyphs_delta = round(UPM * input / 1000.0)
    return quantize_units(float(upm) * float(input_value) / 1000.0)


def convert_web_em_to_glyphs_delta(input_value, upm):
    # CSS letter-spacing in em.
    # Formula:
    # glyphs_delta = round(UPM * input)
    return quantize_units(float(upm) * float(input_value))


def convert_px_based_tracking_to_glyphs_delta(input_value, upm, ref_px):
    # Shared px conversion for Web px and Figma px.
    # Formula:
    # glyphs_delta = round(UPM * input / refPx)
    return quantize_units(float(upm) * float(input_value) / float(ref_px))


def convert_figma_percent_to_glyphs_delta(input_value, upm):
    # Version-1 assumption:
    # Figma % is treated as a percentage of font size.
    # Formula:
    # glyphs_delta = round(UPM * input / 100.0)
    # Keep this isolated so it remains easy to revise later if Figma semantics need a different
    # interpretation.
    return quantize_units(float(upm) * float(input_value) / 100.0)


def convert_input_to_glyphs_units(raw_value, source_mode, upm, figma_unit, web_unit, reference_text_size_text):
    """
    Conversion assumptions are isolated here on purpose so they are easy to audit and edit.

    Percent:
        Interpreted as a proportional scale.
        Formula:
            scale_factor = 1 + input / 100.0
            new_lsb = round(current_lsb * scale_factor)
            new_rsb = round(current_rsb * scale_factor)
            new_kern = round(current_kern * scale_factor)

    Fixed value:
        Formula:
            glyphs_delta = input

    InDesign:
        Assumption for v1: tracking is expressed in 1/1000 em.
        Formula:
            glyphs_delta = round(UPM * input / 1000.0)

    Figma:
        Pixel mode uses the same px conversion as Web:
            glyphs_delta = round(UPM * input / refPx)
        Percent mode uses an explicit version-1 assumption:
            glyphs_delta = round(UPM * input / 100.0)

    Web:
        em mode:
            glyphs_delta = round(UPM * input)
        px mode:
            glyphs_delta = round(UPM * input / refPx)

    All non-percent source modes become per-sidebearing deltas in Glyphs units. This keeps the
    v1 behavior aligned with the fixed-value model while leaving outlines and explicit width writes
    untouched.
    """
    text = safe_string(raw_value).strip()
    if not text:
        return {"status": "empty", "message": "No change"}

    reference_size = parse_reference_px(reference_text_size_text)

    if source_mode == "Percent":
        number = parse_numeric_input(text, ["%"])
        if number is None:
            return {"status": "invalid", "message": "Invalid percent value"}
        return {
            "status": "ok",
            "kind": "scale",
            "factor": percent_input_to_scale_factor(number),
            "raw": number,
            "input_text": text,
            "source_mode": source_mode,
            "source_unit": "%",
        }

    if source_mode == "Fixed value":
        number = parse_numeric_input(text, ["units", "unit", "u"])
        if number is None:
            return {"status": "invalid", "message": "Invalid value"}
        return {
            "status": "ok",
            "kind": "delta",
            "units": convert_fixed_value_to_glyphs_delta(number),
            "raw": number,
            "input_text": text,
            "source_mode": source_mode,
            "source_unit": "u",
        }

    if source_mode == "InDesign":
        number = parse_numeric_input(text)
        if number is None:
            return {"status": "invalid", "message": "Invalid InDesign value"}
        return {
            "status": "ok",
            "kind": "delta",
            "units": convert_indesign_to_glyphs_delta(number, upm),
            "raw": number,
            "input_text": text,
            "source_mode": source_mode,
        }

    if source_mode == "Figma":
        if figma_unit == "%":
            number = parse_numeric_input(text, ["%"])
            if number is None:
                return {"status": "invalid", "message": "Invalid Figma % value"}
            return {
                "status": "ok",
                "kind": "delta",
                "units": convert_figma_percent_to_glyphs_delta(number, upm),
                "raw": number,
                "input_text": text,
                "source_mode": source_mode,
                "source_unit": "%",
            }

        if figma_unit == "px":
            number = parse_numeric_input(text, ["px"])
            if number is None:
                return {"status": "invalid", "message": "Invalid Figma px value"}
            if reference_size is None:
                return {"status": "invalid", "message": "Needs reference size"}
            if reference_size <= 0:
                return {"status": "invalid", "message": "Invalid reference size"}
            return {
                "status": "ok",
                "kind": "delta",
                "units": convert_px_based_tracking_to_glyphs_delta(number, upm, reference_size),
                "raw": number,
                "input_text": text,
                "reference_px": reference_size,
                "source_mode": source_mode,
                "source_unit": "px",
            }

    if source_mode == "Web":
        if web_unit == "em":
            number = parse_numeric_input(text, ["em"])
            if number is None:
                return {"status": "invalid", "message": "Invalid Web em value"}
            return {
                "status": "ok",
                "kind": "delta",
                "units": convert_web_em_to_glyphs_delta(number, upm),
                "raw": number,
                "input_text": text,
                "source_mode": source_mode,
                "source_unit": "em",
            }

        if web_unit == "px":
            number = parse_numeric_input(text, ["px"])
            if number is None:
                return {"status": "invalid", "message": "Invalid Web px value"}
            if reference_size is None:
                return {"status": "invalid", "message": "Needs reference size"}
            if reference_size <= 0:
                return {"status": "invalid", "message": "Invalid reference size"}
            return {
                "status": "ok",
                "kind": "delta",
                "units": convert_px_based_tracking_to_glyphs_delta(number, upm, reference_size),
                "raw": number,
                "input_text": text,
                "reference_px": reference_size,
                "source_mode": source_mode,
                "source_unit": "px",
            }

    return {"status": "invalid", "message": "Invalid source settings"}


def adjustment_is_noop(adjustment):
    if adjustment.get("kind") == "scale":
        return abs(float(adjustment.get("factor", 1.0)) - 1.0) < 1e-9
    return abs(float(adjustment.get("units", 0.0))) < 1e-9


def format_reference_px(reference_px):
    return "%spx" % format_number(reference_px)


def format_source_value_for_preview(adjustment):
    source_mode = adjustment.get("source_mode")
    source_unit = adjustment.get("source_unit")
    raw_value = adjustment.get("raw")

    if raw_value is None:
        return ""

    if source_mode == "InDesign":
        return format_signed_number(raw_value)

    if source_unit == "%":
        return "%s%%" % format_signed_number(raw_value)

    if source_unit == "em":
        return "%sem" % format_number(raw_value, 3)

    if source_unit == "px":
        return "%spx" % format_number(raw_value)

    return format_signed_number(raw_value)


def build_source_context_text(adjustment):
    source_mode = adjustment.get("source_mode")
    if source_mode not in ("InDesign", "Figma", "Web"):
        return ""

    source_value = format_source_value_for_preview(adjustment)
    if source_mode in ("Figma", "Web") and adjustment.get("source_unit") == "px":
        return "(from %s %s @ %s)" % (
            source_mode,
            source_value,
            format_reference_px(adjustment.get("reference_px")),
        )

    return "(from %s %s)" % (source_mode, source_value)


def build_spacing_preview_text(adjustment):
    if adjustment["kind"] == "scale":
        return "LSB/RSB scaled to %s%%" % format_number(adjustment["factor"] * 100.0)

    side_delta = float(adjustment["units"])
    total_spacing = side_delta * 2.0
    preview = "%s u per side (~%s total spacing)" % (
        format_signed_number(side_delta),
        format_signed_number(total_spacing),
    )

    source_context = build_source_context_text(adjustment)
    if source_context:
        preview = "%s %s" % (preview, source_context)

    return preview


def build_kerning_preview_text(adjustment):
    if adjustment["kind"] == "scale":
        return "Kerning scaled to %s%%" % format_number(adjustment["factor"] * 100.0)
    return "Kerning delta: %s u" % format_signed_number(adjustment["units"])


def build_preview_text(adjustment, scope_mode):
    include_kerning = scope_mode == "Spacing and kerning"
    spacing_preview = build_spacing_preview_text(adjustment)

    if include_kerning:
        return "%s | %s" % (spacing_preview, build_kerning_preview_text(adjustment))
    return spacing_preview


def evaluate_row_state(row, font, source_mode, scope_mode, figma_unit, web_unit, reference_text_size_text, preview_on):
    if not row["apply"]:
        return {
            "checked": False,
            "actionable": False,
            "blocking": False,
            "preview": "",
            "note": "Skipped",
            "adjustment": None,
        }

    # Empty checked rows are treated as explicit no-change rows. This lets the user keep every
    # master enabled by default while only filling the masters they actually want to change.
    raw_value = safe_string(row.get("input", ""))
    adjustment = convert_input_to_glyphs_units(
        raw_value,
        source_mode,
        font.upm,
        figma_unit,
        web_unit,
        reference_text_size_text,
    )

    if adjustment["status"] == "empty":
        return {
            "checked": True,
            "actionable": False,
            "blocking": False,
            "preview": "",
            "note": "No change",
            "adjustment": None,
        }

    if adjustment["status"] != "ok":
        return {
            "checked": True,
            "actionable": False,
            "blocking": True,
            "preview": "",
            "note": adjustment["message"],
            "adjustment": None,
        }

    if adjustment_is_noop(adjustment):
        return {
            "checked": True,
            "actionable": False,
            "blocking": False,
            "preview": "No effective change" if preview_on else "",
            "note": "No change",
            "adjustment": adjustment,
        }

    return {
        "checked": True,
        "actionable": True,
        "blocking": False,
        "preview": build_preview_text(adjustment, scope_mode) if preview_on else "",
        "note": "Ready",
        "adjustment": adjustment,
    }


def build_summary_text(actionable_count, source_label, scope_label, glyph_scope_label):
    return "Will adjust %d %s | source: %s | %s | %s" % (
        actionable_count,
        pluralize(actionable_count, "master"),
        source_label,
        scope_label.lower(),
        glyph_scope_label,
    )


def update_summary(controller, text):
    controller.summaryLabel.setStringValue_(text)


def validate_ui_state(controller):
    source_mode = get_selected_source_mode(controller)
    scope_mode = get_selected_scope_mode(controller)
    glyph_scope = get_glyph_scope(controller)
    preview_on = controller.previewCheckbox.state() == STATE_ON
    reference_text = controller.referenceField.stringValue().strip()

    checked_count = 0
    actionable_count = 0
    blocking_count = 0
    row_results = {}

    for row in controller.rows:
        result = evaluate_row_state(
            row,
            controller.font,
            source_mode,
            scope_mode,
            controller.figmaUnit,
            controller.webUnit,
            reference_text,
            preview_on,
        )
        row_results[row["masterID"]] = result
        row["preview"] = result["preview"]
        row["note"] = result["note"]
        if result["checked"]:
            checked_count += 1
        if result["actionable"]:
            actionable_count += 1
        if result["blocking"]:
            blocking_count += 1

    needs_ref, reference_is_valid, reference_message = get_reference_size_state(
        source_mode,
        controller.figmaUnit,
        controller.webUnit,
        reference_text,
    )
    target_glyphs = get_target_glyphs(controller.font, glyph_scope)

    controller.rowResults = row_results
    controller.currentTargetGlyphs = target_glyphs

    source_label = describe_source_mode(source_mode, controller.figmaUnit, controller.webUnit)
    glyph_scope_label = describe_glyph_scope(glyph_scope)

    if checked_count == 0:
        summary = "Select at least one master to adjust."
        can_apply = False
    elif needs_ref and not reference_is_valid:
        summary = reference_message
        can_apply = False
    elif glyph_scope == "Selected glyphs only" and not target_glyphs:
        summary = "Select glyphs in Font View to use Selected glyphs only."
        can_apply = False
    elif glyph_scope == "Exporting glyphs only" and not target_glyphs:
        summary = "No exporting glyphs are available in the current font."
        can_apply = False
    elif blocking_count > 0:
        summary = "Resolve invalid row values before applying."
        can_apply = False
    elif actionable_count == 0:
        summary = "Enter at least one non-zero value for a checked master."
        can_apply = False
    else:
        summary = build_summary_text(actionable_count, source_label, scope_mode, glyph_scope_label)
        can_apply = True

    return can_apply, summary, checked_count


def get_master_layer(glyph, master_id):
    try:
        return glyph.layers[master_id]
    except Exception:
        return None


def quantize_units(value):
    # Metric and kerning values are written back as whole font units.
    return int(round(float(value)))


def apply_percentage_scale_to_value(current_value, percent_input):
    # Percent spacing and kerning formula:
    # new_value = round(current_value * (1 + input / 100.0))
    return quantize_units(float(current_value) * percent_input_to_scale_factor(percent_input))


def apply_adjustment_to_value(current_value, adjustment):
    if adjustment["kind"] == "scale":
        return apply_percentage_scale_to_value(current_value, adjustment["raw"])
    return quantize_units(float(current_value) + float(adjustment["units"]))


def apply_spacing_adjustment_to_master(font, target_glyphs, master_id, master_name, adjustment):
    layers_adjusted = 0
    error_count = 0

    for glyph in target_glyphs:
        try:
            layer = get_master_layer(glyph, master_id)
            if layer is None:
                continue

            old_lsb = float(layer.LSB)
            old_rsb = float(layer.RSB)
            new_lsb = apply_adjustment_to_value(old_lsb, adjustment)
            new_rsb = apply_adjustment_to_value(old_rsb, adjustment)

            if new_lsb == quantize_units(old_lsb) and new_rsb == quantize_units(old_rsb):
                continue

            # Only LSB and RSB are written. The script never writes outlines, anchors, components,
            # groups, features, font info, masters, or layer.width directly.
            layer.LSB = new_lsb
            layer.RSB = new_rsb
            layers_adjusted += 1
        except Exception:
            error_count += 1
            print(
                "Spacing error in glyph '%s' for master '%s':"
                % (safe_string(getattr(glyph, "name", "?")), master_name)
            )
            traceback.print_exc()

    return layers_adjusted, error_count


def build_glyph_id_name_map(font):
    mapping = {}
    for glyph in font.glyphs:
        mapping[safe_string(glyph.id)] = safe_string(glyph.name)
    return mapping


def normalize_kerning_key(key, glyph_id_name_map):
    key_text = safe_string(key)
    if key_text.startswith("@"):
        return key_text
    return glyph_id_name_map.get(key_text, key_text)


def build_allowed_kerning_keys(target_glyphs):
    left_keys = set()
    right_keys = set()

    for glyph in target_glyphs:
        glyph_name = safe_string(getattr(glyph, "name", ""))
        if not glyph_name:
            continue

        right_key = safe_string(getattr(glyph, "rightKerningKey", None) or glyph_name)
        left_key = safe_string(getattr(glyph, "leftKerningKey", None) or glyph_name)

        left_keys.add(glyph_name)
        left_keys.add(right_key)
        right_keys.add(glyph_name)
        right_keys.add(left_key)

    return left_keys, right_keys


def get_ltr_kerning_container(font):
    return getattr(font, "kerningLTR", getattr(font, "kerning", {}))


def iter_kerning_pairs_for_master(font, master_id):
    kerning_container = get_ltr_kerning_container(font)
    try:
        master_kerning = kerning_container[master_id]
    except Exception:
        master_kerning = None

    if not master_kerning:
        return []

    pairs = []
    try:
        left_keys = list(master_kerning.keys())
    except Exception:
        left_keys = list(master_kerning)

    for left_key in left_keys:
        try:
            right_dict = master_kerning[left_key]
        except Exception:
            continue

        try:
            right_keys = list(right_dict.keys())
        except Exception:
            right_keys = list(right_dict)

        for right_key in right_keys:
            try:
                value = float(right_dict[right_key])
            except Exception:
                continue
            pairs.append((left_key, right_key, value))

    return pairs


def pair_is_in_scope(normal_left_key, normal_right_key, glyph_scope, allowed_left_keys, allowed_right_keys):
    if glyph_scope == "All glyphs":
        return True

    # For narrower glyph scopes, a pair is adjusted only when both sides match keys derived from
    # target glyphs. This is the safest interpretation because it minimizes pair updates that would
    # obviously spill beyond the requested glyph subset. Group pairs can still affect other glyphs
    # that share those groups, which is an inherent limitation of group-based kerning.
    return normal_left_key in allowed_left_keys and normal_right_key in allowed_right_keys


def apply_kerning_adjustment_to_master(
    font,
    master_id,
    master_name,
    adjustment,
    glyph_scope,
    glyph_id_name_map,
    allowed_left_keys,
    allowed_right_keys,
):
    pair_count = 0
    error_count = 0

    for left_key, right_key, current_value in iter_kerning_pairs_for_master(font, master_id):
        try:
            normalized_left = normalize_kerning_key(left_key, glyph_id_name_map)
            normalized_right = normalize_kerning_key(right_key, glyph_id_name_map)

            if not pair_is_in_scope(
                normalized_left,
                normalized_right,
                glyph_scope,
                allowed_left_keys,
                allowed_right_keys,
            ):
                continue

            new_value = apply_adjustment_to_value(current_value, adjustment)
            if new_value == quantize_units(current_value):
                continue

            font.setKerningForPair(master_id, normalized_left, normalized_right, new_value, LTR)
            pair_count += 1
        except Exception:
            error_count += 1
            print(
                "Kerning error in master '%s' for pair '%s' / '%s':"
                % (master_name, safe_string(left_key), safe_string(right_key))
            )
            traceback.print_exc()

    return pair_count, error_count


def mark_font_changed(font):
    try:
        document = getattr(font, "parent", None)
        if document is not None and hasattr(document, "updateChangeCount_"):
            document.updateChangeCount_(CHANGE_DONE)
    except Exception:
        pass


def refresh_glyphs_ui():
    try:
        Glyphs.redraw()
        return
    except Exception:
        pass
    try:
        NSNotificationCenter.defaultCenter().postNotificationName_object_("GSRedrawEditView", None)
    except Exception:
        pass


def apply_bulk_value_to_checked_masters(controller, value):
    text = safe_string(value).strip()
    if not text:
        return 0

    updated = 0
    for row in controller.rows:
        if row["apply"]:
            row["input"] = text
            updated += 1

    return updated


def update_preview(controller):
    controller.tableView.reloadData()


def apply_adjustments(controller):
    can_apply, summary, _checked_count = validate_ui_state(controller)
    update_summary(controller, summary)
    update_preview(controller)
    controller.applyButton.setEnabled_(can_apply)

    if not can_apply:
        return

    include_kerning = get_selected_scope_mode(controller) == "Spacing and kerning"
    glyph_scope = get_glyph_scope(controller)
    source_mode = describe_source_mode(get_selected_source_mode(controller), controller.figmaUnit, controller.webUnit)
    target_glyphs = list(controller.currentTargetGlyphs)

    glyph_id_name_map = build_glyph_id_name_map(controller.font) if include_kerning else {}
    allowed_left_keys, allowed_right_keys = build_allowed_kerning_keys(target_glyphs) if include_kerning else (set(), set())

    processed = 0
    layers_adjusted = 0
    kerning_pairs_adjusted = 0
    error_count = 0

    try:
        if hasattr(controller.font, "disableUpdateInterface"):
            controller.font.disableUpdateInterface()

        for row in controller.rows:
            result = controller.rowResults.get(row["masterID"], {})
            adjustment = result.get("adjustment")
            if not result.get("actionable") or adjustment is None:
                continue

            try:
                spacing_count, spacing_errors = apply_spacing_adjustment_to_master(
                    controller.font,
                    target_glyphs,
                    row["masterID"],
                    row["masterName"],
                    adjustment,
                )
                layers_adjusted += spacing_count
                error_count += spacing_errors

                if include_kerning:
                    kerning_count, kerning_errors = apply_kerning_adjustment_to_master(
                        controller.font,
                        row["masterID"],
                        row["masterName"],
                        adjustment,
                        glyph_scope,
                        glyph_id_name_map,
                        allowed_left_keys,
                        allowed_right_keys,
                    )
                    kerning_pairs_adjusted += kerning_count
                    error_count += kerning_errors

                processed += 1
            except Exception:
                error_count += 1
                print("Unexpected error while processing master '%s':" % row["masterName"])
                traceback.print_exc()
    finally:
        try:
            if hasattr(controller.font, "enableUpdateInterface"):
                controller.font.enableUpdateInterface()
        except Exception:
            pass

    if processed > 0:
        mark_font_changed(controller.font)
        refresh_glyphs_ui()

    skipped = len(controller.rows) - processed
    info_lines = [
        "Masters processed: %d" % processed,
        "Masters skipped: %d" % skipped,
        "Glyph layers adjusted: %d" % layers_adjusted,
        "Kerning pairs adjusted: %d%s"
        % (
            kerning_pairs_adjusted,
            "" if include_kerning else " (spacing only)",
        ),
        "Source mode used: %s" % source_mode,
        "Glyph scope used: %s" % describe_glyph_scope(glyph_scope),
    ]

    if error_count:
        info_lines.append("Errors: %d (see Macro window)" % error_count)
        try:
            Glyphs.showMacroWindow()
        except Exception:
            pass

    title = "Metric Adjustment Complete" if error_count == 0 else "Metric Adjustment Completed with Warnings"
    show_alert(title, "\n".join(info_lines))


def calculate_layout(master_count):
    visible_rows = min(max(master_count, 1), MAX_VISIBLE_MASTER_ROWS)
    table_height = TABLE_HEADER_HEIGHT + (visible_rows * TABLE_ROW_HEIGHT) + 2
    masters_box_height = table_height + (TABLE_PADDING * 2) + 12
    window_height = (
        OUTER_MARGIN
        + SETTINGS_BOX_HEIGHT
        + SECTION_GAP
        + BULK_BOX_HEIGHT
        + SECTION_GAP
        + masters_box_height
        + SECTION_GAP
        + FOOTER_HEIGHT
        + OUTER_MARGIN
    )
    return {
        "visible_rows": visible_rows,
        "table_height": table_height,
        "masters_box_height": masters_box_height,
        "window_height": window_height,
    }


def build_ui(controller):
    layout = calculate_layout(len(controller.rows))
    window_height = layout["window_height"]

    frame = NSMakeRect(160, 160, WINDOW_WIDTH, window_height)
    style_mask = STYLE_MASK_TITLED | STYLE_MASK_CLOSABLE | STYLE_MASK_MINIATURIZABLE
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        style_mask,
        NSBackingStoreBuffered,
        False,
    )
    window.setTitle_("Master Spacing and Kerning Adjuster")
    try:
        window.setMinSize_(NSMakeSize(WINDOW_MIN_WIDTH, window_height))
    except Exception:
        pass
    window.setReleasedWhenClosed_(False)
    window.setDelegate_(controller)
    controller.window = window

    content_view = window.contentView()
    content_width = WINDOW_WIDTH - (OUTER_MARGIN * 2)

    settings_y = window_height - OUTER_MARGIN - SETTINGS_BOX_HEIGHT
    bulk_y = settings_y - SECTION_GAP - BULK_BOX_HEIGHT
    masters_y = bulk_y - SECTION_GAP - layout["masters_box_height"]
    footer_y = OUTER_MARGIN

    header_font = NSFont.boldSystemFontOfSize_(11.0)
    label_font = NSFont.systemFontOfSize_(11.0)

    controller.settingsBox = make_box(
        NSMakeRect(OUTER_MARGIN, settings_y, content_width, SETTINGS_BOX_HEIGHT),
        "Settings",
    )
    content_view.addSubview_(controller.settingsBox)

    controller.bulkBox = make_box(
        NSMakeRect(OUTER_MARGIN, bulk_y, content_width, BULK_BOX_HEIGHT),
        "Quick Fill",
    )
    content_view.addSubview_(controller.bulkBox)

    controller.mastersBox = make_box(
        NSMakeRect(OUTER_MARGIN, masters_y, content_width, layout["masters_box_height"]),
        "Masters",
    )
    content_view.addSubview_(controller.mastersBox)

    sx = OUTER_MARGIN + 12
    sy = settings_y

    content_view.addSubview_(make_label(NSMakeRect(sx, sy + 74, 112, 16), "Adjustment source", header_font))
    controller.sourcePopup = make_popup(
        NSMakeRect(sx + 118, sy + 70, 172, 24),
        SOURCE_MODES,
        controller.sourceMode,
        controller,
        "sourceModeChanged:",
    )
    content_view.addSubview_(controller.sourcePopup)

    content_view.addSubview_(make_label(NSMakeRect(sx + 376, sy + 74, 86, 16), "Scope", header_font))
    controller.scopePopup = make_popup(
        NSMakeRect(sx + 438, sy + 70, 190, 24),
        SCOPE_MODES,
        controller.scopeMode,
        controller,
        "scopeChanged:",
    )
    content_view.addSubview_(controller.scopePopup)

    content_view.addSubview_(make_label(NSMakeRect(sx, sy + 42, 112, 16), "Glyph scope", header_font))
    controller.glyphScopePopup = make_popup(
        NSMakeRect(sx + 118, sy + 38, 172, 24),
        GLYPH_SCOPES,
        controller.glyphScope,
        controller,
        "glyphScopeChanged:",
    )
    content_view.addSubview_(controller.glyphScopePopup)

    controller.unitLabel = make_label(NSMakeRect(sx + 376, sy + 42, 86, 16), "Unit", header_font)
    controller.unitPopup = make_popup(
        NSMakeRect(sx + 438, sy + 38, 96, 24),
        FIGMA_UNITS,
        controller.figmaUnit,
        controller,
        "unitChanged:",
    )
    content_view.addSubview_(controller.unitLabel)
    content_view.addSubview_(controller.unitPopup)

    controller.referenceLabel = make_label(NSMakeRect(sx, sy + 10, 112, 16), "Reference text size", header_font)
    controller.referenceField = make_text_field(
        NSMakeRect(sx + 118, sy + 6, 76, 24),
        controller.referenceTextSize,
        True,
        ALIGN_RIGHT,
        "16",
    )
    controller.referenceField.setDelegate_(controller)
    controller.referenceField.setTarget_(controller)
    controller.referenceField.setAction_("referenceSizeChanged:")
    controller.referenceUnitLabel = make_label(NSMakeRect(sx + 200, sy + 10, 20, 16), "px", label_font)
    content_view.addSubview_(controller.referenceLabel)
    content_view.addSubview_(controller.referenceField)
    content_view.addSubview_(controller.referenceUnitLabel)

    controller.previewCheckbox = NSButton.alloc().initWithFrame_(NSMakeRect(sx + 376, sy + 6, 110, 24))
    controller.previewCheckbox.setButtonType_(SWITCH_BUTTON)
    controller.previewCheckbox.setTitle_("Preview")
    controller.previewCheckbox.setState_(STATE_ON if controller.previewOn else STATE_OFF)
    controller.previewCheckbox.setTarget_(controller)
    controller.previewCheckbox.setAction_("previewChanged:")
    set_small_control(controller.previewCheckbox)
    content_view.addSubview_(controller.previewCheckbox)

    controller.previewHelpLabel = make_label(
        NSMakeRect(sx + 470, sy + 10, 170, 16),
        "Lightweight converted-value preview only",
        label_font,
    )
    content_view.addSubview_(controller.previewHelpLabel)

    bx = OUTER_MARGIN + 12
    by = bulk_y
    controller.bulkField = make_text_field(NSMakeRect(bx, by + 16, 108, 24), "", True, ALIGN_RIGHT, "")
    controller.bulkField.setDelegate_(controller)
    controller.bulkField.setTarget_(controller)
    controller.bulkField.setAction_("bulkFieldChanged:")
    content_view.addSubview_(controller.bulkField)

    controller.bulkApplyButton = make_button(
        NSMakeRect(bx + 116, by + 16, 174, 24),
        "Apply to checked masters",
        controller,
        "applyBulkValueFromField:",
    )
    content_view.addSubview_(controller.bulkApplyButton)

    controller.presetButtons = []
    preset_x = bx + 304
    preset_width = 78
    for index in range(3):
        button = make_button(
            NSMakeRect(preset_x + (index * (preset_width + 8)), by + 16, preset_width, 24),
            "",
            controller,
            "applyPresetValue:",
            REGULAR_SQUARE_BEZEL,
        )
        button.setTag_(index)
        controller.presetButtons.append(button)
        content_view.addSubview_(button)

    mx = OUTER_MARGIN + TABLE_PADDING
    my = masters_y + TABLE_PADDING
    table_width = content_width - (TABLE_PADDING * 2)
    controller.scrollView = NSScrollView.alloc().initWithFrame_(NSMakeRect(mx, my, table_width, layout["table_height"]))
    controller.scrollView.setHasVerticalScroller_(len(controller.rows) > layout["visible_rows"])

    controller.tableView = NSTableView.alloc().initWithFrame_(controller.scrollView.bounds())
    controller.tableView.setDataSource_(controller)
    controller.tableView.setDelegate_(controller)
    controller.tableView.setUsesAlternatingRowBackgroundColors_(True)
    controller.tableView.setRowHeight_(TABLE_ROW_HEIGHT)
    try:
        controller.tableView.setColumnAutoresizingStyle_(TABLE_LAST_COLUMN_AUTOSIZE)
    except Exception:
        pass

    apply_column = NSTableColumn.alloc().initWithIdentifier_("apply")
    apply_column.headerCell().setStringValue_("Apply")
    apply_column.setWidth_(54)
    apply_cell = NSButtonCell.alloc().init()
    apply_cell.setButtonType_(SWITCH_BUTTON)
    apply_cell.setTitle_("")
    apply_column.setDataCell_(apply_cell)
    controller.tableView.addTableColumn_(apply_column)

    master_column = NSTableColumn.alloc().initWithIdentifier_("master")
    master_column.headerCell().setStringValue_("Master")
    master_column.setWidth_(182)
    master_cell = NSTextFieldCell.alloc().initTextCell_("")
    master_cell.setEditable_(False)
    master_column.setDataCell_(master_cell)
    controller.tableView.addTableColumn_(master_column)

    input_column = NSTableColumn.alloc().initWithIdentifier_("input")
    input_column.headerCell().setStringValue_("Input")
    input_column.setWidth_(108)
    input_cell = NSTextFieldCell.alloc().initTextCell_("")
    input_cell.setEditable_(True)
    input_cell.setAlignment_(ALIGN_RIGHT)
    input_column.setDataCell_(input_cell)
    controller.tableView.addTableColumn_(input_column)

    preview_column = NSTableColumn.alloc().initWithIdentifier_("preview")
    preview_column.headerCell().setStringValue_("Converted")
    preview_column.setWidth_(208)
    preview_cell = NSTextFieldCell.alloc().initTextCell_("")
    preview_cell.setEditable_(False)
    preview_column.setDataCell_(preview_cell)
    controller.tableView.addTableColumn_(preview_column)

    note_column = NSTableColumn.alloc().initWithIdentifier_("note")
    note_column.headerCell().setStringValue_("Notes")
    note_column.setWidth_(184)
    note_cell = NSTextFieldCell.alloc().initTextCell_("")
    note_cell.setEditable_(False)
    note_column.setDataCell_(note_cell)
    controller.tableView.addTableColumn_(note_column)

    controller.scrollView.setDocumentView_(controller.tableView)
    content_view.addSubview_(controller.scrollView)

    controller.summaryLabel = make_label(
        NSMakeRect(OUTER_MARGIN, footer_y + 12, content_width - 222, 16),
        "",
        NSFont.systemFontOfSize_(12.0),
    )
    content_view.addSubview_(controller.summaryLabel)

    controller.applyButton = make_button(
        NSMakeRect(WINDOW_WIDTH - OUTER_MARGIN - 198, footer_y + 4, 198, 30),
        "Apply Metric Adjustment",
        controller,
        "applyMetricAdjustment:",
    )
    content_view.addSubview_(controller.applyButton)

    controller.updateUnitControls()
    controller.updatePresetButtons()
    controller.updateBulkPlaceholder()
    controller.refreshUIState()
    controller.window.center()
    controller.window.makeKeyAndOrderFront_(None)


def get_controller_class():
    class_name = "DPMasterSpacingKerningController"
    try:
        return objc.lookUpClass(class_name)
    except Exception:
        pass

    class DPMasterSpacingKerningController(NSObject):
        def init(self):
            self = objc.super(DPMasterSpacingKerningController, self).init()
            if self is None:
                return None

            self.window = None
            self.font = None
            self.rows = []
            self.rowResults = {}
            self.currentTargetGlyphs = []

            self.sourceMode = "Fixed value"
            self.scopeMode = "Spacing only"
            self.glyphScope = "All glyphs"
            self.figmaUnit = "%"
            self.webUnit = "em"
            self.referenceTextSize = ""
            self.previewOn = False
            self.presetDefinitions = []

            return self

        @objc.python_method
        def setup(self, font, masters):
            self.font = font
            self.rows = []

            for master in masters:
                self.rows.append(
                    {
                        "apply": True,
                        "masterID": safe_string(master.id),
                        "masterName": safe_string(master.name) or safe_string(master.id),
                        "input": "",
                        "preview": "",
                        "note": "No change",
                    }
                )

            build_ui(self)

        @objc.python_method
        def close(self):
            if self.window is not None:
                self.window.close()

        @objc.python_method
        def updateUnitControls(self):
            source_mode = get_selected_source_mode(self) if getattr(self, "sourcePopup", None) is not None else self.sourceMode

            if source_mode == "Figma":
                self.unitLabel.setStringValue_("Figma unit")
                self.unitPopup.removeAllItems()
                self.unitPopup.addItemsWithTitles_(FIGMA_UNITS)
                self.unitPopup.selectItemWithTitle_(self.figmaUnit)
                set_hidden([self.unitLabel, self.unitPopup], False)
            elif source_mode == "Web":
                self.unitLabel.setStringValue_("Web unit")
                self.unitPopup.removeAllItems()
                self.unitPopup.addItemsWithTitles_(WEB_UNITS)
                self.unitPopup.selectItemWithTitle_(self.webUnit)
                set_hidden([self.unitLabel, self.unitPopup], False)
            else:
                set_hidden([self.unitLabel, self.unitPopup], True)

            reference_needed = needs_reference_size(source_mode, self.figmaUnit, self.webUnit)
            set_hidden(
                [self.referenceLabel, self.referenceField, self.referenceUnitLabel],
                not reference_needed,
            )

        @objc.python_method
        def updatePresetButtons(self):
            self.presetDefinitions = get_preset_definitions(
                get_selected_source_mode(self),
                self.figmaUnit,
                self.webUnit,
            )

            for index, button in enumerate(self.presetButtons):
                preset = self.presetDefinitions[index]
                button.setTitle_(preset["label"])

        @objc.python_method
        def updateBulkPlaceholder(self):
            try:
                self.bulkField.setPlaceholderString_(
                    get_bulk_placeholder(get_selected_source_mode(self), self.figmaUnit, self.webUnit)
                )
            except Exception:
                pass

        @objc.python_method
        def refreshUIState(self):
            can_apply, summary, checked_count = validate_ui_state(self)
            update_summary(self, summary)
            update_preview(self)
            self.applyButton.setEnabled_(can_apply)
            self.bulkApplyButton.setEnabled_(checked_count > 0 and bool(self.bulkField.stringValue().strip()))

            for button in self.presetButtons:
                button.setEnabled_(checked_count > 0)

        def windowWillClose_(self, notification):
            globals()[TOOL_INSTANCE_KEY] = None

        def controlTextDidChange_(self, notification):
            changed = notification.object()
            if changed == self.referenceField:
                self.referenceTextSize = self.referenceField.stringValue()
            elif changed == self.bulkField:
                pass
            self.refreshUIState()

        def sourceModeChanged_(self, sender):
            self.sourceMode = self.sourcePopup.titleOfSelectedItem()
            self.updateUnitControls()
            self.updatePresetButtons()
            self.updateBulkPlaceholder()
            self.refreshUIState()

        def unitChanged_(self, sender):
            source_mode = get_selected_source_mode(self)
            if source_mode == "Figma":
                self.figmaUnit = self.unitPopup.titleOfSelectedItem()
            elif source_mode == "Web":
                self.webUnit = self.unitPopup.titleOfSelectedItem()
            self.updateUnitControls()
            self.updatePresetButtons()
            self.updateBulkPlaceholder()
            self.refreshUIState()

        def scopeChanged_(self, sender):
            self.scopeMode = self.scopePopup.titleOfSelectedItem()
            self.refreshUIState()

        def glyphScopeChanged_(self, sender):
            self.glyphScope = self.glyphScopePopup.titleOfSelectedItem()
            self.refreshUIState()

        def previewChanged_(self, sender):
            self.previewOn = self.previewCheckbox.state() == STATE_ON
            self.refreshUIState()

        def referenceSizeChanged_(self, sender):
            self.referenceTextSize = self.referenceField.stringValue()
            self.refreshUIState()

        def bulkFieldChanged_(self, sender):
            self.refreshUIState()

        def applyBulkValueFromField_(self, sender):
            updated = apply_bulk_value_to_checked_masters(self, self.bulkField.stringValue())
            if updated > 0:
                self.refreshUIState()

        def applyPresetValue_(self, sender):
            preset_index = int(sender.tag())
            if 0 <= preset_index < len(self.presetDefinitions):
                preset_value = self.presetDefinitions[preset_index]["value"]
                self.bulkField.setStringValue_(preset_value)
                if apply_bulk_value_to_checked_masters(self, preset_value) > 0:
                    self.refreshUIState()

        def applyMetricAdjustment_(self, sender):
            apply_adjustments(self)
            self.refreshUIState()

        def numberOfRowsInTableView_(self, table_view):
            return len(self.rows)

        def tableView_shouldEditTableColumn_row_(self, table_view, table_column, row_index):
            return table_column.identifier() in ("apply", "input")

        def tableView_objectValueForTableColumn_row_(self, table_view, table_column, row_index):
            row = self.rows[row_index]
            identifier = table_column.identifier()
            if identifier == "apply":
                return STATE_ON if row["apply"] else STATE_OFF
            if identifier == "master":
                return row["masterName"]
            if identifier == "input":
                return row["input"]
            if identifier == "preview":
                return row.get("preview", "")
            if identifier == "note":
                return row.get("note", "")
            return ""

        def tableView_setObjectValue_forTableColumn_row_(self, table_view, value, table_column, row_index):
            row = self.rows[row_index]
            identifier = table_column.identifier()
            if identifier == "apply":
                row["apply"] = bool(value)
            elif identifier == "input":
                row["input"] = safe_string(value)
            self.refreshUIState()

    return DPMasterSpacingKerningController


def main():
    font, masters = get_font_and_masters()
    if font is None:
        show_alert("No Font Open", "Open a font in Glyphs and run the script again.")
        return

    if not masters:
        show_alert("No Masters Found", "The current font has no masters to adjust.")
        return

    existing = globals().get(TOOL_INSTANCE_KEY)
    if existing is not None:
        try:
            existing.close()
        except Exception:
            pass

    controller_class = get_controller_class()
    controller = controller_class.alloc().init()
    controller.setup(font, masters)
    globals()[TOOL_INSTANCE_KEY] = controller


main()
