"""Pure note storage, lock transitions, and selection helpers for Glyph Note."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field

from .markup import (
    StyleRun,
    display_from_markup,
    style_runs_from_storage,
    style_runs_signature,
    style_runs_to_storage,
    trim_note_styles,
)


PLUGIN_ID = "com.displaay.GlyphNote"
LOCKED_KEY = "{}.locked".format(PLUGIN_ID)
MASTER_NOTES_KEY = "{}.masterNotes".format(PLUGIN_ID)
LAYER_NOTE_KEY = "{}.note".format(PLUGIN_ID)
STYLES_KEY = "{}.styles".format(PLUGIN_ID)
MASTER_STYLES_KEY = "{}.masterStyles".format(PLUGIN_ID)
SHOW_BADGES_DEFAULTS_KEY = "{}.showBadges".format(PLUGIN_ID)

PLACEHOLDER_NO_SELECTION = "No glyph selected."
PLACEHOLDER_MULTIPLE = "Multiple values."
PLACEHOLDER_EMPTY_NOTE = "Empty note."
PLACEHOLDER_EMPTY_NOTES = "Empty notes."


def clean_note(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value).strip()


def _as_bool(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() not in ("", "0", "false", "no", "off")
    return bool(value)


def _as_str_dict(value: object) -> dict[str, str]:
    if not value:
        return {}
    items = None
    if isinstance(value, Mapping):
        items = value.items()
    else:
        try:
            items = dict(value).items()
        except (TypeError, ValueError):
            return {}
    notes = {}
    for key, raw in items:
        text = clean_note(raw)
        if text:
            notes[str(key)] = text
    return notes


@dataclass
class GlyphNoteState:
    note: str = ""
    locked: bool | None = None
    master_notes: dict[str, str] = field(default_factory=dict)
    layer_notes: dict[str, str] = field(default_factory=dict)
    note_styles: list[StyleRun] = field(default_factory=list)
    master_styles: dict[str, list[StyleRun]] = field(default_factory=dict)

    def copy(self) -> GlyphNoteState:
        return GlyphNoteState(
            note=self.note,
            locked=self.locked,
            master_notes=dict(self.master_notes),
            layer_notes=dict(self.layer_notes),
            note_styles=list(self.note_styles),
            master_styles={key: list(value) for key, value in self.master_styles.items()},
        )


@dataclass(frozen=True)
class SelectionDisplay:
    text: str
    placeholder: str
    locked: bool
    mixed_lock: bool
    mixed_notes: bool
    has_selection: bool
    master_name: str = ""
    master_id: str = ""
    styles: tuple[StyleRun, ...] = ()


def empty_state() -> GlyphNoteState:
    return GlyphNoteState()


def is_locked(state: GlyphNoteState) -> bool:
    """Legacy glyphs with only glyph.note are treated as locked."""

    return _as_bool(state.locked, default=True)


def get_master_note(state: GlyphNoteState, master_id: str) -> str:
    return clean_note(state.master_notes.get(master_id)) or clean_note(
        state.layer_notes.get(master_id)
    )


def get_master_styles(state: GlyphNoteState, master_id: str) -> list[StyleRun]:
    return list(state.master_styles.get(master_id) or ())


def get_display_styles(state: GlyphNoteState, master_id: str) -> list[StyleRun]:
    if is_locked(state):
        if state.note_styles:
            return list(state.note_styles)
        return get_master_styles(state, master_id)
    if get_master_note(state, master_id):
        return get_master_styles(state, master_id)
    if state.master_notes or state.layer_notes:
        return []
    return list(state.note_styles)


def get_display_note(state: GlyphNoteState, master_id: str) -> str:
    if is_locked(state):
        return (
            clean_note(state.note)
            or get_master_note(state, master_id)
        )
    stored = get_master_note(state, master_id)
    if stored:
        return stored
    if state.master_notes or state.layer_notes:
        return ""
    return clean_note(state.note)


def has_visible_note(state: GlyphNoteState, master_id: str) -> bool:
    return bool(get_display_note(state, master_id))


def has_any_note(state: GlyphNoteState) -> bool:
    if clean_note(state.note):
        return True
    if any(clean_note(value) for value in state.master_notes.values()):
        return True
    return any(clean_note(value) for value in state.layer_notes.values())


def native_note(
    state: GlyphNoteState, master_id: str, master_ids: Sequence[str]
) -> str:
    """Value written to glyph.note so Glyphs 4 can show its native icon.

    Locked notes use the shared string. Unlocked notes prefer the active
    master and fall back to any other stored master note so the icon stays
    visible without rewriting glyph.note on every master switch.
    """

    if is_locked(state):
        return get_display_note(state, master_id)
    current = get_display_note(state, master_id)
    if current:
        return current
    for mid in master_ids:
        text = get_master_note(state, mid)
        if text:
            return text
    return clean_note(state.note)


def _write_master(
    state: GlyphNoteState,
    master_id: str,
    text: str,
    styles: Sequence[StyleRun] | None = None,
) -> None:
    text, styles = trim_note_styles(text, styles)
    if text:
        state.master_notes[master_id] = text
        state.layer_notes[master_id] = text
        if styles:
            state.master_styles[master_id] = list(styles)
        else:
            state.master_styles.pop(master_id, None)
        return
    state.master_notes.pop(master_id, None)
    state.layer_notes.pop(master_id, None)
    state.master_styles.pop(master_id, None)


def _styles_for_native_note(
    state: GlyphNoteState, master_id: str, master_ids: Sequence[str]
) -> list[StyleRun]:
    note = native_note(state, master_id, master_ids)
    if not note:
        return []
    if get_display_note(state, master_id) == note:
        return get_display_styles(state, master_id)
    for mid in master_ids:
        if get_master_note(state, mid) == note:
            return get_master_styles(state, mid)
    return list(state.note_styles)


def set_display_note(
    state: GlyphNoteState,
    text: str,
    master_id: str,
    master_ids: Sequence[str],
    styles: Sequence[StyleRun] | None = None,
) -> GlyphNoteState:
    new_state = state.copy()
    text, styles = trim_note_styles(text, styles)
    if is_locked(new_state):
        new_state.note = text
        new_state.note_styles = list(styles)
        for mid in master_ids:
            _write_master(new_state, mid, text, styles)
        return new_state
    _write_master(new_state, master_id, text, styles)
    new_state.note = native_note(new_state, master_id, master_ids)
    new_state.note_styles = _styles_for_native_note(new_state, master_id, master_ids)
    return new_state


def set_locked(
    state: GlyphNoteState,
    locked: bool,
    master_ids: Sequence[str],
    active_master_id: str,
) -> GlyphNoteState:
    new_state = state.copy()
    if locked:
        text = get_display_note(state, active_master_id)
        styles = get_display_styles(state, active_master_id)
        if not text:
            text = native_note(state, active_master_id, master_ids)
            styles = _styles_for_native_note(state, active_master_id, master_ids)
        new_state.locked = True
        new_state.note = text
        new_state.note_styles = list(styles)
        for mid in master_ids:
            existing = get_master_note(state, mid)
            existing_styles = get_master_styles(state, mid)
            if existing:
                _write_master(new_state, mid, existing, existing_styles)
            else:
                _write_master(new_state, mid, text, styles)
        return new_state

    shared = get_display_note(state, active_master_id)
    shared_styles = get_display_styles(state, active_master_id)
    new_state.locked = False
    for mid in master_ids:
        existing = get_master_note(state, mid)
        existing_styles = get_master_styles(state, mid)
        if existing:
            _write_master(new_state, mid, existing, existing_styles)
        else:
            _write_master(new_state, mid, shared, shared_styles)
    new_state.note = native_note(new_state, active_master_id, master_ids)
    new_state.note_styles = _styles_for_native_note(
        new_state, active_master_id, master_ids
    )
    return new_state


def clear_active_master_note(
    state: GlyphNoteState, master_id: str, master_ids: Sequence[str]
) -> GlyphNoteState:
    return set_display_note(state, "", master_id, master_ids)


def clear_all_notes(
    state: GlyphNoteState, master_ids: Sequence[str]
) -> GlyphNoteState:
    new_state = state.copy()
    new_state.note = ""
    new_state.note_styles = []
    for mid in master_ids:
        _write_master(new_state, mid, "")
    new_state.master_notes.clear()
    new_state.layer_notes.clear()
    new_state.master_styles.clear()
    return new_state


def selection_display(
    states: Sequence[GlyphNoteState],
    master_id: str,
    master_name: str = "",
) -> SelectionDisplay:
    if not states:
        return SelectionDisplay(
            text="",
            placeholder=PLACEHOLDER_NO_SELECTION,
            locked=True,
            mixed_lock=False,
            mixed_notes=False,
            has_selection=False,
            master_name=master_name,
            master_id=master_id,
            styles=(),
        )

    notes = [get_display_note(state, master_id) for state in states]
    style_keys = [
        style_runs_signature(get_display_styles(state, master_id)) for state in states
    ]
    locks = [is_locked(state) for state in states]
    unique_notes = set(notes)
    unique_styles = set(style_keys)
    unique_locks = set(locks)
    mixed_notes = len(unique_notes) > 1 or len(unique_styles) > 1
    mixed_lock = len(unique_locks) > 1
    text = "" if mixed_notes else notes[0]
    styles = () if mixed_notes else tuple(get_display_styles(states[0], master_id))
    if mixed_notes:
        placeholder = PLACEHOLDER_MULTIPLE
    elif not text:
        placeholder = (
            PLACEHOLDER_EMPTY_NOTES if len(states) > 1 else PLACEHOLDER_EMPTY_NOTE
        )
    else:
        placeholder = (
            PLACEHOLDER_EMPTY_NOTES if len(states) > 1 else PLACEHOLDER_EMPTY_NOTE
        )
    return SelectionDisplay(
        text=text,
        placeholder=placeholder,
        locked=locks[0] if not mixed_lock else False,
        mixed_lock=mixed_lock,
        mixed_notes=mixed_notes,
        has_selection=True,
        master_name=master_name,
        master_id=master_id,
        styles=styles,
    )


def apply_note_to_states(
    states: Sequence[GlyphNoteState],
    text: str,
    master_id: str,
    master_ids: Sequence[str],
    styles: Sequence[StyleRun] | None = None,
) -> list[GlyphNoteState]:
    return [
        set_display_note(state, text, master_id, master_ids, styles) for state in states
    ]


def apply_lock_to_states(
    states: Sequence[GlyphNoteState],
    locked: bool,
    master_ids: Sequence[str],
    active_master_id: str,
) -> list[GlyphNoteState]:
    return [
        set_locked(state, locked, master_ids, active_master_id) for state in states
    ]


def _user_get(data: object, key: str, default: object = None) -> object:
    if data is None:
        return default
    try:
        if key in data:
            return data[key]
    except Exception:
        pass
    getter = getattr(data, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:
            return default
    return default


def _user_data(owner: object) -> MutableMapping[str, object]:
    data = getattr(owner, "userData", None)
    if data is None:
        return {}
    return data


def _layers(glyph: object) -> Mapping[str, object]:
    layers = getattr(glyph, "layers", None)
    return layers if layers is not None else {}


def _as_master_styles(value: object) -> dict[str, list[StyleRun]]:
    if not value:
        return {}
    try:
        items = value.items()
    except Exception:
        try:
            items = dict(value).items()
        except (TypeError, ValueError):
            return {}
    styles = {}
    for key, raw in items:
        runs = style_runs_from_storage(raw)
        if runs:
            styles[str(key)] = runs
    return styles


def _decode_stored_note(text: str, stored_styles: object, has_styles_key: bool) -> tuple[str, list[StyleRun]]:
    text = clean_note(text)
    if has_styles_key:
        return trim_note_styles(text, style_runs_from_storage(stored_styles))
    return display_from_markup(text)


def read_glyph_state(glyph: object, master_ids: Sequence[str]) -> GlyphNoteState:
    user = _user_data(glyph)
    layers = _layers(glyph)
    layer_notes = {}
    for mid in master_ids:
        try:
            layer = layers[mid]
        except Exception:
            layer = None
        if layer is None:
            continue
        layer_notes[mid] = clean_note(_user_get(_user_data(layer), LAYER_NOTE_KEY))
    raw_styles = _user_get(user, STYLES_KEY)
    has_styles_key = raw_styles is not None
    note, note_styles = _decode_stored_note(
        getattr(glyph, "note", ""),
        raw_styles,
        has_styles_key,
    )
    master_notes = _as_str_dict(_user_get(user, MASTER_NOTES_KEY))
    master_styles = _as_master_styles(_user_get(user, MASTER_STYLES_KEY))
    decoded_masters = {}
    decoded_master_styles = {}
    for mid, text in master_notes.items():
        if mid in master_styles:
            plain, runs = trim_note_styles(text, master_styles[mid])
        else:
            plain, runs = display_from_markup(text)
        decoded_masters[mid] = plain
        if runs:
            decoded_master_styles[mid] = runs
    decoded_layers = {}
    for mid, text in _as_str_dict(layer_notes).items():
        if mid in decoded_masters:
            decoded_layers[mid] = decoded_masters[mid]
            continue
        plain, runs = display_from_markup(text)
        decoded_layers[mid] = plain
        if runs and mid not in decoded_master_styles:
            decoded_master_styles[mid] = runs
    return GlyphNoteState(
        note=note,
        locked=_user_get(user, LOCKED_KEY),
        master_notes=decoded_masters,
        layer_notes=decoded_layers,
        note_styles=note_styles,
        master_styles=decoded_master_styles,
    )


def write_glyph_state(
    glyph: object,
    state: GlyphNoteState,
    master_ids: Sequence[str],
    active_master_id: str | None = None,
) -> None:
    mid = active_master_id if active_master_id else next(iter(master_ids), "")
    note = native_note(state, mid, master_ids)
    if is_locked(state):
        note = clean_note(state.note)
    glyph.note = note or None

    user = _user_data(glyph)
    user[LOCKED_KEY] = bool(is_locked(state))
    stored_notes = {
        mid: text
        for mid, text in state.master_notes.items()
        if clean_note(text)
    }
    if stored_notes:
        user[MASTER_NOTES_KEY] = dict(stored_notes)
    elif MASTER_NOTES_KEY in user:
        del user[MASTER_NOTES_KEY]

    stored_styles = style_runs_to_storage(state.note_styles)
    if stored_styles:
        user[STYLES_KEY] = stored_styles
    elif STYLES_KEY in user:
        del user[STYLES_KEY]

    stored_master_styles = {
        mid: style_runs_to_storage(runs)
        for mid, runs in state.master_styles.items()
        if style_runs_to_storage(runs)
    }
    if stored_master_styles:
        user[MASTER_STYLES_KEY] = stored_master_styles
    elif MASTER_STYLES_KEY in user:
        del user[MASTER_STYLES_KEY]

    layers = _layers(glyph)
    for mid in master_ids:
        try:
            layer = layers[mid]
        except Exception:
            layer = None
        if layer is None:
            continue
        layer_user = _user_data(layer)
        text = clean_note(state.layer_notes.get(mid) or state.master_notes.get(mid))
        if text:
            layer_user[LAYER_NOTE_KEY] = text
        elif LAYER_NOTE_KEY in layer_user:
            del layer_user[LAYER_NOTE_KEY]


def layer_has_note(layer: object, glyph: object | None = None) -> bool:
    """Return True when the given Font View layer should show a note badge."""

    if clean_note(_user_get(_user_data(layer), LAYER_NOTE_KEY)):
        return True
    parent = glyph if glyph is not None else getattr(layer, "parent", None)
    if parent is None:
        return False
    master = getattr(layer, "associatedMasterId", None) or getattr(
        layer, "layerId", None
    )
    master_id = str(master) if master else ""
    state = read_glyph_state(parent, [master_id] if master_id else [])
    if is_locked(state):
        return has_any_note(state)
    return has_visible_note(state, master_id)
