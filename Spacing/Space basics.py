# MenuTitle: Space basics
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

"""Review and apply derivative metrics keys and kerning groups in Glyphs 4.

The planning functions are deliberately independent of GlyphsApp and vanilla so
that the decision rules can be checked without modifying an open font.
"""

import json
import traceback


PREFS_KEY = "com.displaay.derivativeMetricsAndKerningGroups.options.v1"
METRIC_FIELDS = ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey")
GROUP_FIELDS = ("leftKerningGroup", "rightKerningGroup")
FIELD_SIDE = {
    "leftMetricsKey": "Left", "rightMetricsKey": "Right",
    "widthMetricsKey": "Width", "leftKerningGroup": "Left",
    "rightKerningGroup": "Right",
}
CONFIDENCE_ORDER = {"Low": 0, "Medium": 1, "High": 2}
SEPARATE_SUFFIXES = {"tf", "tosf", "tnum", "lf", "osf", "pnum", "sups", "subs", "numr", "dnom"}
# The dotted forms are commonly built from these independent base glyphs.
# Never derive their spacing or groups backwards from the dotted composite.
DOTLESS_BASES = {
    "idotless": "i", "jdotless": "j", "dotlessi": "i", "dotlessj": "j",
    "Idotless": "I", "Jdotless": "J",
}
# Small candidate sets, not universal type-design rules. Contours must agree.
SIDE_FAMILIES = {
    "left": {"O": ("C", "G", "Q"), "n": ("h", "m", "u"),
             "o": ("c", "d", "e", "q")},
    "right": {"n": ("h", "m"), "o": ("b", "c", "e", "p")},
}
# Examples from Glyphs' spacing guide. These are candidates for metrics keys,
# not automatic kerning-group rules; the user's outlines decide the confidence.
SIDE_METRIC_FAMILIES = {
    "left": {
        "H": ("B", "D", "E", "F", "I", "K", "L", "M", "N", "P", "R"),
        "O": ("C", "G", "Q"),
        "n": ("b", "h", "i", "k", "l", "m", "p", "r"),
        "o": ("c", "d", "e", "g", "q"),
    },
    "right": {
        "H": ("I", "M", "N"), "O": ("D", "Q"),
        "n": ("a", "h", "m"), "o": ("b", "p"),
    },
}
DEFAULT_OPTIONS = {
    "scope": "All glyphs", "existing": "Fill empty only", "confidence": "High",
    "contour_tolerance": "Normal (2% em)",
    "metric_left": True, "metric_right": True, "metric_width": False,
    "group_left": True, "group_right": True,
    "actual_components": True, "glyph_database": True, "suffix_variants": True,
    "metrics_hints": False, "reference_metrics": True, "font_specific_checks": False,
    "seed_bases": True, "contour_check": True,
    "shape_families": True,
    "cross_script": False, "include_figures": False, "include_marks": False,
    "include_empty": False, "include_nonexporting": False,
    "include_alternates": False, "auto_groups": True,
    "sync_metrics": False, "sync_special_layers": False,
}
OPTION_HELP = {
    "scope": "Choose all glyphs or only the selected glyphs. With Font specific checks on, eligible metrics are scanned across the whole font.",
    "existing": "Fill empty only keeps existing keys and groups. Allow overwrite lets checked preview rows replace them.",
    "confidence": "Minimum confidence for rows checked automatically. Every proposal remains visible for review.",
    "contour_tolerance": "Maximum side-outline difference allowed for a shape match, measured as a percentage of the em.",
    "metric_left": "Suggest left sidebearing metrics keys for eligible glyphs.",
    "metric_right": "Suggest right sidebearing metrics keys for eligible glyphs.",
    "metric_width": "Suggest width metrics keys when the same safe source supplies both sides.",
    "group_left": "Suggest left kerning groups; this does not create kerning pairs.",
    "group_right": "Suggest right kerning groups; this does not create kerning pairs.",
    "actual_components": "Find derivative sources from matching components in every master.",
    "glyph_database": "Use Glyphs' glyph database recipes as possible derivative sources.",
    "suffix_variants": "Look for matching suffixed sources and, when appropriate, an unsuffixed base.",
    "metrics_hints": "Consider existing metrics-key references as low-confidence source hints.",
    "reference_metrics": "Suggest the usual H/O and n/o sidebearing links where their sides fit.",
    "font_specific_checks": "Audit eligible Latin letter outlines in every master; add better links or flag mismatched keys for review.",
    "seed_bases": "Give independent base letters their own left and right kerning groups.",
    "contour_check": "Compare side outlines across masters before sharing spacing or kerning-group references.",
    "shape_families": "Suggest shared Latin kerning groups for matching sides, such as G with O on the left.",
    "cross_script": "Allow derivative sources in another script when their construction is otherwise compatible.",
    "include_figures": "Include figures and figure-style suffixes in ordinary proposals.",
    "include_marks": "Include mark glyphs in ordinary proposals.",
    "include_empty": "Include empty placeholders, whose shape cannot yet be checked.",
    "include_nonexporting": "Include glyphs marked as non-exporting.",
    "include_alternates": "Include suffixed alternates such as a.ss01 in proposals and font-specific checks.",
    "auto_groups": "Allow auto-aligned composites to inherit safe kerning groups.",
    "sync_metrics": "Update the affected master-layer sidebearings and widths after applying keys.",
    "sync_special_layers": "Also update special layers when Sync master-layer metrics is enabled.",
}


def normalized_options(options):
    result = DEFAULT_OPTIONS.copy()
    if isinstance(options, dict):
        for key, default in DEFAULT_OPTIONS.items():
            value = options.get(key, default)
            if isinstance(default, bool):
                result[key] = bool(value)
            elif isinstance(value, str):
                result[key] = value
    if result["scope"] not in ("All glyphs", "Selected glyphs"):
        result["scope"] = DEFAULT_OPTIONS["scope"]
    if result["existing"] not in ("Fill empty only", "Allow overwrite"):
        result["existing"] = DEFAULT_OPTIONS["existing"]
    if result["confidence"] not in CONFIDENCE_ORDER:
        result["confidence"] = DEFAULT_OPTIONS["confidence"]
    if result["contour_tolerance"] not in ("Strict (1% em)", "Normal (2% em)", "Loose (3% em)"):
        result["contour_tolerance"] = DEFAULT_OPTIONS["contour_tolerance"]
    return result


def exact_glyph_map(font):
    return {str(glyph.name): glyph for glyph in font.glyphs if getattr(glyph, "name", None)}


def snapshot_items(value):
    """Read a Glyphs collection without invoking a possibly broken truth test."""
    if value is None:
        return []
    try:
        return list(value)
    except (TypeError, ValueError):
        return []


