#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#import <GlyphsCore/GlyphsReporterProtocol.h>
#import <GlyphsCore/GSGlyphEditViewProtocol.h>
#import <GlyphsCore/GSGlyphViewControllerProtocol.h>
#import <GlyphsCore/GSFont.h>
#import <GlyphsCore/GSFontMaster.h>
#import <GlyphsCore/GSInstance.h>
#import <GlyphsCore/GSGlyph.h>
#import <GlyphsCore/GSLayer.h>
#import <GlyphsCore/GSPath.h>
#import <GlyphsCore/GSNode.h>
#import <GlyphsCore/GSComponent.h>
#import <GlyphsCore/GSAxis.h>
#import <GlyphsCore/GSMetricValue.h>

static NSString * const DPVFPrefPrefix = @"com.displaay.VFPreview.native";
static NSString * const DPVFSyntheticAxisID = @"__vfpreview_axis0__";

static BOOL DPVFIsOffcurve(GSNode *node) {
	return node.type == OFFCURVE;
}

static id DPVFCall(id object, SEL selector) {
	if (!object || ![object respondsToSelector:selector]) {
		return nil;
	}
	#pragma clang diagnostic push
	#pragma clang diagnostic ignored "-Warc-performSelector-leaks"
	return [object performSelector:selector];
	#pragma clang diagnostic pop
}

static CGFloat DPVFNumber(id value, CGFloat fallback) {
	if ([value respondsToSelector:@selector(doubleValue)]) {
		return [value doubleValue];
	}
	return fallback;
}

static NSPoint DPVFTransformPoint(NSPoint point, NSAffineTransformStruct transform) {
	return NSMakePoint(point.x * transform.m11 + point.y * transform.m21 + transform.tX,
					   point.x * transform.m12 + point.y * transform.m22 + transform.tY);
}

static BOOL DPVFHasPieceSettings(GSComponent *component) {
	id settings = component.pieceSettings;
	return [settings respondsToSelector:@selector(count)] && [settings count] > 0;
}

static GSFont *DPVFFontFromLayer(GSLayer *layer) {
	if (layer.font) {
		return layer.font;
	}
	if (layer.parent.font) {
		return layer.parent.font;
	}
	return nil;
}

static CGFloat DPVFIndexedNumber(id object, NSUInteger index, CGFloat fallback) {
	if (!object || ![object respondsToSelector:@selector(count)] || ![object respondsToSelector:@selector(objectAtIndex:)]) {
		return fallback;
	}
	if (index >= [object count]) {
		return fallback;
	}
	id value = [object objectAtIndex:index];
	if ([value respondsToSelector:@selector(doubleValue)]) {
		return [value doubleValue];
	}
	if ([value isKindOfClass:GSMetricValue.class]) {
		return ((GSMetricValue *)value).position;
	}
	return fallback;
}

@interface DPVFNodeFrame : NSObject
@property CGFloat x;
@property CGFloat y;
@property GSNodeType type;
+ (instancetype)nodeWithX:(CGFloat)x y:(CGFloat)y type:(GSNodeType)type;
@end

@implementation DPVFNodeFrame
+ (instancetype)nodeWithX:(CGFloat)x y:(CGFloat)y type:(GSNodeType)type {
	DPVFNodeFrame *node = [[DPVFNodeFrame alloc] init];
	node.x = x;
	node.y = y;
	node.type = type;
	return node;
}
@end

@interface DPVFPathFrame : NSObject
@property BOOL closed;
@property (strong) NSArray<DPVFNodeFrame *> *nodes;
@end

@implementation DPVFPathFrame
@end

@interface DPVFFrame : NSObject
@property (strong) NSBezierPath *bezierPath;
@property (strong) NSArray<DPVFPathFrame *> *paths;
@property CGFloat width;
@end

@implementation DPVFFrame
@end

@interface DPVFAxisRow : NSObject
@property (strong) GSAxis *axis;
@property (strong) NSString *axisId;
@property (strong) NSString *name;
@property CGFloat minimum;
@property CGFloat maximum;
@property CGFloat defaultValue;
@property NSUInteger index;
@property BOOL synthetic;
@end

@implementation DPVFAxisRow
@end

@class DPVFPreview;

@interface DPVFPreviewView : NSView
@property (weak) DPVFPreview *plugin;
@end

@interface DPVFSliderPanel : NSObject
@property (weak) DPVFPreview *plugin;
@property (strong) NSPanel *panel;
@property (strong) DPVFPreviewView *previewView;
@property (strong) NSMutableArray<NSSlider *> *sliders;
@property (strong) NSMutableArray<NSTextField *> *labels;
@property (strong) NSMutableArray<NSTextField *> *values;
@property (strong) NSString *axisSignature;
- (instancetype)initWithPlugin:(DPVFPreview *)plugin;
- (void)open;
- (void)close;
- (void)rebuild;
- (void)refreshValues;
- (void)sliderChanged:(NSSlider *)sender;
@end

@interface DPVFPreview : NSObject <GlyphsReporter>
@property (weak) NSViewController<GSGlyphEditViewControllerProtocol> *controller;
@property (strong) GSInstance *instance;
@property (strong) NSMutableDictionary<NSString *, NSNumber *> *axisValues;
@property (strong) NSMutableDictionary<NSString *, DPVFFrame *> *frameCache;
@property (strong) DPVFSliderPanel *panel;
@property BOOL hideForeground;
@property BOOL centerPreview;
@property BOOL showNodes;
@property BOOL drawInEditView;
@property BOOL liveDragging;
- (void)axisValueChangedFromSlider;
- (void)ensureFontBound;
- (GSFont *)currentFont;
- (GSFontMaster *)activeMaster;
- (NSArray<GSAxis *> *)fontAxes;
- (NSArray<DPVFAxisRow *> *)axisRows;
- (NSDictionary<NSString *, NSNumber *> *)currentInterpolations;
- (GSLayer *)interpolatedLayerForGlyph:(GSGlyph *)glyph;
- (DPVFFrame *)frameForGlyph:(GSGlyph *)glyph;
- (void)drawFrame:(DPVFFrame *)frame scale:(CGFloat)scale forPanel:(BOOL)forPanel;
- (NSArray<GSLayer *> *)visibleLayers;
- (void)redrawLive;
- (DPVFFrame *)directFrameForGlyph:(GSGlyph *)glyph seen:(NSMutableSet<NSString *> *)seenGlyphs;
- (void)appendFrame:(DPVFFrame *)componentFrame transform:(NSAffineTransformStruct)transform toPathFrames:(NSMutableArray<DPVFPathFrame *> *)pathFrames bezierPath:(NSBezierPath *)bezierPath;
@end

