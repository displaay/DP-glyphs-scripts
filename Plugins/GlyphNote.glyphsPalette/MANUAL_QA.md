# Glyph Note manual QA

Test with a disposable multi-master font.

- [ ] Glyphs 4 launches with no Glyph Note exception in the Macro window.
- [ ] Glyph Note appears in the right Palette, after Script Board and before Dimensions.
- [ ] Empty state, checkbox, master label, and editor fit the Palette at minimum width.
- [ ] No glyph selected shows “No glyph selected.” and disables editing.
- [ ] Selecting one glyph with no note shows “Empty note.”
- [ ] Typing a note persists after switching glyphs and after reopening the font.
- [ ] Locked notes stay identical after switching masters (Cmd-1 / Cmd-2).
- [ ] Unlocking copies the shared note to every master, then each master can diverge.
- [ ] Locking writes the active master’s note onto every master.
- [ ] Multi-selection with the same note shows that text; differing notes show “Multiple values.”
- [ ] Mixed lock states show a mixed checkbox; clicking it locks the selection.
- [ ] Edit View and Font View selections both update the palette.
- [ ] Existing `glyph.note` values from Note Palettes or UFO import appear as locked notes.
- [ ] Font View shows Glyphs 4’s native note icon when `glyph.note` is not empty.
- [ ] List View Notes column (enable it from the header menu) shows the stored `glyph.note`.
- [ ] Show Badges in Font View draws a bottom-left badge on layers that have a note.
- [ ] Clearing the active master note only clears that master when unlocked.
- [ ] Clear All Notes in Selection removes shared and per-master notes.
- [ ] The interface remains legible in light, dark, and increased-contrast modes.
- [ ] Unloading/relaunching leaves no duplicate observers or DrawFontView callbacks.