def selected_names(font):
    return {layer.parent.name for layer in snapshot_items(getattr(font, "selectedLayers", None))
            if getattr(layer, "parent", None) is not None}


def master_layers(font, glyph):
    layers = []
    for master in font.masters:
        try:
            layer = glyph.layers[master.id]
        except (KeyError, IndexError, TypeError):
            layer = None
        if layer is None:
            return []
        layers.append(layer)
    return layers


def is_empty(layers):
    return not layers or all(not snapshot_items(getattr(layer, "paths", None)) and
                             not snapshot_items(getattr(layer, "components", None)) for layer in layers)


def is_auto_aligned(layers):
    for layer in layers:
        for attribute in ("hasAlignedSideBearings", "hasAlignedWidth", "isAligned"):
            try:
                state = getattr(layer, attribute, None)
                if state is not None and bool(state() if callable(state) else state):
                    return True
            except Exception:
                pass
        if snapshot_items(getattr(layer, "paths", None)):
            continue
        for component in snapshot_items(getattr(layer, "components", None)):
            try:
                if bool(component.automaticAlignment):
                    return True
            except Exception:
                pass
    return False


def suffix_of(name):
    return name.split(".", 1)[1] if "." in name else ""


def category_of(glyph):
    return str(getattr(glyph, "category", "") or "")


def script_of(glyph):
    return str(getattr(glyph, "script", "") or "")


def excluded(glyph, options):
    name = str(glyph.name)
    category = category_of(glyph)
    suffix = suffix_of(name)
    if not options["include_nonexporting"] and getattr(glyph, "export", True) is False:
        return "non-exporting glyph"
    if (category == "Mark" or name.endswith("comb") or ".comb" in name) and not options["include_marks"]:
        return "mark"
    if (category == "Number" or suffix.split(".")[0] in SEPARATE_SUFFIXES) and not options["include_figures"]:
        return "figure"
    if suffix and suffix.split(".")[0] not in SEPARATE_SUFFIXES and not options["include_alternates"]:
        return "suffixed alternate"
    return ""


def compatible_source(target, source, options):
    if source is None or target.name == source.name:
        return False
    if not options["cross_script"]:
        a, b = script_of(target), script_of(source)
        if a and b and a != b:
            return False
    target_suffix = suffix_of(target.name)
    source_suffix = suffix_of(source.name)
    if target_suffix != source_suffix and not options["suffix_variants"]:
        return False
    if target_suffix != source_suffix and target_suffix.split(".")[0] in SEPARATE_SUFFIXES:
        return False
    if category_of(source) == "Mark":
        return False
    return True


def resolve_style_source(target, source_name, glyphs, options):
    if not source_name:
        return None
    suffix = suffix_of(target.name)
    names = []
    if suffix and options["suffix_variants"]:
        names.append(source_name + "." + suffix)
    names.append(source_name)
    for name in names:
        source = glyphs.get(name)
        if compatible_source(target, source, options):
            return source
    return None


def component_name(component):
    name = getattr(component, "componentName", None)
    if name:
        return str(name)
    component_glyph = getattr(component, "component", None)
    return str(getattr(component_glyph, "name", "") or "")


def component_dependencies(glyph):
    """Include every layer: a special layer may expose a reverse dependency."""
    names = set()
    for layer in snapshot_items(getattr(glyph, "layers", None)):
        for component in snapshot_items(getattr(layer, "components", None)):
            name = component_name(component)
            if name:
                names.add(name)
    return names


def source_depends_on_target(source, target_name, glyphs):
    pending = [source.name]
    seen = set()
    while pending:
        name = pending.pop()
        if name == target_name:
            return True
        if name in seen or name not in glyphs:
            continue
        seen.add(name)
        pending.extend(component_dependencies(glyphs[name]))
    return False


def source_relationship_issue(target, source, glyphs):
    if source is None:
        return ""
    target_base = target.name.split(".", 1)[0]
    source_base = source.name.split(".", 1)[0]
    if DOTLESS_BASES.get(target_base) == source_base:
        return "dotless glyph must be the independent base"
    if source_depends_on_target(source, target.name, glyphs):
        return "source uses this glyph as a component"
    return ""


def component_preserves_side_shape(component):
    # Glyphs 4 may return a dict-like proxy even for a regular component. Its
    # __len__ calls len(values()), while values() is None in that case, so a
    # plain truth test raises TypeError inside the app.
    smart_values = getattr(component, "smartComponentValues", None)
    if smart_values is not None:
        try:
            entries = smart_values.values() if hasattr(smart_values, "values") else smart_values
            if entries is not None and len(entries) > 0:
                return False
        except (AttributeError, TypeError):
            return False  # Unknown smart-component state: avoid a high-confidence rule.
    matrix = getattr(component, "transform", None)
    if matrix is None:
        return True
    try:
        values = [matrix.m11, matrix.m12, matrix.m21, matrix.m22]
    except AttributeError:
        try:
            values = list(matrix)[:4]
        except TypeError:
            return False
    return len(values) == 4 and all(abs(float(a) - b) < 1e-6 for a, b in
                                    zip(values, (1.0, 0.0, 0.0, 1.0)))


def actual_base_names(font, glyph, glyphs):
    layers = master_layers(font, glyph)
    if not layers:
        return []
    signatures = []
    for layer in layers:
        if snapshot_items(getattr(layer, "paths", None)):
            return []  # Mixed construction does not prove the outer side shapes.
        bases = []
        for component in snapshot_items(getattr(layer, "components", None)):
            name = component_name(component)
            if name not in glyphs or category_of(glyphs[name]) == "Mark" or name.endswith("comb"):
                continue
            if not component_preserves_side_shape(component):
                return []
            source_master_id = getattr(component, "componentMasterId", None)
            current_master_id = getattr(layer, "associatedMasterId", None)
            if source_master_id and current_master_id and source_master_id != current_master_id:
                return []
            bases.append(name)
        if not bases:
            return []
        signatures.append(tuple(bases))
    return list(signatures[0]) if len(set(signatures)) == 1 else []


def database_base_names(glyph, glyph_info):
    info = glyph_info(glyph.name) if glyph_info else getattr(glyph, "glyphInfo", None)
    if info is None:
        return []
    result = []
    for item in snapshot_items(getattr(info, "components", None)):
        name = str(getattr(item, "name", "") or "")
        category = str(getattr(item, "category", "") or "")
        if name and category != "Mark" and not name.endswith("comb"):
            result.append(name)
    return result


def metric_reference(key, names):
    text = str(key or "").lstrip("=")
    if text.startswith("|"):
        text = text[1:]
    for name in sorted(names, key=len, reverse=True):
        if text == name or (text.startswith(name) and text[len(name):len(name) + 1] in ("+", "-", "*", "/", "@")):
            return name
    return None


