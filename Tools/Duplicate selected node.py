# MenuTitle: Duplicate selected node
# -*- coding: utf-8 -*-

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