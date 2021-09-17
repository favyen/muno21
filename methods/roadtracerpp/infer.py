import json
import numpy
import math
import os
import os.path
import random
import skimage.io
import skimage.morphology
import sys
import tensorflow as tf
import time

sys.path.append('../../python')
from discoverlib import geom, graph, tf_util
import model
import model_utils

from PIL import Image
Image.MAX_IMAGE_PIXELS = None

MAX_PATH_LENGTH = 1000000
SEGMENT_LENGTH = 12
THRESHOLD_BRANCH = 0.3
THRESHOLD_FOLLOW = 0.3
WINDOW_SIZE = 256

def vector_to_action(extension_vertex, angle_outputs, threshold):
	# mask out buckets that are similar to existing edges
	blacklisted_buckets = set()
	for edge in extension_vertex.out_edges:
		angle = geom.Point(1, 0).signed_angle(edge.segment().vector())
		bucket = int((angle + math.pi) * 64.0 / math.pi / 2)
		for offset in range(6):
			clockwise_bucket = (bucket + offset) % 64
			counterclockwise_bucket = (bucket + 64 - offset) % 64
			blacklisted_buckets.add(clockwise_bucket)
			blacklisted_buckets.add(counterclockwise_bucket)

	seen_vertices = set()
	search_queue = []
	nearby_points = {}
	seen_vertices.add(extension_vertex)
	for edge in extension_vertex.out_edges:
		search_queue.append((graph.EdgePos(edge, 0), 0))
	while len(search_queue) > 0:
		edge_pos, distance = search_queue[0]
		search_queue = search_queue[1:]
		if distance > 0:
			nearby_points[edge_pos.point()] = distance
		if distance >= 4 * SEGMENT_LENGTH:
			continue

		edge = edge_pos.edge
		l = edge.segment().length()
		if edge_pos.distance + SEGMENT_LENGTH < l:
			search_queue.append((graph.EdgePos(edge, edge_pos.distance + SEGMENT_LENGTH), distance + SEGMENT_LENGTH))
		elif edge.dst not in seen_vertices:
			seen_vertices.add(edge.dst)
			for edge in edge.dst.out_edges:
				search_queue.append((graph.EdgePos(edge, 0), distance + l - edge_pos.distance))

	# any leftover targets above threshold?
	best_bucket = None
	best_value = None
	for bucket in range(64):
		if bucket in blacklisted_buckets:
			continue
		next_point = model_utils.get_next_point(extension_vertex.point, bucket, SEGMENT_LENGTH)
		bad = False
		for nearby_point, distance in nearby_points.items():
			if nearby_point.distance(next_point) < 0.5 * (SEGMENT_LENGTH + distance):
				bad = True
				break
		if bad:
			continue

		value = angle_outputs[bucket]
		if value > threshold and (best_bucket is None or value > best_value):
			best_bucket = bucket
			best_value = value

	x = numpy.zeros((64,), dtype='float32')
	if best_bucket is not None:
		x[best_bucket] = best_value
	return x

