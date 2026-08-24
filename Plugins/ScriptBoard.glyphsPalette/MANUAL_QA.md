# Script Board manual QA

Test with a disposable font and scripts whose behavior is understood.

- [ ] Glyphs 4 launches with no Script Board exception in the Macro window.
- [ ] Script Board appears directly above Dimensions.
- [ ] Empty state and controls fit the Palette at minimum width.
- [ ] Dragging the lower Palette divider resizes Script Board from 72–520 pt.
- [ ] The plus button, reload button, and script count stay pinned to the lower edge while resizing.
- [ ] Short script names use standard system-font width; only overflowing names narrow.
- [ ] Changing the Palette width recalculates script-name width, then truncates only beyond the readable limit.
- [ ] The resized height persists after reopening Glyphs.
- [ ] Add picker searches by script, repository, and folder.
- [ ] Multiple selected scripts are added once and Cancel changes nothing.
- [ ] Clicking a row runs the intended script exactly once.
- [ ] A throwing test script reports through Glyphs without crashing it.
- [ ] Dragging rows persists after reopening Glyphs.
- [ ] Removing a row leaves its script file untouched.
- [ ] Reloading scripts refreshes the catalog.
- [ ] Moving or deleting a script produces a Missing row without data loss.
- [ ] Printable shortcuts without a safe modifier are rejected.
- [ ] Function keys and modifier-plus-special-key shortcuts run once.
- [ ] Duplicate board and existing Glyphs menu shortcuts are rejected.
- [ ] Delete clears and Escape cancels shortcut recording.
- [ ] Long script names truncate without widening the Palette.
- [ ] Context menu actions work, including Reveal and Show Details.
- [ ] Two open font windows run scripts against the active document.
- [ ] The interface remains legible in light, dark, and increased-contrast modes.
- [ ] Unloading/relaunching leaves no duplicate Script Board menu or observers.
