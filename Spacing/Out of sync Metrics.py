# MenuTitle: Find Out-of-Sync Auto-Aligned Glyphs
# -*- coding: utf-8 -*-

__doc__ = """
Finds pure-composite glyphs whose auto-aligned sidebearings or width are out of
sync with a fresh alignment, and opens them in a new Edit tab.
"""

font = Glyphs.font
master_id = font.selectedFontMaster.id

out_of_sync_glyphs = []

# Iterate through all glyphs in the font
for glyph in font.glyphs:
    layer = glyph.layers[master_id]
    
    # 1. Check if the layer is a pure composite (has components, but no paths)
    if len(layer.components) > 0 and len(layer.paths) == 0:
        
        # 2. Check if the components are auto-aligned
        is_auto_aligned = any(comp.automaticAlignment for comp in layer.components)
        
        if is_auto_aligned:
            # 3. Safely check what the auto-aligned metrics SHOULD be
            test_layer = layer.copy()
            test_layer.parent = glyph  # Required so the layer knows its parent context
            
            # THE FIX: Use doAlignComponents() to snap components into their correct auto-aligned places
            test_layer.doAlignComponents() 
            test_layer.syncMetrics()
            
            # 4. Compare current metrics against the forced synced metrics
            width_diff = abs(layer.width - test_layer.width) > 0.001
            lsb_diff = abs(layer.LSB - test_layer.LSB) > 0.001
            rsb_diff = abs(layer.RSB - test_layer.RSB) > 0.001
            
            if width_diff or lsb_diff or rsb_diff:
                out_of_sync_glyphs.append(glyph.name)

# 5. Output results
if out_of_sync_glyphs:
    # Create a new tab (page) with the affected glyphs
    tab_text = "/" + "/".join(out_of_sync_glyphs)
    font.newTab(tab_text)
    
    # Print a summary to the Macro Panel
    print(f"Found {len(out_of_sync_glyphs)} out-of-sync glyphs in master '{font.selectedFontMaster.name}':")
    print(", ".join(out_of_sync_glyphs))
    Glyphs.showMacroWindow()
else:
    # If everything is perfectly aligned, notify the user
    Message("All Good!", "No out-of-sync auto-aligned glyphs found in the current master.")
    print("All auto-aligned components are perfectly in sync.")