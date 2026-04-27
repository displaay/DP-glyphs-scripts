# MenuTitle: Fill Up Intermediate Layers 
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.


import itertools

axes_coords = [[] for axis in Font.axes]

for layer in Font.selectedLayers:
	special_layers = [special_layer for special_layer in layer.parent.layers if special_layer.isSpecialLayer]

	for i, axis in enumerate(Font.axes):
		for special_layer in special_layers:
			special_layer_coordinates = special_layer.attributes["coordinates"]
			if list(special_layer_coordinates.values())[i] not in axes_coords[i]:
				axes_coords[i].append(list(special_layer_coordinates.values())[i])

	existing_special_layers = [tuple(special_layer.attributes["coordinates"].values()) for special_layer in special_layers]

	necessary_coords = list(itertools.product(*axes_coords))

	missing_coords = [coord for coord in necessary_coords if coord not in existing_special_layers]

	for coord in missing_coords:
		coord_layer = GSLayer()
		coord_layer.attributes["coordinates"] = {Font.axes[0].axisId: coord[0], Font.axes[1].axisId: coord[1]}
		if coord[1]:
			coord_layer.associatedMasterId = Font.masters[2].id
		else:
			coord_layer.associatedMasterId = Font.masters[0].id
			coord_layer.color = 6
			layer.parent.layers.append(coord_layer)
			coord_layer.reinterpolate()

print ("done!")