static NSArray *DPVFShapeArray(id proxy) {
	if (!proxy) {
		return @[];
	}
	if ([proxy isKindOfClass:NSArray.class]) {
		return proxy;
	}
	if ([proxy respondsToSelector:@selector(allObjects)]) {
		id objects = DPVFCall(proxy, @selector(allObjects));
		if ([objects isKindOfClass:NSArray.class]) {
			return objects;
		}
	}
	if ([proxy conformsToProtocol:@protocol(NSFastEnumeration)]) {
		NSMutableArray *objects = [NSMutableArray array];
		for (id object in proxy) {
			if (object) {
				[objects addObject:object];
			}
		}
		return objects;
	}
	return @[];
}

@implementation DPVFPreviewView

- (instancetype)initWithFrame:(NSRect)frameRect {
	self = [super initWithFrame:frameRect];
	if (self) {
		self.wantsLayer = YES;
		if ([self respondsToSelector:@selector(setCanDrawConcurrently:)]) {
			self.canDrawConcurrently = YES;
		}
	}
	return self;
}

- (BOOL)isFlipped {
	return YES;
}

- (void)drawRect:(NSRect)dirtyRect {
	[[NSColor whiteColor] setFill];
	NSRectFill(self.bounds);
	DPVFPreview *plugin = self.plugin;
	if (!plugin) {
		return;
	}
	NSArray<GSLayer *> *layers = [plugin visibleLayers];
	if (layers.count == 0) {
		return;
	}

	CGFloat ascender = 800.0;
	CGFloat descender = -200.0;
	GSFontMaster *master = [plugin activeMaster];
	if (master) {
		ascender = master.defaultAscender;
		descender = master.defaultDescender;
	}
	CGFloat cursor = 0.0;
	NSMutableArray<NSDictionary *> *items = [NSMutableArray array];
	for (GSLayer *layer in layers) {
		GSGlyph *glyph = layer.parent;
		if (!glyph) {
			continue;
		}
		DPVFFrame *frame = [plugin frameForGlyph:glyph];
		if (!frame) {
			continue;
		}
		[items addObject:@{@"frame": frame, @"x": @(cursor)}];
		cursor += MAX(frame.width, 1.0);
	}
	if (items.count == 0) {
		return;
	}
	CGFloat width = MAX(cursor, 1.0);
	CGFloat height = MAX(ascender - descender, 1.0);
	CGFloat padding = 12.0;
	CGFloat scale = MIN((self.bounds.size.width - padding * 2.0) / width,
						(self.bounds.size.height - padding * 2.0) / height) * 0.95;
	if (scale <= 0.0) {
		return;
	}
	CGFloat originX = padding;
	CGFloat baselineY = (self.bounds.size.height - height * scale) / 2.0 + ascender * scale;

	for (NSDictionary *item in items) {
		DPVFFrame *frame = item[@"frame"];
		CGFloat x = [item[@"x"] doubleValue];
		[NSGraphicsContext saveGraphicsState];
		NSAffineTransform *transform = [NSAffineTransform transform];
		[transform translateXBy:originX + x * scale yBy:baselineY];
		[transform scaleXBy:scale yBy:-scale];
		[transform concat];
		[plugin drawFrame:frame scale:scale forPanel:YES];
		[NSGraphicsContext restoreGraphicsState];
	}
}

@end

@implementation DPVFSliderPanel

- (instancetype)initWithPlugin:(DPVFPreview *)plugin {
	self = [super init];
	if (self) {
		_plugin = plugin;
		_sliders = [NSMutableArray array];
		_labels = [NSMutableArray array];
		_values = [NSMutableArray array];
	}
	return self;
}

- (NSArray<DPVFAxisRow *> *)rows {
	return [self.plugin axisRows];
}

- (NSString *)currentAxisSignature {
	NSMutableArray<NSString *> *parts = [NSMutableArray array];
	for (DPVFAxisRow *row in [self rows]) {
		[parts addObject:[NSString stringWithFormat:@"%@:%@:%lu",
						  row.synthetic ? @"synthetic" : @"axis",
						  row.axisId ?: @"",
						  (unsigned long)row.index]];
	}
	return [parts componentsJoinedByString:@"|"];
}

- (BOOL)needsRebuild {
	NSString *signature = [self currentAxisSignature];
	return !self.panel || ![self.axisSignature isEqualToString:signature];
}

- (void)open {
	[self.plugin ensureFontBound];
	if ([self needsRebuild]) {
		[self rebuild];
	}
	[self.panel makeKeyAndOrderFront:nil];
	[self refreshValues];
}

- (void)close {
	[self.panel orderOut:nil];
}

