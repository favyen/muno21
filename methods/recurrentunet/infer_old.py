import sys
sys.path.append('../lib')

from roadcnn import dataset
import model
import cv2
import numpy as np
import matplotlib.pyplot as plt
plt.switch_backend('agg')
from keras import backend as K
import numpy
from PIL import Image
import random
import scipy.ndimage
import subprocess
import tensorflow as tf
import time

sat_path = sys.argv[1]
model_path = sys.argv[2]

best_path = model_path + '/model_best/model'
m = model.Model(big=True)
session = tf.Session()
m.saver.restore(session, best_path)

def vis_conv(images, n, name, t):
    """visualize conv output and conv filter.

    Args:
           img: original image.
           n: number of col and row.
           t: vis type.
           name: save name.
    """
    size = 32
    margin = 5

    if t == 'filter':
        results = np.zeros((n * size + 7 * margin, n * size + 7 * margin, 3))
    if t == 'conv':
        results = np.zeros((n * size + 7 * margin, n * size + 7 * margin))

    for i in range(n):
        for j in range(n):
            if t == 'filter':
                filter_img = images[i + (j * n)]
            if t == 'conv':
                filter_img = images[..., i + (j * n)]
            filter_img = cv2.resize(filter_img, (size, size))

            # Put the result in the square `(i, j)` of the results grid
            horizontal_start = i * size + i * margin
            horizontal_end = horizontal_start + size
            vertical_start = j * size + j * margin
            vertical_end = vertical_start + size
            if t == 'filter':
                results[horizontal_start: horizontal_end, vertical_start: vertical_end, :] = filter_img
            if t == 'conv':
                results[horizontal_start: horizontal_end, vertical_start: vertical_end] = filter_img

    # Display the results grid
    plt.imshow(results)
    plt.xticks([])
    plt.yticks([])
    plt.savefig('./images/{}_{}.jpg'.format(t, name), dpi=600)
    plt.show()

def apply_model(sat):
	output = numpy.zeros((sat.shape[0], sat.shape[1]), dtype='uint8')

	conv_input = sat[4096:6144, 4096:6144, :].astype('float32') / 255.0
	conv_output = session.run(m.outputs, feed_dict={
				m.is_training: False,
				m.inputs: [conv_input],
			})[0, :, :]
	vis_conv(conv_output, 8, 'layer1', 'conv')
	vis_conv(conv_output, 8, 'RCL1', 'conv')
	vis_conv(conv_output, 8, 'RCL2', 'conv')
	#input = conv_input * 255
	#plt.savefig('images\{}_{}.jpg'.format(t, name), dpi=600)


	return conv_output, input

def get_test_tiles():
	regions = ['kansas city']
	tiles = {}
	for region in regions:
		if region == 'chicago':
			s = (-1, -2)
		elif region == 'boston':
			s = (1, -1)
		else:
			s = (-1, -1)
		im = numpy.zeros((8192, 8192, 3), dtype='uint8')
		for x in xrange(2):
			for y in xrange(2):
				fname = '{}/{}_{}_{}_sat.png'.format(sat_path, region, s[0] + x, s[1] + y)
				sat = scipy.ndimage.imread(fname)[:, :, 0:3]
				im[y*4096:y*4096+4096, x*4096:x*4096+4096, :] = sat
		tiles[region] = im
	return tiles

tiles = get_test_tiles()
for region, sat in tiles.items():
	output= apply_model(sat)
	#print(input.shape)
	#input.save('./images/input.jpg')
	#plt.savefig('./images/input.jpg', format(input) )
	#Image.fromarray(input).save('images/{}.png'.format(region))
