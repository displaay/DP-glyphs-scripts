# MenuTitle: Master Consistency Checker
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

"""
Master Consistency Checker for Glyphs 3.

Finds interpolation and production inconsistencies across font masters:
outline/path compatibility, component setup, anchor names/positions, metrics,
and suspicious shape-order/shape-shift problems.
"""

from __future__ import annotations

import math
import os
import re
import traceback
import webbrowser
from datetime import datetime
from html import escape as escape_html
from urllib.parse import unquote, urlparse
from urllib.request import pathname2url

from GlyphsApp import Glyphs, Message, OFFCURVE
from vanilla import (
    Button,
    CheckBox,
    EditText,
    FloatingWindow,
    HorizontalLine,
    List,
    PopUpButton,
    ProgressBar,
    TextBox,
)


SCRIPT_NAME = "Master Consistency Checker"

DEFAULT_METRIC_TOLERANCE = 1.0
DEFAULT_ANCHOR_TOLERANCE = 4.0
DEFAULT_TRANSFORM_TOLERANCE = 0.001
DEFAULT_SEGMENT_ANGLE_TOLERANCE = 20.0
DEFAULT_HANDLE_RATIO_TOLERANCE = 0.35
DEFAULT_SHAPE_SHIFT_TOLERANCE = 80.0
SEVERITIES = ("Info", "Warning", "Error", "Critical")

GLYPH_SCOPES = (
    "Selected glyphs",
    "All glyphs",
    "Exporting glyphs",
)

CHECKS = (
    "Missing master layers",
    "Empty/content mismatches",
    "Shape order/type mismatches",
    "Path count, direction, node type and smoothness mismatches",
    "Segment angle differences above the threshold",
    "Smooth curve handle-ratio differences",
    "Component count, base glyph, transform, alignment and smart settings",
    "Anchor name/order mismatches",
    "Anchor position differences above the threshold",
    "Width, LSB and RSB differences above the threshold",
    "Metrics-key and auto-alignment state mismatches",
    "Layer bounds differences above the threshold",
    "Suspicious shape-center order or large shape-center jumps",
)


def safe_float(value, fallback):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return fallback


def format_number(value, decimals=2):
    try:
        value = float(value)
    except Exception:
        return str(value)
    if abs(value - round(value)) < 0.000001:
        return str(int(round(value)))
    text = ("%%.%df" % decimals) % value
    return text.rstrip("0").rstrip(".")


def clean_filename(value, fallback="Master-Consistency-Report"):
    value = str(value or "").strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    value = value.strip("-._")
    return value or fallback


def join_values(values):
    values = [str(value) for value in values if value is not None and str(value) != ""]
    return ", ".join(values)


def point_tuple(point):
    try:
        return (float(point.x), float(point.y))
    except Exception:
        try:
            return (float(point[0]), float(point[1]))
        except Exception:
            return (0.0, 0.0)


def distance(a, b):
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def angle_between_points(a, b):
    return math.degrees(math.atan2(float(b[1]) - float(a[1]), float(b[0]) - float(a[0])))


def angle_delta(a, b):
    delta = abs((a - b + 180.0) % 360.0 - 180.0)
    return delta


def is_offcurve(node):
    try:
        return node.type == OFFCURVE
    except Exception:
        return str(getattr(node, "type", "")).lower() == "offcurve"


def node_type_name(node):
    return str(getattr(node, "type", "")).lower()


def is_curve_node(node):
    return "curve" in node_type_name(node)


def safe_direction(path):
    try:
        direction = path.direction
        if callable(direction):
            direction = direction()
        return int(direction)
    except Exception:
        return None


def rect_tuple(rect):
    if callable(rect):
        try:
            rect = rect()
        except Exception:
            return None
    try:
        x = float(rect.origin.x)
        y = float(rect.origin.y)
        w = float(rect.size.width)
        h = float(rect.size.height)
        return (x, y, w, h)
    except Exception:
        return None


def rect_center(rect):
    values = rect_tuple(rect)
    if values is None:
        return (0.0, 0.0)
    x, y, w, h = values
    return (x + w * 0.5, y + h * 0.5)


def rect_edges(rect):
    values = rect_tuple(rect)
    if values is None:
        return None
    x, y, w, h = values
    return {
        "xMin": x,
        "yMin": y,
        "xMax": x + w,
        "yMax": y + h,
        "width": w,
        "height": h,
    }


def object_bounds(obj):
    try:
        bounds = getattr(obj, "bounds", None)
        if callable(bounds):
            bounds = bounds()
        return bounds
    except Exception:
        return None


def bool_value(obj, attr):
    try:
        value = getattr(obj, attr)
        if callable(value):
            value = value()
        return bool(value)
    except Exception:
        return None


def class_name(obj):
    try:
        return obj.__class__.__name__
    except Exception:
        return str(type(obj))


def is_component(shape):
    return hasattr(shape, "componentName")


def is_path(shape):
    return hasattr(shape, "nodes") and hasattr(shape, "closed")


def layer_name(layer, master_by_id=None):
    if layer is None:
        return "No layer"
    master_id = getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None)
    if master_by_id and master_id in master_by_id:
        return master_by_id[master_id].name
    name = getattr(layer, "name", None)
    return name or master_id or "Unnamed layer"


def get_master_layer(glyph, master):
    try:
        return glyph.layers[master.id]
    except Exception:
        return None


def unique_glyphs_from_layers(layers):
    glyphs = []
    seen = set()
    for layer in layers or []:
        glyph = getattr(layer, "parent", None)
        if glyph is None:
            continue
        key = getattr(glyph, "id", None) or glyph.name
        if key in seen:
            continue
        seen.add(key)
        glyphs.append(glyph)
    return glyphs


def glyph_is_exporting(glyph):
    try:
        return bool(glyph.export)
    except Exception:
        return True


def selected_glyphs(font):
    return unique_glyphs_from_layers(getattr(font, "selectedLayers", []))


def get_scope_glyphs(font, scope):
    if scope == "Selected glyphs":
        glyphs = selected_glyphs(font)
    elif scope == "Exporting glyphs":
        glyphs = [glyph for glyph in font.glyphs if glyph_is_exporting(glyph)]
    else:
        glyphs = list(font.glyphs)
    return glyphs


def anchor_dict(layer):
    anchors = {}
    order = []
    for anchor in list(getattr(layer, "anchors", []) or []):
        name = getattr(anchor, "name", None)
        if not name:
            continue
        anchors[name] = anchor
        order.append(name)
    return anchors, order


def path_signature(path):
    nodes = list(getattr(path, "nodes", []) or [])
    return {
        "closed": bool(getattr(path, "closed", False)),
        "direction": safe_direction(path),
        "node_count": len(nodes),
        "node_types": tuple(str(getattr(node, "type", "")) for node in nodes),
        "connections": tuple(str(getattr(node, "connection", "")) for node in nodes),
    }


def node_positions(path):
    return [point_tuple(getattr(node, "position", None)) for node in list(getattr(path, "nodes", []) or [])]


def oncurve_indices(path):
    return [i for i, node in enumerate(list(getattr(path, "nodes", []) or [])) if not is_offcurve(node)]


def path_segment_angles(path):
    nodes = list(getattr(path, "nodes", []) or [])
    positions = node_positions(path)
    indices = oncurve_indices(path)
    if len(indices) < 2:
        return []
    closed = bool(getattr(path, "closed", False))
    result = []
    start_index = 0 if closed else 1
    for i in range(start_index, len(indices)):
        previous_index = indices[i - 1]
        current_index = indices[i]
        result.append(angle_between_points(positions[previous_index], positions[current_index]))
    return result


def smooth_curve_handle_ratios(path):
    nodes = list(getattr(path, "nodes", []) or [])
    positions = node_positions(path)
    if not nodes:
        return []
    closed = bool(getattr(path, "closed", False))
    ratios = []
    for index, node in enumerate(nodes):
        if is_offcurve(node):
            continue
        connection = str(getattr(node, "connection", "")).lower()
        if "smooth" not in connection:
            continue

        prev_index = index - 1
        next_index = index + 1
        if prev_index < 0:
            if not closed:
                continue
            prev_index = len(nodes) - 1
        if next_index >= len(nodes):
            if not closed:
                continue
            next_index = 0

        prev_node = nodes[prev_index]
        next_node = nodes[next_index]
        if not (is_offcurve(prev_node) or is_offcurve(next_node)):
            continue

        node_position = positions[index]
        prev_len = distance(positions[prev_index], node_position) if is_offcurve(prev_node) else 0.0
        next_len = distance(node_position, positions[next_index]) if is_offcurve(next_node) else 0.0
        total = prev_len + next_len
        if total <= 0:
            ratios.append(None)
        else:
            ratios.append(prev_len / total)
    return ratios