- (void)rebuild {
	NSArray<DPVFAxisRow *> *rows = [self rows];
	self.axisSignature = [self currentAxisSignature];
	NSUInteger count = MAX((NSUInteger)1, rows.count);
	CGFloat width = 620.0;
	CGFloat previewHeight = 92.0;
	CGFloat rowHeight = 30.0;
	CGFloat height = 16.0 + previewHeight + 12.0 + count * rowHeight + 14.0;

	if (!self.panel) {
		self.panel = [[NSPanel alloc] initWithContentRect:NSMakeRect(180, 180, width, height)
												styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskUtilityWindow | NSWindowStyleMaskNonactivatingPanel
												  backing:NSBackingStoreBuffered
													defer:NO];
		self.panel.title = @"VF Preview";
		self.panel.floatingPanel = YES;
		self.panel.hidesOnDeactivate = NO;
	}
	else {
		NSRect frame = self.panel.frame;
		frame.origin.y += frame.size.height - height;
		frame.size = NSMakeSize(width, height);
		[self.panel setFrame:frame display:NO];
	}

	NSView *content = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, width, height)];
	self.panel.contentView = content;

	self.previewView = [[DPVFPreviewView alloc] initWithFrame:NSMakeRect(12, height - previewHeight - 12, width - 24, previewHeight)];
	self.previewView.plugin = self.plugin;
	[content addSubview:self.previewView];

	[self.sliders removeAllObjects];
	[self.labels removeAllObjects];
	[self.values removeAllObjects];
	CGFloat y = height - previewHeight - 24.0 - rowHeight;
	for (NSUInteger index = 0; index < count; index++) {
		DPVFAxisRow *row = index < rows.count ? rows[index] : nil;
		NSTextField *label = [NSTextField labelWithString:row ? row.name : @"No variable axes"];
		label.frame = NSMakeRect(12, y + 6, 120, 18);
		[content addSubview:label];
		[self.labels addObject:label];

		NSSlider *slider = [[NSSlider alloc] initWithFrame:NSMakeRect(138, y + 2, width - 230, 24)];
		slider.minValue = 0.0;
		slider.maxValue = 1.0;
		slider.continuous = YES;
		slider.target = self;
		slider.action = @selector(sliderChanged:);
		slider.tag = (NSInteger)index;
		slider.enabled = row != nil;
		[content addSubview:slider];
		[self.sliders addObject:slider];

		NSTextField *value = [NSTextField labelWithString:@"0"];
		value.alignment = NSTextAlignmentRight;
		value.frame = NSMakeRect(width - 82, y + 6, 70, 18);
		[content addSubview:value];
		[self.values addObject:value];
		y -= rowHeight;
	}
}

- (void)axisRangeForIndex:(NSUInteger)index min:(CGFloat *)minValue max:(CGFloat *)maxValue {
	NSArray<DPVFAxisRow *> *rows = [self rows];
	DPVFAxisRow *row = index < rows.count ? rows[index] : nil;
	*minValue = row ? row.minimum : 0.0;
	*maxValue = row ? row.maximum : 1.0;
}

- (void)refreshValues {
	[self.plugin ensureFontBound];
	if ([self needsRebuild]) {
		[self rebuild];
	}
	NSArray<DPVFAxisRow *> *rows = [self rows];
	for (NSUInteger index = 0; index < self.sliders.count; index++) {
		NSSlider *slider = self.sliders[index];
		NSTextField *valueField = self.values[index];
		NSTextField *label = self.labels[index];
		if (index >= rows.count) {
			slider.enabled = NO;
			label.stringValue = @"No variable axes";
			valueField.stringValue = @"";
			continue;
		}
		DPVFAxisRow *row = rows[index];
		CGFloat minV = 0.0;
		CGFloat maxV = 1.0;
		[self axisRangeForIndex:index min:&minV max:&maxV];
		CGFloat value = [self.plugin.axisValues[row.axisId] doubleValue];
		CGFloat normalized = (value - minV) / MAX(maxV - minV, 0.0001);
		label.stringValue = row.name;
		slider.enabled = YES;
		slider.doubleValue = MIN(1.0, MAX(0.0, normalized));
		valueField.stringValue = [NSString stringWithFormat:@"%.0f", value];
	}
	[self.previewView setNeedsDisplay:YES];
}

- (void)sliderChanged:(NSSlider *)sender {
	NSArray<DPVFAxisRow *> *rows = [self rows];
	NSUInteger index = (NSUInteger)sender.tag;
	if (index >= rows.count) {
		return;
	}
	CGFloat minV = 0.0;
	CGFloat maxV = 1.0;
	[self axisRangeForIndex:index min:&minV max:&maxV];
	CGFloat value = minV + sender.doubleValue * (maxV - minV);
	DPVFAxisRow *row = rows[index];
	self.plugin.axisValues[row.axisId] = @(value);
	self.values[index].stringValue = [NSString stringWithFormat:@"%.0f", value];
	[self.plugin axisValueChangedFromSlider];
}

@end

@implementation DPVFPreview

@synthesize controller = _controller;

- (instancetype)init {
	self = [super init];
	if (self) {
		_axisValues = [NSMutableDictionary dictionary];
		_frameCache = [NSMutableDictionary dictionary];
		_drawInEditView = YES;
		_showNodes = YES;
		_hideForeground = NO;
		_centerPreview = NO;
	}
	return self;
}

- (NSUInteger)interfaceVersion {
	return 1;
}

- (NSString *)title {
	return @"VF Preview";
}

- (NSString *)keyEquivalent {
	return @"v";
}

- (NSEventModifierFlags)modifierMask {
	return NSEventModifierFlagCommand | NSEventModifierFlagOption | NSEventModifierFlagControl;
}

- (void)willActivate {
	[self ensureFontBound];
	if (!self.panel) {
		self.panel = [[DPVFSliderPanel alloc] initWithPlugin:self];
	}
	[self.panel open];
}

- (void)willDeactivate {
	[self.panel close];
}

- (GSFont *)currentFont {
	id representedObject = self.controller.representedObject;
	if ([representedObject isKindOfClass:GSFont.class]) {
		return representedObject;
	}
	GSFont *font = DPVFFontFromLayer(self.controller.activeLayer);
	if (font) {
		return font;
	}
	id< GSGlyphEditViewProtocol > graphicView = self.controller.graphicView;
	font = DPVFFontFromLayer(graphicView.activeLayer);
	if (font) {
		return font;
	}
	NSUInteger cachedLayerCount = graphicView.cachedLayerCount;
	for (NSUInteger index = 0; index < cachedLayerCount; index++) {
		font = DPVFFontFromLayer([graphicView cachedGlyphAtIndex:index]);
		if (font) {
			return font;
		}
	}
	for (GSLayer *layer in self.controller.selectedLayers) {
		font = DPVFFontFromLayer(layer);
		if (font) {
			return font;
		}
	}
	for (GSLayer *layer in self.controller.allLayers) {
		font = DPVFFontFromLayer(layer);
		if (font) {
			return font;
		}
	}
	Class glyphsClass = NSClassFromString(@"Glyphs");
	id appFont = DPVFCall(glyphsClass, @selector(font));
	if ([appFont isKindOfClass:GSFont.class]) {
		return appFont;
	}
	return nil;
}

- (GSFontMaster *)activeMaster {
	if ([self.controller respondsToSelector:@selector(activeMaster)]) {
		GSFontMaster *master = [self.controller activeMaster];
		if (master) {
			return master;
		}
	}
	return [self currentFont].fontMasters.firstObject;
}

