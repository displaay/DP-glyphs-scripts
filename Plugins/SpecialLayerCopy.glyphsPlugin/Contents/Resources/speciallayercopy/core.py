"""Planning and transactional copying. Importable without Glyphs or AppKit."""
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

from dataclasses import dataclass, field
from uuid import uuid4


SPECIAL_ATTRIBUTES = ("coordinates", "axisRules", "colorPalette", "sbixSize", "color", "svg")
KINDS = ("intermediate", "alternate", "other")


def attribute(layer, key):
    # Glyphs' dictionary proxy also accepts .get(), but plain keyed access works
    # with both the proxy and NSDictionary, including empty values and index 0.
    try:
        return layer.attributes[key]
    except (KeyError, TypeError):
        return None


def frozen(value):
    if hasattr(value, "keys"):
        return tuple(sorted((str(key), frozen(value[key])) for key in value.keys()))
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        return tuple(frozen(item) for item in value)
    return value


def special_kind(layer):
    if layer.isMasterLayer:
        return None
    if layer.isBraceLayer or attribute(layer, "coordinates") is not None:
        return "intermediate"
    if layer.isBracketLayer or attribute(layer, "axisRules") is not None:
        return "alternate"
    if layer.isSpecialLayer or any(
        attribute(layer, key) is not None for key in SPECIAL_ATTRIBUTES[2:]
    ):
        return "other"
    return None


def master_coordinates(master, axes):
    values = list(master.axes)
    return {axis.axisId: values[index] for index, axis in enumerate(axes) if index < len(values)}


def copied_coordinates(layer, source, target, axes, follow_master):
    coordinates = attribute(layer, "coordinates")
    if coordinates is None:
        return None
    coordinates = dict(coordinates)
    if follow_master:
        source_values = master_coordinates(source, axes)
        target_values = master_coordinates(target, axes)
        for axis_id, value in list(coordinates.items()):
            if axis_id in source_values and axis_id in target_values:
                if abs(float(value) - float(source_values[axis_id])) < 0.000001:
                    coordinates[axis_id] = target_values[axis_id]
    return coordinates


def signature(layer, master, axes, coordinates=None):
    """Settings identify layers; labels and nonfunctional metadata do not.

    Expand sparse intermediate coordinates against the associated master so
    that an implicit and an explicit master coordinate match one another.
    """
    settings = []
    for key in SPECIAL_ATTRIBUTES:
        value = attribute(layer, key)
        if key == "coordinates" and value is not None:
            effective = master_coordinates(master, axes)
            effective.update(dict(value) if coordinates is None else coordinates)
            value = effective
        if value is not None:
            settings.append((key, frozen(value)))
    # Glyphs 4 smart layers use coordinates keyed by GSGlyph.axes IDs too;
    # smartComponentPoleMapping was removed and must not be queried.
    return (special_kind(layer), tuple(settings) or (("name", layer.name),))


def selected_glyphs(font):
    glyphs, seen = [], set()
    for layer in font.selectedLayers or []:
        glyph = layer.parent
        if glyph is not None and glyph.name not in seen:
            seen.add(glyph.name)
            glyphs.append(glyph)
    return glyphs


@dataclass
class CopyOperation:
    glyph: object
    source: object
    target_master: object
    existing: object = None
    coordinates: object = None


@dataclass
class CopyPlan:
    font: object
    operations: list = field(default_factory=list)
    skipped: int = 0
    without_source: int = 0

    @property
    def created(self):
        return sum(op.existing is None for op in self.operations)

    @property
    def replaced(self):
        return len(self.operations) - self.created

    @property
    def summary(self):
        return "%d to add · %d to replace · %d skipped · %d glyphs without source layers" % (
            self.created, self.replaced, self.skipped, self.without_source
        )


