from __future__ import print_function

import argparse
import json
import os
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data as data
from model.models import MODELS
from road_dataset import DeepGlobeDataset, SpacenetDataset
from torch.autograd import Variable
from torch.optim.lr_scheduler import MultiStepLR
from utils.loss import CrossEntropyLoss2d, mIoULoss
from utils import util
from utils import viz_util

import numpy
import skimage.io
import skimage.morphology
import sys
import subprocess

from PIL import Image
Image.MAX_IMAGE_PIXELS = None

sys.path.append('../../python')
from discoverlib import geom, graph

jpg_dir = '/mnt/tmp/mapupdate/naip/jpg/'
annotation_fname = '/mnt/tmp/mapupdate/annotations.json'
test_fname = '/mnt/tmp/mapupdate/test.csv'
out_dir = '/mnt/tmp/mapupdate/roadconnectivity/out/'

model_path = '/ssd_scratch/cvit/anil.k/exp/deepglobe100/dg_stak_mtl/model_best.pth.tar'
model_name = 'StackHourglassNetMTL'

config = torch.load(model_path)["config"]
assert config is not None

util.setSeed(config)
num_gpus = torch.cuda.device_count()
model = MODELS[model_name](
	config["task1_classes"], config["task2_classes"]
)
model.cuda()

print("Loading from existing FCN and copying weights to continue....")
checkpoint = torch.load(model_path)
start_epoch = checkpoint["epoch"] + 1
best_miou = checkpoint["miou"]
# stat_parallel_dict = util.getParllelNetworkStateDict(checkpoint['state_dict'])
# model.load_state_dict(stat_parallel_dict)
model.load_state_dict(checkpoint["state_dict"])

mean_bgr = [70.95016901, 71.16398124, 71.30953645]

def get_output(sat):
	model.eval()
	output = numpy.zeros((sat.shape[0], sat.shape[1]), dtype='uint8')
	for x in range(0, sat.shape[0] - 512, 256) + [sat.shape[0] - 512]:
		for y in range(0, sat.shape[1] - 512, 256) + [sat.shape[1] - 512]:
			cur_input = sat[x:x+512, y:y+512, :].astype('float32')
			# convert to BGR and subtract mean
			cur_input = numpy.stack([
				cur_input[:, :, 2] - mean_bgr[0],
				cur_input[:, :, 1] - mean_bgr[1],
				cur_input[:, :, 0] - mean_bgr[2],
			], axis=2)
			# make batched and then NHWC -> NCHW and then tensor
			cur_input = cur_input.reshape(1, 512, 512, 3)
			cur_input = cur_input.transpose(0, 3, 1, 2)
			cur_input = torch.tensor(cur_input, dtype=torch.float32).cuda()

			cur_outputs, _ = model(cur_input)
			cur_output = cur_outputs[-1]
			cur_output = cur_output.detach().cpu()
			cur_output = torch.nn.functional.softmax(cur_output, dim=1)
			cur_output = cur_output.numpy()[0, 1, :, :]
			cur_output = (cur_output*255).astype('uint8')

			startx = (512 - 256) // 2
			endx = (512 + 256) // 2
			starty = (512 - 256) // 2
			endy = (512 + 256) // 2
			if x == 0:
				startx = 0
			elif x >= sat.shape[0] - 512 - 256 - 1:
				endx = 512
			if y == 0:
				starty = 0
			elif y >= sat.shape[1] - 512 - 256 - 1:
				endy = 512
			output[x+startx:x+endx, y+starty:y+endy] = cur_output[startx:endx, starty:endy]
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
	if crop.shape[0] < 512 or crop.shape[1] < 512:
		lx = max(512, crop.shape[1])
		ly = max(512, crop.shape[0])
		ncrop = numpy.zeros((ly, lx, 3), dtype='uint8')
		ncrop[0:crop.shape[0], 0:crop.shape[1], :] = crop
		crop = ncrop

	output = get_output(crop)

	for threshold in thresholds:
		out_im_fname = os.path.join(out_dir, str(threshold), '{}.png'.format(annotation_idx))
		out_tmp_fname = os.path.join(out_dir, str(threshold), '{}_tmp.graph'.format(annotation_idx))
		out_fname = os.path.join(out_dir, str(threshold), '{}.graph'.format(annotation_idx))

		selem = skimage.morphology.disk(2)
		output = skimage.morphology.binary_dilation(output > 128, selem)
		output = output.astype('uint8')*255
		skimage.io.imsave(out_im_fname, output)

		subprocess.call(['python3', '../../python/discoverlib/mapextract.py', out_im_fname, str(threshold), out_tmp_fname])
		g = graph.read_graph(out_tmp_fname)
		for vertex in g.vertices:
			vertex.point = vertex.point.add(geom.Point(sx, sy))
		g.save(out_fname)