- (NSArray<GSAxis *> *)fontAxes {
	GSFont *font = [self currentFont];
	NSArray<GSAxis *> *axes = font.axes;
	if (axes.count > 0) {
		return axes;
	}
	if ([font respondsToSelector:@selector(legacyAxes)]) {
		id legacyAxes = DPVFCall(font, @selector(legacyAxes));
		if ([legacyAxes isKindOfClass:NSArray.class] && [legacyAxes count] > 0) {
			return legacyAxes;
		}
	}
	return @[];
}

- (CGFloat)axisValueForMaster:(GSFontMaster *)master axis:(GSAxis *)axis index:(NSUInteger)index fallback:(CGFloat)fallback {
	if (axis.axisId.length > 0) {
		CGFloat value = [master axisValueValueForId:axis.axisId];
		if (isfinite(value)) {
			return value;
		}
	}
	return DPVFIndexedNumber(master.axes, index, fallback);
}

- (CGFloat)syntheticAxisValueForMaster:(GSFontMaster *)master index:(NSUInteger)index fallback:(CGFloat)fallback {
	id internalAxesValues = DPVFCall(master, @selector(internalAxesValues));
	CGFloat value = DPVFIndexedNumber(internalAxesValues, index, CGFLOAT_MAX);
	if (value != CGFLOAT_MAX) {
		return value;
	}
	return DPVFIndexedNumber(master.axes, index, fallback);
}

- (BOOL)usesSyntheticAxis {
	return [self fontAxes].count == 0 && [self currentFont].fontMasters.count >= 2;
}

- (NSArray<DPVFAxisRow *> *)axisRows {
	GSFont *font = [self currentFont];
	if (!font) {
		return @[];
	}
	NSArray<GSAxis *> *axes = [self fontAxes];
	NSMutableArray<DPVFAxisRow *> *rows = [NSMutableArray array];
	if (axes.count > 0) {
		for (NSUInteger index = 0; index < axes.count; index++) {
			GSAxis *axis = axes[index];
			DPVFAxisRow *row = [[DPVFAxisRow alloc] init];
			row.axis = axis;
			row.axisId = axis.axisId ?: [NSString stringWithFormat:@"axis%lu", (unsigned long)index];
			row.name = axis.name.length > 0 ? axis.name : (axis.axisTag.length > 0 ? axis.axisTag : row.axisId);
			row.index = index;
			row.synthetic = NO;
			row.minimum = CGFLOAT_MAX;
			row.maximum = -CGFLOAT_MAX;
			for (GSFontMaster *master in font.fontMasters) {
				CGFloat value = [self axisValueForMaster:master axis:axis index:index fallback:axis.defaultValue];
				row.minimum = MIN(row.minimum, value);
				row.maximum = MAX(row.maximum, value);
			}
			if (row.minimum == CGFLOAT_MAX || fabs(row.maximum - row.minimum) < 0.0001) {
				row.minimum = 0.0;
				row.maximum = 1.0;
			}
			row.defaultValue = axis.defaultValue != 0.0 ? axis.defaultValue : (row.minimum + row.maximum) * 0.5;
			[rows addObject:row];
		}
		return rows;
	}
	if ([self usesSyntheticAxis]) {
		DPVFAxisRow *row = [[DPVFAxisRow alloc] init];
		row.axisId = DPVFSyntheticAxisID;
		row.name = @"Interpolation";
		row.index = 0;
		row.synthetic = YES;
		row.minimum = CGFLOAT_MAX;
		row.maximum = -CGFLOAT_MAX;
		NSUInteger masterIndex = 0;
		for (GSFontMaster *master in font.fontMasters) {
			CGFloat value = [self syntheticAxisValueForMaster:master index:0 fallback:(CGFloat)masterIndex];
			row.minimum = MIN(row.minimum, value);
			row.maximum = MAX(row.maximum, value);
			masterIndex++;
		}
		if (row.minimum == CGFLOAT_MAX || fabs(row.maximum - row.minimum) < 0.0001) {
			row.minimum = 0.0;
			row.maximum = MAX((CGFloat)font.fontMasters.count - 1.0, 1.0);
		}
		row.defaultValue = (row.minimum + row.maximum) * 0.5;
		[rows addObject:row];
	}
	return rows;
}

- (void)ensureFontBound {
	GSFont *font = [self currentFont];
	if (!font) {
		return;
	}
	if (!self.instance || self.instance.font != font) {
		self.instance = [[GSInstance alloc] initWithType:GSInstanceTypeSingle];
		self.instance.font = font;
		[self.axisValues removeAllObjects];
		[self.frameCache removeAllObjects];
	}
	NSMutableSet<NSString *> *validAxisIds = [NSMutableSet set];
	for (DPVFAxisRow *row in [self axisRows]) {
		if (row.axisId) {
			[validAxisIds addObject:row.axisId];
			if (!self.axisValues[row.axisId]) {
				self.axisValues[row.axisId] = @(row.defaultValue);
			}
		}
	}
	for (NSString *axisId in self.axisValues.allKeys) {
		if (![validAxisIds containsObject:axisId]) {
			[self.axisValues removeObjectForKey:axisId];
		}
	}
	[self applyAxisValuesToInstance];
}

- (void)applyAxisValuesToInstance {
	[self ensureInstanceOnly];
	GSFont *font = [self currentFont];
	if (!font) {
		return;
	}
	if ([self usesSyntheticAxis]) {
		NSNumber *value = self.axisValues[DPVFSyntheticAxisID];
		if (value && [self.instance respondsToSelector:@selector(setAxes:)]) {
			#pragma clang diagnostic push
			#pragma clang diagnostic ignored "-Warc-performSelector-leaks"
			[self.instance performSelector:@selector(setAxes:) withObject:@[value]];
			#pragma clang diagnostic pop
		}
		[self.instance updateInterpolationValues];
		return;
	}
	for (GSAxis *axis in [self fontAxes]) {
		NSNumber *value = self.axisValues[axis.axisId];
		if (value) {
			[self.instance setAxisValueValue:value.doubleValue forId:axis.axisId];
		}
	}
	[self.instance updateInterpolationValues];
}

- (void)ensureInstanceOnly {
	if (!self.instance) {
		GSFont *font = [self currentFont];
		self.instance = [[GSInstance alloc] initWithType:GSInstanceTypeSingle];
		self.instance.font = font;
	}
}

