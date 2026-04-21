# MenuTitle: Copy Kerning Exceptions to Double Accents (with UI)
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals
__doc__ = """
Copies Kerning exceptions from selected base accented characters (e.g., Abreve, Acircumflex…)
into the corresponding Vietnamese/Pinyin double-accent glyphs.
"""

import vanilla
from GlyphsApp import Glyphs

thisFont = Glyphs.font  # frontmost font
allGlyphNames = [g.name for g in thisFont.glyphs if g.export]

baseGlyphNames = (
    "Abreve", "Acircumflex", "Ecircumflex", "Ocircumflex", "Udieresis",
    "Ohorn", "Uhorn",
    "abreve", "acircumflex", "ecircumflex", "ocircumflex", "udieresis",
    "ohorn", "uhorn"
)


class KerningUI(object):
    def __init__(self):
        self.w = vanilla.Window(
            (360, 420),
            "Copy Kerning Exceptions",
            minSize=(320, 350)
        )

        self.w.text = vanilla.TextBox(
            (10, 10, -10, 20),
            "Select base glyphs to process:"
        )

        # Prepare list data
        data = [{"Glyph": g, "Do": False} for g in baseGlyphNames]

        # Checkbox column
        self.w.list = vanilla.List(
            (10, 40, -10, -50),
            data,
            columnDescriptions={
                "Glyph": {"title": "Glyph"},
                "Do": {
                    "title": "✔",
                    "cell": vanilla.CheckBoxListCell(),
                    "width": 30,
                },
            },
            rowHeight=22,
            showColumnTitles=True
        )

        self.w.runButton = vanilla.Button(
            (-120, -35, -10, 20),
            "Run",
            callback=self.runCallback
        )

        self.w.open()

	def runCallback(self, sender):
	    data = self.w.list.get()   # ✅ returns list of dicts

	    selectedGlyphs = [
	        row["Glyph"]
	        for row in data
	        if row.get("Do")
	    ]

	    if not selectedGlyphs:
	        Glyphs.showMacroWindow()
	        print("⚠️ No glyphs selected.")
	        return

	    self.copyKerning(selectedGlyphs)

    def copyKerning(self, selectedGlyphs):
        Glyphs.clearLog()
        Glyphs.showMacroWindow()

        for baseGlyphName in selectedGlyphs:
            baseGlyph = thisFont.glyphs[baseGlyphName]
            if not baseGlyph:
                print("Missing glyph:", baseGlyphName)
                continue

            baseGlyphID = baseGlyph.id

            doubleaccentIDs = [
                thisFont.glyphs[g].id
                for g in allGlyphNames
                if g.startswith(baseGlyphName)
                and g != baseGlyphName
                and "." not in g
            ]

            print("\nCopying exceptions for:", baseGlyphName)

            if not doubleaccentIDs:
                print("  No double-accent glyphs found.")
                continue

            for thisMaster in thisFont.masters:
                print(" Master:", thisMaster.name)
                masterKerning = thisFont.kerning[thisMaster.id]

                # Base on left side
                if baseGlyphID in masterKerning:
                    for rightKey in masterKerning[baseGlyphID]:
                        kernValue = masterKerning[baseGlyphID][rightKey]

                        for doubleaccentID in doubleaccentIDs:
                            doubleaccentName = (
                                thisFont.glyphForId_(doubleaccentID).name
                            )

                            if rightKey[0] == "@":
                                rightKeyName = rightKey
                            else:
                                rightKeyName = thisFont.glyphForId_(rightKey).name

                            thisFont.setKerningForPair(
                                thisMaster.id,
                                doubleaccentName,
                                rightKeyName,
                                kernValue
                            )

                            print(f"  Added: {doubleaccentName} ⟺ {rightKeyName} ({kernValue:.1f})")

                # Base on right side
                for leftKey in masterKerning.keys():
                    if baseGlyphID in masterKerning[leftKey]:
                        kernValue = masterKerning[leftKey][baseGlyphID]

                        for doubleaccentID in doubleaccentIDs:
                            doubleaccentName = thisFont.glyphForId_(doubleaccentID).name

                            if leftKey[0] == "@":
                                leftKeyName = leftKey
                            else:
                                leftKeyName = thisFont.glyphForId_(leftKey).name

                            thisFont.setKerningForPair(
                                thisMaster.id,
                                leftKeyName,
                                doubleaccentName,
                                kernValue
                            )

                            print(f"  Added: {leftKeyName} ⟺ {doubleaccentName} ({kernValue:.1f})")

        print("\n✅ Done.")


KerningUI()
