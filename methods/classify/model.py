import numpy
import tensorflow as tf
import os
import os.path
import random
import math
import time

MAX_LENGTH = 32
KERNEL_SIZE = 4

class Model:
	def _conv_layer(self, name, input_var, stride, in_channels, out_channels, options = {}):
		activation = options.get('activation', 'relu')
		dropout = options.get('dropout', None)
		padding = options.get('padding', 'SAME')
		batchnorm = options.get('batchnorm', False)
		transpose = options.get('transpose', False)

		with tf.variable_scope(name) as scope:
			if not transpose:
				filter_shape = [KERNEL_SIZE, KERNEL_SIZE, in_channels, out_channels]
			else:
				filter_shape = [KERNEL_SIZE, KERNEL_SIZE, out_channels, in_channels]
			kernel = tf.get_variable(
				'weights',
				shape=filter_shape,
				initializer=tf.truncated_normal_initializer(stddev=math.sqrt(2.0 / KERNEL_SIZE / KERNEL_SIZE / in_channels)),
				dtype=tf.float32
			)
			biases = tf.get_variable(
				'biases',
				shape=[out_channels],
				initializer=tf.constant_initializer(0.0),
				dtype=tf.float32
			)
			if not transpose:
				output = tf.nn.bias_add(
					tf.nn.conv2d(
						input_var,
						kernel,
						[1, stride, stride, 1],
						padding=padding
					),
					biases
				)
			else:
				batch = tf.shape(input_var)[0]
				side = tf.shape(input_var)[1]
				output = tf.nn.bias_add(
					tf.nn.conv2d_transpose(
						input_var,
						kernel,
						[batch, side * stride, side * stride, out_channels],
						[1, stride, stride, 1],
						padding=padding
					),
					biases
				)
			if batchnorm:
				output = tf.contrib.layers.batch_norm(output, center=True, scale=True, is_training=self.is_training, decay=0.99)
			if dropout is not None:
				output = tf.nn.dropout(output, keep_prob=1-dropout)

			if activation == 'relu':
				return tf.nn.relu(output, name=scope.name)
			elif activation == 'sigmoid':
				return tf.nn.sigmoid(output, name=scope.name)
			elif activation == 'none':
				return output
			else:
				raise Exception('invalid activation {} specified'.format(activation))

	def _fc_layer(self, name, input_var, input_size, output_size, options = {}):
		activation = options.get('activation', 'relu')
		dropout = options.get('dropout', None)
		batchnorm = options.get('batchnorm', False)

		with tf.variable_scope(name) as scope:
			weights = tf.get_variable(
				'weights',
				shape=[input_size, output_size],
				initializer=tf.truncated_normal_initializer(stddev=math.sqrt(2.0 / input_size)),
				dtype=tf.float32
			)
			biases = tf.get_variable(
				'biases',
				shape=[output_size],
				initializer=tf.constant_initializer(0.0),
				dtype=tf.float32
			)
			output = tf.matmul(input_var, weights) + biases
			if batchnorm:
				output = tf.contrib.layers.batch_norm(output, center=True, scale=True, is_training=self.is_training, decay=0.99)
			if dropout is not None:
				output = tf.nn.dropout(output, keep_prob=1-dropout)

			if activation == 'relu':
				return tf.nn.relu(output, name=scope.name)
			elif activation == 'sigmoid':
				return tf.nn.sigmoid(output, name=scope.name)
			elif activation == 'none':
				return output
			else:
				raise Exception('invalid activation {} specified'.format(activation))

	def __init__(self, in_channels=3):
		tf.reset_default_graph()

		self.inputs = tf.placeholder(tf.uint8, [None, MAX_LENGTH, 64, 64, in_channels])
		self.lengths = tf.placeholder(tf.int32, [None])
		self.labels = tf.placeholder(tf.float32, [None])
		self.learning_rate = tf.placeholder(tf.float32, shape=())
		batch_size = tf.shape(self.inputs)[0]

		# CNN
		inputs = tf.cast(self.inputs, tf.float32)/255
		inputs = tf.reshape(inputs, [batch_size*MAX_LENGTH, 64, 64, in_channels])
		conv1 = self._conv_layer('conv1', inputs, 2, in_channels, 32) # -> 32x32x32
		conv2 = self._conv_layer('conv2', conv1, 2, 32, 64) # -> 16x16x64
		conv3 = self._conv_layer('conv3', conv2, 2, 64, 128) # -> 8x8x128
		conv4 = self._conv_layer('conv4', conv3, 2, 128, 256) # -> 4x4x256
		conv5 = self._conv_layer('conv5', conv4, 2, 256, 256) # -> 2x2x256
		conv6 = self._conv_layer('conv6', conv5, 2, 256, 64)[:, 0, 0, :] # -> 64
		self.features = tf.reshape(conv6, [batch_size, MAX_LENGTH, 64])

		# RNN
		def rnn_step(prev_state, cur_input):
			with tf.variable_scope('rnn_step', reuse=tf.AUTO_REUSE):
				pairs = tf.concat([prev_state, cur_input], axis=1)
				rnn1 = self._fc_layer('rnn1', pairs, 128, 128)
				rnn2 = self._fc_layer('rnn2', rnn1, 128, 128)
				rnn3 = self._fc_layer('rnn3', rnn2, 128, 128)
				rnn4 = self._fc_layer('rnn4', rnn3, 128, 128, {'activation': 'none'})
				return rnn4[:, 0:64], rnn4[:, 64:128]

		cur_state = tf.zeros([batch_size, 64], dtype=tf.float32)
		rnn_outputs = []
		for i in range(MAX_LENGTH):
			cur_state, cur_outputs = rnn_step(cur_state, self.features[:, i, :])
			rnn_outputs.append(cur_outputs)
		rnn_outputs = tf.stack(rnn_outputs, axis=1)

		# gather the RNN features based on lengths
		self.rnn_features = tf.gather_nd(rnn_outputs, tf.reshape(self.lengths-1, [batch_size, 1]), batch_dims=1)
		fc1 = self._fc_layer('fc1', self.rnn_features, 64, 128)
		fc2 = self._fc_layer('fc2', fc1, 128, 1, {'activation': 'none'})
		self.scores = fc2[:, 0]
		self.probs = tf.nn.sigmoid(self.scores)

		self.loss = tf.nn.sigmoid_cross_entropy_with_logits(labels=self.labels, logits=self.scores)
		self.loss = tf.reduce_mean(self.loss)

		with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):
			self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)

		self.init_op = tf.initialize_all_variables()
		self.saver = tf.train.Saver(max_to_keep=None)