- (void)axisValueChangedFromSlider {
	self.liveDragging = YES;
	[self applyAxisValuesToInstance];
	[self.frameCache removeAllObjects];
	[self.panel.previewView setNeedsDisplay:YES];
	[self redrawLive];
	self.liveDragging = NO;
}

- (NSArray<GSLayer *> *)visibleLayers {
	id< GSGlyphEditViewProtocol > graphicView = self.controller.graphicView;
	NSUInteger count = graphicView.cachedLayerCount;
	NSMutableArray<GSLayer *> *layers = [NSMutableArray array];
	for (NSUInteger index = 0; index < count; index++) {
		GSLayer *layer = [graphicView cachedGlyphAtIndex:index];
		if (layer) {
			[layers addObject:layer];
		}
	}
	if (layers.count == 0 && graphicView.activeLayer) {
		[layers addObject:graphicView.activeLayer];
	}
	return layers;
}

- (GSLayer *)masterLayerForGlyph:(GSGlyph *)glyph master:(GSFontMaster *)master {
	id layers = DPVFCall(glyph, @selector(layers));
	if ([layers respondsToSelector:@selector(objectForKeyedSubscript:)]) {
		id layer = [layers objectForKeyedSubscript:master.id];
		if ([layer isKindOfClass:GSLayer.class]) {
			return layer;
		}
	}
	if ([layers respondsToSelector:@selector(objectForKey:)]) {
		id layer = [layers objectForKey:master.id];
		if ([layer isKindOfClass:GSLayer.class]) {
			return layer;
		}
	}
	for (GSLayer *layer in layers) {
		if ([layer.layerId isEqualToString:master.id] || [layer.associatedMasterId isEqualToString:master.id]) {
			return layer;
		}
	}
	return nil;
}

- (BOOL)layersAreDirectCompatible:(NSArray<GSLayer *> *)layers {
	if (layers.count == 0) {
		return NO;
	}
	for (GSLayer *layer in layers) {
		if (layer.isSpecialLayer || layer.anyColorLayer) {
			return NO;
		}
	}
	GSLayer *first = layers.firstObject;
	if ([first.parent respondsToSelector:@selector(mastersCompatibleForLayers:)]) {
		return [first.parent mastersCompatibleForLayers:layers];
	}
	return YES;
}

- (DPVFFrame *)directFrameForGlyph:(GSGlyph *)glyph {
	return [self directFrameForGlyph:glyph seen:[NSMutableSet set]];
}

- (DPVFFrame *)directFrameForGlyph:(GSGlyph *)glyph seen:(NSMutableSet<NSString *> *)seenGlyphs {
	if (!glyph) {
		return nil;
	}
	NSString *seenKey = glyph.name ?: [NSString stringWithFormat:@"%p", glyph];
	if ([seenGlyphs containsObject:seenKey]) {
		return nil;
	}
	[seenGlyphs addObject:seenKey];

	NSDictionary *weights = [self currentInterpolations];
	if (weights.count == 0) {
		[seenGlyphs removeObject:seenKey];
		return nil;
	}
	GSFont *font = [self currentFont];
	NSMutableArray<GSLayer *> *layers = [NSMutableArray array];
	NSMutableArray<NSNumber *> *layerWeights = [NSMutableArray array];
	for (GSFontMaster *master in font.fontMasters) {
		CGFloat weight = [weights[master.id] doubleValue];
		if (fabs(weight) < 0.000001) {
			continue;
		}
		GSLayer *layer = [self masterLayerForGlyph:glyph master:master];
		if (!layer) {
			[seenGlyphs removeObject:seenKey];
			return nil;
		}
		[layers addObject:layer];
		[layerWeights addObject:@(weight)];
	}
	if (![self layersAreDirectCompatible:layers]) {
		[seenGlyphs removeObject:seenKey];
		return nil;
	}

	DPVFFrame *frame = [[DPVFFrame alloc] init];
	frame.bezierPath = [NSBezierPath bezierPath];
	NSMutableArray<DPVFPathFrame *> *pathFrames = [NSMutableArray array];
	CGFloat width = 0.0;
	for (NSUInteger layerIndex = 0; layerIndex < layers.count; layerIndex++) {
		width += layers[layerIndex].width * layerWeights[layerIndex].doubleValue;
	}
	GSLayer *firstLayer = layers.firstObject;
	NSArray *firstPaths = DPVFShapeArray(firstLayer.paths);
	NSUInteger pathCount = firstPaths.count;
	for (NSUInteger pathIndex = 0; pathIndex < pathCount; pathIndex++) {
		NSMutableArray<NSArray<GSNode *> *> *nodeLists = [NSMutableArray array];
		for (GSLayer *layer in layers) {
			NSArray *layerPaths = DPVFShapeArray(layer.paths);
			if (pathIndex >= layerPaths.count) {
				[seenGlyphs removeObject:seenKey];
				return nil;
			}
			GSPath *path = layerPaths[pathIndex];
			[nodeLists addObject:path.nodes ?: @[]];
		}
		NSArray<GSNode *> *sourceNodes = nodeLists.firstObject;
		if (sourceNodes.count == 0) {
			continue;
		}
		DPVFPathFrame *pathFrame = [[DPVFPathFrame alloc] init];
		pathFrame.closed = ((GSPath *)firstPaths[pathIndex]).closed;
		NSMutableArray<DPVFNodeFrame *> *nodes = [NSMutableArray array];
		for (NSUInteger nodeIndex = 0; nodeIndex < sourceNodes.count; nodeIndex++) {
			CGFloat x = 0.0;
			CGFloat y = 0.0;
			for (NSUInteger layerIndex = 0; layerIndex < nodeLists.count; layerIndex++) {
				if (nodeIndex >= nodeLists[layerIndex].count) {
					[seenGlyphs removeObject:seenKey];
					return nil;
				}
				GSNode *node = nodeLists[layerIndex][nodeIndex];
				CGFloat weight = layerWeights[layerIndex].doubleValue;
				x += node.position.x * weight;
				y += node.position.y * weight;
			}
			[nodes addObject:[DPVFNodeFrame nodeWithX:x y:y type:sourceNodes[nodeIndex].type]];
		}
		pathFrame.nodes = nodes;
		[pathFrames addObject:pathFrame];
		[self appendPathFrame:pathFrame toBezierPath:frame.bezierPath];
	}

	NSArray *firstComponents = DPVFShapeArray(firstLayer.components);
	NSUInteger componentCount = firstComponents.count;
	for (NSUInteger componentIndex = 0; componentIndex < componentCount; componentIndex++) {
		GSComponent *firstComponent = firstComponents[componentIndex];
		if (firstComponent.componentLayerKey || DPVFHasPieceSettings(firstComponent)) {
			[seenGlyphs removeObject:seenKey];
			return nil;
		}
		GSGlyph *baseGlyph = firstComponent.component;
		NSString *baseName = firstComponent.componentName ?: baseGlyph.name;
		if (!baseGlyph || baseName.length == 0) {
			[seenGlyphs removeObject:seenKey];
			return nil;
		}
		NSAffineTransformStruct transform = {0, 0, 0, 0, 0, 0};
		for (NSUInteger layerIndex = 0; layerIndex < layers.count; layerIndex++) {
			NSArray *components = DPVFShapeArray(layers[layerIndex].components);
			if (componentIndex >= components.count) {
				[seenGlyphs removeObject:seenKey];
				return nil;
			}
			GSComponent *component = components[componentIndex];
			NSString *componentName = component.componentName ?: component.component.name;
			if (![componentName isEqualToString:baseName] || component.componentLayerKey || DPVFHasPieceSettings(component)) {
				[seenGlyphs removeObject:seenKey];
				return nil;
			}
			CGFloat weight = layerWeights[layerIndex].doubleValue;
			NSAffineTransformStruct componentTransform = component.transformStruct;
			transform.m11 += componentTransform.m11 * weight;
			transform.m12 += componentTransform.m12 * weight;
			transform.m21 += componentTransform.m21 * weight;
			transform.m22 += componentTransform.m22 * weight;
			transform.tX += componentTransform.tX * weight;
			transform.tY += componentTransform.tY * weight;
		}
		DPVFFrame *componentFrame = [self directFrameForGlyph:baseGlyph seen:seenGlyphs];
		if (!componentFrame) {
			[seenGlyphs removeObject:seenKey];
			return nil;
		}
		[self appendFrame:componentFrame transform:transform toPathFrames:pathFrames bezierPath:frame.bezierPath];
	}

	frame.paths = pathFrames;
	frame.width = width;
	[seenGlyphs removeObject:seenKey];
	return frame;
}