def eval(paths, m, session, max_path_length=MAX_PATH_LENGTH, segment_length=SEGMENT_LENGTH, save=False, compute_targets=True, max_batch_size=model.BATCH_SIZE, window_size=WINDOW_SIZE, verbose=True, threshold_override=None, cache_m6=None):
	path_lengths = {path_idx: 0 for path_idx in range(len(paths))}

	last_time = None
	big_time = None

	last_extended = False

	for len_it in range(99999999):
		if len_it % 500 == 0 and verbose:
			print('it {}'.format(len_it))
			big_time = time.time()
		path_indices = []
		extension_vertices = []
		for path_idx in range(len(paths)):
			if path_lengths[path_idx] >= max_path_length:
				continue
			extension_vertex = paths[path_idx].pop()
			if extension_vertex is None:
				continue
			path_indices.append(path_idx)
			path_lengths[path_idx] += 1
			extension_vertices.append(extension_vertex)

			if len(path_indices) >= max_batch_size:
				break

		if len(path_indices) == 0:
			break

		batch_inputs = []
		batch_detect_targets = []
		batch_angle_targets = numpy.zeros((len(path_indices), 64), 'float32')
		inputs_per_path = 1

		for i in range(len(path_indices)):
			path_idx = path_indices[i]

			path_input, path_detect_target = model_utils.make_path_input(paths[path_idx], extension_vertices[i], segment_length, window_size=window_size)
			if type(path_input) == list:
				batch_inputs.extend([x[:, :, 0:3] for x in path_input])
				inputs_per_path = len(path_input)
				#batch_inputs.append(numpy.concatenate([x[:, :, 0:3] for x in path_input], axis=2))
			else:
				batch_inputs.append(path_input[:, :, 0:3])
			#batch_detect_targets.append(path_detect_target)
			batch_detect_targets.append(numpy.zeros((64, 64, 1), dtype='float32'))

			if compute_targets:
				angle_targets, _ = model_utils.compute_targets_by_best(paths[path_idx], extension_vertices[i], segment_length)
				batch_angle_targets[i, :] = angle_targets

		p = extension_vertices[0].point.sub(paths[0].tile_data['rect'].start).scale(0.25)
		batch_angle_outputs = numpy.array([cache_m6[p.x, p.y, :]], dtype='float32')

		if inputs_per_path > 1:
			actual_outputs = numpy.zeros((len(path_indices), 64), 'float32')
			for i in range(len(path_indices)):
				actual_outputs[i, :] = batch_angle_outputs[i*inputs_per_path:(i+1)*inputs_per_path, :].max(axis=0)
			batch_angle_outputs = actual_outputs

		if (save is True and len_it % 1 == 0) or (save == 'extends' and last_extended):
			fname = '/home/ubuntu/data/{}_'.format(len_it)
			save_angle_targets = batch_angle_targets[0, :]
			if not compute_targets:
				save_angle_targets = None
			#if numpy.max(batch_angle_outputs[0, :]) > 0.1:
			#	batch_angle_outputs[0, :] *= 1.0 / numpy.max(batch_angle_outputs[0, :])
			model_utils.make_path_input(paths[path_indices[0]], extension_vertices[0], segment_length, fname=fname, angle_targets=save_angle_targets, angle_outputs=batch_angle_outputs[0, :], window_size=window_size)

			with open(fname + 'meta.txt', 'w') as f:
				f.write('max angle output: {}\n'.format(batch_angle_outputs[0, :].max()))

		for i in range(len(path_indices)):
			path_idx = path_indices[i]
			if len(extension_vertices[i].out_edges) >= 2:
				threshold = THRESHOLD_BRANCH
			else:
				threshold = THRESHOLD_FOLLOW
			if threshold_override is not None:
				threshold = threshold_override

			x = vector_to_action(extension_vertices[i], batch_angle_outputs[i, :], threshold)
			last_extended = x.max() > 0
			paths[path_idx].push(extension_vertices[i], x, segment_length, training=False, branch_threshold=0.01, follow_threshold=0.01)

	if save:
		paths[0].graph.save('out.graph')

	return len_it

def graph_filter(g, threshold=0.3, min_len=None):
	road_segments, _ = graph.get_graph_road_segments(g)
	bad_edges = set()
	for rs in road_segments:
		if min_len is not None and len(rs.edges) < min_len:
			bad_edges.update(rs.edges)
			continue
		probs = []
		if len(rs.edges) < 5 or True:
			for edge in rs.edges:
				if hasattr(edge, 'prob'):
					probs.append(edge.prob)
		else:
			for edge in rs.edges[2:-2]:
				if hasattr(edge, 'prob'):
					probs.append(edge.prob)
		if not probs:
			continue
		avg_prob = numpy.mean(probs)
		if avg_prob < threshold:
			bad_edges.update(rs.edges)
	print('filtering {} edges'.format(len(bad_edges)))
	ng = graph.Graph()
	vertex_map = {}
	for vertex in g.vertices:
		vertex_map[vertex] = ng.add_vertex(vertex.point)
	for edge in g.edges:
		if edge not in bad_edges:
			ng.add_edge(vertex_map[edge.src], vertex_map[edge.dst])
	return ng