def creates_cycle(target_name, source_name, field, glyphs, planned):
    pending = [(source_name, field)]
    visited = set()
    names = set(glyphs)
    while pending:
        name, current_field = pending.pop()
        if (name, current_field) == (target_name, field):
            return True
        if (name, current_field) in visited or name not in glyphs:
            continue
        visited.add((name, current_field))
        glyph = glyphs[name]
        key = planned.get((name, current_field), getattr(glyph, current_field, None))
        for key in [key] + [getattr(layer, current_field, None) for layer in
                            snapshot_items(getattr(glyph, "layers", None))]:
            ref = metric_reference(key, names)
            if ref:
                opposite = str(key or "").lstrip("=").startswith("|")
                next_field = current_field
                if opposite and current_field == "leftMetricsKey":
                    next_field = "rightMetricsKey"
                elif opposite and current_field == "rightMetricsKey":
                    next_field = "leftMetricsKey"
                pending.append((ref, next_field))
        # Auto-aligned composites inherit metrics from their base components,
        # even when no explicit metrics key exposes that dependency.
        if is_auto_aligned(snapshot_items(getattr(glyph, "layers", None))):
            for component_name_value in component_dependencies(glyph):
                component = glyphs.get(component_name_value)
                if component is not None and category_of(component) != "Mark":
                    pending.append((component_name_value, current_field))
    return False


def contour_agreement(font, target, source, side, tolerance=0.02):
    """Return supporting evidence only; failure or missing APIs never implies similarity."""
    try:
        from Foundation import NSMakePoint
    except ImportError:
        return None
    upm = float(getattr(font, "upm", 1000) or 1000)
    scores = []
    for t_layer, s_layer in zip(master_layers(font, target), master_layers(font, source)):
        if (not snapshot_items(getattr(t_layer, "paths", None)) or
                not snapshot_items(getattr(s_layer, "paths", None))):
            return None
        try:
            t_bounds, s_bounds = t_layer.bounds, s_layer.bounds
            low = max(t_bounds.origin.y, s_bounds.origin.y)
            high = min(t_bounds.origin.y + t_bounds.size.height,
                       s_bounds.origin.y + s_bounds.size.height)
            if high - low < upm * 0.1:
                return None
            samples = []
            for layer in (t_layer, s_layer):
                profile = []
                for fraction in (0.15, 0.30, 0.45, 0.60, 0.75):
                    y = low + (high - low) * fraction
                    points = snapshot_items(layer.intersectionsBetweenPoints(
                        NSMakePoint(-10000, y), NSMakePoint(10000, y), True))
                    ink = [point.x for point in points[1:-1]] if len(points) > 2 else []
                    profile.append((min(ink) if side == "left" else max(ink)) if ink else None)
                samples.append(profile)
            pairs = [(a, b) for a, b in zip(*samples) if a is not None and b is not None]
            if len(pairs) < 3:
                return None
            a_edge = min(p[0] for p in pairs) if side == "left" else max(p[0] for p in pairs)
            b_edge = min(p[1] for p in pairs) if side == "left" else max(p[1] for p in pairs)
            scores.append(max(abs((a - a_edge) - (b - b_edge)) for a, b in pairs))
        except Exception:
            return None  # An unavailable Glyphs geometry API is missing evidence.
    return max(scores) <= upm * tolerance if scores else None


def contour_tolerance(options):
    return {"Strict (1% em)": 0.01, "Normal (2% em)": 0.02,
            "Loose (3% em)": 0.03}[options["contour_tolerance"]]


def side_contour_distance(font, target, source, side):
    """Max normalized outer-edge difference in em; None means no reliable evidence."""
    try:
        from Foundation import NSMakePoint
    except ImportError:
        return None
    target_layers = master_layers(font, target)
    source_layers = master_layers(font, source)
    if not target_layers or len(target_layers) != len(source_layers):
        return None
    upm = float(getattr(font, "upm", 1000) or 1000)
    distances = []
    for target_layer, source_layer in zip(target_layers, source_layers):
        if (not snapshot_items(getattr(target_layer, "paths", None)) or
                not snapshot_items(getattr(source_layer, "paths", None))):
            return None
        try:
            a_bounds, b_bounds = target_layer.bounds, source_layer.bounds
            low = max(a_bounds.origin.y, b_bounds.origin.y)
            high = min(a_bounds.origin.y + a_bounds.size.height,
                       b_bounds.origin.y + b_bounds.size.height)
            if high - low < upm * 0.1:
                return None
            profiles = []
            def outer_at(layer, y):
                points = snapshot_items(layer.intersectionsBetweenPoints(
                    NSMakePoint(-10000, y), NSMakePoint(10000, y), True))
                ink = [point.x for point in points[1:-1]] if len(points) > 2 else []
                return ((min(ink) if side == "left" else max(ink)) if ink else None)

            for layer in (target_layer, source_layer):
                profiles.append([outer_at(layer, low + (high - low) * fraction)
                                 for fraction in (0.08, 0.15, 0.22, 0.29, 0.36, 0.43,
                                                  0.50, 0.57, 0.64, 0.71, 0.78,
                                                  0.85, 0.92)])
            pairs = [(a, b) for a, b in zip(*profiles) if a is not None and b is not None]
            if len(pairs) < 9:
                return None
            a_edge = min(a for a, _ in pairs) if side == "left" else max(a for a, _ in pairs)
            b_edge = min(b for _, b in pairs) if side == "left" else max(b for _, b in pairs)
            difference = max(abs((a - a_edge) - (b - b_edge)) for a, b in pairs)
            # An ascender, descender, or terminal can reach outward beyond the
            # shared height. Inward extensions do not affect this side's edge.
            for layer, bounds, edge in ((target_layer, a_bounds, a_edge),
                                        (source_layer, b_bounds, b_edge)):
                bottom = bounds.origin.y
                top = bottom + bounds.size.height
                for start, end in ((bottom, low), (high, top)):
                    if end - start < upm * 0.02:
                        continue
                    for fraction in (0.1, 0.3, 0.5, 0.7, 0.9):
                        outer = outer_at(layer, start + (end - start) * fraction)
                        if outer is not None:
                            difference = max(difference, max(0, edge - outer)
                                             if side == "left" else max(0, outer - edge))
            distances.append(difference / upm)
        except Exception:
            return None
    return max(distances) if distances else None


def conventional_metric_source(name, side):
    for anchor, members in SIDE_METRIC_FAMILIES[side].items():
        if name in members:
            return anchor
    return None


def smart_anchor_names(name, side):
    anchors = ("H", "O") if name[:1].isupper() else ("n", "o")
    # These are the spacing references, never targets of this optional pass.
    return [] if name in anchors else list(anchors)