- (void)appendPathFrame:(DPVFPathFrame *)pathFrame toBezierPath:(NSBezierPath *)bezierPath {
	NSArray<DPVFNodeFrame *> *nodes = pathFrame.nodes;
	NSUInteger start = NSNotFound;
	for (NSUInteger index = 0; index < nodes.count; index++) {
		if (nodes[index].type != OFFCURVE) {
			start = index;
			break;
		}
	}
	if (start == NSNotFound) {
		return;
	}
	DPVFNodeFrame *startNode = nodes[start];
	[bezierPath moveToPoint:NSMakePoint(startNode.x, startNode.y)];
	NSMutableArray<NSValue *> *pending = [NSMutableArray array];
	NSMutableArray<NSNumber *> *order = [NSMutableArray array];
	if (pathFrame.closed) {
		for (NSUInteger i = start + 1; i < nodes.count; i++) {
			[order addObject:@(i)];
		}
		for (NSUInteger i = 0; i <= start; i++) {
			[order addObject:@(i)];
		}
	}
	else {
		for (NSUInteger i = start + 1; i < nodes.count; i++) {
			[order addObject:@(i)];
		}
	}
	for (NSNumber *number in order) {
		DPVFNodeFrame *node = nodes[number.unsignedIntegerValue];
		NSPoint point = NSMakePoint(node.x, node.y);
		if (node.type == OFFCURVE) {
			[pending addObject:[NSValue valueWithPoint:point]];
			continue;
		}
		if (pending.count >= 2) {
			[bezierPath curveToPoint:point
					   controlPoint1:pending[pending.count - 2].pointValue
					   controlPoint2:pending[pending.count - 1].pointValue];
		}
		else if (pending.count == 1) {
			NSPoint control = pending[0].pointValue;
			[bezierPath curveToPoint:point controlPoint1:control controlPoint2:control];
		}
		else {
			[bezierPath lineToPoint:point];
		}
		[pending removeAllObjects];
	}
	if (pathFrame.closed) {
		[bezierPath closePath];
	}
}

- (void)appendFrame:(DPVFFrame *)componentFrame transform:(NSAffineTransformStruct)transform toPathFrames:(NSMutableArray<DPVFPathFrame *> *)pathFrames bezierPath:(NSBezierPath *)bezierPath {
	for (DPVFPathFrame *sourcePath in componentFrame.paths) {
		DPVFPathFrame *pathFrame = [[DPVFPathFrame alloc] init];
		pathFrame.closed = sourcePath.closed;
		NSMutableArray<DPVFNodeFrame *> *nodes = [NSMutableArray arrayWithCapacity:sourcePath.nodes.count];
		for (DPVFNodeFrame *node in sourcePath.nodes) {
			NSPoint transformed = DPVFTransformPoint(NSMakePoint(node.x, node.y), transform);
			[nodes addObject:[DPVFNodeFrame nodeWithX:transformed.x y:transformed.y type:node.type]];
		}
		pathFrame.nodes = nodes;
		[pathFrames addObject:pathFrame];
		[self appendPathFrame:pathFrame toBezierPath:bezierPath];
	}
}

