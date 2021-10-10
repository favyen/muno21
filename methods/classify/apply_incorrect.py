import json
import math
import numpy
import os
import os.path
import skimage.io
import skimage.transform
import sys
import tensorflow as tf

import classify_lib
import model

sys.path.append('../../python')
from discoverlib import geom, graph

from PIL import Image
Image.MAX_IMAGE_PIXELS = None

# apply incorrect predicted road removal model, either:
# - incorrect, which is trained on examples of correct/incorrect roads inferred in the training set
# - construct, which removes roads that do not seem to be new construction based on comparing old/new images
# to run this method:
# (1) run another map update method
# (2) run remove_ignore_segments on the outputs
# (3) run fuse on the outputs, but in the onlynew mode so the base graph is discarded
# then this can be run on the "fused" graphs
# and finally the resulting graphs should be fused with the base graphs

annotation_fname = sys.argv[1]
model_path = sys.argv[2]
jpg_dir = sys.argv[3]
mode = sys.argv[4]
in_dir = sys.argv[5]
out_dir = sys.argv[6]

#annotation_fname = '/mnt/tmp/mapupdate/annotations.json'
#model_path = 'model/incorrect/model'
#jpg_dir = '/mnt/tmp/mapupdate/naip/jpg/'
#mode = 'incorrect'
#in_dir = '/mnt/tmp/mapupdate/roadtracerpp/normal/infer/out-remove-fuse-onlynew/60/'
#out_dir = '/mnt/tmp/mapupdate/roadtracerpp/normal/infer/filter-incorrect/60/'

#annotation_fname = '/mnt/tmp/mapupdate/annotations.json'
#model_path = 'model/construct/model'
#jpg_dir = '/mnt/tmp/mapupdate/naip/jpg/'
#mode = 'construct'
#in_dir = '/mnt/tmp/mapupdate/roadtracerpp/normal/infer/out-remove-fuse-onlynew/60/'
#out_dir = '/mnt/tmp/mapupdate/roadtracerpp/normal/infer/filter-construct/60/'

print(in_dir, out_dir)

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)

# threshold_func returns True if the probability indicates we should remove the road
if mode == 'incorrect':
	m = model.Model(in_channels=3)
	threshold_func = lambda prob: prob > 0.5
elif mode == 'construct':
	m = model.Model(in_channels=6)
	threshold_func = lambda prob: prob < 0.5

config = tf.ConfigProto()
config.gpu_options.allow_growth = True
session = tf.Session(config=config)
m.saver.restore(session, model_path)

for annotation_idx, annotation in enumerate(annotations):
	in_fname = os.path.join(in_dir, '{}.graph'.format(annotation_idx))
	out_fname = os.path.join(out_dir, '{}.graph'.format(annotation_idx))
	if not os.path.exists(in_fname) or os.path.exists(out_fname):
		continue

	print(annotation_idx, '/', len(annotations))
	g = graph.read_graph(in_fname)
	cluster = annotation['Cluster']
	im = classify_lib.get_im(jpg_dir, cluster['Region'], cluster['Tile'])
	if mode == 'construct':
		old_im = classify_lib.get_im(jpg_dir, cluster['Region'], cluster['Tile'], get_old=True)

	if mode == 'construct':
		good_edges = []

		# in each connected component, check if at least one edge is correct
		# if so, we retain the component
		# if ALL the edges are INCORRECT, then we remove the component
		components = classify_lib.get_components(g)
		retained_components = 0
		for subg in components:
			bad_edges = set()
			seen_rs = set()
			road_segments, _ = graph.get_graph_road_segments(subg)
			any_correct = False
			for rs in road_segments:
				if rs.edges[0].id in seen_rs or rs.edges[0].get_opposite_edge() in seen_rs:
					continue

				seen_rs.add(rs.edges[0].id)
				seen_rs.add(rs.edges[-1].id)

				points3 = classify_lib.get_points3(rs)
				orig_length = min(len(points3), model.MAX_LENGTH)

				if mode == 'incorrect':
					inputs = classify_lib.get_inputs_from_points(im, points3, pad=model.MAX_LENGTH)
				elif mode == 'construct':
					old_inputs = classify_lib.get_inputs_from_points(old_im, points3, pad=model.MAX_LENGTH)
					new_inputs = classify_lib.get_inputs_from_points(im, points3, pad=model.MAX_LENGTH)
					inputs = [numpy.concatenate([old_inputs[i], new_inputs[i]], axis=2) for i in range(model.MAX_LENGTH)]

				prob = session.run(m.probs, feed_dict={
					m.inputs: [inputs],
					m.lengths: [orig_length],
				})[0]

				if threshold_func(prob):
					continue

				any_correct = True
				break

			if not any_correct:
				# don't retain this component!
				continue

			retained_components += 1
			for edge in subg.edges:
				good_edges.append(edge)

		ng = graph.graph_from_edges(good_edges)
		print('pruning from {} to {} edges (retained {} of {} components)'.format(len(g.edges), len(ng.edges), retained_components, len(components)))
		ng.save(out_fname)

	if mode == 'incorrect':
		bad_edges = set()
		seen_rs = set()
		road_segments, _ = graph.get_graph_road_segments(g)
		for rs in road_segments:
			if rs.edges[0].id in seen_rs or rs.edges[0].get_opposite_edge() in seen_rs:
				continue

			seen_rs.add(rs.edges[0].id)
			seen_rs.add(rs.edges[-1].id)

			points3 = classify_lib.get_points3(rs)
			orig_length = min(len(points3), model.MAX_LENGTH)

			if mode == 'incorrect':
				inputs = classify_lib.get_inputs_from_points(im, points3, pad=model.MAX_LENGTH)
			elif mode == 'construct':
				old_inputs = classify_lib.get_inputs_from_points(old_im, points3, pad=model.MAX_LENGTH)
				new_inputs = classify_lib.get_inputs_from_points(im, points3, pad=model.MAX_LENGTH)
				inputs = [numpy.concatenate([old_inputs[i], new_inputs[i]], axis=2) for i in range(model.MAX_LENGTH)]

			prob = session.run(m.probs, feed_dict={
				m.inputs: [inputs],
				m.lengths: [orig_length],
			})[0]

			if not threshold_func(prob):
				continue

			# bad rs! remove it
			for edge in rs.edges:
				bad_edges.add(edge)
				bad_edges.add(edge.get_opposite_edge())

		print('removing {} of {} edges'.format(len(bad_edges), len(g.edges)))
		g = g.filter_edges(bad_edges)
		g.save(out_fname)
