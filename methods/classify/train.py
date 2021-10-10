import classify_lib
import model

import json
import numpy
import os, os.path
import math
import random
import skimage.io, skimage.transform
import sys
import tensorflow as tf
import time

mode = sys.argv[1]
data_dir = sys.argv[2]
jpg_dir = sys.argv[3]
train_fname = sys.argv[4]
model_path = sys.argv[5]

if mode == 'delroad':
	target_precision = 0.9
elif mode == 'incorrect':
	target_precision = 0.5
	# really want 0.6-0.7 recall (i.e., find most of the incorrect roads)
elif mode == 'construct':
	target_precision = 0.5
	# - construct (apply_incorrect): want like 0.8 recall or something
	# - deconstruct (apply_delroad): also want like 0.8 recall, but need 0.9+ precision

with open(os.path.join(data_dir, '{}_data.json'.format(mode)), 'r') as f:
	raw_examples = json.load(f)
with open(train_fname, 'r') as f:
	train_regions = json.load(f)

examples = []
for i, raw in enumerate(raw_examples):
	print(i, '/', len(raw_examples))
	region = raw[0]
	tile = raw[1]
	points3 = raw[2]
	label = raw[3]
	im = classify_lib.get_im(jpg_dir, region, tile)
	inputs = classify_lib.get_inputs_from_points(im, points3, train=True)

	if mode == 'construct':
		# need the old image too
		old_im = classify_lib.get_im(jpg_dir, region, tile, get_old=True)
		old_inputs = classify_lib.get_inputs_from_points(old_im, points3, train=True)
		years = raw[4]
		if years[0] < years[1]:
			inputs = (old_inputs, inputs)
		else:
			inputs = (inputs, old_inputs)

	examples.append((inputs, label, region, tile, points3))

zero_crop = numpy.zeros((64, 64, 3), dtype='uint8')
def prepare(example, noisy=True):
	raw_inputs = example[0]
	label = example[1]

	def select_crops(raw_inputs):
		# randomly pick angle offsets and extract center 64x64
		# also apply random x/y offset perturbation
		inputs = []
		for big_crop_choices in raw_inputs[0:model.MAX_LENGTH]:
			if noisy:
				big_crop = random.choice(big_crop_choices)
			else:
				big_crop = big_crop_choices[2]

			cx, cy = big_crop.shape[1]//2, big_crop.shape[0]//2
			if noisy:
				cx += random.randint(-3, 3)
				cy += random.randint(-3, 3)

			crop = big_crop[cy-32:cy+32, cx-32:cx+32, :]
			inputs.append(crop)

		# pad to model.MAX_LENGTH
		orig_length = len(inputs)
		while len(inputs) < model.MAX_LENGTH:
			inputs.append(zero_crop)

		return inputs, orig_length

	if mode == 'construct':
		pre_inputs, post_inputs = raw_inputs
		pre_inputs, orig_length = select_crops(post_inputs)
		post_inputs, _ = select_crops(post_inputs)
		inputs = []
		for i in range(model.MAX_LENGTH):
			inputs.append(numpy.concatenate([pre_inputs[i], post_inputs[i]], axis=2))
	else:
		inputs, orig_length = select_crops(raw_inputs)

	return (inputs, orig_length, label)

def vis(examples):
	for i, example in enumerate(examples):
		inputs, orig_length, label = example
		for j, crop in enumerate(inputs[0:orig_length]):
			if mode == 'construct':
				skimage.io.imsave('/home/ubuntu/vis/{}_{}_old_{}.jpg'.format(i, j, label), crop[:, :, 0:3])
				skimage.io.imsave('/home/ubuntu/vis/{}_{}_new_{}.jpg'.format(i, j, label), crop[:, :, 3:6])
			else:
				skimage.io.imsave('/home/ubuntu/vis/{}_{}_{}.jpg'.format(i, j, label), crop)