- (NSDictionary<NSString *, NSNumber *> *)syntheticInterpolations {
	GSFont *font = [self currentFont];
	NSArray<GSFontMaster *> *masters = font.fontMasters ?: @[];
	if (masters.count == 0) {
		return @{};
	}
	if (masters.count == 1) {
		GSFontMaster *master = masters.firstObject;
		return master.id ? @{master.id: @1.0} : @{};
	}
	CGFloat value = [self.axisValues[DPVFSyntheticAxisID] doubleValue];
	NSMutableArray<NSDictionary *> *positions = [NSMutableArray array];
	for (NSUInteger index = 0; index < masters.count; index++) {
		GSFontMaster *master = masters[index];
		[positions addObject:@{
			@"master": master,
			@"position": @([self syntheticAxisValueForMaster:master index:0 fallback:(CGFloat)index])
		}];
	}
	[positions sortUsingComparator:^NSComparisonResult(NSDictionary *left, NSDictionary *right) {
		CGFloat leftValue = [left[@"position"] doubleValue];
		CGFloat rightValue = [right[@"position"] doubleValue];
		if (leftValue < rightValue) {
			return NSOrderedAscending;
		}
		if (leftValue > rightValue) {
			return NSOrderedDescending;
		}
		return NSOrderedSame;
	}];

	NSDictionary *lower = positions.firstObject;
	NSDictionary *upper = positions.lastObject;
	for (NSUInteger index = 0; index + 1 < positions.count; index++) {
		NSDictionary *a = positions[index];
		NSDictionary *b = positions[index + 1];
		CGFloat aPos = [a[@"position"] doubleValue];
		CGFloat bPos = [b[@"position"] doubleValue];
		if (value >= aPos && value <= bPos) {
			lower = a;
			upper = b;
			break;
		}
	}
	if (value < [positions.firstObject[@"position"] doubleValue] && positions.count >= 2) {
		lower = positions[0];
		upper = positions[1];
	}
	else if (value > [positions.lastObject[@"position"] doubleValue] && positions.count >= 2) {
		lower = positions[positions.count - 2];
		upper = positions.lastObject;
	}
	GSFontMaster *lowerMaster = lower[@"master"];
	GSFontMaster *upperMaster = upper[@"master"];
	CGFloat lowerPosition = [lower[@"position"] doubleValue];
	CGFloat upperPosition = [upper[@"position"] doubleValue];
	if (!lowerMaster.id || !upperMaster.id || fabs(upperPosition - lowerPosition) < 0.0001) {
		return lowerMaster.id ? @{lowerMaster.id: @1.0} : @{};
	}
	CGFloat t = (value - lowerPosition) / (upperPosition - lowerPosition);
	return @{
		lowerMaster.id: @(1.0 - t),
		upperMaster.id: @(t)
	};
}

- (NSDictionary<NSString *, NSNumber *> *)currentInterpolations {
	if ([self usesSyntheticAxis]) {
		return [self syntheticInterpolations];
	}
	NSDictionary *weights = self.instance.instanceInterpolations;
	if (weights.count == 0 && [self.instance respondsToSelector:@selector(instanceInterpolationsWithUpdates:)]) {
		weights = [self.instance instanceInterpolationsWithUpdates:NO];
	}
	return weights ?: @{};
}

- (NSString *)axisCacheKey {
	NSMutableArray<NSString *> *parts = [NSMutableArray array];
	for (DPVFAxisRow *row in [self axisRows]) {
		CGFloat value = [self.axisValues[row.axisId] doubleValue];
		[parts addObject:[NSString stringWithFormat:@"%@=%.4f", row.axisId, value]];
	}
	return [parts componentsJoinedByString:@","];
}

- (NSTimeInterval)sourceLastOperationForGlyph:(GSGlyph *)glyph {
	GSFont *font = [self currentFont];
	NSTimeInterval stamp = glyph.lastOperation.timeIntervalSinceReferenceDate;
	for (GSFontMaster *master in font.fontMasters) {
		GSLayer *layer = [self masterLayerForGlyph:glyph master:master];
		if (layer) {
			stamp = MAX(stamp, [layer lastOperation]);
		}
	}
	return stamp;
}

- (NSString *)cacheKeyForGlyph:(GSGlyph *)glyph {
	NSString *name = glyph.name ?: [NSString stringWithFormat:@"%p", glyph];
	return [NSString stringWithFormat:@"%@|%@|%.6f",
			name,
			[self axisCacheKey],
			[self sourceLastOperationForGlyph:glyph]];
}

- (GSLayer *)interpolatedLayerForGlyph:(GSGlyph *)glyph {
	NSError *error = nil;
	NSArray *masters = [self currentFont].fontMasters ?: @[];
	if ([self usesSyntheticAxis]) {
		return [glyph interpolate:[self currentInterpolations] masters:masters decompose:YES error:&error];
	}
	GSLayer *layer = [glyph interpolate:self.instance masters:masters keepSmart:NO smartSettings:nil layerName:nil additionalLayers:nil error:&error];
	return layer;
}

- (DPVFFrame *)frameFromFallbackLayer:(GSLayer *)layer {
	if (!layer) {
		return nil;
	}
	DPVFFrame *frame = [[DPVFFrame alloc] init];
	frame.bezierPath = [layer drawBezierPath];
	frame.width = layer.width;
	NSMutableArray<DPVFPathFrame *> *paths = [NSMutableArray array];
	for (GSPath *path in DPVFShapeArray(layer.paths)) {
		DPVFPathFrame *pathFrame = [[DPVFPathFrame alloc] init];
		pathFrame.closed = path.closed;
		NSMutableArray<DPVFNodeFrame *> *nodes = [NSMutableArray array];
		for (GSNode *node in path.nodes) {
			[nodes addObject:[DPVFNodeFrame nodeWithX:node.position.x y:node.position.y type:node.type]];
		}
		pathFrame.nodes = nodes;
		[paths addObject:pathFrame];
	}
	frame.paths = paths;
	return frame;
}

- (DPVFFrame *)frameForGlyph:(GSGlyph *)glyph {
	[self ensureFontBound];
	NSString *cacheKey = [self cacheKeyForGlyph:glyph];
	DPVFFrame *cached = self.frameCache[cacheKey];
	if (cached) {
		return cached;
	}
	DPVFFrame *frame = [self directFrameForGlyph:glyph];
	if (!frame) {
		frame = [self frameFromFallbackLayer:[self interpolatedLayerForGlyph:glyph]];
	}
	if (frame) {
		self.frameCache[cacheKey] = frame;
	}
	return frame;
}