def family_reference(font, glyph, side, glyphs, options):
    if not options["shape_families"] or not options["contour_check"]:
        return None
    if script_of(glyph) not in ("", "latin") or suffix_of(glyph.name):
        return None
    for anchor, members in SIDE_FAMILIES[side].items():
        if glyph.name not in members or anchor not in glyphs:
            continue
        reference = glyphs[anchor]
        if compatible_source(glyph, reference, options) and contour_agreement(
                font, glyph, reference, side, contour_tolerance(options)) is True:
            return reference
    return None


def metric_family_reference(glyph, side, glyphs, options):
    if (not options["reference_metrics"] or script_of(glyph) not in ("", "latin") or
            suffix_of(glyph.name) or category_of(glyph) != "Letter"):
        return None
    for anchor, members in SIDE_METRIC_FAMILIES[side].items():
        if glyph.name in members:
            source = glyphs.get(anchor)
            if source is not None and compatible_source(glyph, source, options):
                return source
    return None


def make_proposal(glyph, field, value, source, confidence, reason, options, warning=""):
    before = getattr(glyph, field, None) or None
    if before == value:
        return None
    conflict = before is not None and options["existing"] == "Fill empty only"
    meets_threshold = CONFIDENCE_ORDER[confidence] >= CONFIDENCE_ORDER[options["confidence"]]
    if conflict:
        warning = (warning + "; " if warning else "") + "existing value is preserved"
    if not meets_threshold:
        warning = (warning + "; " if warning else "") + "below confidence threshold"
    return {
        "id": (glyph.name, field), "glyph": glyph.name, "field": field,
        "kind": "Metrics" if field in METRIC_FIELDS else "Kerning group",
        "side": FIELD_SIDE[field], "before": before, "after": value,
        "source": source, "confidence": confidence, "reason": reason,
        "warning": warning, "include": not conflict and meets_threshold and not warning,
    }


def simple_metric_reference(key, names):
    value = str(key or "")
    if value.startswith("=="):
        return None  # A local key is an intentional master-specific exception.
    if value.startswith("="):
        value = value[1:]
    return value if value in names else None


def apply_font_specific_checks(font, glyphs, sources, proposals, diagnostics, options):
    """Revise metrics suggestions using side outlines from every master."""
    if not options["font_specific_checks"]:
        return proposals
    by_id = {item["id"]: item for item in proposals}
    tolerance = contour_tolerance(options)
    processed = set()

    def proposed_metric_keys():
        return {(item["glyph"], item["field"]): item["after"]
                for item in by_id.values() if item["include"] and
                item["field"] in METRIC_FIELDS and item["after"] is not None}

    for name in sorted(glyphs):
        glyph = glyphs[name]
        if (excluded(glyph, options) or category_of(glyph) != "Letter" or
                script_of(glyph) not in ("", "latin")):
            continue
        layers = master_layers(font, glyph)
        if not layers or is_empty(layers) or is_auto_aligned(layers):
            continue
        for side in ("left", "right"):
            if not options["metric_" + side]:
                continue
            anchors = smart_anchor_names(name, side)
            if not anchors:
                continue
            field = side + "MetricsKey"
            item_id = (name, field)
            raw_key = getattr(glyph, field, None)
            current = simple_metric_reference(raw_key, glyphs)
            old_proposal = by_id.get(item_id)
            if raw_key and current is None:
                by_id.pop(item_id, None)
                processed.add(item_id)
                diagnostics.append((name, "%s custom or local metrics key needs manual review" % side))
                continue
            derivative_source = (sources[name][0 if side == "left" else 1]
                                 if name in sources else None)
            if derivative_source is not None:
                source_distance = side_contour_distance(font, glyph, derivative_source, side)
                if source_distance is None or source_distance <= tolerance:
                    continue
            distances = {}
            for anchor in anchors:
                source = glyphs.get(anchor)
                if (source is None or not compatible_source(glyph, source, options) or
                        not master_layers(font, source) or
                        is_auto_aligned(master_layers(font, source)) or
                        source_relationship_issue(glyph, source, glyphs)):
                    continue
                distance = side_contour_distance(font, glyph, source, side)
                if distance is not None:
                    distances[anchor] = distance
            if not distances:
                continue  # No outline evidence: keep the ordinary preview.
            processed.add(item_id)
            normal = conventional_metric_source(name.split(".", 1)[0], side)
            if ((normal is not None and normal in glyphs and normal not in distances) or
                    (current in anchors and current not in distances)):
                continue  # A missing outline is not evidence against an existing link.
            fitting = [(distance, anchor) for anchor, distance in distances.items()
                       if distance <= tolerance]
            fitting.sort()
            best = fitting[0][1] if fitting else None
            if normal in distances and distances[normal] <= tolerance:
                # Keep the conventional link unless another contour is clearly closer.
                if best is None or distances[normal] <= distances[best] + tolerance * 0.25:
                    best = normal
            if best is None:
                if old_proposal and (old_proposal["source"] in anchors or
                                     old_proposal["source"] == getattr(derivative_source, "name", None)):
                    by_id.pop(item_id)
                if (current in anchors or
                        (derivative_source is not None and current == derivative_source.name)):
                    proposal = make_proposal(
                        glyph, field, None, None, "High",
                        "Font specific checks: side differs from spacing references",
                        options, "review and space this side independently")
                    if proposal:
                        by_id[item_id] = proposal
                if normal in distances or current in anchors:
                    diagnostics.append((name, "%s side differs from available H/O/n/o references" % side))
                continue
            if current == best:
                by_id.pop(item_id, None)
                continue
            if old_proposal and (old_proposal["source"] in anchors or
                                 old_proposal["source"] == getattr(derivative_source, "name", None)):
                by_id.pop(item_id)
            if creates_cycle(name, best, field, glyphs, proposed_metric_keys()):
                diagnostics.append((name, "%s smart link to %s would create a cycle" % (side, best)))
                continue
            confidence = "High" if distances[best] <= tolerance * 0.5 else "Medium"
            proposal = make_proposal(
                glyph, field, "=" + best, best, confidence,
                "Font specific checks: matching %s contour in every master" % best,
                options)
            if proposal:
                by_id[item_id] = proposal
                if best != normal:
                    diagnostics.append((name, "%s side matches %s better than %s" %
                                        (side, best, normal or "the usual references")))

    # A derivative with altered outlines may no longer share its construction
    # source's side shape. Only examine sides with actual path evidence.
    for name, source_data in sources.items():
        glyph = glyphs[name]
        if excluded(glyph, options):
            continue
        for index, side in enumerate(("left", "right")):
            if not options["metric_" + side]:
                continue
            field = side + "MetricsKey"
            item_id = (name, field)
            if item_id in processed:
                continue
            source = source_data[index]
            if source is None:
                continue
            distance = side_contour_distance(font, glyph, source, side)
            if distance is None or distance <= tolerance:
                continue
            by_id.pop(item_id, None)
            diagnostics.append((name, "%s side differs from derivative source %s" %
                                (side, source.name)))
            if simple_metric_reference(getattr(glyph, field, None), glyphs) == source.name:
                proposal = make_proposal(
                    glyph, field, None, None, "High",
                    "Font specific checks: side differs from derivative source",
                    options, "review and space this side independently")
                if proposal:
                    by_id[item_id] = proposal
    return list(by_id.values())


