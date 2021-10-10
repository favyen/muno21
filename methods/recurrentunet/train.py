import sys
sys.path.append('../../python')

from roadcnn import dataset
import model

import numpy
from PIL import Image
import random
import scipy.ndimage
import subprocess
import tensorflow as tf
import time

sat_path = sys.argv[1]
osm_path = sys.argv[2]
model_path = sys.argv[3]

print 'loading train tiles'
train_tiles = dataset.load_tiles(sat_path, osm_path, 'train')

random.shuffle(train_tiles)
val_tiles = train_tiles[0:4]
train_tiles = train_tiles[4:]

val_examples = []
for tile in val_tiles:
	val_examples.extend(dataset.load_all_examples(tile))

print 'using {} train tiles, {} val tiles, {} val examples'.format(len(train_tiles), len(val_tiles), len(val_examples))

m = model.Model()
session = tf.Session()
session.run(m.init_op)

best_loss = None

def epoch_to_learning_rate(epoch):
	if epoch < 100:
		return 1e-4
	elif epoch < 200:
		return 1e-4
	elif epoch < 300:
		return 1e-5
	else:
		return 1e-6

for epoch in xrange(100):
	start_time = time.time()
	random.shuffle(train_tiles)
	train_losses = []
	for _ in xrange(1):
		for i in xrange(0, len(train_tiles), model.BATCH_SIZE):
			examples = [dataset.load_example(tile) for tile in train_tiles[i:i+model.BATCH_SIZE]]
			_, loss = session.run([m.optimizer, m.loss], feed_dict={
				m.is_training: True,
				m.inputs: [example[0] for example in examples],
				m.targets: [example[1] for example in examples],
				m.learning_rate: 1e-5,
			})
			train_losses.append(loss)
	train_loss = numpy.mean(train_losses)
	train_time = time.time()

	val_losses = []
	for i in xrange(0, len(val_examples), model.BATCH_SIZE):
		examples = val_examples[i:i+model.BATCH_SIZE]
		loss = session.run(m.loss, feed_dict={
			m.is_training: False,
			m.inputs: [example[0] for example in examples],
			m.targets: [example[1] for example in examples],
		})
		val_losses.append(loss)

	val_loss = numpy.mean(val_losses)
	val_time = time.time()

	print 'iteration {}: train_time={}, val_time={}, train_loss={}, val_loss={}/{}'.format(epoch, int(train_time - start_time), int(val_time - train_time), train_loss, val_loss, best_loss)

	if best_loss is None or val_loss < best_loss:
		best_loss = val_loss
		m.saver.save(session, model_path)