def shape_kind(shape):
    if is_component(shape):
        return "component"
    if is_path(shape):
        return "path"
    return class_name(shape)


def shape_label(shape):
    if is_component(shape):
        return "component:%s" % (getattr(shape, "componentName", "") or "<missing base>")
    if is_path(shape):
        nodes = list(getattr(shape, "nodes", []) or [])
        return "path:%s nodes:%s dir:%s" % (
            "closed" if getattr(shape, "closed", False) else "open",
            len(nodes),
            safe_direction(shape),
        )
    return class_name(shape)


def shape_center(shape):
    return rect_center(object_bounds(shape))


def shape_center_rank_signature(layer):
    centers = []
    for index, shape in enumerate(list(getattr(layer, "shapes", []) or [])):
        center = shape_center(shape)
        centers.append((index, center[0], center[1]))
    x_rank = tuple(index for index, _x, _y in sorted(centers, key=lambda item: (item[1], item[2], item[0])))
    y_rank = tuple(index for index, _x, _y in sorted(centers, key=lambda item: (item[2], item[1], item[0])))
    return x_rank, y_rank


def component_transform_tuple(component):
    values = []
    for attr in ("position", "scale"):
        try:
            point = getattr(component, attr)
            values.extend([float(point.x), float(point.y)])
        except Exception:
            values.extend([0.0, 0.0])
    for attr in ("angle", "slantHorizontal", "slantVertical", "keepWeight"):
        try:
            values.append(float(getattr(component, attr)))
        except Exception:
            values.append(0.0)
    try:
        transform = component.transformStruct
        for attr in ("m11", "m12", "m21", "m22", "tX", "tY"):
            values.append(float(getattr(transform, attr)))
    except Exception:
        pass
    return tuple(values)


def component_piece_settings(component):
    try:
        settings = getattr(component, "pieceSettings", None)
        if not settings:
            return ()
        return tuple(sorted((str(key), float(settings[key])) for key in settings.keys()))
    except Exception:
        return ()


def component_signature(component):
    return {
        "base": getattr(component, "componentName", None) or "",
        "anchor": getattr(component, "anchor", None) or "",
        "alignment": getattr(component, "alignment", None),
        "transform": component_transform_tuple(component),
        "piece_settings": component_piece_settings(component),
    }


def normalize_severity(severity, check, details=""):
    severity = str(severity or "Warning").strip().title()
    if severity not in SEVERITIES:
        severity = "Warning"

    check = str(check or "")
    details = str(details or "").lower()

    critical_patterns = (
        "missing layer",
        "path count",
        "shape count",
        "node count",
        "node type",
        "component count",
        "base differs",
        "references missing glyph",
        "missing:",
        "extra:",
    )
    if check == "Missing layer":
        return "Critical"
    if check in ("Paths", "Shape order", "Components", "Anchors"):
        if any(pattern in details for pattern in critical_patterns):
            return "Critical"
    if check == "Empty/content" and "shapes" in details:
        return "Error"
    if check in ("Metrics", "Metrics keys", "Alignment", "Bounds"):
        if severity in ("Warning", "Error"):
            return "Info"
    return severity


def suggested_solution(check, details=""):
    check = str(check or "")
    details = str(details or "").lower()

    if check == "Missing layer":
        return "Create the missing master layer, copy compatible source geometry from another master, then re-interpolate or redraw only the intended differences."
    if check == "Empty/content":
        return "Make the glyph intentionally empty in every master, or copy/rebuild the same outline/component/anchor structure across masters."
    if check == "Shape order":
        return "Run Correct Path Direction for all masters first, then use Filter > Shape Order to put paths and components in the same order."
    if check == "Paths":
        if "node count" in details:
            return "Add or remove corresponding nodes so every master has the same node count in this path."
        if "node type" in details or "open/closed" in details:
            return "Make the path structure identical: same open/closed state and the same line/curve/offcurve sequence."
        if "direction" in details:
            return "Run Correct Path Direction for all masters, then check start nodes if the warning remains."
        if "smooth" in details:
            return "Make smooth/sharp connections intentional and consistent; mismatched smoothness can create interpolation kinks."
        return "Compare the path in Compatibility View and make the node sequence match across masters."
    if check == "Segment angle":
        return "Inspect the marked path segment in Compatibility View. A large angle jump often means a missing corresponding node or a swapped shape."
    if check == "Handle ratio":
        return "Balance the handles around the smooth point, or add matching support nodes, so intermediate weights do not kink."
    if check == "Components":
        if "missing glyph" in details:
            return "Restore or rename the referenced component glyph, or replace this component with the correct base glyph."
        if "base differs" in details or "component count" in details:
            return "Use the same component count and the same base glyphs in the same order across masters, or decompose consistently."
        if "transform" in details:
            return "Check component position, scale, rotation and slant; reset or copy the transform if the shift was accidental."
        if "smart" in details:
            return "Copy the same smart component settings to all masters, unless the design intentionally changes the part interpolation."
        return "Normalize component setup: base glyph, order, alignment, attachment anchor and transform should match unless intentionally different."
    if check == "Anchors":
        if "missing" in details or "extra" in details:
            return "Add missing anchors or remove extras so every master has the same anchor names."
        return "Reorder anchors consistently and keep anchor names identical across masters."
    if check == "Anchor positions":
        return "Move the anchor to the equivalent optical/structural location in this master; if the shift is intentional, raise the tolerance or disable this check."
    if check == "Metrics":
        return "If the width/sidebearing shift is accidental, copy or recalculate metrics from the reference master. If spacing intentionally varies, raise tolerance or disable metrics."
    if check == "Metrics keys":
        return "Copy the same metrics keys across masters or clear per-layer overrides so formulas resolve consistently."
    if check == "Alignment":
        return "Make component auto-alignment state consistent across masters; re-enable alignment or disable it deliberately everywhere."
    if check == "Bounds":
        return "Compare the outlines visually. Large bounds changes can be intended, but accidental extremes or misplaced components should be fixed."
    if check == "Shape centers":
        return "Check shape order and component/path placement. Crossing center order usually points to swapped shapes even when node counts match."
    return "Review this glyph in Master Compatibility view and make the structure match the reference master."


def svg_number(value):
    return format_number(value, 2)


def svg_path_data(path):
    nodes = list(getattr(path, "nodes", []) or [])
    if not nodes:
        return ""

    oncurve = [index for index, node in enumerate(nodes) if not is_offcurve(node)]
    if not oncurve:
        return ""

    closed = bool(getattr(path, "closed", False))
    first = oncurve[0]
    ordered = nodes[first:] + nodes[:first] if closed else nodes
    if is_offcurve(ordered[0]):
        for index, node in enumerate(ordered):
            if not is_offcurve(node):
                ordered = ordered[index:]
                break

    start = point_tuple(getattr(ordered[0], "position", None))
    commands = ["M %s %s" % (svg_number(start[0]), svg_number(-start[1]))]
    offcurves = []

    for node in ordered[1:]:
        position = point_tuple(getattr(node, "position", None))
        if is_offcurve(node):
            offcurves.append(position)
            continue
        if is_curve_node(node) and len(offcurves) >= 2:
            c1, c2 = offcurves[-2], offcurves[-1]
            commands.append(
                "C %s %s %s %s %s %s"
                % (
                    svg_number(c1[0]),
                    svg_number(-c1[1]),
                    svg_number(c2[0]),
                    svg_number(-c2[1]),
                    svg_number(position[0]),
                    svg_number(-position[1]),
                )
            )
        else:
            commands.append("L %s %s" % (svg_number(position[0]), svg_number(-position[1])))
        offcurves = []

    if closed:
        if len(offcurves) >= 2 and is_curve_node(ordered[0]):
            c1, c2 = offcurves[-2], offcurves[-1]
            commands.append(
                "C %s %s %s %s %s %s"
                % (
                    svg_number(c1[0]),
                    svg_number(-c1[1]),
                    svg_number(c2[0]),
                    svg_number(-c2[1]),
                    svg_number(start[0]),
                    svg_number(-start[1]),
                )
            )
        commands.append("Z")

    return " ".join(commands)


def preview_layer(layer):
    if layer is None:
        return None
    try:
        return layer.copyDecomposedLayer()
    except Exception:
        return layer


