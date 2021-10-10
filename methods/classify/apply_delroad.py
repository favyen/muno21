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

# apply road deletion model, either:
# - delroad, which looks at one timestamp only to target all incorrect/deconstructed roads
# - deconstruct, which compares images but focuses only on deconstructed roads
# this can be run on identity graphs to just do road deletion
# or another method can be run on the delroad outputs to combine the methods
#  (in this case, fusing should be done against the delroad outputs instead of the base graphs...?)

annotation_fname = sys.argv[1]
model_path = sys.argv[2]
jpg_dir = sys.argv[3]
mode = sys.argv[4]
in_dir = sys.argv[5]
out_dir = sys.argv[6]
threshold = float(sys.argv[7])

#annotation_fname = '/mnt/tmp/mapupdate/annotations.json'
#model_path = 'model/delroad/model'
#jpg_dir = '/mnt/tmp/mapupdate/naip/jpg/'
#mode = 'delroad'
#in_dir = '/mnt/tmp/mapupdate/identity/'
#out_dir = '/mnt/tmp/mapupdate/classify/delroad/out/995/'
#threshold = 0.995

#annotation_fname = '/mnt/tmp/mapupdate/annotations.json'
#model_path = 'model/construct/model'
#jpg_dir = '/mnt/tmp/mapupdate/naip/jpg/'
#mode = 'deconstruct'
#in_dir = '/mnt/tmp/mapupdate/identity/'
#out_dir = '/mnt/tmp/mapupdate/classify/deconstruct/out/90/'
#threshold = 0.90

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)

if mode == 'delroad':
	m = model.Model(in_channels=3)
elif mode == 'deconstruct':
	m = model.Model(in_channels=6)

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
	window = cluster['Window']
	rect = geom.Rectangle(
		geom.Point(window[0], window[1]),
		geom.Point(window[2], window[3])
	).add_tol(128)

	im = classify_lib.get_im(jpg_dir, cluster['Region'], cluster['Tile'])
	if mode == 'deconstruct':
		old_im = classify_lib.get_im(jpg_dir, cluster['Region'], cluster['Tile'], get_old=True)

	bad_edges = set()
	seen_rs = set()
	road_segments, _ = graph.get_graph_road_segments(g)
	for rs in road_segments:
		if rs.edges[0].id in seen_rs or rs.edges[0].get_opposite_edge() in seen_rs:
			continue

		seen_rs.add(rs.edges[0].id)
		seen_rs.add(rs.edges[-1].id)

		points3 = classify_lib.get_points3(rs)
		points3 = [p3 for p3 in points3 if rect.contains(geom.Point(p3[0], p3[1]))]
		if not points3:
			# this rs is all outside the rectangle? probably doesn't matter then
			continue
		orig_length = min(len(points3), model.MAX_LENGTH)

		if mode == 'delroad':
			inputs = classify_lib.get_inputs_from_points(im, points3, pad=model.MAX_LENGTH)
		elif mode == 'deconstruct':
			old_inputs = classify_lib.get_inputs_from_points(old_im, points3, pad=model.MAX_LENGTH)
			new_inputs = classify_lib.get_inputs_from_points(im, points3, pad=model.MAX_LENGTH)
			inputs = [numpy.concatenate([new_inputs[i], old_inputs[i]], axis=2) for i in range(model.MAX_LENGTH)]

		prob = session.run(m.probs, feed_dict={
			m.inputs: [inputs],
			m.lengths: [orig_length],
		})[0]

		if prob <= threshold:
			continue

		#print(rs.src().point.sub(window_origin), rs.dst().point.sub(window_origin), prob, [geom.Point(p3[0], p3[1]).sub(rect.start) for p3 in points3])

		# bad rs! remove it
		for edge in rs.edges:
			bad_edges.add(edge)
			bad_edges.add(edge.get_opposite_edge())

	print('removing {} of {} edges'.format(len(bad_edges), len(g.edges)))
	g = g.filter_edges(bad_edges)
	g.save(out_fname)
