import model

import json
import numpy
import os.path
import random
import skimage.io
import subprocess
import sys
import tensorflow as tf
import time

sys.path.append('../../python')
from discoverlib import geom, graph

from PIL import Image
Image.MAX_IMAGE_PIXELS = None

model_path = sys.argv[1]
jpg_dir = sys.argv[2]
annotation_fname = sys.argv[3]
test_fname = sys.argv[4]
out_dir = sys.argv[5]

m = model.Model(big=True)
session = tf.Session()
m.saver.restore(session, model_path)

def apply_model(sat):
	output = numpy.zeros((sat.shape[0], sat.shape[1]), dtype='uint8')
	for x in list(range(0, sat.shape[0] - 2048, 512)) + [sat.shape[0] - 2048]:
		for y in list(range(0, sat.shape[1] - 2048, 512)) + [sat.shape[1] - 2048]:
			conv_input = sat[x:x+2048, y:y+2048, :].astype('float32') / 255.0
			conv_output = session.run(m.outputs, feed_dict={
				m.is_training: False,
				m.inputs: [conv_input],
			})[0, :, :]
			startx = (2048 - 512) // 2
			endx = (2048 + 512) // 2
			starty = (2048 - 512) // 2
			endy = (2048 + 512) // 2
			if x == 0:
				startx = 0
			elif x >= sat.shape[0] - 2048 - 512 - 1:
				endx = 2048
			if y == 0:
				starty = 0
			elif y >= sat.shape[1] - 2048 - 512 - 1:
				endy = 2048
			output[x+startx:x+endx, y+starty:y+endy] = conv_output[startx:endx, starty:endy] * 255.0
	return output

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)
with open(test_fname, 'r') as f:
	test_regions = json.load(f)

ims = {}
def get_im(cluster):
	k = '{}_{}_{}'.format(cluster['Region'], cluster['Tile'][0], cluster['Tile'][1])
	if k not in ims:
		jpg_fname = None
		for suffix in ['_2019.jpg', '_2018.jpg']:
			path = os.path.join(jpg_dir, k+suffix)
			if not os.path.exists(path):
				continue
			jpg_fname = path
			break
		if jpg_fname is None:
			raise Exception('cannot find any suitable image for label {}'.format(k))
		print('loading image at {} from {}'.format(k, jpg_fname))
		im = skimage.io.imread(jpg_fname)
		ims.clear()
		ims[k] = im
	return ims[k]

thresholds = [60, 80, 100, 120, 140, 160, 180]

for annotation_idx, annotation in enumerate(annotations):
	cluster = annotation['Cluster']
	if cluster['Region'] not in test_regions:
		continue

	out_fname = os.path.join(out_dir, str(thresholds[-1]), '{}.graph'.format(annotation_idx))
	if os.path.exists(out_fname):
		continue

	print(annotation_idx, '/', len(annotations))

	im = get_im(cluster)
	window = cluster['Window']
	padding = 128+64
	sx = max(window[0]-padding, 0)
	sy = max(window[1]-padding, 0)
	ex = min(window[2]+padding, im.shape[1])
	ey = min(window[3]+padding, im.shape[0])

	crop = im[sy:ey, sx:ex, :]
	if crop.shape[0] < 2048 or crop.shape[1] < 2048:
		lx = max(2048, crop.shape[1])
		ly = max(2048, crop.shape[0])
		ncrop = numpy.zeros((ly, lx, 3), dtype='uint8')
		ncrop[0:crop.shape[0], 0:crop.shape[1], :] = crop
		crop = ncrop

	output = apply_model(crop)

	out_im_fname = os.path.join(out_dir, '{}.png'.format(annotation_idx))
	skimage.io.imsave(out_im_fname, output)

	for threshold in thresholds:
		out_fname = os.path.join(out_dir, str(threshold), '{}.graph'.format(annotation_idx))
		out_tmp_fname = os.path.join(out_dir, str(threshold), '{}_tmp.graph'.format(annotation_idx))
		subprocess.call(['python3', '../../python/discoverlib/mapextract.py', out_im_fname, str(threshold), out_tmp_fname])
		g = graph.read_graph(out_tmp_fname)
		for vertex in g.vertices:
			vertex.point = vertex.point.add(geom.Point(sx, sy))
		g.save(out_fname)
