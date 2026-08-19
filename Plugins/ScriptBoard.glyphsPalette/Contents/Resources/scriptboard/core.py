"""Pure data, search, persistence, and shortcut helpers for Script Board."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping, Sequence


SCHEMA_VERSION = 1

# Stable NSEvent modifier values. Keeping them here lets this module run without
# AppKit, which makes persistence and shortcut logic independently testable.
MODIFIER_SHIFT = 1 << 17
MODIFIER_CONTROL = 1 << 18
MODIFIER_OPTION = 1 << 19
MODIFIER_COMMAND = 1 << 20
SUPPORTED_MODIFIERS = (
    MODIFIER_SHIFT | MODIFIER_CONTROL | MODIFIER_OPTION | MODIFIER_COMMAND
)

FUNCTION_KEY_FIRST = 0xF704
FUNCTION_KEY_LAST = 0xF726

SPECIAL_KEY_NAMES = {
    "\x1b": "Esc",
    "\x08": "⌫",
    "\x09": "⇥",
    "\x0d": "↩",
    "\x7f": "⌫",
    chr(0xF700): "↑",
    chr(0xF701): "↓",
    chr(0xF702): "←",
    chr(0xF703): "→",
    chr(0xF727): "Insert",
    chr(0xF728): "⌦",
    chr(0xF729): "Home",
    chr(0xF72B): "End",
    chr(0xF72C): "Page Up",
    chr(0xF72D): "Page Down",
    " ": "Space",
}


def _clean_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized_path(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(text)))


def catalog_identity(entry: Mapping[str, object]) -> tuple[str, str]:
    """Return the stable source/relative-path identity for a catalog entry."""

    source = _clean_text(entry.get("source")).casefold()
    relative = _clean_text(entry.get("relative_path"))
    if relative:
        relative = os.path.normcase(os.path.normpath(relative))
    else:
        relative = _normalized_path(entry.get("absolute_path"))
    return source, relative


def _normalized_shortcut(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    key = value.get("key")
    if not isinstance(key, str) or not key:
        return None
    modifiers = value.get("modifiers", 0)
    try:
        modifiers = int(modifiers) & SUPPORTED_MODIFIERS
    except (TypeError, ValueError):
        return None
    key_code = value.get("key_code", 0)
    try:
        key_code = int(key_code)
    except (TypeError, ValueError):
        key_code = 0
    if len(key) == 1 and ord(key) < 0xF700:
        key = key.lower()
    shortcut = {"key": key, "modifiers": modifiers, "key_code": key_code}
    return shortcut if validate_shortcut(shortcut) is None else None


def shortcut_signature(value: object) -> tuple[str, int] | None:
    shortcut = _normalized_shortcut(value)
    if shortcut is None:
        return None
    return str(shortcut["key"]), int(shortcut["modifiers"])


def validate_shortcut(value: object) -> str | None:
    """Return a user-facing validation error, or None for a safe shortcut."""

    if not isinstance(value, Mapping):
        return "Press a key to record a shortcut."
    key = value.get("key")
    if not isinstance(key, str) or len(key) != 1:
        return "That key cannot be used as a shortcut."
    try:
        modifiers = int(value.get("modifiers", 0)) & SUPPORTED_MODIFIERS
    except (TypeError, ValueError):
        return "That modifier combination cannot be used."

    codepoint = ord(key)
    is_function_key = FUNCTION_KEY_FIRST <= codepoint <= FUNCTION_KEY_LAST
    is_printable = codepoint < 0xF700 and key.isprintable()
    has_command_modifier = bool(
        modifiers & (MODIFIER_COMMAND | MODIFIER_OPTION | MODIFIER_CONTROL)
    )

    if is_function_key:
        return None
    if is_printable and not has_command_modifier:
        return "Printable keys need Command, Option, or Control."
    if not is_printable and modifiers == 0:
        return "Use a modifier with this special key."
    return None


def display_shortcut(value: object) -> str:
    shortcut = _normalized_shortcut(value)
    if shortcut is None:
        return ""
    modifiers = int(shortcut["modifiers"])
    prefix = ""
    for flag, symbol in (
        (MODIFIER_CONTROL, "⌃"),
        (MODIFIER_OPTION, "⌥"),
        (MODIFIER_SHIFT, "⇧"),
        (MODIFIER_COMMAND, "⌘"),
    ):
        if modifiers & flag:
            prefix += symbol

    key = str(shortcut["key"])
    codepoint = ord(key)
    if FUNCTION_KEY_FIRST <= codepoint <= FUNCTION_KEY_LAST:
        label = "F{}".format(codepoint - FUNCTION_KEY_FIRST + 1)
    else:
        label = SPECIAL_KEY_NAMES.get(key, key.upper())
    return prefix + label


def make_board_item(
    entry: Mapping[str, object],
    shortcut: object = None,
    item_id: str | None = None,
) -> dict[str, object]:
    """Create a serializable board item from a runtime catalog entry."""

    return {
        "id": item_id or uuid.uuid4().hex,
        "source": _clean_text(entry.get("source")) or "Scripts",
        "source_root": _clean_text(entry.get("source_root")),
        "relative_path": _clean_text(entry.get("relative_path")),
        "absolute_path": _clean_text(entry.get("absolute_path")),
        "title": _clean_text(entry.get("title")) or "Untitled Script",
        "folder": _clean_text(entry.get("folder")),
        "shortcut": _normalized_shortcut(shortcut),
    }


def _legacy_path_item(path: str) -> dict[str, object]:
    path = os.path.abspath(path)
    return make_board_item(
        {
            "source": "Legacy",
            "source_root": os.path.dirname(path),
            "relative_path": os.path.basename(path),
            "absolute_path": path,
            "title": os.path.splitext(os.path.basename(path))[0],
            "folder": os.path.basename(os.path.dirname(path)),
        }
    )


def _normalized_item(value: object) -> dict[str, object] | None:
    if isinstance(value, str) and value.strip():
        return _legacy_path_item(value)
    if not isinstance(value, Mapping):
        return None
    absolute_path = _clean_text(value.get("absolute_path"))
    relative_path = _clean_text(value.get("relative_path"))
    if not absolute_path and not relative_path:
        return None
    item_id = _clean_text(value.get("id")) or uuid.uuid4().hex
    return make_board_item(value, value.get("shortcut"), item_id=item_id)


def normalize_state(value: object) -> dict[str, object]:
    """Validate current state and migrate the old list-of-paths representation."""

    if isinstance(value, Mapping):
        raw_items = value.get("items", [])
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw_items = value
    else:
        raw_items = []

    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        raw_items = []

    items: list[dict[str, object]] = []
    seen_entries: set[tuple[str, str]] = set()
    seen_shortcuts: set[tuple[str, int]] = set()
    seen_ids: set[str] = set()
    for raw_item in raw_items:
        item = _normalized_item(raw_item)
        if item is None:
            continue
        identity = catalog_identity(item)
        if identity in seen_entries:
            continue
        seen_entries.add(identity)
        item_id = str(item["id"])
        if item_id in seen_ids:
            item["id"] = uuid.uuid4().hex
        seen_ids.add(str(item["id"]))

        signature = shortcut_signature(item.get("shortcut"))
        if signature is not None and signature in seen_shortcuts:
            item["shortcut"] = None
        elif signature is not None:
            seen_shortcuts.add(signature)
        items.append(item)

    return {"schema_version": SCHEMA_VERSION, "items": items}


def state_for_preferences(value: object) -> dict[str, object]:
    """Return a deep property-list-safe representation of normalized state."""

    state = normalize_state(value)
    items = []
    for item in state["items"]:
        serialized = {
            key: item[key]
            for key in (
                "id",
                "source",
                "source_root",
                "relative_path",
                "absolute_path",
                "title",
                "folder",
            )
        }
        if item.get("shortcut") is not None:
            serialized["shortcut"] = dict(item["shortcut"])
        items.append(serialized)
    return {"schema_version": SCHEMA_VERSION, "items": items}


def resolve_board_item(
    item: Mapping[str, object], catalog: Sequence[Mapping[str, object]]
) -> Mapping[str, object] | None:
    """Resolve a persisted item after repositories have moved or been renamed."""

    absolute = _normalized_path(item.get("absolute_path"))
    if absolute:
        for entry in catalog:
            if _normalized_path(entry.get("absolute_path")) == absolute:
                return entry

    identity = catalog_identity(item)
    matches = [entry for entry in catalog if catalog_identity(entry) == identity]
    if len(matches) == 1:
        return matches[0]

    relative = os.path.normcase(
        os.path.normpath(_clean_text(item.get("relative_path")))
    )
    if relative:
        matches = [
            entry
            for entry in catalog
            if os.path.normcase(
                os.path.normpath(_clean_text(entry.get("relative_path")))
            )
            == relative
        ]
        if len(matches) == 1:
            return matches[0]

    basename = os.path.basename(relative or absolute)
    if basename:
        matches = [
            entry
            for entry in catalog
            if os.path.basename(_clean_text(entry.get("absolute_path"))) == basename
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def filter_catalog(
    catalog: Sequence[Mapping[str, object]], query: str
) -> list[Mapping[str, object]]:
    tokens = [token.casefold() for token in query.split() if token]

    def searchable(entry: Mapping[str, object]) -> str:
        return " ".join(
            _clean_text(entry.get(key))
            for key in ("title", "source", "folder", "relative_path")
        ).casefold()

    filtered = [
        entry
        for entry in catalog
        if all(token in searchable(entry) for token in tokens)
    ]
    return sorted(
        filtered,
        key=lambda entry: (
            _clean_text(entry.get("title")).casefold(),
            _clean_text(entry.get("source")).casefold(),
            _clean_text(entry.get("relative_path")).casefold(),
        ),
    )


def find_shortcut_conflict(
    items: Sequence[Mapping[str, object]],
    shortcut: object,
    excluding_id: str | None = None,
) -> Mapping[str, object] | None:
    signature = shortcut_signature(shortcut)
    if signature is None:
        return None
    for item in items:
        if excluding_id and item.get("id") == excluding_id:
            continue
        if shortcut_signature(item.get("shortcut")) == signature:
            return item
    return None


def move_items(
    items: Sequence[Mapping[str, object]], indexes: Sequence[int], destination: int
) -> list[Mapping[str, object]]:
    """Move rows using NSTableView's destination-before-removal convention."""

    valid = sorted({index for index in indexes if 0 <= index < len(items)})
    if not valid:
        return list(items)
    moving = [items[index] for index in valid]
    remaining = [item for index, item in enumerate(items) if index not in valid]
    adjusted = max(0, min(destination - sum(i < destination for i in valid), len(remaining)))
    return remaining[:adjusted] + moving + remaining[adjusted:]
