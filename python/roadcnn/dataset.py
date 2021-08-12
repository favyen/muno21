import numpy
import os
import os.path
import random
import scipy.ndimage
import scipy.misc
import multiprocessing
import time

SIZE = 256

def load_tile(sat_fname, osm_fname):
	region = sat_fname.split('/')[-1].split('.png')[0]
	sat = scipy.ndimage.imread(sat_fname)[:, :, 0:3]
	osm = scipy.ndimage.imread(osm_fname).reshape(sat.shape[0], sat.shape[1], 1)
	return (region, sat, osm)

def load_tiles(sat_path, osm_path, traintest):
	files = [fname.split('.png')[0] for fname in os.listdir(sat_path) if '.png' in fname]

	tiles = []
	for i, fname in enumerate(files):
		if i % 10 == 0:
			print '{}/{}'.format(i, len(files))
		sat_fname = '{}/{}.png'.format(sat_path, fname)
		osm_fname = '{}/{}.png'.format(osm_path, fname)
		tiles.append(load_tile(sat_fname, osm_fname))
	return tiles

def load_example(tile):
	_, sat, osm = tile
	i = random.randint(0, sat.shape[0] - 256)
	j = random.randint(0, sat.shape[1] - 256)
	example_sat = sat[i:i+256, j:j+256, :].astype('float32') / 255.0
	example_osm = osm[i:i+256, j:j+256, :].astype('float32') / 255.0
	return example_sat, example_osm

def load_all_examples(tile):
	_, sat, osm = tile
	examples = []
	for i in xrange(0, sat.shape[0], SIZE):
		for j in xrange(0, sat.shape[1], SIZE):
			example_sat = sat[i:i+SIZE, j:j+SIZE, :].astype('float32') / 255.0
			example_osm = osm[i:i+SIZE, j:j+SIZE, :].astype('float32') / 255.0
			examples.append((example_sat, example_osm))
	return examples