def build_proposals(font, raw_options, glyph_info=None):
    options = normalized_options(raw_options)
    glyphs = exact_glyph_map(font)
    selected = selected_names(font) if options["scope"] == "Selected glyphs" else None
    scoped = set(glyphs) if options["font_specific_checks"] or selected is None else selected
    proposals = []
    diagnostics = []
    planned_metrics = {}
    sources = {}
    for name in sorted(scoped):
        glyph = glyphs.get(name)
        if glyph is None:
            continue
        exclusion = excluded(glyph, options)
        if exclusion:
            diagnostics.append((name, "Skipped: " + exclusion))
            continue
        layers = master_layers(font, glyph)
        if not layers:
            diagnostics.append((name, "Skipped: missing master layer"))
            continue
        if is_empty(layers) and not options["include_empty"]:
            diagnostics.append((name, "Skipped: empty placeholder"))
            continue
        candidates = []
        if options["actual_components"]:
            components = actual_base_names(font, glyph, glyphs)
            if components:
                candidates.append((components, "High", "matching components in every master"))
        if options["glyph_database"]:
            components = database_base_names(glyph, glyph_info)
            if components:
                candidates.append((components, "Medium", "Glyphs glyph database recipe"))
        if options["suffix_variants"] and "." in name:
            base_name = name.split(".", 1)[0]
            if base_name in glyphs:
                candidates.append(([base_name], "Low", "matching unsuffixed name"))
        if options["metrics_hints"]:
            left_name = metric_reference(getattr(glyph, "leftMetricsKey", None), glyphs)
            right_name = metric_reference(getattr(glyph, "rightMetricsKey", None), glyphs)
            if left_name or right_name:
                candidates.append(((left_name, right_name), "Low", "existing metrics-key reference"))
        reported = set()
        for names, confidence, reason in candidates:
            left = resolve_style_source(glyph, names[0], glyphs, options)
            right = resolve_style_source(glyph, names[-1], glyphs, options)
            for side, source in (("left", left), ("right", right)):
                issue = source_relationship_issue(glyph, source, glyphs)
                if issue:
                    message = "%s source %s rejected: %s" % (side, source.name, issue)
                    if message not in reported:
                        diagnostics.append((name, message))
                        reported.add(message)
                    if side == "left":
                        left = None
                    else:
                        right = None
            if left or right:
                sources[name] = (left, right, confidence, reason)
                break

    # Built-in spacing examples provide base-letter metrics relationships as well
    # as composite/recipe relationships. A contour match raises confidence; a
    # disagreement stays visible but is never selected automatically.
    for name in sorted(scoped):
        glyph = glyphs.get(name)
        if glyph is None or excluded(glyph, options):
            continue
        layers = master_layers(font, glyph)
        if not layers or (is_empty(layers) and not options["include_empty"]):
            continue
        if is_auto_aligned(layers):
            continue
        for side in ("left", "right"):
            if not options["metric_" + side]:
                continue
            if name in sources and sources[name][0 if side == "left" else 1] is not None:
                continue
            reference = metric_family_reference(glyph, side, glyphs, options)
            if reference is None or not master_layers(font, reference):
                continue
            if is_auto_aligned(master_layers(font, reference)):
                diagnostics.append((name, "%s reference %s is auto-aligned" % (side, reference.name)))
                continue
            if is_empty(master_layers(font, reference)) and not options["include_empty"]:
                diagnostics.append((name, "%s reference %s is empty" % (side, reference.name)))
                continue
            agreement = (contour_agreement(font, glyph, reference, side,
                                          contour_tolerance(options))
                         if options["contour_check"] else None)
            confidence = "High" if agreement is True else "Medium"
            warning = "side contour differs in at least one master" if agreement is False else ""
            if warning:
                diagnostics.append((name, "%s contour differs from %s; review metrics key" %
                                    (side, reference.name)))
            if creates_cycle(name, reference.name, side + "MetricsKey", glyphs, planned_metrics):
                diagnostics.append((name, "%s metrics key would create a cycle" % side))
                continue
            proposal = make_proposal(
                glyph, side + "MetricsKey", "=" + reference.name, reference.name,
                confidence, "Glyphs spacing guide; %s side" % side, options, warning)
            if proposal:
                proposals.append(proposal)
                if proposal["include"]:
                    planned_metrics[(name, side + "MetricsKey")] = proposal["after"]

    # A new font needs named base groups before derivatives can inherit them.
    base_groups = {}
    if options["seed_bases"]:
        for name in sorted(selected if selected is not None else scoped):
            glyph = glyphs.get(name)
            if glyph is None or excluded(glyph, options):
                continue
            layers = master_layers(font, glyph)
            eligible_category = category_of(glyph) == "Letter" or (
                category_of(glyph) == "Number" and options["include_figures"])
            if (not layers or (is_empty(layers) and not options["include_empty"]) or
                    not eligible_category):
                continue
            for field, enabled in (("leftKerningGroup", "group_left"),
                                   ("rightKerningGroup", "group_right")):
                if name in sources and sources[name][0 if field == "leftKerningGroup" else 1] is not None:
                    continue
                if options[enabled]:
                    side = "left" if field == "leftKerningGroup" else "right"
                    family = family_reference(font, glyph, side, glyphs, options)
                    use_family = family is not None and options["confidence"] != "High"
                    value = ((getattr(family, field, None) or family.name) if use_family else name)
                    reason = ("matching %s contour in every master" % family.name if use_family
                              else "base letter seeds its own group")
                    proposal = make_proposal(glyph, field, value,
                                             family.name if use_family else name,
                                             "Medium" if use_family else "High", reason, options)
                    if proposal:
                        proposals.append(proposal)
                        if proposal["include"]:
                            base_groups[(name, field)] = value

    def inherited_group(source, group_field, seen=None):
        seen = seen or set()
        if source is None or source.name in seen:
            return None
        seen.add(source.name)
        value = getattr(source, group_field, None) or base_groups.get((source.name, group_field))
        if value:
            return value
        if source.name in sources:
            ancestor = sources[source.name][0 if group_field == "leftKerningGroup" else 1]
            return inherited_group(ancestor, group_field, seen)
        return None

    for name in sorted(sources):
        glyph = glyphs[name]
        left, right, confidence, reason = sources[name]
        layers = master_layers(font, glyph)
        auto = is_auto_aligned(layers)
        for side, source in (("left", left), ("right", right)):
            if source is None:
                diagnostics.append((name, "No compatible %s-side source" % side))
                continue
            if not master_layers(font, source):
                diagnostics.append((name, "%s source %s lacks a master layer" % (side, source.name)))
                continue
            if is_empty(master_layers(font, source)) and not options["include_empty"]:
                diagnostics.append((name, "%s source %s is empty" % (side, source.name)))
                continue
            if options["contour_check"] and confidence != "High":
                agreement = contour_agreement(font, glyph, source, side,
                                              contour_tolerance(options))
                if agreement is False:
                    diagnostics.append((name, "%s contour differs from %s; review proposals" % (side, source.name)))
                    side_warning = "contour differs in at least one master"
                else:
                    side_warning = ""
            else:
                side_warning = ""
            metric_field = side + "MetricsKey"
            group_field = side + "KerningGroup"
            if options["metric_" + side]:
                if auto:
                    diagnostics.append((name, "Auto-aligned: %s metrics key skipped" % side))
                elif is_auto_aligned(master_layers(font, source)):
                    diagnostics.append((name, "%s metrics source %s is auto-aligned" % (side, source.name)))
                elif creates_cycle(name, source.name, metric_field, glyphs, planned_metrics):
                    diagnostics.append((name, "%s metrics key would create a cycle" % side))
                else:
                    proposal = make_proposal(glyph, metric_field, "=" + source.name,
                                             source.name, confidence, reason, options, side_warning)
                    if proposal:
                        proposals.append(proposal)
                        if proposal["include"]:
                            planned_metrics[(name, metric_field)] = proposal["after"]
            if (options["group_" + side] and
                    (selected is None or name in selected) and
                    (not auto or options["auto_groups"])):
                value = inherited_group(source, group_field)
                if value:
                    proposal = make_proposal(glyph, group_field, value, source.name,
                                             confidence, reason, options, side_warning)
                    if proposal:
                        proposals.append(proposal)
                else:
                    diagnostics.append((name, "%s source %s has no group" % (side, source.name)))
        if options["metric_width"] and left is not None and left is right:
            if auto:
                diagnostics.append((name, "Auto-aligned: width metrics key skipped"))
            elif is_auto_aligned(master_layers(font, left)):
                diagnostics.append((name, "Width metrics source %s is auto-aligned" % left.name))
            elif creates_cycle(name, left.name, "widthMetricsKey", glyphs, planned_metrics):
                diagnostics.append((name, "Width metrics key would create a cycle"))
            elif master_layers(font, left) and (options["include_empty"] or
                                                 not is_empty(master_layers(font, left))):
                proposal = make_proposal(glyph, "widthMetricsKey", "=" + left.name,
                                         left.name, confidence, reason + "; single base", options)
                if proposal:
                    proposals.append(proposal)
                    if proposal["include"]:
                        planned_metrics[(name, "widthMetricsKey")] = proposal["after"]
    proposals = apply_font_specific_checks(font, glyphs, sources, proposals, diagnostics, options)
    if options["font_specific_checks"] and selected is not None:
        # The smart metrics audit is font-wide; ordinary group/width work still
        # obeys the user's selection in the Scope menu.
        proposals = [item for item in proposals if item["glyph"] in selected or
                     item["field"] in ("leftMetricsKey", "rightMetricsKey")]
    return proposals, diagnostics