def layer_svg_data(layer):
    layer = preview_layer(layer)
    if layer is None:
        return None

    paths = list(getattr(layer, "paths", []) or [])
    path_data = [svg_path_data(path) for path in paths]
    path_data = [data for data in path_data if data]

    edges = rect_edges(object_bounds(layer))
    if edges is None:
        edges = {"xMin": 0.0, "yMin": -200.0, "xMax": float(getattr(layer, "width", 600)), "yMax": 800.0, "width": float(getattr(layer, "width", 600)), "height": 1000.0}
    width = float(getattr(layer, "width", edges["width"] or 600.0) or 600.0)
    if width <= 0:
        width = max(edges["width"], 600.0)

    x_min = min(0.0, edges["xMin"]) - 60.0
    x_max = max(width, edges["xMax"]) + 60.0
    y_min = min(-edges["yMax"], -800.0) - 60.0
    y_max = max(-edges["yMin"], 200.0) + 60.0

    return {
        "path": " ".join(path_data),
        "viewbox": "%s %s %s %s"
        % (
            svg_number(x_min),
            svg_number(y_min),
            svg_number(max(1.0, x_max - x_min)),
            svg_number(max(1.0, y_max - y_min)),
        ),
        "width_line": "M %s %s L %s %s" % (svg_number(width), svg_number(y_min), svg_number(width), svg_number(y_max)),
        "baseline": "M %s 0 L %s 0" % (svg_number(x_min), svg_number(x_max)),
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "width": width,
        "has_paths": bool(path_data),
    }


