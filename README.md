# DP Glyphs Scripts

A small collection of utility scripts for [Glyphs](https://glyphsapp.com/) focused on spacing, kerning, and moving metrics data between UFOs and `.glyphs` sources.

These scripts are meant to run inside Glyphs on macOS, not as standalone command-line tools.

## Included Scripts

### `master_spacing_and_kerning.py`

Batch-adjust spacing per master, with optional kerning updates to match.

Highlights:

- Adjust selected masters from one window
- Work in `Percent`, `Fixed value`, `InDesign`, `Figma`, or `Web` units
- Limit the scope to `All glyphs`, `Selected glyphs only`, or `Exporting glyphs only`
- Choose between `Spacing only` and `Spacing and kerning`
- Preview converted values before applying them

Notes:

- For spacing, the script writes `LSB` and `RSB`
- It does not edit outlines or write widths directly
- For kerning, it updates pairs in the selected master scope

### `transfer_ufo_metrics_and_kerning.py`

Transfer spacing, kerning, and kerning groups from UFO sources into a Glyphs file, master by master.

Highlights:

- Assign a different UFO to each master
- Import spacing (`width + sidebearings`)
- Import kerning
- Import kerning groups before kerning
- Replace existing kerning or merge into what is already in the file
- Process all glyphs or only the currently selected glyphs
- Optionally keep auto spacing untouched
- Optionally remove existing metrics keys before import
- Optionally lock imported values with `==`

This script also includes a **Clean & Normalise Metrics** workflow that converts metric formulas into fixed values and can lock those values with `==` afterward.

The script prints detailed progress and verification output to the Macro window.

### `double equals before SB.py`

Convert current sidebearings into locked `==` metric keys, or normalize existing sidebearing keys so they start with `==`.

Highlights:

- Apply to the active master or all masters
- Apply to selected glyphs or the whole font
- Optionally skip masters where the `MONO` axis value is `>= 1`

This is useful when you want to freeze current sidebearing values into explicit metrics keys.

### `Sidebearing Manager.py`

This file is currently empty in the repository.

## Requirements

- macOS
- Glyphs 3
- Glyphs' built-in Python environment

One script, `double equals before SB.py`, imports `vanilla` for its floating window UI.

## Installation

1. Download or clone this repository.
2. In Glyphs, open the Scripts folder:
   `Script > Open Scripts Folder`
3. Copy the `.py` files you want into that folder.
4. Restart Glyphs or reload scripts so they appear in the Scripts menu.

Because the scripts include `# MenuTitle` metadata, Glyphs should expose them in the Scripts menu once they are placed in the right folder.

## Usage Tips

- Back up your `.glyphs` file before running bulk spacing or kerning operations
- Open the Macro window if you want to inspect warnings, skips, or verification output
- Start on a copy of the font when testing a new workflow, especially for UFO transfer

## Repo Notes

- This repository is a script collection, not a packaged Glyphs plugin
- File names are currently functional rather than polished
- There is no test suite or standalone install process in the repo at the moment

