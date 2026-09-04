"""Plain-text note markup: *bold*, _italic_, and ~~strikethrough~~."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
import re


KIND_BOLD = "bold"
KIND_ITALIC = "italic"
KIND_STRIKE = "strike"

MARKER_BY_KIND = {
    KIND_BOLD: "*",
    KIND_ITALIC: "_",
    KIND_STRIKE: "~~",
}

FLAG_NONE = 0
FLAG_BOLD = 1
FLAG_ITALIC = 2
FLAG_STRIKE = 4
FLAG_MARKER = 8

_KIND_FLAGS = {
    KIND_BOLD: FLAG_BOLD,
    KIND_ITALIC: FLAG_ITALIC,
    KIND_STRIKE: FLAG_STRIKE,
}

_BOLD_RE = re.compile(r"(?<![A-Za-z0-9])\*([^*\n]+)\*(?![A-Za-z0-9])")
_ITALIC_RE = re.compile(r"(?<![A-Za-z0-9])_([^_\n]+)_(?![A-Za-z0-9])")
_STRIKE_RE = re.compile(r"~~([^~\n]+)~~")

_PATTERNS = (
    (KIND_STRIKE, _STRIKE_RE),
    (KIND_BOLD, _BOLD_RE),
    (KIND_ITALIC, _ITALIC_RE),
)


@dataclass(frozen=True)
class MarkupMatch:
    kind: str
    outer_start: int
    outer_end: int
    inner_start: int
    inner_end: int

    @property
    def marker_ranges(self) -> tuple[tuple[int, int], tuple[int, int]]:
        return (
            (self.outer_start, self.inner_start),
            (self.inner_end, self.outer_end),
        )


@dataclass(frozen=True)
class StyleRun:
    start: int
    end: int
    flags: int


def parse_note_markup(text: str) -> list[MarkupMatch]:
    """Return markup spans. Matches may overlap; they never nest the same kind."""

    if not text:
        return []
    matches = []
    for kind, pattern in _PATTERNS:
        for found in pattern.finditer(text):
            inner = found.group(1)
            if not inner.strip():
                continue
            matches.append(
                MarkupMatch(
                    kind=kind,
                    outer_start=found.start(),
                    outer_end=found.end(),
                    inner_start=found.start(1),
                    inner_end=found.end(1),
                )
            )
    matches.sort(key=lambda item: (item.outer_start, item.outer_end, item.kind))
    return matches


def markup_style_runs(text: str) -> list[tuple[int, int, int]]:
    """Cover `text` with (start, end, flags) runs, including marker characters."""

    length = len(text)
    if length == 0:
        return []
    flags = _flags_for_markup(text)
    runs = []
    start = 0
    for index in range(1, length + 1):
        if index == length or flags[index] != flags[start]:
            runs.append((start, index, flags[start]))
            start = index
    return runs


def display_from_markup(text: str) -> tuple[str, list[StyleRun]]:
    """Strip visible markers and return the displayed text plus style runs."""

    if not text:
        return "", []
    flags = _flags_for_markup(text)
    plain_chars = []
    plain_flags = []
    for index, char in enumerate(text):
        if flags[index] & FLAG_MARKER:
            continue
        plain_chars.append(char)
        plain_flags.append(flags[index] & ~FLAG_MARKER)
    return "".join(plain_chars), _coalesce_style_runs(plain_flags)


def trim_note_styles(text: str, runs: Sequence[StyleRun] | None) -> tuple[str, list[StyleRun]]:
    source = text if isinstance(text, str) else str(text or "")
    leading = len(source) - len(source.lstrip())
    stripped = source.strip()
    length = len(stripped)
    shifted = []
    for run in runs or ():
        start = max(0, int(run.start) - leading)
        end = min(length, int(run.end) - leading)
        if end > start and (run.flags & ~FLAG_MARKER):
            shifted.append(StyleRun(start, end, run.flags & ~FLAG_MARKER))
    return stripped, _merge_style_runs(shifted, length)


def style_runs_signature(runs: Sequence[StyleRun] | None) -> tuple[tuple[int, int, int], ...]:
    return tuple((run.start, run.end, run.flags) for run in _merge_style_runs(runs, None))


def style_runs_to_plist(runs: Sequence[StyleRun] | None) -> list[dict[str, object]]:
    payload = []
    for run in _merge_style_runs(runs, None):
        item = {"start": run.start, "end": run.end}
        if run.flags & FLAG_BOLD:
            item["bold"] = True
        if run.flags & FLAG_ITALIC:
            item["italic"] = True
        if run.flags & FLAG_STRIKE:
            item["strike"] = True
        payload.append(item)
    return payload


def style_runs_to_storage(runs: Sequence[StyleRun] | None) -> str:
    """Compact `start:end:flags;...` string that Glyphs userData can store."""

    return ";".join(
        "{}:{}:{}".format(run.start, run.end, run.flags)
        for run in _merge_style_runs(runs, None)
    )


def style_runs_from_storage(value: object) -> list[StyleRun]:
    if value is None or value is False:
        return []
    if isinstance(value, StyleRun):
        return _merge_style_runs([value], None)
    if isinstance(value, str):
        return _style_runs_from_token(value)
    if isinstance(value, bytes):
        return _style_runs_from_token(value.decode("utf-8", "replace"))
    try:
        items = list(value)
    except TypeError:
        return _style_runs_from_token(str(value))
    if not items:
        return []
    if all(isinstance(item, StyleRun) for item in items):
        return _merge_style_runs(items, None)
    return style_runs_from_plist(items)


def style_runs_from_plist(value: object) -> list[StyleRun]:
    if not value:
        return []
    try:
        items = list(value)
    except TypeError:
        return []
    runs = []
    for item in items:
        if isinstance(item, StyleRun):
            if item.end > item.start and item.flags:
                runs.append(item)
            continue
        if not isinstance(item, dict):
            try:
                item = dict(item)
            except (TypeError, ValueError):
                continue
        try:
            start = int(item.get("start", 0))
            end = int(item.get("end", 0))
        except (TypeError, ValueError):
            continue
        flags = FLAG_NONE
        if _as_flag(item.get("bold")):
            flags |= FLAG_BOLD
        if _as_flag(item.get("italic")):
            flags |= FLAG_ITALIC
        if _as_flag(item.get("strike")):
            flags |= FLAG_STRIKE
        if end > start and flags:
            runs.append(StyleRun(start, end, flags))
    return _merge_style_runs(runs, None)


def toggle_style_runs(
    runs: Sequence[StyleRun] | None,
    start: int,
    end: int,
    flag: int,
    length: int,
) -> list[StyleRun]:
    """Toggle one style bit on `start:end` of a `length`-long string."""

    length = max(0, int(length))
    start = max(0, min(int(start), length))
    end = max(start, min(int(end), length))
    flags = [FLAG_NONE] * length
    for run in _merge_style_runs(runs, length):
        for index in range(run.start, run.end):
            flags[index] |= run.flags
    if end > start:
        all_have = all(item & flag for item in flags[start:end])
        for index in range(start, end):
            if all_have:
                flags[index] &= ~flag
            else:
                flags[index] |= flag
    return _coalesce_style_runs(flags)


def _style_runs_from_token(value: str) -> list[StyleRun]:
    text = value.strip()
    if not text:
        return []
    runs = []
    for chunk in text.split(";"):
        parts = chunk.split(":")
        if len(parts) != 3:
            continue
        try:
            start = int(parts[0])
            end = int(parts[1])
            flags = int(parts[2]) & ~FLAG_MARKER
        except ValueError:
            continue
        if end > start and flags:
            runs.append(StyleRun(start, end, flags))
    return _merge_style_runs(runs, None)


def python_index_to_utf16(text: str, index: int) -> int:
    index = max(0, min(index, len(text)))
    return len(text[:index].encode("utf-16-le")) // 2


def utf16_index_to_python(text: str, utf16_index: int) -> int:
    if utf16_index <= 0:
        return 0
    encoded = text.encode("utf-16-le")
    byte_index = min(int(utf16_index) * 2, len(encoded))
    return len(encoded[:byte_index].decode("utf-16-le"))


def _flags_for_markup(text: str) -> list[int]:
    flags = [FLAG_NONE] * len(text)
    for match in parse_note_markup(text):
        bit = _KIND_FLAGS[match.kind]
        for index in range(match.inner_start, match.inner_end):
            flags[index] |= bit
        for marker_start, marker_end in match.marker_ranges:
            for index in range(marker_start, marker_end):
                flags[index] |= FLAG_MARKER
    return flags


def _coalesce_style_runs(flags: list[int]) -> list[StyleRun]:
    runs = []
    start = 0
    length = len(flags)
    for index in range(1, length + 1):
        if index == length or flags[index] != flags[start]:
            if flags[start]:
                runs.append(StyleRun(start, index, flags[start]))
            start = index
    return runs


def _merge_style_runs(runs: Sequence[StyleRun] | None, length: int | None) -> list[StyleRun]:
    cleaned = []
    for run in runs or ():
        start = int(run.start)
        end = int(run.end)
        flags = int(run.flags) & ~FLAG_MARKER
        if length is not None:
            start = max(0, min(start, length))
            end = max(0, min(end, length))
        if end > start and flags:
            cleaned.append(StyleRun(start, end, flags))
    cleaned.sort(key=lambda item: (item.start, item.end, item.flags))
    merged = []
    for run in cleaned:
        if merged and merged[-1].end >= run.start and merged[-1].flags == run.flags:
            previous = merged[-1]
            merged[-1] = StyleRun(previous.start, max(previous.end, run.end), previous.flags)
        else:
            merged.append(run)
    return merged


def _as_flag(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() not in ("", "0", "false", "no", "off")
    return bool(value)
