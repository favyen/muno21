import math
import numpy
import os.path
import skimage.io
import skimage.transform
import sys

sys.path.append('../../python')
from discoverlib import geom, graph

# get points and orientations along the given road segment
def get_points3(rs):
	points3 = []
	for distance in range(0, int(rs.length()), 32):
		edge = rs.distance_to_edge(distance)
		point = rs.point_at_factor(distance)
		orientation = geom.Point(1, 0).signed_angle(edge.segment().vector())
		points3.append((point.x, point.y, orientation))
	return points3

# Load large graphs with caching
graph_cache = {}
def get_graph(graph_dir, region, tile, suffix):
	fname = '{}_{}_{}'.format(region, tile[0], tile[1]) + suffix
	if fname not in graph_cache:
		print('load graph', fname)
		g = graph.read_graph(os.path.join(graph_dir, fname))
		graph_cache[fname] = g.edge_grid_index(128)
	return graph_cache[fname]

# Load large aerial images with caching.
ims = {}
def get_im(jpg_dir, region, tile, get_old=False):
	label = '{}_{}_{}'.format(region, tile[0], tile[1])
	if (label, get_old) not in ims:
		if get_old:
			suffixes = ['_2012.jpg', '_2013.jpg']
		else:
			suffixes = ['_2019.jpg', '_2018.jpg']
		jpg_fname = None
		for suffix in suffixes:
			try_fname = os.path.join(jpg_dir, label+suffix)
			if not os.path.exists(try_fname):
				continue
			jpg_fname = try_fname
			break
		print('loading {} from {}'.format(label, jpg_fname))
		ims[(label, get_old)] = skimage.io.imread(jpg_fname)
	return ims[(label, get_old)]

# Only check the years of the earliest/latest aerial images available.
# But don't actually fetch the images.
def get_image_years(jpg_dir, region, tile):
	try_years = range(2012, 2020)
	years = []
	for year in try_years:
		fname = os.path.join(jpg_dir, '{}_{}_{}_{}.jpg'.format(region, tile[0], tile[1], year))
		if not os.path.exists(fname):
			continue
		years.append(year)
	return years[0], years[-1]

BigRadius = 64
CropSize = 64
zero_crop = numpy.zeros((CropSize, CropSize, 3), dtype='uint8')

def clip(x, lo, hi):
	if x < lo:
		return lo
	elif x > hi:
		return hi
	else:
		return x

# Given an image and oriented points, get crop of image around each point.
# The crop is rotated so that the road in the crop always points to the right.
def get_inputs_from_points(im, points3, train=False, pad=None):
	inputs = []
	if pad is not None:
		points3 = points3[0:pad]
	for p in points3:
		x, y, angle = p
		x = clip(x, BigRadius, im.shape[1]-BigRadius)
		y = clip(y, BigRadius, im.shape[0]-BigRadius)
		big_crop = im[y-BigRadius:y+BigRadius, x-BigRadius:x+BigRadius, :]

		if train:
			# store eight random rotations at different angle offsets
			# and don't crop to the center
			cur_crops = []
			for offset in [-0.2, -0.1, 0.0, 0.1, 0.2]:
				rotated = skimage.transform.rotate(big_crop, (offset+angle)*180/math.pi, preserve_range=True).astype('uint8')
				cur_crops.append(rotated)

			inputs.append(cur_crops)
		else:
			rotated = skimage.transform.rotate(big_crop, angle*180/math.pi, preserve_range=True).astype('uint8')
			crop = rotated[BigRadius-CropSize//2:BigRadius+CropSize//2, BigRadius-CropSize//2:BigRadius+CropSize//2, :]
			inputs.append(crop)

	if pad is not None:
		while len(inputs) < pad:
			inputs.append(zero_crop)

	return inputs

# Returns whether the point3 is close to any edge in the graph grid index.
def is_point_close_to_graph(point3, g_index, threshold):
	p = geom.Point(point3[0], point3[1])
	for edge in g_index.search(p.bounds().add_tol(threshold)):
		if edge.segment().distance(p) > threshold:
			continue
		return True
	return False

# Create a graph from a list of common.Segment.
def make_graph_from_segments(segments):
	g = graph.Graph()
	point_to_vertex = {}
	for segment in segments:
		sx = int(segment['Start']['X'])
		sy = int(segment['Start']['Y'])
		ex = int(segment['End']['X'])
		ey = int(segment['End']['Y'])
		if (sx, sy) == (ex, ey):
			continue
		if (sx, sy) not in point_to_vertex:
			point_to_vertex[(sx, sy)] = g.add_vertex(geom.Point(sx, sy))
		if (ex, ey) not in point_to_vertex:
			point_to_vertex[(ex, ey)] = g.add_vertex(geom.Point(ex, ey))
		g.add_bidirectional_edge(point_to_vertex[(sx, sy)], point_to_vertex[(ex, ey)])
	return g

# get each connected component of the graph, as a subgraph
def get_components(g):
	ngraphs = []
	seen_edge_ids = set()
	for edge in g.edges:
		if edge.id in seen_edge_ids:
			continue
		seen_edge_ids.add(edge.id)
		q = [edge]
		comp_edges = [edge]
		while len(q) > 0:
			cur = q.pop()
			for neighbor in cur.src.in_edges + cur.src.out_edges + cur.dst.in_edges + cur.dst.out_edges:
				if neighbor.id in seen_edge_ids:
					continue
				seen_edge_ids.add(neighbor.id)
				comp_edges.append(neighbor)
				q.append(neighbor)
		ng = graph.graph_from_edges(comp_edges)
		ngraphs.append(ng)
	return ngraphs

# After cropping a road network and getting road segments, we may have road segments
# that exit the crop window and then come back. Because the other roads at the junction
# outside the crop are not captured. This function ensures that these segments are split
# up properly.
# Update: keep this function for now, but decided to update identity/run.py instead
# so identity graphs will make sure that vertices outside the bounds aren't shared across edges
def split_rs_in_rect(road_segments, rect):
	out = []
	for rs in road_segments:
		was_inside = False
		was_outside = False
		last_idx = 0
		for i, edge in enumerate(rs.edges):
			is_inside = rect.contains(edge.src.point) or rect.contains(edge.dst.point)
			is_outside = not rect.contains(edge.dst.point)
			if is_inside and was_inside and was_outside:
				split_rs = graph.RoadSegment(len(out))
				for edge in rs.edges[last_idx:i]:
					split_rs.add_edge(edge, 'forwards')
				out.append(split_rs)
				last_idx = i
				was_inside = True
				was_outside = False
			was_inside = was_inside or is_inside
			# only set was_outside if we were inside before going outside
			# because outside at the very beginning and then going inside is fine
			was_outside = was_outside or (was_inside and is_outside)

		# add final split segment
		split_rs = graph.RoadSegment(len(out))
		for edge in rs.edges[last_idx:]:
			split_rs.add_edge(edge, 'forwards')
		out.append(split_rs)
	return out