- (void)drawNodeOverlaysForFrame:(DPVFFrame *)frame scale:(CGFloat)scale {
	NSColor *onCurve = [NSColor colorWithCalibratedRed:0.25 green:0.78 blue:0.35 alpha:0.95];
	NSColor *offCurve = [NSColor colorWithCalibratedRed:0.55 green:0.35 blue:0.88 alpha:0.95];
	NSColor *handle = [NSColor colorWithCalibratedRed:0.45 green:0.75 blue:0.45 alpha:0.85];
	CGFloat radius = 3.0 / MAX(scale, 0.001);
	CGFloat lineWidth = 0.8 / MAX(scale, 0.001);
	for (DPVFPathFrame *path in frame.paths) {
		for (NSUInteger index = 0; index < path.nodes.count; index++) {
			DPVFNodeFrame *node = path.nodes[index];
			if (node.type == OFFCURVE) {
				continue;
			}
			NSArray<NSNumber *> *neighborIndexes = @[];
			if (path.nodes.count > 1) {
				NSMutableArray<NSNumber *> *indexes = [NSMutableArray array];
				if (index > 0) {
					[indexes addObject:@(index - 1)];
				}
				else if (path.closed) {
					[indexes addObject:@(path.nodes.count - 1)];
				}
				if (index + 1 < path.nodes.count) {
					[indexes addObject:@(index + 1)];
				}
				else if (path.closed) {
					[indexes addObject:@0];
				}
				neighborIndexes = indexes;
			}
			for (NSNumber *number in neighborIndexes) {
				DPVFNodeFrame *neighbor = path.nodes[number.unsignedIntegerValue];
				if (neighbor.type != OFFCURVE) {
					continue;
				}
				NSBezierPath *line = [NSBezierPath bezierPath];
				[line moveToPoint:NSMakePoint(node.x, node.y)];
				[line lineToPoint:NSMakePoint(neighbor.x, neighbor.y)];
				line.lineWidth = lineWidth;
				[handle setStroke];
				[line stroke];
			}
		}
	}
	for (DPVFPathFrame *path in frame.paths) {
		for (DPVFNodeFrame *node in path.nodes) {
			NSRect rect = NSMakeRect(node.x - radius, node.y - radius, radius * 2.0, radius * 2.0);
			if (node.type == OFFCURVE) {
				[offCurve setFill];
				NSRectFill(rect);
			}
			else {
				[onCurve setFill];
				[[NSBezierPath bezierPathWithOvalInRect:rect] fill];
			}
		}
	}
}

- (void)drawFrame:(DPVFFrame *)frame scale:(CGFloat)scale forPanel:(BOOL)forPanel {
	if (!frame) {
		return;
	}
	if (forPanel) {
		[[NSColor blackColor] setFill];
	}
	else {
		[[NSColor colorWithCalibratedRed:0.18 green:0.42 blue:0.88 alpha:0.40] setFill];
	}
	[frame.bezierPath fill];
	if (self.showNodes) {
		[self drawNodeOverlaysForFrame:frame scale:scale];
	}
}

- (void)drawPreviewForLayer:(GSLayer *)layer options:(NSDictionary *)options active:(BOOL)active {
	if (!self.drawInEditView || !layer.parent) {
		return;
	}
	NSNumber *onSpace = options[@"OnSpaceDown"];
	if (onSpace.boolValue) {
		return;
	}
	DPVFFrame *frame = [self frameForGlyph:layer.parent];
	if (!frame) {
		return;
	}
	CGFloat scale = DPVFNumber(options[@"Scale"], 1.0);
	CGFloat shift = 0.0;
	if (self.centerPreview) {
		NSRect sourceBounds = layer.bounds;
		NSRect frameBounds = frame.bezierPath.bounds;
		shift = NSMidX(sourceBounds) - NSMidX(frameBounds);
	}
	[NSGraphicsContext saveGraphicsState];
	if (fabs(shift) > 0.001) {
		NSAffineTransform *transform = [NSAffineTransform transform];
		[transform translateXBy:shift yBy:0.0];
		[transform concat];
	}
	[self drawFrame:frame scale:scale forPanel:NO];
	[NSGraphicsContext restoreGraphicsState];
}

- (void)drawBackgroundForLayer:(GSLayer *)layer options:(NSDictionary *)options {
	[self drawPreviewForLayer:layer options:options active:YES];
}

- (void)drawBackgroundForInactiveLayer:(GSLayer *)layer options:(NSDictionary *)options {
	[self drawPreviewForLayer:layer options:options active:NO];
}

- (BOOL)needsExtraMainOutlineDrawingForActiveLayer:(GSLayer *)layer {
	return !self.hideForeground;
}

- (void)redrawLive {
	NSView<GSGlyphEditViewProtocol, NSTextInputClient> *graphicView = self.controller.graphicView;
	if ([graphicView isKindOfClass:NSView.class]) {
		NSView *view = (NSView *)graphicView;
		[view setNeedsDisplay:YES];
		[view display];
	}
	[self.panel.previewView setNeedsDisplay:YES];
	[self.panel.previewView displayIfNeeded];
}

- (void)addMenuItemsForEvent:(NSEvent *)event controller:(NSViewController<GSGlyphEditViewControllerProtocol> *)controller toMenu:(NSMenu *)menu {
	NSMenuItem *hide = [[NSMenuItem alloc] initWithTitle:@"VF Preview: Hide Foreground" action:@selector(toggleHideForeground:) keyEquivalent:@""];
	hide.target = self;
	hide.state = self.hideForeground ? NSControlStateValueOn : NSControlStateValueOff;
	[menu addItem:hide];
	NSMenuItem *center = [[NSMenuItem alloc] initWithTitle:@"VF Preview: Center Preview" action:@selector(toggleCenterPreview:) keyEquivalent:@""];
	center.target = self;
	center.state = self.centerPreview ? NSControlStateValueOn : NSControlStateValueOff;
	[menu addItem:center];
	NSMenuItem *nodes = [[NSMenuItem alloc] initWithTitle:@"VF Preview: Preview Nodes" action:@selector(toggleNodes:) keyEquivalent:@""];
	nodes.target = self;
	nodes.state = self.showNodes ? NSControlStateValueOn : NSControlStateValueOff;
	[menu addItem:nodes];
}

- (void)toggleHideForeground:(id)sender {
	self.hideForeground = !self.hideForeground;
	[self redrawLive];
}

- (void)toggleCenterPreview:(id)sender {
	self.centerPreview = !self.centerPreview;
	[self redrawLive];
}

- (void)toggleNodes:(id)sender {
	self.showNodes = !self.showNodes;
	[self redrawLive];
}

@end
