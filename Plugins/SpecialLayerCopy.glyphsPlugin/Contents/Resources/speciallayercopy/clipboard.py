"""Snapshot selected special layers and paste them into selected master rows."""

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from .core import (
    CopyOperation, CopyPlan, copied_coordinates, full_layer_copy, signature, special_kind,
)


PASTEBOARD_TYPE = "com.displaay.SpecialLayerCopy.layers.v1"


@dataclass
class CopiedLayer:
    glyph_name: str
    layer: object
    master: object


@dataclass
class LayerClipboard:
    font: object
    axes: tuple
    layers: list
    token: str


def snapshot_layers(font, layers):
    """Return None for ordinary Copy; never hold live source-layer content."""
    masters = {master.id: master for master in font.masters}
    entries, seen = [], set()
    for layer in layers:
        glyph = layer.parent
        if glyph is None or glyph.parent != font or special_kind(layer) is None:
            continue
        key = (glyph.name, layer.layerId)
        if key in seen:
            continue
        seen.add(key)
        master = masters.get(layer.associatedMasterId)
        if master is None:
            raise ValueError("The selected layer has no associated master.")
        master_snapshot = SimpleNamespace(id=master.id, name=master.name, axes=list(master.axes))
        entries.append(CopiedLayer(glyph.name, full_layer_copy(layer), master_snapshot))
    if not entries:
        return None
    return LayerClipboard(
        font, tuple(SimpleNamespace(axisId=axis.axisId) for axis in font.axes), entries,
        str(uuid4()),
    )


def build_paste_plan(clipboard, font, destination_layers):
    """Paste to matching glyphs under the masters selected in the palette.

    Existing matches are skipped. Masters/backup layers can be destinations,
    but are never replaced. Source snapshots may outlive edits/deletions of
    their original layers and masters.
    """
    if clipboard.font != font:
        raise ValueError("Copy and paste special layers within the same font.")
    if tuple(axis.axisId for axis in font.axes) != tuple(axis.axisId for axis in clipboard.axes):
        raise ValueError("The font axes changed. Copy the special layers again.")
    masters = {master.id: master for master in font.masters}
    sources = {}
    for entry in clipboard.layers:
        sources.setdefault(entry.glyph_name, []).append(entry)
    destinations = {}
    for layer in destination_layers:
        glyph = layer.parent
        if glyph is None or glyph.parent != font or glyph.name not in sources:
            continue
        master_id = layer.associatedMasterId
        if master_id in masters:
            destinations[(glyph.name, master_id)] = (glyph, masters[master_id])
    if not destinations:
        raise ValueError("Select a target master row for the copied glyphs in the Layers palette.")
    plan = CopyPlan(font)
    for glyph, target in destinations.values():
        existing = {
            signature(layer, target, font.axes)
            for layer in glyph.layers
            if layer.associatedMasterId == target.id and special_kind(layer) is not None
        }
        planned = set()
        for entry in sources[glyph.name]:
            coordinates = copied_coordinates(entry.layer, entry.master, target, clipboard.axes, True)
            key = signature(entry.layer, target, font.axes, coordinates)
            if key in planned:
                raise ValueError("%s has multiple copied layers with the same settings." % glyph.name)
            planned.add(key)
            if key in existing:
                plan.skipped += 1
                continue
            plan.operations.append(CopyOperation(glyph, entry.layer, target, coordinates=coordinates))
    return plan