def apply_proposals(font, proposals, options):
    """Apply checked, unchanged proposals; return a report and roll back on error."""
    glyphs = exact_glyph_map(font)
    chosen = [item for item in proposals if item["include"]]
    if not chosen:
        return ["No proposals selected."]
    if len({item["id"] for item in chosen}) != len(chosen):
        raise ValueError("Duplicate proposals; refresh the preview.")
    for item in chosen:
        glyph = glyphs.get(item["glyph"])
        if glyph is None or (getattr(glyph, item["field"], None) or None) != item["before"]:
            raise ValueError("Font changed since preview; refresh before applying.")
        if options["existing"] == "Fill empty only" and item["before"] is not None:
            raise ValueError("An existing value is selected. Choose Allow overwrite and preview again.")
        if item["field"] in METRIC_FIELDS:
            if item["after"] is None:
                if not options["font_specific_checks"]:
                    raise ValueError("A metrics-key removal requires Font specific checks.")
                continue
            if item["source"] not in glyphs:
                raise ValueError("A metrics source was removed; refresh the preview.")
            source = glyphs[item["source"]]
            if source_relationship_issue(glyph, source, glyphs):
                raise ValueError("A metrics source now depends on its target; refresh the preview.")
            if is_auto_aligned(master_layers(font, source)):
                raise ValueError("A metrics source is auto-aligned; refresh the preview.")
            if creates_cycle(item["glyph"], item["source"], item["field"], glyphs,
                             {(p["glyph"], p["field"]): p["after"] for p in chosen if p["field"] in METRIC_FIELDS}):
                raise ValueError("A metrics cycle was detected; refresh the preview.")
    snapshots = []
    touched = {}
    for item in chosen:
        glyph = glyphs[item["glyph"]]
        touched[glyph.name] = glyph
        snapshots.append((glyph, item["field"], getattr(glyph, item["field"], None)))
    layer_metrics = []
    if options["sync_metrics"]:
        for glyph in touched.values():
            for layer in glyph.layers:
                if getattr(layer, "isMasterLayer", False) or (options["sync_special_layers"] and getattr(layer, "isSpecialLayer", False)):
                    layer_metrics.append((layer, layer.LSB, layer.RSB, layer.width))
    font.disableUpdateInterface()
    begun = []
    try:
        for glyph in touched.values():
            glyph.beginUndo()
            begun.append(glyph)
        for item in chosen:
            setattr(glyphs[item["glyph"]], item["field"], item["after"])
        if options["sync_metrics"]:
            for layer, _, _, _ in layer_metrics:
                layer.syncMetrics()
        return ["Applied %d proposal(s) to %d glyph(s)." % (len(chosen), len(touched))]
    except Exception:
        for glyph, field, value in reversed(snapshots):
            setattr(glyph, field, value)
        for layer, lsb, rsb, width in layer_metrics:
            layer.width, layer.LSB, layer.RSB = width, lsb, rsb
        raise
    finally:
        try:
            for glyph in reversed(begun):
                try:
                    glyph.endUndo()
                except Exception:
                    print("Could not close undo group for %s" % glyph.name)
        finally:
            font.enableUpdateInterface()