if __name__ == '__main__':
	import sys
	model_path = sys.argv[1]
	jpg_dir = sys.argv[2]
	graph_dir = sys.argv[3]
	annotation_fname = sys.argv[4]
	test_fname = sys.argv[5]
	out_dir = sys.argv[6]
	mode = sys.argv[7] # either extend or infer
	threshold = sys.argv[8]

	THRESHOLD_BRANCH = float(threshold)
	THRESHOLD_FOLLOW = float(threshold)

	base_graph_suffix = '_2013-07-01.graph'
	im_suffix = ['_2020.jpg', '_2019.jpg', '_2018.jpg']
	old_im_suffix = ['_2013.jpg', '_2012.jpg']

	print('initializing model')
	m = model.Model(bn=True, size=2048)
	config = tf.ConfigProto()
	config.gpu_options.allow_growth = True
	session = tf.Session(config=config)
	m.saver.restore(session, model_path)

	with open(annotation_fname, 'r') as f:
		annotations = json.load(f)
	with open(test_fname, 'r') as f:
		test_regions = json.load(f)

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

	ims = {}
	def get_im(cluster):
		k = '{}_{}_{}'.format(cluster['Region'], cluster['Tile'][0], cluster['Tile'][1])
		if k not in ims:
			jpg_fname = None
			for suffix in im_suffix:
				path = os.path.join(jpg_dir, k+suffix)
				if not os.path.exists(path):
					continue
				jpg_fname = path
				break
			if jpg_fname is None:
				raise Exception('cannot find any suitable image for label {}'.format(k))
			print('loading image at {} from {}'.format(k, jpg_fname))
			im = skimage.io.imread(jpg_fname).swapaxes(0, 1)

			print('cache_m6: begin')
			start_time = time.time()
			cache_m6 = tf_util.apply_conv(session, m, im, scale=4, channels=64)
			print('cache_m6: conv in {} sec'.format(time.time() - start_time))

			if mode == 'maintain':
				old_jpg_fname = None
				for suffix in old_im_suffix:
					path = os.path.join(jpg_dir, k+suffix)
					if not os.path.exists(path):
						continue
					old_jpg_fname = path
					break
				if old_jpg_fname is None:
					raise Exception('cannot find any suitable OLD image for label {}'.format(k))
				print('loading OLD image at {} from {}'.format(k, old_jpg_fname))
				old_im = skimage.io.imread(old_jpg_fname).swapaxes(0, 1)

				print('cache_m6: begin OLD')
				start_time = time.time()
				old_m6 = tf_util.apply_conv(session, m, old_im, scale=4, channels=64)
				print('cache_m6: conv OLD in {} sec'.format(time.time() - start_time))

				m6_mask = old_m6 > 0.4
				m6_mask = m6_mask.reshape((-1, 64))
				m6_mask = numpy.concatenate([m6_mask, m6_mask], axis=1)
				m6_mask = skimage.morphology.binary_dilation(m6_mask, numpy.ones((1, 5), dtype='bool'))
				m6_mask = numpy.concatenate([m6_mask[:, 64:96], m6_mask[:, 32:64]], axis=1).reshape((old_m6.shape[0], old_m6.shape[1], 64)).astype('float32')
				m6_mask = 1-m6_mask
				cache_m6 *= m6_mask
				print('cache_m6 done combining OLD and new cool')

			ims.clear()
			ims[k] = (im, cache_m6)

		return ims[k]

	for annotation_idx, annotation in enumerate(annotations):
		cluster = annotation['Cluster']
		if cluster['Region'] not in test_regions:
			continue

		out_fname = os.path.join(out_dir, '{}.graph'.format(annotation_idx))
		if os.path.exists(out_fname):
			continue

		g, g_idx = get_graph(cluster)
		im, cache_m6 = get_im(cluster)

		window = cluster['Window']
		# pad 128 for the scenario, and another WINDOW_SIZE/2 for RoadTracer
		total_padding = 128 + WINDOW_SIZE//2
		rect = geom.Rectangle(
			geom.Point(max(window[0], total_padding), max(window[1], total_padding)),
			geom.Point(min(window[2], im.shape[0]-total_padding), min(window[3], im.shape[1]-total_padding))
		).add_tol(total_padding)

		tile_data = {
			'rect': geom.Rectangle(
				geom.Point(0, 0),
				geom.Point(im.shape[0], im.shape[1]),
			),
			'search_rect': rect.add_tol(-WINDOW_SIZE//2),
			'big_ims': {'input': im},
		}

		if mode == 'extend' or mode == 'maintain':
			g = graph.graph_from_edges(g_idx.search(rect))
			graph.densify(g, SEGMENT_LENGTH)
			path = model_utils.Path(None, tile_data, g=g)

			for vertex in g.vertices:
				vertex.edge_pos = None
				path.prepend_search_vertex(vertex)

			eval([path], m, session, save=False, compute_targets=False, cache_m6=cache_m6)
			path.graph.save(out_fname)
		elif mode == 'infer':
			# use ng for starting locations
			ng = graph.graph_from_edges(g_idx.search(rect))
			pg = graph.Graph()
			path = model_utils.Path(None, tile_data, g=pg)
			for edge in ng.edges:
				r = edge.segment().bounds().add_tol(64)
				nearby_edges = path.edge_rtree.intersection((r.start.x, r.start.y, r.end.x, r.end.y))
				if len(list(nearby_edges)) > 0:
					continue
				v1 = pg.add_vertex(edge.src.point)
				v2 = pg.add_vertex(edge.dst.point)
				v1.edge_pos = None
				v2.edge_pos = None
				path.prepend_search_vertex(v1)
				path.prepend_search_vertex(v2)
				eval([path], m, session, save=False, compute_targets=False, cache_m6=cache_m6)

			path.graph.save(out_fname)
		else:
			raise Exception('invalid mode {}'.format(mode))
