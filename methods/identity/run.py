import json
import os
import os.path
import sys

# Identity method.
# Just outputs the old graph.
# This is useful because it does crop the old graph,
# so we just end up with graph in the scenario windows.

sys.path.append('../../python')
from discoverlib import geom, graph

graph_dir = sys.argv[1]
annotation_fname = sys.argv[2]
out_dir = sys.argv[3]

base_graph_suffix = '_2013-07-01.graph'

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)

graphs = {}
def get_graph(cluster):
	k = '{}_{}_{}'.format(cluster['Region'], cluster['Tile'][0], cluster['Tile'][1])
	if k not in graphs:
		graph_fname = os.path.join(graph_dir, k+base_graph_suffix)
		print('loading graph at {} from {}'.format(k, graph_fname))
		g = graph.read_graph(graph_fname)
		g_idx = g.edge_grid_index(128)
		graphs[k] = (g, g_idx)
	return graphs[k]

for annotation_idx, annotation in enumerate(annotations):
	cluster = annotation['Cluster']

	out_fname = os.path.join(out_dir, '{}.graph'.format(annotation_idx))
	if os.path.exists(out_fname):
		continue

	g, g_idx = get_graph(cluster)

	window = cluster['Window']
	total_padding = 128 + 64
	rect = geom.Rectangle(
		geom.Point(window[0], window[1]),
		geom.Point(window[2], window[3])
	).add_tol(total_padding)

	# we use a custom graph_from_edges function here because we want to make sure
	# that vertices outside the rect bounds are considered junctions
	# (in particular, we should not end up with road segments that start in the bounds,
	# then go out of rect, then come back in; unless the road was actually like that in
	# the original graph)
	# to do so, we just make sure that when we incorporate edges with one vertex outside
	# the bounds, that vertex is separate from the vertex of any other edge
	#g = graph.graph_from_edges(g_idx.search(rect))
	ng = graph.Graph()
	vertex_map = {}
	used_points = set()
	seen_edge_ids = set()
	for edge in g_idx.search(rect):
		if edge.id in seen_edge_ids:
			continue

		for vertex in [edge.src, edge.dst]:
			if vertex not in vertex_map:
				vertex_map[vertex] = ng.add_vertex(vertex.point)
				used_points.add(vertex.point)
				continue
			if rect.contains(vertex.point):
				continue
			# this vertex is out of bounds and we are about to reuse it
			# so instead we create a new vertex
			good_point = None
			for offset_x in [0, -3, 3, -6, 6]:
				for offset_y in [0, -3, 3, -6, 6]:
					try_point = vertex.point.add(geom.Point(offset_x, offset_y))
					if try_point not in used_points:
						good_point = try_point
						break
				if good_point:
					break
			if good_point is None:
				good_point = vertex.point
			used_points.add(good_point)
			vertex_map[vertex] = ng.add_vertex(good_point)

		nedge = ng.add_bidirectional_edge(vertex_map[edge.src], vertex_map[edge.dst])
		seen_edge_ids.add(edge.id)
		seen_edge_ids.add(edge.get_opposite_edge().id)

	ng.save(out_fname)