def build_plan(font, glyphs, source_id, target_ids, kinds=KINDS,
               conflict="skip", follow_master=True, selected_layer_ids=None):
    """Validate the entire batch before permitting any change to the font."""
    if conflict not in ("skip", "replace"):
        raise ValueError("Choose skip or replace for existing layers.")
    masters = {master.id: master for master in font.masters}
    if source_id not in masters:
        raise ValueError("The source master no longer exists. Refresh the window.")
    targets = list(dict.fromkeys(target_ids))
    targets = [target_id for target_id in targets if target_id != source_id]
    if not targets or any(target_id not in masters for target_id in targets):
        raise ValueError("Select at least one other target master.")
    if not kinds or any(kind not in KINDS for kind in kinds):
        raise ValueError("Choose at least one special-layer type.")
    plan = CopyPlan(font)
    axes = list(font.axes)
    source_master = masters[source_id]
    seen_glyphs = set()
    for glyph in glyphs:
        if glyph.name in seen_glyphs:
            continue
        seen_glyphs.add(glyph.name)
        if glyph.parent != font:
            raise ValueError("A selected glyph no longer belongs to this font. Refresh the window.")
        layers = list(glyph.layers)
        sources = [layer for layer in layers
                   if layer.associatedMasterId == source_id and special_kind(layer) in kinds
                   and (selected_layer_ids is None or layer.layerId in selected_layer_ids)]
        if not sources:
            plan.without_source += 1
            continue
        for target_id in targets:
            target = masters[target_id]
            existing = {}
            for layer in layers:
                if layer.associatedMasterId == target_id and special_kind(layer) in kinds:
                    key = signature(layer, target, axes)
                    existing.setdefault(key, []).append(layer)
            planned = set()
            for source in sources:
                coordinates = copied_coordinates(source, source_master, target, axes, follow_master)
                key = signature(source, target, axes, coordinates)
                if key in planned:
                    raise ValueError(
                        "%s: multiple source layers would have the same settings in %s. "
                        "Select one source layer or resolve the duplicate first." % (glyph.name, target.name)
                    )
                planned.add(key)
                matches = existing.get(key, [])
                if matches and conflict == "skip":
                    plan.skipped += 1
                    continue
                if len(matches) > 1:
                    raise ValueError(
                        "%s: multiple matching layers in %s. Resolve the duplicates before replacing."
                        % (glyph.name, target.name)
                    )
                plan.operations.append(CopyOperation(
                    glyph, source, target, matches[0] if matches else None, coordinates
                ))
    return plan


def full_layer_copy(source):
    layer = source.copy()
    # A plain GSLayer.copy() does not reconnect hint origin/target nodes in
    # Glyphs 4. The native content copier also preserves shape groups/order.
    layer.getCopyOfContentFromLayer_doSelection_(source, False)
    layer.width = source.width
    layer.clearSelection()
    return layer


def execute_plan(plan):
    """Make native full-layer copies; restore touched layers if any write fails.

    Call immediately after building a fresh plan on the main thread. Prepare
    every copy before writing so a copy failure cannot leave a partial batch.
    """
    prepared = []
    for op in plan.operations:
        layer = full_layer_copy(op.source)
        layer.layerId = op.existing.layerId if op.existing is not None else str(uuid4()).upper()
        layer.associatedMasterId = op.target_master.id
        if op.coordinates is not None:
            layer.attributes["coordinates"] = dict(op.coordinates)
        backup = full_layer_copy(op.existing) if op.existing is not None else None
        prepared.append((op, layer, backup))
    if not prepared:
        return 0
    opened, touched, seen = [], [], set()
    plan.font.disableUpdateInterface()
    try:
        for op, layer, backup in prepared:
            if op.glyph.name not in seen:
                op.glyph.beginUndo()
                opened.append(op.glyph)
                seen.add(op.glyph.name)
            touched.append((op.glyph, layer.layerId, backup))
            op.glyph.layers[layer.layerId] = layer
    except Exception as error:
        rollback_errors = []
        for glyph, layer_id, backup in reversed(touched):
            try:
                if backup is not None:
                    glyph.layers[layer_id] = backup
                elif glyph.layers[layer_id] is not None:
                    del glyph.layers[layer_id]
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise RuntimeError(
                "Copy failed and some layers could not be restored. Use Undo and inspect the font. %s"
                % "; ".join(rollback_errors)
            ) from error
        raise RuntimeError("Copy failed; the original layers were restored. %s" % error) from error
    finally:
        try:
            for glyph in reversed(opened):
                glyph.endUndo()
        finally:
            plan.font.enableUpdateInterface()
    return len(prepared)
