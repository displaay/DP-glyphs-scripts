# MenuTitle: Duplicate selected node
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Displaay Type Foundry. All rights reserved.

__doc__ = """
Duplicates the selected on-curve node as a new line segment inserted after it
on the path.
"""

node = Layer.selection[0]

print(node)
if isinstance(node, GSNode): 
	if node.type == LINE or node.type == CURVE:
		node.smooth = False
		newNode = node.copy()
		newNode.type = LINE
		path = node.parent
		path.nodes.insert(node.index + 1, newNode)
else:
	print("select one node")