def vis2(examples):
	for i, example in enumerate(examples):
		region = example[2]
		tile = example[3]
		points3 = example[4]
		bbox = [points3[0][0], points3[0][1], points3[0][0], points3[0][1]]
		for p in points3:
			bbox[0] = min(bbox[0], p[0]-32)
			bbox[1] = min(bbox[1], p[1]-32)
			bbox[2] = max(bbox[2], p[0]+32)
			bbox[3] = max(bbox[3], p[1]+32)
		im = classify_lib.get_im(jpg_dir, region, tile)
		bbox[0] = classify_lib.clip(bbox[0], 0, im.shape[1])
		bbox[1] = classify_lib.clip(bbox[1], 0, im.shape[0])
		bbox[2] = classify_lib.clip(bbox[2], 0, im.shape[1])
		bbox[3] = classify_lib.clip(bbox[3], 0, im.shape[0])
		crop = im[bbox[1]:bbox[3], bbox[0]:bbox[2], :]
		skimage.io.imsave('/home/ubuntu/vis/{}.jpg'.format(i), crop)

val_regions = train_regions[0:1]
train_regions = train_regions[1:]
val_examples = [example for example in examples if example[2] in val_regions]
train_examples = [example for example in examples if example[2] in train_regions]
val_prepared = [prepare(example, noisy=False) for example in val_examples]
print('split {} examples into {} for training and {} for validation'.format(len(examples), len(train_examples), len(val_examples)))

train_positive = [example for example in train_examples if example[1] == 1]
train_negative = [example for example in train_examples if example[1] == 0]

print('initializing model')
if mode == 'construct':
	in_channels = 6
else:
	in_channels = 3
m = model.Model(in_channels=in_channels)
config = tf.ConfigProto()
config.gpu_options.allow_growth = True
session = tf.Session(config=config)
session.run(m.init_op)

# compute accuracy
def get_accuracy():
	probs = []
	for i in range(0, len(val_prepared), batch_size):
		batch = val_prepared[i:i+batch_size]
		batch_probs = session.run(m.probs, feed_dict={
			m.inputs: [example[0] for example in batch],
			m.lengths: [example[1] for example in batch],
		})
		probs.extend(batch_probs)

	recall_at_target = 0
	for threshold in [0.5, 0.65, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.998]:
		tp = 0
		fp = 0
		fn = 0
		for i, example in enumerate(val_prepared):
			label = example[2] == 1
			out = probs[i] > threshold
			if label and out:
				tp += 1
			if label and not out:
				fn += 1
			if not label and out:
				fp += 1

		if tp+fp > 0:
			precision = tp/(tp+fp)
		else:
			precision = 0
		recall = tp/(tp+fn)
		print(threshold, precision, recall)

		if precision >= target_precision:
			recall_at_target = max(recall_at_target, recall)

	return recall_at_target

print('begin training')
best_loss = None
batch_size = 16
for epoch in range(9999):
	start_time = time.time()
	train_losses = []
	for _ in range(128):
		#batch = [prepare(example) for example in random.sample(train_examples, batch_size)]
		batch = random.sample(train_positive, batch_size//2) + random.sample(train_negative, batch_size//2)
		random.shuffle(batch)
		batch = [prepare(example) for example in batch]
		_, loss = session.run([m.optimizer, m.loss], feed_dict={
			m.inputs: [example[0] for example in batch],
			m.lengths: [example[1] for example in batch],
			m.labels: [example[2] for example in batch],
			m.learning_rate: 1e-4,
		})
		train_losses.append(loss)
	train_loss = numpy.mean(train_losses)
	train_time = time.time()

	'''val_losses = []
	for i in range(0, len(val_prepared), batch_size):
		batch = val_prepared[i:i+batch_size]
		loss = session.run(m.loss, feed_dict={
			m.inputs: [example[0] for example in batch],
			m.lengths: [example[1] for example in batch],
			m.labels: [example[2] for example in batch],
		})
		val_losses.append(loss)

	val_loss = numpy.mean(val_losses)'''
	val_loss = -get_accuracy()
	val_time = time.time()

	print('iteration {}: train_time={}, val_time={}, train_loss={}, val_loss={}/{}'.format(epoch, int(train_time - start_time), int(val_time - train_time), train_loss, val_loss, best_loss))

	if best_loss is None or val_loss < best_loss:
		best_loss = val_loss
		m.saver.save(session, model_path)
