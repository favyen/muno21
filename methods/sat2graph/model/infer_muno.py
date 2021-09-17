import json
import os
import os.path
import scipy.misc
import math
import cv2
import numpy as np
import tensorflow as tf
from time import time
import sys
import skimage.io

from model import Sat2GraphModel
from decoder import DecodeAndVis
from douglasPeucker import simpilfyGraph

sys.path.append('../../python')
from discoverlib import geom
from discoverlib import graph as munograph

from PIL import Image
Image.MAX_IMAGE_PIXELS = None

model_path = sys.argv[1]
jpg_dir = sys.argv[2]
annotation_fname = sys.argv[3]
test_fname = sys.argv[4]
out_dir = sys.argv[5]

base_graph_suffix = '_2013-07-01.graph'
im_suffix = ['_2020.jpg', '_2019.jpg', '_2018.jpg']

# load model
sess = tf.Session()
print('initializing model')
model = Sat2GraphModel(sess, image_size=352, resnet_step = 8, batchsize = 1, channel = 12, mode = "test")
print('restoring model')
model.restoreModel(model_path)

# some variables/constants
gt_prob_placeholder = np.zeros((1,352,352,14))
gt_vector_placeholder = np.zeros((1,352,352,12))
gt_seg_placeholder = np.zeros((1,352,352,1))
snap_dist = 15
snap_w = 50

# loop over annotations
print('load annotations')
with open(annotation_fname, 'r') as f:
	annotations = json.load(f)
with open(test_fname, 'r') as f:
	test_regions =json.load(f)

ims = {}
def get_im(k):
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
		im = skimage.io.imread(jpg_fname)
		ims[k] = im

	return ims[k]

PADDING = 128
thresholds = [2, 4, 5, 6, 8, 10, 15, 20]

for annotation_idx, annotation in enumerate(annotations):
	cluster = annotation['Cluster']
	if cluster['Region'] not in test_regions:
		continue

	out_fname = os.path.join(out_dir, str(thresholds[-1]), '{}.graph'.format(annotation_idx))
	if os.path.exists(out_fname):
		continue

	k = '{}_{}_{}'.format(cluster['Region'], cluster['Tile'][0], cluster['Tile'][1])
	print('process annotation {} at {}'.format(annotation_idx, k))
	im = get_im(k)

	window = cluster['Window']
	rect = geom.Rectangle(
		geom.Point(max(window[0], PADDING), max(window[1], PADDING)),
		geom.Point(min(window[2], im.shape[1]-PADDING), min(window[3], im.shape[0]-PADDING))
	).add_tol(PADDING)

	sat_img = np.zeros((2048, 2048, 3), dtype='uint8')
	lx = min(2048, rect.end.x-rect.start.x)
	ly = min(2048, rect.end.y-rect.start.y)
	sat_img[0:ly, 0:lx, :] = im[rect.start.y:rect.start.y+ly, rect.start.x:rect.start.x+lx, :]

	max_v = 255
	sat_img = (sat_img.astype(np.float)/ max_v - 0.5) * 0.9
	sat_img = sat_img.reshape((1,2048,2048,3))

	image_size = 352

	weights = np.ones((image_size,image_size, 2+4*6 + 2)) * 0.001
	weights[32:image_size-32,32:image_size-32, :] = 0.5
	weights[56:image_size-56,56:image_size-56, :] = 1.0
	weights[88:image_size-88,88:image_size-88, :] = 1.5

	mask = np.zeros((2048+64, 2048+64, 2+4*6 + 2))
	output = np.zeros((2048+64, 2048+64, 2+4*6 + 2))
	sat_img = np.pad(sat_img, ((0,0),(32,32),(32,32),(0,0)), 'constant')

	for x in range(0,352*6-176-88,176//2):
		for y in range(0,352*6-176-88,176//2):

			alloutputs  = model.Evaluate(sat_img[:,x:x+image_size, y:y+image_size,:], gt_prob_placeholder, gt_vector_placeholder, gt_seg_placeholder)
			_output = alloutputs[1]

			mask[x:x+image_size, y:y+image_size, :] += weights
			output[x:x+image_size, y:y+image_size,:] += np.multiply(_output[0,:,:,:], weights)


	output = np.divide(output, mask)
	output = output[32:2048+32,32:2048+32,:]
	output_file = '/tmp/sat2graph.p'

	for threshold in thresholds:
		graph = DecodeAndVis(output, output_file, thr=threshold/100, edge_thr=threshold/100, angledistance_weight=snap_w, snap_dist = snap_dist, snap=True, imagesize = 2048)
		graph = simpilfyGraph(graph)

		g = munograph.Graph()
		vertex_map = {}
		for k in graph.keys():
			p = geom.Point(rect.start.x+k[1], rect.start.y+k[0])
			vertex_map[k] = g.add_vertex(p)
		for n1, v in graph.items():
			for n2 in v:
				g.add_bidirectional_edge(vertex_map[n1], vertex_map[n2])
		out_fname = os.path.join(out_dir, str(threshold), '{}.graph'.format(annotation_idx))
		g.save(out_fname)