class MasterConsistencyChecker:

    def __init__(self):
        self.font = Glyphs.font
        if self.font is None:
            Message("No Font Open", "Please open a font before running %s." % SCRIPT_NAME)
            return

        self.results = []
        self.issue_glyph_names = []
        self.last_html_path = None
        self.master_by_id = {master.id: master for master in self.font.masters}

        self.w = FloatingWindow(
            (920, 720),
            SCRIPT_NAME,
            minSize=(820, 560),
            autosaveName="com.displaay.MasterConsistencyChecker.window",
        )
        self._build_ui()
        self.w.open()
        self.w.makeKey()

    def _build_ui(self):
        y = 14
        self.w.scopeLabel = TextBox((14, y + 3, 42, 18), "Scope:", sizeStyle="small")
        self.w.scopePopup = PopUpButton((58, y, 150, 22), GLYPH_SCOPES, sizeStyle="small")

        selected_master_index = 0
        try:
            selected_master = self.font.selectedFontMaster
            selected_master_index = [m.id for m in self.font.masters].index(selected_master.id)
        except Exception:
            pass
        master_names = [master.name for master in self.font.masters]
        self.w.refLabel = TextBox((224, y + 3, 102, 18), "Reference master:", sizeStyle="small")
        self.w.refPopup = PopUpButton((328, y, 178, 22), master_names, sizeStyle="small")
        self.w.refPopup.set(selected_master_index)

        self.w.showMacro = CheckBox((522, y + 2, 112, 18), "Print report", value=True, sizeStyle="small")
        self.w.openTab = CheckBox((640, y + 2, 150, 18), "Open glyphs tab", value=True, sizeStyle="small")

        y += 28
        self.w.createHtml = CheckBox((58, y + 2, 148, 18), "Create HTML report", value=True, sizeStyle="small")
        self.w.openHtml = CheckBox((224, y + 2, 148, 18), "Open HTML report", value=True, sizeStyle="small")

        y += 32
        self.w.lineTop = HorizontalLine((14, y, -14, 1))

        y += 12
        left_x = 18
        right_x = 430
        row_h = 23

        self.w.outlineLabel = TextBox((left_x, y, 260, 18), "Outlines and shapes", sizeStyle="small")
        self.w.metricsLabel = TextBox((right_x, y, 260, 18), "Metrics, anchors and bounds", sizeStyle="small")
        y += 22

        self.w.checkShapeOrder = CheckBox((left_x, y, 360, 18), "Shape order and path/component type", value=True, sizeStyle="small")
        self.w.checkMetrics = CheckBox((right_x, y, 230, 18), "Width, LSB and RSB", value=True, sizeStyle="small")
        self.w.metricTolLabel = TextBox((right_x + 242, y + 2, 58, 18), "Tol.", sizeStyle="small")
        self.w.metricTol = EditText((right_x + 284, y - 2, 50, 22), format_number(DEFAULT_METRIC_TOLERANCE), sizeStyle="small")
        y += row_h

        self.w.checkPaths = CheckBox((left_x, y, 360, 18), "Path count, direction, nodes and smoothness", value=True, sizeStyle="small")
        self.w.checkMetricKeys = CheckBox((right_x, y, 360, 18), "Metrics keys and auto-alignment state", value=True, sizeStyle="small")
        y += row_h

        self.w.checkComponents = CheckBox((left_x, y, 360, 18), "Components, transforms and smart settings", value=True, sizeStyle="small")
        self.w.checkAnchors = CheckBox((right_x, y, 230, 18), "Anchor names and order", value=True, sizeStyle="small")
        y += row_h

        self.w.checkAngles = CheckBox((left_x, y, 212, 18), "Segment angle jumps", value=True, sizeStyle="small")
        self.w.angleTolLabel = TextBox((left_x + 226, y + 2, 58, 18), "Deg.", sizeStyle="small")
        self.w.angleTol = EditText((left_x + 268, y - 2, 50, 22), format_number(DEFAULT_SEGMENT_ANGLE_TOLERANCE), sizeStyle="small")
        self.w.checkAnchorPositions = CheckBox((right_x, y, 230, 18), "Anchor positions", value=True, sizeStyle="small")
        self.w.anchorTolLabel = TextBox((right_x + 242, y + 2, 58, 18), "Tol.", sizeStyle="small")
        self.w.anchorTol = EditText((right_x + 284, y - 2, 50, 22), format_number(DEFAULT_ANCHOR_TOLERANCE), sizeStyle="small")
        y += row_h

        self.w.checkHandles = CheckBox((left_x, y, 212, 18), "Smooth handle ratios", value=True, sizeStyle="small")
        self.w.handleTolLabel = TextBox((left_x + 226, y + 2, 58, 18), "Ratio", sizeStyle="small")
        self.w.handleTol = EditText((left_x + 268, y - 2, 50, 22), format_number(DEFAULT_HANDLE_RATIO_TOLERANCE), sizeStyle="small")
        self.w.checkBounds = CheckBox((right_x, y, 230, 18), "Layer bounds", value=False, sizeStyle="small")
        self.w.boundsTolLabel = TextBox((right_x + 242, y + 2, 58, 18), "Tol.", sizeStyle="small")
        self.w.boundsTol = EditText((right_x + 284, y - 2, 50, 22), format_number(DEFAULT_SHAPE_SHIFT_TOLERANCE), sizeStyle="small")
        y += row_h

        self.w.checkShapeShifts = CheckBox((left_x, y, 212, 18), "Shape center shifts/order", value=True, sizeStyle="small")
        self.w.shiftTolLabel = TextBox((left_x + 226, y + 2, 58, 18), "Tol.", sizeStyle="small")
        self.w.shiftTol = EditText((left_x + 268, y - 2, 50, 22), format_number(DEFAULT_SHAPE_SHIFT_TOLERANCE), sizeStyle="small")
        self.w.checkEmpty = CheckBox((right_x, y, 360, 18), "Missing layers and empty/content mismatches", value=True, sizeStyle="small")
        y += 30

        self.w.checkListLabel = TextBox((14, y, -14, 18), "Checks included in this tool", sizeStyle="small")
        y += 20
        self.w.checkList = List(
            (14, y, -14, 94),
            [{"Check": check} for check in CHECKS],
            columnDescriptions=[{"title": "Check", "width": 790}],
            allowsMultipleSelection=False,
            allowsEmptySelection=True,
        )
        y += 104

        self.w.resultsLabel = TextBox((14, y, -14, 18), "Results", sizeStyle="small")
        y += 20
        self.w.resultsList = List(
            (14, y, -14, -82),
            [],
            columnDescriptions=[
                {"title": "Severity", "width": 70},
                {"title": "Glyph", "width": 120},
                {"title": "Master", "width": 120},
                {"title": "Check", "width": 150},
                {"title": "Details", "width": 300},
                {"title": "Likely Fix", "width": 340},
            ],
            allowsMultipleSelection=True,
            allowsEmptySelection=True,
            selectionCallback=self._selection_changed,
        )

        self.w.footerLine = HorizontalLine((14, -72, -14, 1))
        self.w.progress = ProgressBar((14, -52, 220, 14), isIndeterminate=False)
        self.w.statusText = TextBox((248, -56, -304, 18), "Ready.", sizeStyle="small")
        self.w.openHtmlButton = Button((-286, -60, 82, 24), "HTML", callback=self._open_html_callback, sizeStyle="small")
        self.w.openGlyphsButton = Button((-194, -60, 82, 24), "Glyphs", callback=self._open_tab_callback, sizeStyle="small")
        self.w.reportButton = Button((-106, -60, 92, 24), "Run Check", callback=self._run_callback, sizeStyle="small")
        self.w.setDefaultButton(self.w.reportButton)

    def _settings(self):
        return {
            "scope": GLYPH_SCOPES[self.w.scopePopup.get()],
            "reference_master": list(self.font.masters)[self.w.refPopup.get()],
            "show_macro": bool(self.w.showMacro.get()),
            "open_tab": bool(self.w.openTab.get()),
            "create_html": bool(self.w.createHtml.get()),
            "open_html": bool(self.w.openHtml.get()),
            "check_empty": bool(self.w.checkEmpty.get()),
            "check_shape_order": bool(self.w.checkShapeOrder.get()),
            "check_paths": bool(self.w.checkPaths.get()),
            "check_components": bool(self.w.checkComponents.get()),
            "check_angles": bool(self.w.checkAngles.get()),
            "check_handles": bool(self.w.checkHandles.get()),
            "check_shape_shifts": bool(self.w.checkShapeShifts.get()),
            "check_metrics": bool(self.w.checkMetrics.get()),
            "check_metric_keys": bool(self.w.checkMetricKeys.get()),
            "check_anchors": bool(self.w.checkAnchors.get()),
            "check_anchor_positions": bool(self.w.checkAnchorPositions.get()),
            "check_bounds": bool(self.w.checkBounds.get()),
            "metric_tolerance": safe_float(self.w.metricTol.get(), DEFAULT_METRIC_TOLERANCE),
            "anchor_tolerance": safe_float(self.w.anchorTol.get(), DEFAULT_ANCHOR_TOLERANCE),
            "transform_tolerance": DEFAULT_TRANSFORM_TOLERANCE,
            "segment_angle_tolerance": safe_float(self.w.angleTol.get(), DEFAULT_SEGMENT_ANGLE_TOLERANCE),
            "handle_ratio_tolerance": safe_float(self.w.handleTol.get(), DEFAULT_HANDLE_RATIO_TOLERANCE),
            "shape_shift_tolerance": safe_float(self.w.shiftTol.get(), DEFAULT_SHAPE_SHIFT_TOLERANCE),
            "bounds_tolerance": safe_float(self.w.boundsTol.get(), DEFAULT_SHAPE_SHIFT_TOLERANCE),
        }

    def _add_issue(self, severity, glyph, layer, check, details, reference="", current="", suggestion=None, current_master=None):
        glyph_name = getattr(glyph, "name", "") or ""
        severity = normalize_severity(severity, check, details)
        suggestion = suggestion or suggested_solution(check, details)
        master_id = ""
        if layer is not None:
            master_id = getattr(layer, "associatedMasterId", None) or getattr(layer, "layerId", None) or ""
        elif current_master is not None:
            master_id = getattr(current_master, "id", "") or ""
        row = {
            "Severity": severity,
            "Glyph": glyph_name,
            "Master": getattr(current_master, "name", None) or layer_name(layer, self.master_by_id),
            "MasterId": master_id,
            "Check": check,
            "Details": details,
            "Reference": str(reference or ""),
            "Current": str(current or ""),
            "Likely Fix": suggestion,
        }
        self.results.append(row)

    def _run_callback(self, sender):
        try:
            self.run()
        except Exception:
            Glyphs.showMacroWindow()
            print(traceback.format_exc())
            Message(SCRIPT_NAME, "The check stopped because of an error. See the Macro Window for details.")

    def run(self):
        settings = self._settings()
        glyphs = get_scope_glyphs(self.font, settings["scope"])
        if not glyphs:
            Message(SCRIPT_NAME, "No glyphs found for the selected scope.")
            return

        self.results = []
        self.issue_glyph_names = []
        self.w.resultsList.set([])
        self.w.progress.set(0)
        self.w.statusText.set("Checking %s glyphs..." % len(glyphs))

        masters = list(self.font.masters)
        reference_master = settings["reference_master"]
        other_masters = [master for master in masters if master.id != reference_master.id]

        if len(masters) < 2:
            Message(SCRIPT_NAME, "This font has fewer than two masters.")
            self.w.statusText.set("Need at least two masters.")
            return

        for index, glyph in enumerate(glyphs):
            reference_layer = get_master_layer(glyph, reference_master)
            self._check_glyph(glyph, reference_layer, other_masters, settings)
            self.w.progress.set((index + 1) / float(len(glyphs)) * 100.0)

        self.w.resultsList.set(self.results)
        self.issue_glyph_names = sorted(set(row["Glyph"] for row in self.results if row.get("Glyph")))
        summary = self._summary_text(len(glyphs))
        self.w.statusText.set(summary)

        if settings["create_html"]:
            self.last_html_path = self._write_html_report(settings, glyphs)
            if self.last_html_path and settings["open_html"]:
                self._open_html_path(self.last_html_path)
        if settings["show_macro"]:
            self._print_report(settings, glyphs)
        if settings["open_tab"] and self.issue_glyph_names:
            self._open_affected_tab()

        Glyphs.showNotification(SCRIPT_NAME, summary)

    def _check_glyph(self, glyph, reference_layer, other_masters, settings):
        if reference_layer is None:
            self._add_issue("Error", glyph, None, "Missing layer", "Missing reference master layer.", current="missing")
            return

        for master in other_masters:
            layer = get_master_layer(glyph, master)
            if layer is None:
                if settings["check_empty"]:
                    self._add_issue(
                        "Error",
                        glyph,
                        None,
                        "Missing layer",
                        "Missing layer for master '%s'." % master.name,
                        reference=layer_name(reference_layer, self.master_by_id),
                        current="missing",
                        current_master=master,
                    )
                continue

            if settings["check_empty"]:
                self._check_empty_content(glyph, reference_layer, layer)
            if settings["check_shape_order"]:
                self._check_shape_order(glyph, reference_layer, layer)
            if settings["check_paths"]:
                self._check_paths(glyph, reference_layer, layer)
            if settings["check_angles"]:
                self._check_segment_angles(glyph, reference_layer, layer, settings)
            if settings["check_handles"]:
                self._check_handle_ratios(glyph, reference_layer, layer, settings)
            if settings["check_components"]:
                self._check_components(glyph, reference_layer, layer, settings)
            if settings["check_shape_shifts"]:
                self._check_shape_shifts(glyph, reference_layer, layer, settings)
            if settings["check_metrics"]:
                self._check_metrics(glyph, reference_layer, layer, settings)
            if settings["check_metric_keys"]:
                self._check_metric_keys(glyph, reference_layer, layer)
            if settings["check_anchors"]:
                self._check_anchor_names(glyph, reference_layer, layer)
            if settings["check_anchor_positions"]:
                self._check_anchor_positions(glyph, reference_layer, layer, settings)
            if settings["check_bounds"]:
                self._check_bounds(glyph, reference_layer, layer, settings)

    def _check_empty_content(self, glyph, reference_layer, layer):
        ref_shapes = len(list(getattr(reference_layer, "shapes", []) or []))
        shapes = len(list(getattr(layer, "shapes", []) or []))
        ref_anchors = len(list(getattr(reference_layer, "anchors", []) or []))
        anchors = len(list(getattr(layer, "anchors", []) or []))
        if (ref_shapes == 0) != (shapes == 0):
            self._add_issue(
                "Error",
                glyph,
                layer,
                "Empty/content",
                "Reference has %s shapes, this master has %s." % (ref_shapes, shapes),
                reference="%s shapes" % ref_shapes,
                current="%s shapes" % shapes,
            )
        if (ref_anchors == 0) != (anchors == 0):
            self._add_issue(
                "Warning",
                glyph,
                layer,
                "Empty/content",
                "Reference has %s anchors, this master has %s." % (ref_anchors, anchors),
                reference="%s anchors" % ref_anchors,
                current="%s anchors" % anchors,
            )

    def _check_shape_order(self, glyph, reference_layer, layer):
        ref_shapes = list(getattr(reference_layer, "shapes", []) or [])
        shapes = list(getattr(layer, "shapes", []) or [])
        if len(ref_shapes) != len(shapes):
            self._add_issue(
                "Error",
                glyph,
                layer,
                "Shape order",
                "Shape count differs: reference %s, this master %s." % (len(ref_shapes), len(shapes)),
                reference="%s shapes" % len(ref_shapes),
                current="%s shapes" % len(shapes),
            )
        for index in range(min(len(ref_shapes), len(shapes))):
            ref_shape = ref_shapes[index]
            shape = shapes[index]
            ref_kind = shape_kind(ref_shape)
            kind = shape_kind(shape)
            if ref_kind != kind:
                self._add_issue(
                    "Error",
                    glyph,
                    layer,
                    "Shape order",
                    "Shape %s is %s in reference but %s here." % (index + 1, ref_kind, kind),
                    reference=shape_label(ref_shape),
                    current=shape_label(shape),
                )
                continue
            if is_component(ref_shape) and is_component(shape):
                ref_name = getattr(ref_shape, "componentName", "") or ""
                name = getattr(shape, "componentName", "") or ""
                if ref_name != name:
                    self._add_issue(
                        "Error",
                        glyph,
                        layer,
                        "Shape order",
                        "Shape %s component base differs: %s vs %s." % (index + 1, ref_name, name),
                        reference=ref_name,
                        current=name,
                    )

    def _check_paths(self, glyph, reference_layer, layer):
        ref_paths = list(getattr(reference_layer, "paths", []) or [])
        paths = list(getattr(layer, "paths", []) or [])
        if len(ref_paths) != len(paths):
            self._add_issue(
                "Error",
                glyph,
                layer,
                "Paths",
                "Path count differs: reference %s, this master %s." % (len(ref_paths), len(paths)),
                reference="%s paths" % len(ref_paths),
                current="%s paths" % len(paths),
            )
        for path_index in range(min(len(ref_paths), len(paths))):
            ref_sig = path_signature(ref_paths[path_index])
            sig = path_signature(paths[path_index])
            label = "Path %s" % (path_index + 1)
            for key, title in (
                ("closed", "open/closed state"),
                ("direction", "direction"),
                ("node_count", "node count"),
                ("node_types", "node type sequence"),
                ("connections", "smooth/sharp sequence"),
            ):
                if ref_sig[key] != sig[key]:
                    severity = "Error" if key in ("closed", "node_count", "node_types") else "Warning"
                    self._add_issue(
                        severity,
                        glyph,
                        layer,
                        "Paths",
                        "%s %s differs." % (label, title),
                        reference=str(ref_sig[key]),
                        current=str(sig[key]),
                    )

    def _check_segment_angles(self, glyph, reference_layer, layer, settings):
        tolerance = settings["segment_angle_tolerance"]
        ref_paths = list(getattr(reference_layer, "paths", []) or [])
        paths = list(getattr(layer, "paths", []) or [])
        for path_index in range(min(len(ref_paths), len(paths))):
            ref_angles = path_segment_angles(ref_paths[path_index])
            angles = path_segment_angles(paths[path_index])
            if len(ref_angles) != len(angles):
                continue
            for segment_index, ref_angle in enumerate(ref_angles):
                delta = angle_delta(ref_angle, angles[segment_index])
                if delta > tolerance:
                    self._add_issue(
                        "Warning",
                        glyph,
                        layer,
                        "Segment angle",
                        "Path %s segment %s angle differs by %s deg." % (
                            path_index + 1,
                            segment_index + 1,
                            format_number(delta),
                        ),
                        reference="%s deg" % format_number(ref_angle),
                        current="%s deg" % format_number(angles[segment_index]),
                    )

    def _check_handle_ratios(self, glyph, reference_layer, layer, settings):
        tolerance = settings["handle_ratio_tolerance"]
        ref_paths = list(getattr(reference_layer, "paths", []) or [])
        paths = list(getattr(layer, "paths", []) or [])
        for path_index in range(min(len(ref_paths), len(paths))):
            ref_ratios = smooth_curve_handle_ratios(ref_paths[path_index])
            ratios = smooth_curve_handle_ratios(paths[path_index])
            if len(ref_ratios) != len(ratios):
                continue
            for ratio_index, ref_ratio in enumerate(ref_ratios):
                ratio = ratios[ratio_index]
                if ref_ratio is None or ratio is None:
                    continue
                delta = abs(ref_ratio - ratio)
                if delta > tolerance:
                    self._add_issue(
                        "Warning",
                        glyph,
                        layer,
                        "Handle ratio",
                        "Path %s smooth point %s handle ratio differs by %s." % (
                            path_index + 1,
                            ratio_index + 1,
                            format_number(delta),
                        ),
                        reference=format_number(ref_ratio, 3),
                        current=format_number(ratio, 3),
                    )

    def _check_components(self, glyph, reference_layer, layer, settings):
        tolerance = settings["transform_tolerance"]
        ref_components = list(getattr(reference_layer, "components", []) or [])
        components = list(getattr(layer, "components", []) or [])
        if len(ref_components) != len(components):
            self._add_issue(
                "Error",
                glyph,
                layer,
                "Components",
                "Component count differs: reference %s, this master %s." % (len(ref_components), len(components)),
                reference="%s components" % len(ref_components),
                current="%s components" % len(components),
            )
        for comp_index in range(min(len(ref_components), len(components))):
            ref_sig = component_signature(ref_components[comp_index])
            sig = component_signature(components[comp_index])
            label = "Component %s" % (comp_index + 1)
            if sig["base"]:
                try:
                    if self.font.glyphs[sig["base"]] is None:
                        self._add_issue(
                            "Error",
                            glyph,
                            layer,
                            "Components",
                            "%s references missing glyph '%s'." % (label, sig["base"]),
                            current=sig["base"],
                        )
                except Exception:
                    pass
            if ref_sig["base"] != sig["base"]:
                self._add_issue(
                    "Error",
                    glyph,
                    layer,
                    "Components",
                    "%s base differs: %s vs %s." % (label, ref_sig["base"], sig["base"]),
                    reference=ref_sig["base"],
                    current=sig["base"],
                )
            for key, title in (("anchor", "anchor attachment"), ("alignment", "alignment"), ("piece_settings", "smart settings")):
                if ref_sig[key] != sig[key]:
                    self._add_issue(
                        "Warning",
                        glyph,
                        layer,
                        "Components",
                        "%s %s differs." % (label, title),
                        reference=str(ref_sig[key]),
                        current=str(sig[key]),
                    )
            ref_transform = ref_sig["transform"]
            transform = sig["transform"]
            for value_index in range(min(len(ref_transform), len(transform))):
                if abs(ref_transform[value_index] - transform[value_index]) > tolerance:
                    self._add_issue(
                        "Warning",
                        glyph,
                        layer,
                        "Components",
                        "%s transform differs." % label,
                        reference=str(ref_transform),
                        current=str(transform),
                    )
                    break

    def _check_shape_shifts(self, glyph, reference_layer, layer, settings):
        tolerance = settings["shape_shift_tolerance"]
        ref_shapes = list(getattr(reference_layer, "shapes", []) or [])
        shapes = list(getattr(layer, "shapes", []) or [])
        if len(ref_shapes) != len(shapes):
            return
        ref_x_rank, ref_y_rank = shape_center_rank_signature(reference_layer)
        x_rank, y_rank = shape_center_rank_signature(layer)
        if len(ref_shapes) > 1 and (ref_x_rank != x_rank or ref_y_rank != y_rank):
            self._add_issue(
                "Warning",
                glyph,
                layer,
                "Shape centers",
                "Shape center order differs from reference; possible shape-order mismatch.",
                reference="x %s, y %s" % (ref_x_rank, ref_y_rank),
                current="x %s, y %s" % (x_rank, y_rank),
            )
        for shape_index in range(len(ref_shapes)):
            delta = distance(shape_center(ref_shapes[shape_index]), shape_center(shapes[shape_index]))
            if delta > tolerance:
                self._add_issue(
                    "Warning",
                    glyph,
                    layer,
                    "Shape centers",
                    "Shape %s center moved by %s units." % (shape_index + 1, format_number(delta)),
                    reference="(%s, %s)" % (
                        format_number(shape_center(ref_shapes[shape_index])[0]),
                        format_number(shape_center(ref_shapes[shape_index])[1]),
                    ),
                    current="(%s, %s)" % (
                        format_number(shape_center(shapes[shape_index])[0]),
                        format_number(shape_center(shapes[shape_index])[1]),
                    ),
                )

    def _check_metrics(self, glyph, reference_layer, layer, settings):
        tolerance = settings["metric_tolerance"]
        for attr in ("width", "LSB", "RSB"):
            try:
                ref_value = float(getattr(reference_layer, attr))
                value = float(getattr(layer, attr))
            except Exception:
                continue
            delta = abs(ref_value - value)
            if delta > tolerance:
                self._add_issue(
                    "Warning",
                    glyph,
                    layer,
                    "Metrics",
                    "%s differs by %s: reference %s, this master %s." % (
                        attr,
                        format_number(delta),
                        format_number(ref_value),
                        format_number(value),
                    ),
                    reference="%s %s" % (attr, format_number(ref_value)),
                    current="%s %s" % (attr, format_number(value)),
                )

    def _check_metric_keys(self, glyph, reference_layer, layer):
        for attr in ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey"):
            ref_value = getattr(reference_layer, attr, None) or ""
            value = getattr(layer, attr, None) or ""
            if ref_value != value:
                self._add_issue(
                    "Warning",
                    glyph,
                    layer,
                    "Metrics keys",
                    "%s differs: '%s' vs '%s'." % (attr, ref_value, value),
                    reference="%s = %s" % (attr, ref_value or "<empty>"),
                    current="%s = %s" % (attr, value or "<empty>"),
                )
        for attr in ("isAligned", "hasAlignedWidth"):
            ref_value = bool_value(reference_layer, attr)
            value = bool_value(layer, attr)
            if ref_value is None or value is None:
                continue
            if ref_value != value:
                self._add_issue(
                    "Warning",
                    glyph,
                    layer,
                    "Alignment",
                    "%s differs: reference %s, this master %s." % (attr, ref_value, value),
                    reference="%s = %s" % (attr, ref_value),
                    current="%s = %s" % (attr, value),
                )

    def _check_anchor_names(self, glyph, reference_layer, layer):
        ref_anchors, ref_order = anchor_dict(reference_layer)
        anchors, order = anchor_dict(layer)
        ref_names = set(ref_anchors.keys())
        names = set(anchors.keys())
        missing = sorted(ref_names - names)
        extra = sorted(names - ref_names)
        if missing or extra:
            details = []
            if missing:
                details.append("missing: %s" % ", ".join(missing))
            if extra:
                details.append("extra: %s" % ", ".join(extra))
            self._add_issue(
                "Error",
                glyph,
                layer,
                "Anchors",
                "; ".join(details),
                reference=join_values(ref_order),
                current=join_values(order),
            )
        if ref_order != order and ref_names == names:
            self._add_issue(
                "Warning",
                glyph,
                layer,
                "Anchors",
                "Anchor order differs: %s vs %s." % (", ".join(ref_order), ", ".join(order)),
                reference=join_values(ref_order),
                current=join_values(order),
            )

    def _check_anchor_positions(self, glyph, reference_layer, layer, settings):
        tolerance = settings["anchor_tolerance"]
        ref_anchors, _ref_order = anchor_dict(reference_layer)
        anchors, _order = anchor_dict(layer)
        for name in sorted(set(ref_anchors.keys()) & set(anchors.keys())):
            ref_position = point_tuple(ref_anchors[name].position)
            position = point_tuple(anchors[name].position)
            delta = distance(ref_position, position)
            if delta > tolerance:
                self._add_issue(
                    "Warning",
                    glyph,
                    layer,
                    "Anchor positions",
                    "'%s' moved by %s units: (%s, %s) -> (%s, %s)." % (
                        name,
                        format_number(delta),
                        format_number(ref_position[0]),
                        format_number(ref_position[1]),
                        format_number(position[0]),
                        format_number(position[1]),
                    ),
                    reference="%s (%s, %s)" % (name, format_number(ref_position[0]), format_number(ref_position[1])),
                    current="%s (%s, %s)" % (name, format_number(position[0]), format_number(position[1])),
                )

    def _check_bounds(self, glyph, reference_layer, layer, settings):
        tolerance = settings["bounds_tolerance"]
        ref_edges = rect_edges(object_bounds(reference_layer))
        edges = rect_edges(object_bounds(layer))
        if not ref_edges or not edges:
            return
        for key in ("xMin", "yMin", "xMax", "yMax", "width", "height"):
            delta = abs(ref_edges[key] - edges[key])
            if delta > tolerance:
                self._add_issue(
                    "Warning",
                    glyph,
                    layer,
                    "Bounds",
                    "%s differs by %s: reference %s, this master %s." % (
                        key,
                        format_number(delta),
                        format_number(ref_edges[key]),
                        format_number(edges[key]),
                    ),
                    reference="%s %s" % (key, format_number(ref_edges[key])),
                    current="%s %s" % (key, format_number(edges[key])),
                )

    def _summary_text(self, glyph_count):
        counts = self._severity_counts()
        affected = len(set(row["Glyph"] for row in self.results))
        if not self.results:
            return "No issues found in %s glyphs." % glyph_count
        return "%s issues in %s glyphs: %s critical, %s errors, %s warnings, %s info." % (
            len(self.results),
            affected,
            counts["Critical"],
            counts["Error"],
            counts["Warning"],
            counts["Info"],
        )

    def _severity_counts(self, rows=None):
        rows = rows if rows is not None else self.results
        return {severity: len([row for row in rows if row["Severity"] == severity]) for severity in SEVERITIES}

    def _print_report(self, settings, glyphs):
        Glyphs.showMacroWindow()
        print("\n%s" % SCRIPT_NAME)
        print("=" * len(SCRIPT_NAME))
        print("Font: %s" % getattr(self.font, "familyName", "Untitled"))
        print("Scope: %s (%s glyphs)" % (settings["scope"], len(glyphs)))
        print("Reference master: %s" % settings["reference_master"].name)
        print("\nChecks:")
        for check in CHECKS:
            print("- %s" % check)
        print("\n%s" % self._summary_text(len(glyphs)))

        if not self.results:
            return

        print("\nIssues:")
        for row in self.results:
            print(
                "[%(Severity)s] %(Glyph)s / %(Master)s / %(Check)s: %(Details)s\n"
                "  Reference: %(Reference)s\n"
                "  Current: %(Current)s\n"
                "  Likely fix: %(Likely Fix)s"
                % row
            )

        if self.last_html_path:
            print("\nHTML report: %s" % self.last_html_path)

    def _report_directory(self):
        font_path = getattr(self.font, "filepath", None)
        if callable(font_path):
            try:
                font_path = font_path()
            except Exception:
                font_path = None
        font_path = str(font_path or "").strip()
        if font_path.startswith("file://"):
            font_path = unquote(urlparse(font_path).path)
        if font_path and font_path.lower() != "none":
            base_dir = os.path.dirname(font_path)
        else:
            base_dir = os.path.expanduser("~/Desktop")
        report_dir = os.path.join(base_dir, "Master Consistency Reports")
        try:
            os.makedirs(report_dir)
        except OSError:
            if not os.path.isdir(report_dir):
                report_dir = os.path.expanduser("~/Desktop")
        return report_dir

    def _write_html_report(self, settings, glyphs):
        report_dir = self._report_directory()
        family_name = getattr(self.font, "familyName", "Untitled") or "Untitled"
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        file_name = "%s-master-consistency-%s.html" % (clean_filename(family_name), timestamp)
        report_path = os.path.join(report_dir, file_name)
        html = self._build_html_report(settings, glyphs, report_path)
        with open(report_path, "w", encoding="utf-8") as report_file:
            report_file.write(html)
        print("HTML report saved: %s" % report_path)
        return report_path

    def _glyph_for_name(self, glyph_name):
        try:
            return self.font.glyphs[glyph_name]
        except Exception:
            return None

    def _layer_for_master_id(self, glyph, master_id):
        if glyph is None or not master_id:
            return None
        try:
            return glyph.layers[master_id]
        except Exception:
            return None

    def _overlay_svg(self, glyph, reference_master, master_id, label):
        reference_layer = get_master_layer(glyph, reference_master)
        current_layer = self._layer_for_master_id(glyph, master_id)
        reference_svg = layer_svg_data(reference_layer)
        current_svg = layer_svg_data(current_layer)

        if not reference_svg and not current_svg:
            return '<div class="preview-empty">No drawable preview available.</div>'

        svg_infos = [info for info in (reference_svg, current_svg) if info]
        x_min = min(info["x_min"] for info in svg_infos)
        x_max = max(info["x_max"] for info in svg_infos)
        y_min = min(info["y_min"] for info in svg_infos)
        y_max = max(info["y_max"] for info in svg_infos)
        width = max(info["width"] for info in svg_infos)
        viewbox = "%s %s %s %s" % (
            svg_number(x_min),
            svg_number(y_min),
            svg_number(max(1.0, x_max - x_min)),
            svg_number(max(1.0, y_max - y_min)),
        )
        baseline = "M %s 0 L %s 0" % (svg_number(x_min), svg_number(x_max))
        width_line = "M %s %s L %s %s" % (svg_number(width), svg_number(y_min), svg_number(width), svg_number(y_max))
        ref_path = escape_html((reference_svg or {}).get("path", ""))
        current_path = escape_html((current_svg or {}).get("path", ""))
        ref_has_paths = bool((reference_svg or {}).get("has_paths"))
        current_has_paths = bool((current_svg or {}).get("has_paths"))
        viewbox = escape_html(viewbox)
        baseline = escape_html(baseline)
        width_line = escape_html(width_line)

        if not current_has_paths:
            current_path = ""
        if not ref_has_paths:
            ref_path = ""

        return """
        <figure class="overlay-preview">
            <figcaption>
                <strong>%(label)s</strong>
                <span><i class="swatch reference"></i>Reference <i class="swatch current"></i>This master</span>
            </figcaption>
            <svg viewBox="%(viewbox)s" role="img" aria-label="Overlay preview">
                <path class="guide" d="%(baseline)s"></path>
                <path class="guide width" d="%(width_line)s"></path>
                <path class="outline reference" d="%(ref_path)s"></path>
                <path class="outline current" d="%(current_path)s"></path>
            </svg>
        </figure>
        """ % {
            "label": escape_html(label),
            "viewbox": viewbox,
            "baseline": baseline,
            "width_line": width_line,
            "ref_path": ref_path,
            "current_path": current_path,
        }

    def _glyph_previews_html(self, glyph_name, rows, reference_master):
        glyph = self._glyph_for_name(glyph_name)
        if glyph is None:
            return '<div class="preview-empty">Glyph is no longer available in the font.</div>'
        seen = []
        previews = []
        for row in rows:
            master_id = row.get("MasterId")
            if not master_id or master_id in seen:
                continue
            seen.append(master_id)
            previews.append(self._overlay_svg(glyph, reference_master, master_id, row.get("Master", "Master")))
        if not previews:
            return '<div class="preview-empty">No affected master layer preview available.</div>'
        return '<div class="preview-grid">%s</div>' % "\n".join(previews)

    def _build_html_report(self, settings, glyphs, report_path):
        generated = datetime.now().strftime("%Y-%m-%d %H:%M")
        family_name = getattr(self.font, "familyName", "Untitled") or "Untitled"
        severity_counts = self._severity_counts()
        affected_glyphs = sorted(set(row["Glyph"] for row in self.results if row.get("Glyph")))
        checks = sorted(set(row["Check"] for row in self.results))

        by_check = []
        for check in checks:
            rows = [row for row in self.results if row["Check"] == check]
            counts = self._severity_counts(rows)
            by_check.append((check, len(rows), counts))

        rows_by_glyph = []
        for glyph_name in affected_glyphs:
            rows = [row for row in self.results if row["Glyph"] == glyph_name]
            rows_by_glyph.append((glyph_name, rows))

        def e(value):
            return escape_html(str(value or ""))

        def severity_class(severity):
            return str(severity or "warning").lower()

        check_summary = []
        for check, count, counts in by_check:
            check_summary.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (e(check), count, counts["Critical"], counts["Error"], counts["Warning"], counts["Info"])
            )

        glyph_cards = []
        for glyph_name, rows in rows_by_glyph:
            glyph_counts = self._severity_counts(rows)
            row_html = []
            for row in rows:
                row_html.append(
                    """
                    <tr>
                        <td><span class="badge %(severity_class)s">%(severity)s</span></td>
                        <td>%(master)s</td>
                        <td>%(check)s</td>
                        <td>%(details)s</td>
                        <td><div class="value-label">Reference</div>%(reference)s<div class="value-label current">This master</div>%(current)s</td>
                        <td>%(solution)s</td>
                    </tr>
                    """
                    % {
                        "severity_class": severity_class(row["Severity"]),
                        "severity": e(row["Severity"]),
                        "master": e(row["Master"]),
                        "check": e(row["Check"]),
                        "details": e(row["Details"]),
                        "reference": e(row.get("Reference")),
                        "current": e(row.get("Current")),
                        "solution": e(row.get("Likely Fix")),
                    }
                )
            glyph_cards.append(
                """
                <section class="glyph-card" id="glyph-%(slug)s">
                    <header>
                        <div>
                            <h2>%(glyph)s</h2>
                            <p>%(count)s issue%(plural)s across checked masters</p>
                        </div>
                        <div class="severity-strip">
                            <span class="critical">%(critical)s Critical</span>
                            <span class="error">%(error)s Error</span>
                            <span class="warning">%(warning)s Warning</span>
                            <span class="info">%(info)s Info</span>
                        </div>
                        <a href="#top">Back to top</a>
                    </header>
                    %(previews)s
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Severity</th>
                                    <th>Master</th>
                                    <th>Check</th>
                                    <th>Difference</th>
                                    <th>Master Values</th>
                                    <th>Likely Fix</th>
                                </tr>
                            </thead>
                            <tbody>
                                %(rows)s
                            </tbody>
                        </table>
                    </div>
                </section>
                """
                % {
                    "slug": clean_filename(glyph_name, "glyph"),
                    "glyph": e(glyph_name),
                    "count": len(rows),
                    "plural": "" if len(rows) == 1 else "s",
                    "critical": glyph_counts["Critical"],
                    "error": glyph_counts["Error"],
                    "warning": glyph_counts["Warning"],
                    "info": glyph_counts["Info"],
                    "previews": self._glyph_previews_html(glyph_name, rows, settings["reference_master"]),
                    "rows": "\n".join(row_html),
                }
            )

        glyph_nav = []
        for glyph_name, rows in rows_by_glyph:
            counts = self._severity_counts(rows)
            glyph_nav.append(
                '<a class="glyph-link" href="#glyph-%s"><span>%s</span><strong>%s</strong><em>%s C</em></a>'
                % (clean_filename(glyph_name, "glyph"), e(glyph_name), len(rows), counts["Critical"])
            )

        if not glyph_cards:
            glyph_cards.append(
                """
                <section class="glyph-card empty-state">
                    <h2>No affected glyphs</h2>
                    <p>The selected checks did not find master inconsistencies in this run.</p>
                </section>
                """
            )

        return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(family)s - Master Consistency Report</title>
