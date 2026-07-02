PLUGIN_DIR := ../VFPreview.glyphsReporter
CONTENTS_DIR := $(PLUGIN_DIR)/Contents
MACOS_DIR := $(CONTENTS_DIR)/MacOS
EXECUTABLE := $(MACOS_DIR)/VFPreview
SOURCES := DPVFPreview.m
GLYPHS_APP := /Applications/Glyphs 3.app
FRAMEWORKS_DIR := $(GLYPHS_APP)/Contents/Frameworks
SDKROOT := $(shell xcrun --sdk macosx --show-sdk-path 2>/dev/null)
ARCHS ?= arm64 x86_64

ARCH_FLAGS := $(foreach arch,$(ARCHS),-arch $(arch))
SDK_FLAGS := $(if $(SDKROOT),-isysroot $(SDKROOT),)
CFLAGS := -fobjc-arc -fmodules -fobjc-weak -mmacosx-version-min=10.14 $(SDK_FLAGS) $(ARCH_FLAGS)
CFLAGS += -I"$(FRAMEWORKS_DIR)/GlyphsCore.framework/Headers"
CFLAGS += -F"$(FRAMEWORKS_DIR)"
LDFLAGS := -bundle -mmacosx-version-min=10.14 $(SDK_FLAGS) $(ARCH_FLAGS)
LDFLAGS += -F"$(FRAMEWORKS_DIR)"
LDFLAGS += -framework Cocoa -framework GlyphsCore -framework CoreText -framework CoreGraphics -framework QuartzCore
LDFLAGS += -Wl,-rpath,@executable_path/../Frameworks

.PHONY: all clean prepare

all: prepare $(EXECUTABLE)

prepare:
	@mkdir -p "$(MACOS_DIR)"

$(EXECUTABLE): $(SOURCES)
	clang $(CFLAGS) $(LDFLAGS) -o "$@" $^

clean:
	rm -f "$(EXECUTABLE)"
