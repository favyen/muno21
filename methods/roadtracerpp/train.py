from collections import deque
import json
import math
import numpy
import os
import os.path
import random
import skimage.io
import sys
import tensorflow as tf
import time

sys.path.append('../../python')
from discoverlib import geom, graph
import model

train_csv = sys.argv[1]
jpg_dir = sys.argv[2]
angles_dir = sys.argv[3]
model_path = sys.argv[4]

TRAIN_YEARS = ['2016', '2017', '2018', '2019', '2020']
WINDOW_SIZE = 256
NUM_BUCKETS = 64

with open(train_csv, 'r') as f:
	train_set = json.load(f)

val_set = train_set[0:1]
train_set = train_set[1:]

def load_data(regions):
	examples = []
	for jpg_fname in os.listdir(jpg_dir):
		if not jpg_fname.endswith('.jpg'):
			continue
		parts = jpg_fname.split('.jpg')[0].split('_')
		label = '_'.join(parts[0:3])
		region = parts[0]
		year = parts[3].split('-')[0]
		if region not in regions:
			continue
		if year not in TRAIN_YEARS:
			continue

		print('load', jpg_fname)
		im = skimage.io.imread(os.path.join(jpg_dir, jpg_fname)).swapaxes(0, 1)
		angles = numpy.fromfile(os.path.join(angles_dir, label+'.bin'), dtype='uint8')
		angles = angles.reshape(im.shape[0]//4, im.shape[1]//4, 64)
		examples.append({
			'im': im,
			'angles': angles,
			'region': region,
			'label': label,
			'year': year,
		})
	return examples

train_examples = load_data(train_set)
val_examples = load_data(val_set)

# initialize model and session
print('initializing model')
m = model.Model(input_channels=3, bn=True)
session = tf.Session()
session.run(m.init_op)

def prepare(example):
	while True:
		# pick origin: must be multiple of the output scale
		origin = geom.Point(random.randint(0, example['im'].shape[0]//4 - WINDOW_SIZE//4), random.randint(0, example['im'].shape[1]//4 - WINDOW_SIZE//4))
		origin = origin.scale(4)

		im = example['im'][origin.x:origin.x+WINDOW_SIZE, origin.y:origin.y+WINDOW_SIZE, :].astype('float32') / 255.0
		angles = example['angles'][origin.x//4:(origin.x+WINDOW_SIZE)//4, origin.y//4:(origin.y+WINDOW_SIZE)//4, :].astype('float32') / 255.0

		# skip if there are not enough nearby roads, or if the input image contains missing regions (black pixels)
		if numpy.count_nonzero(angles.max(axis=2)) < 32 or numpy.count_nonzero(im.max(axis=2) == 0) > 200:
			continue

		return {
			'im': im,
			'angles': angles,
			'origin': origin,
			'region': example['region'],
			'label': example['label'],
			'year': example['year'],
		}

val_prepared = []
for example in val_examples:
	for i in range(1024):
		val_prepared.append(prepare(example))

def vis_example(example, outputs=None, edge_index=None):
	x = numpy.zeros((WINDOW_SIZE, WINDOW_SIZE, 3), dtype='uint8')
	x[:, :, :] = (example['im']*255).astype('uint8')
	x[WINDOW_SIZE//2-2:WINDOW_SIZE//2+2, WINDOW_SIZE//2-2:WINDOW_SIZE//2+2, :] = 255

	if edge_index is not None:
		rect = geom.Rectangle(example['origin'], example['origin'].add(geom.Point(WINDOW_SIZE, WINDOW_SIZE)))
		for edge in edge_index.search(rect):
			start = edge.src.point
			end = edge.dst.point
			for p in geom.draw_line(start.sub(example['origin']), end.sub(example['origin']), geom.Point(WINDOW_SIZE, WINDOW_SIZE)):
				x[p.x, p.y, 0:2] = 0
				x[p.x, p.y, 2] = 255

	for i in range(WINDOW_SIZE):
		for j in range(WINDOW_SIZE):
			di = i - WINDOW_SIZE//2
			dj = j - WINDOW_SIZE//2
			d = math.sqrt(di * di + dj * dj)
			a = int((math.atan2(dj, di) - math.atan2(0, 1) + math.pi) * NUM_BUCKETS / 2 / math.pi)
			if a >= NUM_BUCKETS:
				a = NUM_BUCKETS - 1
			elif a < 0:
				a = 0
			elif d > 100 and d <= 120 and example['angles'] is not None:
				x[i, j, 0] = example['angles'][WINDOW_SIZE//8, WINDOW_SIZE//8, a] * 255
				x[i, j, 1] = example['angles'][WINDOW_SIZE//8, WINDOW_SIZE//8, a] * 255
				x[i, j, 2] = 0
			elif d > 70 and d <= 90 and outputs is not None:
				x[i, j, 0] = outputs[WINDOW_SIZE//8, WINDOW_SIZE//8, a] * 255
				x[i, j, 1] = outputs[WINDOW_SIZE//8, WINDOW_SIZE//8, a] * 255
				x[i, j, 2] = 0
	return x

best_loss = None

for epoch in range(9999):
	start_time = time.time()
	train_losses = []
	for _ in range(1024):
		batch = [prepare(random.choice(train_examples)) for _ in range(model.BATCH_SIZE)]
		_, loss = session.run([m.optimizer, m.loss], feed_dict={
			m.is_training: True,
			m.inputs: [example['im'] for example in batch],
			m.targets: [example['angles'] for example in batch],
			m.learning_rate: 1e-4,
		})
		train_losses.append(loss)

	train_loss = numpy.mean(train_losses)
	train_time = time.time()

	val_losses = []
	for i in range(0, len(val_prepared), model.BATCH_SIZE):
		batch = val_prepared[i:i+model.BATCH_SIZE]
		loss = session.run(m.loss, feed_dict={
			m.is_training: False,
			m.inputs: [example['im'] for example in batch],
			m.targets: [example['angles'] for example in batch],
		})
		val_losses.append(loss)

	val_loss = numpy.mean(val_losses)
	val_time = time.time()

	print('iteration {}: train_time={}, val_time={}, train_loss={}, val_loss={}/{}'.format(epoch, int(train_time - start_time), int(val_time - train_time), train_loss, val_loss, best_loss))

	if best_loss is None or val_loss < best_loss:
		best_loss = val_loss
		m.saver.save(session, model_path)

'''
for i in range(0, 256, model.BATCH_SIZE):
	batch = val_prepared[i:i+model.BATCH_SIZE]
	outputs = session.run(m.outputs, feed_dict={
		m.is_training: False,
		m.inputs: [example['im'] for example in batch],
	})
	for j in range(model.BATCH_SIZE):
		im = vis_example(batch[j], outputs=outputs[j, :])
		skimage.io.imsave('/home/ubuntu/vis/{}.jpg'.format(i+j), im)
'''