def launch():
    import math
    import vanilla
    from AppKit import NSBezierPath, NSColor, NSImage
    from Foundation import NSMakePoint, NSMakeSize
    from GlyphsApp import Glyphs, Message

    font = Glyphs.font
    if font is None:
        Message("No Font", "Open a Glyphs font first.", OKButton="OK")
        return

    def rainbow_sparkle():
        icon = NSImage.alloc().initWithSize_(NSMakeSize(18, 18))
        icon.lockFocus()
        try:
            for index in range(8):
                angle = math.pi * index / 4.0
                path = NSBezierPath.bezierPath()
                path.moveToPoint_(NSMakePoint(9, 9))
                path.lineToPoint_(NSMakePoint(9 + 8 * math.cos(angle),
                                             9 + 8 * math.sin(angle)))
                path.lineToPoint_(NSMakePoint(9 + 3 * math.cos(angle + math.pi / 8),
                                             9 + 3 * math.sin(angle + math.pi / 8)))
                path.closePath()
                NSColor.colorWithCalibratedHue_saturation_brightness_alpha_(
                    index / 8.0, 0.78, 0.95, 1.0).set()
                path.fill()
        finally:
            icon.unlockFocus()
        return icon

    class DerivativeManager:
        def __init__(self, active_font):
            self.font = active_font
            self.proposals = []
            self.diagnostics = []
            self.preview_options = None
            try:
                saved = json.loads(Glyphs.defaults[PREFS_KEY] or "{}")
            except Exception:
                saved = {}
            options = normalized_options(saved)
            self.w = vanilla.Window((980, 540), "Space basics",
                                    minSize=(940, 500))
            self.controls = {}

            def popup(key, x, y, width, label, items):
                label_control = vanilla.TextBox((x, y, width, 18), label, sizeStyle="small")
                label_control.setToolTip(OPTION_HELP[key])
                self.w.__setattr__(key + "Label", label_control)
                control = vanilla.PopUpButton((x, y + 18, width, 22), items,
                                               callback=self.option_changed, sizeStyle="small")
                control.set(items.index(options[key]))
                control.setToolTip(OPTION_HELP[key])
                self.w.__setattr__(key + "Control", control)
                self.controls[key] = (control, items)

            def check(key, x, y, width, label, parent=None):
                parent = self.w if parent is None else parent
                control = vanilla.CheckBox((x, y, width, 20), label,
                                           value=options[key], callback=self.option_changed,
                                           sizeStyle="small")
                control.setToolTip(OPTION_HELP[key])
                parent.__setattr__(key + "Control", control)
                self.controls[key] = control

            popup("scope", 16, 10, 210, "Scope", ["All glyphs", "Selected glyphs"])
            popup("existing", 244, 10, 210, "Existing assignments", ["Fill empty only", "Allow overwrite"])
            popup("confidence", 472, 10, 185, "Apply threshold", ["High", "Medium", "Low"])
            popup("contour_tolerance", 675, 10, 235, "Contour match", [
                "Strict (1% em)", "Normal (2% em)", "Loose (3% em)"])

            self.w.settingsTabs = vanilla.Tabs(
                (16, 61, -16, 146), ["Spacing", "Kerning groups", "Eligibility & update"],
                sizeStyle="small")
            spacing = self.w.settingsTabs[0]
            kerning = self.w.settingsTabs[1]
            eligibility = self.w.settingsTabs[2]

            spacing.metricTitle = vanilla.TextBox((16, 4, 360, 18),
                                                  "Metric keys", sizeStyle="small")
            check("metric_left", 16, 25, 84, "Left", spacing)
            check("metric_right", 104, 25, 84, "Right", spacing)
            check("metric_width", 192, 25, 90, "Width", spacing)
            check("reference_metrics", 16, 51, 390,
                  "Suggest H/O and n/o spacing links", spacing)
            check("font_specific_checks", 16, 78, 410,
                  "Font specific checks", spacing)
            spacing.smartIcon = vanilla.ImageView((180, 78, 18, 18), scale="none")
            spacing.smartIcon.setImage(imageObject=rainbow_sparkle())
            spacing.smartIcon.setToolTip(OPTION_HELP["font_specific_checks"])

            spacing.sourceTitle = vanilla.TextBox((454, 4, 400, 18),
                                                  "Derivative sources", sizeStyle="small")
            check("actual_components", 454, 25, 410,
                  "Matching components in every master", spacing)
            check("glyph_database", 454, 49, 410,
                  "Glyphs database recipes", spacing)
            check("suffix_variants", 454, 73, 410,
                  "Matching suffixed sources", spacing)
            check("metrics_hints", 454, 97, 410,
                  "Existing metrics-key hints", spacing)

            kerning.groupTitle = vanilla.TextBox((16, 4, 360, 18),
                                                  "Kerning groups", sizeStyle="small")
            check("group_left", 16, 25, 84, "Left", kerning)
            check("group_right", 104, 25, 84, "Right", kerning)
            check("seed_bases", 16, 51, 410,
                  "Seed base letters with own group", kerning)
            check("shape_families", 16, 75, 410,
                  "Suggest shared Latin side groups", kerning)
            check("contour_check", 16, 99, 410,
                  "Check side contours across masters", kerning)
            kerning.exceptionTitle = vanilla.TextBox((454, 4, 400, 18),
                                                      "Source choices", sizeStyle="small")
            check("auto_groups", 454, 25, 410,
                  "Auto-aligned composite groups", kerning)
            check("cross_script", 454, 49, 410,
                  "Allow cross-script sources", kerning)

            eligibility.includeTitle = vanilla.TextBox((16, 4, 360, 18),
                                                        "Include in preview", sizeStyle="small")
            check("include_figures", 16, 25, 190, "Figures", eligibility)
            check("include_marks", 220, 25, 190, "Marks", eligibility)
            check("include_empty", 16, 49, 190, "Empty placeholders", eligibility)
            check("include_nonexporting", 220, 49, 230,
                  "Non-exporting glyphs", eligibility)
            check("include_alternates", 16, 73, 420,
                  "Suffix variants and alternates", eligibility)
            eligibility.updateTitle = vanilla.TextBox((454, 4, 400, 18),
                                                       "After applying", sizeStyle="small")
            check("sync_metrics", 454, 25, 410,
                  "Sync master-layer metrics", eligibility)
            check("sync_special_layers", 454, 49, 410,
                  "Sync special layers too", eligibility)

            self.w.rule = vanilla.HorizontalLine((16, 214, -16, 1))
            self.w.previewButton = vanilla.Button((16, 222, 130, 26), "Preview", callback=self.preview)
            self.w.previewButton.setToolTip("Build proposals and diagnostics without changing the font.")
            self.w.selectButton = vanilla.Button((164, 222, 140, 26), "Select eligible", callback=self.select_eligible)
            self.w.selectButton.setToolTip("Check preview rows that have no warnings.")
            self.w.clearButton = vanilla.Button((322, 222, 135, 26), "Clear selection", callback=self.clear_selection)
            self.w.clearButton.setToolTip("Uncheck every preview row.")
            self.w.applyButton = vanilla.Button((-155, 222, 139, 26), "Apply checked", callback=self.apply)
            self.w.applyButton.setToolTip("Apply only the checked preview rows to this font.")
            self.w.applyButton.enable(False)
            self.w.summary = vanilla.TextBox((16, 253, -16, 18),
                                             "Choose options and preview the font.", sizeStyle="small")
            column_descriptions = [
                {"title": "Use", "key": "Use", "width": 42, "editable": True,
                 "cell": vanilla.CheckBoxListCell()},
                {"title": "Glyph", "key": "Glyph", "width": 115, "editable": False},
                {"title": "Type", "key": "Type", "width": 85, "editable": False},
                {"title": "Side", "key": "Side", "width": 48, "editable": False},
                {"title": "Current", "key": "Current", "width": 84, "editable": False},
                {"title": "Proposed", "key": "Proposed", "width": 84, "editable": False},
                {"title": "Confidence", "key": "Confidence", "width": 75, "editable": False},
                {"title": "Reason", "key": "Reason", "width": 177, "editable": False},
                {"title": "Warning", "key": "Warning", "width": 177, "editable": False},
            ]
            self.w.proposalList = vanilla.List((16, 274, -16, -89), [],
                columnDescriptions=column_descriptions, showColumnTitles=True,
                allowsSorting=False, editCallback=self.list_edited)
            self.w.reportButton = vanilla.Button((16, -78, 150, 24), "Show full report",
                                                  callback=self.show_report)
            self.w.reportButton.setToolTip("Show every proposal and diagnostic note in the Macro Window.")
            self.w.status = vanilla.TextBox((16, -47, -16, 28),
                "No font changes until Apply checked.", sizeStyle="small")
            self.w.open()

        def current_options(self):
            result = {}
            for key, control in self.controls.items():
                if isinstance(control, tuple):
                    widget, values = control
                    result[key] = values[widget.get()]
                else:
                    result[key] = bool(control.get())
            return normalized_options(result)

        def option_changed(self, sender=None):
            options = self.current_options()
            Glyphs.defaults[PREFS_KEY] = json.dumps(options)
            self.w.applyButton.enable(False)
            self.w.status.set("Options changed. Preview again before applying.")

        def glyph_info(self, name):
            try:
                return Glyphs.glyphInfoForName(name, self.font)
            except Exception:
                return None

        def preview(self, sender=None):
            options = self.current_options()
            self.proposals, self.diagnostics = build_proposals(self.font, options, self.glyph_info)
            self.preview_options = options
            rows = []
            for item in self.proposals:
                rows.append({"Use": item["include"], "Glyph": item["glyph"],
                    "Type": item["kind"], "Side": item["side"],
                    "Current": item["before"] or "—", "Proposed": item["after"] or "—",
                    "Confidence": item["confidence"], "Reason": item["reason"],
                    "Warning": item["warning"]})
            self.w.proposalList.set(rows)
            self.list_edited(None)
            ready = sum(bool(item["include"]) for item in self.proposals)
            self.w.summary.set("%d proposals | %d checked | %d diagnostic notes" %
                               (len(rows), ready, len(self.diagnostics)))
            if (options["scope"] == "Selected glyphs" and
                    not options["font_specific_checks"] and not selected_names(self.font)):
                self.w.status.set("No glyphs selected. Select glyphs and preview again.")
            elif options["font_specific_checks"]:
                self.w.status.set("Font specific checks scanned the whole font. Review proposals.")
            else:
                self.w.status.set("Review checkboxes. No changes have been made.")

        def list_edited(self, sender=None):
            rows = self.w.proposalList.get()
            for item, row in zip(self.proposals, rows):
                item["include"] = bool(row["Use"])
            self.w.applyButton.enable(bool(self.preview_options and any(p["include"] for p in self.proposals)))
            if self.preview_options is not None:
                self.w.summary.set("%d proposals | %d checked | %d diagnostic notes" %
                    (len(self.proposals), sum(bool(p["include"]) for p in self.proposals), len(self.diagnostics)))

        def select_eligible(self, sender=None):
            if self.preview_options is None:
                return
            rows = self.w.proposalList.get()
            for item, row in zip(self.proposals, rows):
                row["Use"] = not bool(item["warning"])
            self.w.proposalList.set(rows)
            self.list_edited()

        def clear_selection(self, sender=None):
            rows = self.w.proposalList.get()
            for row in rows:
                row["Use"] = False
            self.w.proposalList.set(rows)
            self.list_edited()

        def show_report(self, sender=None):
            Glyphs.showMacroWindow()
            print("\nSpace basics — preview report")
            for item in self.proposals:
                print("%s %s: %s -> %s | %s | %s%s" %
                      (item["glyph"], item["field"], item["before"], item["after"],
                       item["confidence"], item["reason"],
                       (" | " + item["warning"]) if item["warning"] else ""))
            for name, message in self.diagnostics:
                print("%s: %s" % (name, message))

        def apply(self, sender=None):
            if self.preview_options is None or self.current_options() != self.preview_options:
                self.w.status.set("Options changed. Preview again before applying.")
                return
            if self.font not in Glyphs.fonts:
                self.w.status.set("This font is closed. Reopen the script for the target font.")
                return
            self.list_edited()
            try:
                fresh, _ = build_proposals(self.font, self.preview_options, self.glyph_info)
                current_by_id = {item["id"]: item for item in fresh}
                for item in self.proposals:
                    if not item["include"]:
                        continue
                    current = current_by_id.get(item["id"])
                    if current is None or any(current[key] != item[key] for key in
                                              ("before", "after", "source", "reason")):
                        raise ValueError("Font changed since preview; refresh before applying.")
                result = apply_proposals(self.font, self.proposals, self.preview_options)
                self.preview()
                self.w.status.set(" ".join(result) + " Preview refreshed.")
            except Exception as error:
                Glyphs.showMacroWindow()
                print(traceback.format_exc())
                self.w.status.set("Apply failed: %s" % error)

    # Keep the window controller alive after the script finishes.
    global DERIVATIVE_MANAGER_WINDOW
    DERIVATIVE_MANAGER_WINDOW = DerivativeManager(font)


if __name__ == "__main__":
    launch()
