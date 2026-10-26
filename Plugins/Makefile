# Build helpers for Glyphs plug-in bundles in this repo.
#
# Python plug-ins ship a standard Glyphs SDK loader in
# Contents/MacOS/plugin. Python sources live in Contents/Resources/.

ROOT := $(abspath ..)
TESTS := $(ROOT)/Tests
SDK_PLUGIN_URL := https://raw.githubusercontent.com/schriftgestalt/GlyphsSDK/Glyphs3/Python%20Templates/Palette/____PluginName____.glyphsPalette/Contents/MacOS/plugin

PALETTE_PLUGINS := ScriptBoard.glyphsPalette GlyphNote.glyphsPalette
PYTHON_PLUGINS := $(PALETTE_PLUGINS) SpecialLayerCopy.glyphsPlugin
DIST_DIR := $(ROOT)/dist

.PHONY: all test clean dist clean-dist $(PYTHON_PLUGINS)

all: $(PYTHON_PLUGINS) test

$(PYTHON_PLUGINS):
	@plugin_dir="$@/Contents/MacOS"; \
	mkdir -p "$$plugin_dir"; \
	curl -fsSL "$(SDK_PLUGIN_URL)" -o "$$plugin_dir/plugin"; \
	chmod +x "$$plugin_dir/plugin"; \
	echo "Rebuilt $$plugin_dir/plugin"

test:
	python3 -m unittest discover -s "$(TESTS)" -v

clean:
	@for bundle in $(PYTHON_PLUGINS); do \
		rm -f "$$bundle/Contents/MacOS/plugin"; \
	done

dist: $(PYTHON_PLUGINS)
	@mkdir -p "$(DIST_DIR)"
	@for bundle in $(PYTHON_PLUGINS); do \
		zip_path="$(DIST_DIR)/$$bundle.zip"; \
		rm -f "$$zip_path"; \
		ditto -c -k --norsrc --noextattr --keepParent "$$bundle" "$$zip_path"; \
		echo "Wrote $$zip_path"; \
	done

clean-dist:
	rm -f $(addprefix $(DIST_DIR)/,$(addsuffix .zip,$(PYTHON_PLUGINS)))