<style>
:root {
    color-scheme: light;
    --bg: #f4f3ef;
    --ink: #171717;
    --muted: #67645f;
    --line: #d9d4ca;
    --panel: #fffdfa;
    --accent: #126c64;
    --accent-soft: #dcefeb;
    --info: #2d5b87;
    --info-bg: #dceafa;
    --warn: #9a5b00;
    --warn-bg: #fff0cf;
    --error: #b42318;
    --error-bg: #ffe1dd;
    --critical: #681515;
    --critical-bg: #ffd0c7;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
a { color: var(--accent); text-decoration: none; }
.shell {
    display: grid;
    grid-template-columns: 250px minmax(0, 1fr);
    min-height: 100vh;
}
aside {
    border-right: 1px solid var(--line);
    padding: 22px 16px;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow: auto;
    background: #ebe7dd;
}
main { padding: 28px; }
.eyebrow {
    color: var(--accent);
    font-weight: 700;
    letter-spacing: .04em;
    text-transform: uppercase;
    font-size: 11px;
}
h1, h2, h3 { margin: 0; line-height: 1.12; }
h1 { font-size: 34px; max-width: 820px; }
h2 { font-size: 22px; }
p { margin: 6px 0 0; color: var(--muted); }
.top-actions {
    display: flex;
    gap: 8px;
    margin: 18px 0 0;
    align-items: center;
    flex-wrap: wrap;
}
.top-actions button {
    border: 1px solid var(--line);
    background: var(--panel);
    color: var(--ink);
    border-radius: 6px;
    padding: 8px 12px;
    font: inherit;
    cursor: pointer;
}
.top-actions button:hover { border-color: var(--accent); color: var(--accent); }
#navStatus { color: var(--muted); font-size: 12px; }
.meta {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 10px;
    margin: 24px 0;
}
.stat, .glyph-card, .summary-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
}
.stat { padding: 14px; }
.stat span { display: block; color: var(--muted); font-size: 12px; }
.stat strong { display: block; font-size: 26px; margin-top: 3px; }
.summary-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 250px;
    gap: 16px;
    align-items: start;
}
.summary-card { padding: 16px; }
.summary-card table { margin-top: 12px; }
.nav-title {
    display: flex;
    justify-content: space-between;
    color: var(--muted);
    font-size: 12px;
    margin: 22px 0 8px;
}
.glyph-nav { display: grid; gap: 6px; }
.glyph-nav a {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 8px;
    align-items: center;
    padding: 8px 9px;
    border-radius: 6px;
    color: var(--ink);
}
.glyph-nav a:hover { background: rgba(18, 108, 100, .1); }
.glyph-nav span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.glyph-nav strong, .glyph-nav em {
    font-size: 11px;
    font-style: normal;
    color: var(--muted);
}
.glyph-card { margin-top: 18px; overflow: hidden; }
.glyph-card header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 18px;
    border-bottom: 1px solid var(--line);
    background: #faf7ef;
}
.severity-strip {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: flex-end;
    margin-left: auto;
}
.severity-strip span {
    border-radius: 999px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 700;
}
.severity-strip .critical { background: var(--critical-bg); color: var(--critical); }
.severity-strip .error { background: var(--error-bg); color: var(--error); }
.severity-strip .warning { background: var(--warn-bg); color: var(--warn); }
.severity-strip .info { background: var(--info-bg); color: var(--info); }
.preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px;
    padding: 16px 18px;
    border-bottom: 1px solid var(--line);
    background: #f7f5ef;
}
.overlay-preview {
    margin: 0;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #fffefa;
    overflow: hidden;
}
.overlay-preview figcaption {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
    padding: 8px 10px;
    border-bottom: 1px solid var(--line);
    color: var(--muted);
    font-size: 12px;
}
.overlay-preview figcaption strong { color: var(--ink); }
.swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%%;
    margin: 0 4px 0 8px;
    vertical-align: -1px;
}
.swatch.reference { background: #1b1b1b; }
.swatch.current { background: #d4482a; }
.overlay-preview svg {
    display: block;
    width: 100%%;
    height: 260px;
    background:
        linear-gradient(to right, rgba(0,0,0,.035) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(0,0,0,.035) 1px, transparent 1px);
    background-size: 40px 40px;
}
.outline {
    fill: none;
    stroke-width: 10;
    stroke-linecap: round;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
}
.outline.reference { stroke: #111; opacity: .78; }
.outline.current { stroke: #d4482a; opacity: .78; stroke-dasharray: 28 15; }
.guide {
    fill: none;
    stroke: #126c64;
    stroke-width: 4;
    opacity: .28;
    vector-effect: non-scaling-stroke;
}
.guide.width { stroke-dasharray: 12 12; }
.preview-empty {
    padding: 16px 18px;
    color: var(--muted);
    border-bottom: 1px solid var(--line);
    background: #f7f5ef;
}
.table-wrap { overflow: auto; }
table {
    border-collapse: collapse;
    width: 100%%;
}
th, td {
    border-bottom: 1px solid var(--line);
    padding: 10px 12px;
    text-align: left;
    vertical-align: top;
}
th {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .03em;
    background: #f7f3ea;
}
td { min-width: 120px; }
td:nth-child(4), td:nth-child(6) { min-width: 260px; }
.badge {
    display: inline-block;
    padding: 3px 7px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
}
.badge.critical { background: var(--critical-bg); color: var(--critical); }
.badge.error { background: var(--error-bg); color: var(--error); }
.badge.warning { background: var(--warn-bg); color: var(--warn); }
.badge.info { background: var(--info-bg); color: var(--info); }
.value-label {
    color: var(--muted);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 2px;
}
.value-label.current { margin-top: 8px; }
.empty-state { padding: 24px; }
.path-note {
    overflow-wrap: anywhere;
    color: var(--muted);
    font-size: 12px;
    margin-top: 20px;
}
@media (max-width: 900px) {
    .shell { display: block; }
    aside { position: relative; height: auto; }
    .meta, .summary-grid { grid-template-columns: 1fr; }
    main { padding: 18px; }
}
</style>
</head>
<body>
<div class="shell">
<aside>
    <div class="eyebrow">Glyphs 3 Report</div>
    <h3>%(family)s</h3>
    <p>Generated %(generated)s</p>
    <div class="nav-title"><span>Affected glyphs</span><span>Issues</span></div>
    <nav class="glyph-nav">%(glyph_nav)s</nav>
</aside>
<main id="top">
    <div class="eyebrow">Master Consistency Checker</div>
    <h1>Master-to-master inconsistency report</h1>
    <p>Reference master: <strong>%(reference_master)s</strong>. Scope: <strong>%(scope)s</strong>.</p>
    <div class="top-actions">
        <button type="button" id="prevGlyph">Previous Glyph</button>
        <button type="button" id="nextGlyph">Next Glyph</button>
        <span id="navStatus"></span>
    </div>
    <section class="meta">
        <div class="stat"><span>Glyphs checked</span><strong>%(glyphs_checked)s</strong></div>
        <div class="stat"><span>Affected glyphs</span><strong>%(affected)s</strong></div>
        <div class="stat"><span>Critical</span><strong>%(critical)s</strong></div>
        <div class="stat"><span>Errors</span><strong>%(errors)s</strong></div>
        <div class="stat"><span>Warnings</span><strong>%(warnings)s</strong></div>
        <div class="stat"><span>Info</span><strong>%(info)s</strong></div>
    </section>
    <section class="summary-grid">
        <div class="summary-card">
            <h2>Checks With Issues</h2>
            <p>Each row below is a category where at least one difference was found.</p>
            <table>
                <thead><tr><th>Check</th><th>Total</th><th>Critical</th><th>Errors</th><th>Warnings</th><th>Info</th></tr></thead>
                <tbody>%(check_summary)s</tbody>
            </table>
        </div>
        <div class="summary-card">
            <h2>Likely Fixes</h2>
            <p>The suggestions are rule-based. They point to the most probable repair, but intentional design differences should stay intentional.</p>
        </div>
    </section>
    %(glyph_cards)s
    <p class="path-note">Report file: %(report_path)s</p>
</main>
</div>
<script>
(function () {
    const cards = Array.from(document.querySelectorAll(".glyph-card[id]"));
    const status = document.getElementById("navStatus");
    let index = 0;

    function currentIndexFromScroll() {
        if (!cards.length) return 0;
        const y = window.scrollY + 120;
        let current = 0;
        cards.forEach(function (card, i) {
            if (card.offsetTop <= y) current = i;
        });
        return current;
    }

    function updateStatus() {
        if (!status) return;
        if (!cards.length) {
            status.textContent = "No affected glyphs";
            return;
        }
        index = currentIndexFromScroll();
        const title = cards[index].querySelector("h2");
        status.textContent = (index + 1) + " / " + cards.length + (title ? " - " + title.textContent : "");
    }

    function go(delta) {
        if (!cards.length) return;
        index = currentIndexFromScroll();
        index = Math.max(0, Math.min(cards.length - 1, index + delta));
        cards[index].scrollIntoView({ behavior: "smooth", block: "start" });
        window.setTimeout(updateStatus, 250);
    }

    const prev = document.getElementById("prevGlyph");
    const next = document.getElementById("nextGlyph");
    if (prev) prev.addEventListener("click", function () { go(-1); });
    if (next) next.addEventListener("click", function () { go(1); });
    window.addEventListener("scroll", updateStatus, { passive: true });
    updateStatus();
}());
</script>
</body>
</html>
""" % {
            "family": e(family_name),
            "generated": e(generated),
            "reference_master": e(settings["reference_master"].name),
            "scope": e(settings["scope"]),
            "glyphs_checked": len(glyphs),
            "affected": len(affected_glyphs),
            "critical": severity_counts["Critical"],
            "errors": severity_counts["Error"],
            "warnings": severity_counts["Warning"],
            "info": severity_counts["Info"],
            "check_summary": "\n".join(check_summary) if check_summary else '<tr><td colspan="6">No issues found.</td></tr>',
            "glyph_cards": "\n".join(glyph_cards),
            "glyph_nav": "\n".join(glyph_nav) if glyph_nav else "<p>No affected glyphs.</p>",
            "report_path": e(report_path),
        }

    def _open_html_path(self, path):
        if not path:
            return
        try:
            webbrowser.open("file://" + pathname2url(path))
        except Exception:
            try:
                Glyphs.showNotification(SCRIPT_NAME, "HTML report saved, but could not be opened automatically.")
            except Exception:
                pass

    def _open_affected_tab(self):
        if not self.issue_glyph_names:
            return
        tab_string = "/" + "/".join(self.issue_glyph_names)
        try:
            self.font.newTab(tab_string)
        except Exception:
            try:
                Glyphs.currentDocument.windowController().addTabWithString_(tab_string)
            except Exception:
                pass

    def _open_tab_callback(self, sender):
        self.issue_glyph_names = sorted(set(row["Glyph"] for row in self.results if row.get("Glyph")))
        if not self.issue_glyph_names:
            Message(SCRIPT_NAME, "No affected glyphs to open.")
            return
        self._open_affected_tab()

    def _open_html_callback(self, sender):
        if not self.last_html_path or not os.path.exists(self.last_html_path):
            Message(SCRIPT_NAME, "Run the check first to create an HTML report.")
            return
        self._open_html_path(self.last_html_path)

    def _selection_changed(self, sender):
        pass


MasterConsistencyChecker()
