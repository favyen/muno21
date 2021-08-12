import numpy
import tensorflow as tf
import os
import os.path
import random
import math
import time
from PIL import Image
import keras
from keras.models import *
from keras.layers import Input, add, Conv2D, MaxPooling2D, UpSampling2D, BatchNormalization, Activation, Add, concatenate, Dropout
from keras.optimizers import *
from keras.callbacks import ModelCheckpoint, LearningRateScheduler
from keras import backend as keras


BATCH_SIZE = 2

class Model:
	def _conv_layer(self, name, input_var,KERNEL_SIZE , stride, in_channels, out_channels, options = {}):
		activation = options.get('activation', 'relu')
		dropout = options.get('dropout', None)
		padding = options.get('padding', 'SAME')
		batchnorm = options.get('batchnorm', True)
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
	def RCL_block(self, stage, filedepth, nb_layers,  inputs):
		conv_name_base = 'conv' + str(stage)
		conv1 = self._conv_layer(conv_name_base+'_1', inputs,3, 1, filedepth, nb_layers, {'activation': 'relu','batchnorm': True})

		conv2 = self._conv_layer(conv_name_base+'_2', conv1, 3,1, nb_layers, nb_layers, {'batchnorm': False})
		add1 = tf.add(conv2, conv1)


		conv3 = self._conv_layer(conv_name_base + '_3', add1,3, 1, nb_layers, nb_layers,
									   {'batchnorm': True})
		add2 = tf.add(conv3, conv1)

		conv4 = self._conv_layer(conv_name_base + '_4', add2,3, 1, nb_layers, nb_layers,
									   {'batchnorm': True})
		add3 = tf.add(conv4, conv1)

		conv5 = self._conv_layer(conv_name_base + '_5', add3, 3,1, nb_layers, nb_layers,
									   {'batchnorm': True})
		add4 = tf.add(conv5, conv1)


		return  add4

	def __init__(self, big=False):
		tf.reset_default_graph()

		self.is_training = tf.placeholder(tf.bool)
		if big:
			self.inputs = tf.placeholder(tf.float32, [None, 2048, 2048, 3])
			self.targets = tf.placeholder(tf.float32, [None, 2048, 2048, 1])
		else:
			self.inputs = tf.placeholder(tf.float32, [None, 256, 256, 3])
			self.targets = tf.placeholder(tf.float32, [None, 256, 256, 1])
		self.learning_rate = tf.placeholder(tf.float32)

		self.dropout_factor = tf.to_float(self.is_training) * 0.3
		## encoder
		self.layer1 = self._conv_layer('layer1', self.inputs,3, 1, 3, 32, {'activation':'relu','batchnorm': True})#256*256
		#self.layer2 = self._conv_layer('layer2', self.layer1, 1, 16, 32, {'batchnorm': False})
		#self.layer3 = self._conv_layer('layer3', self.layer2, 1, 32, 32, {'batchnorm': True})
		#self.layer4_inputs = tf.add(self.layer3, self.layer2)
		self.layer4 = self.RCL_block(stage = 'RCL1', filedepth=32, nb_layers=64, inputs=self.layer1)#256*256
		self.layer5 = self._conv_layer('layer5', self.layer4,3, 2, 64, 64, {'batchnorm': True})#128*128
		self.layer6 = self.RCL_block(stage='RCL2', filedepth=64, nb_layers=128, inputs=self.layer5)#128*128
		self.layer7 = self._conv_layer('layer7', self.layer6, 3,2, 128, 128, {'batchnorm': True})#64*64
		self.layer8 = self.RCL_block(stage='RCL3', filedepth=128, nb_layers=256, inputs=self.layer7)#64*64
		self.layer9 = self._conv_layer('layer9', self.layer8,3, 2, 256, 256, {'batchnorm': True})#32*32

		## bridge
		self.layer10 = self.RCL_block(stage='RCL4', filedepth=256, nb_layers=512, inputs=self.layer9)

		## decoder
		self.layer11 = self._conv_layer('layer11', self.layer10, 3, 2, 512, 256, {'transpose': True})#64*64*256
		self.layer12_inputs = tf.concat([self.layer11, self.layer8], axis=3)#64*64*512
		self.layer12 = self.RCL_block(stage='RCL5', filedepth=512, nb_layers=256, inputs=self.layer12_inputs)#64*64*256
		self.layer13 = self._conv_layer('layer13', self.layer12,3, 2, 256, 128, {'transpose': True})#128*128*128
		self.layer14_inputs = tf.concat([self.layer13, self.layer6], axis=3)
		self.layer14 = self.RCL_block(stage='RCL6', filedepth=256, nb_layers=128, inputs=self.layer14_inputs)
		self.layer15 = self._conv_layer('layer15', self.layer14, 3, 2, 128, 64, {'transpose': True})#256*256*64
		self.layer16_inputs = tf.concat([self.layer15, self.layer4], axis=3)
		self.layer16 = self.RCL_block(stage='RCL7', filedepth=128, nb_layers=64, inputs=self.layer16_inputs)#256*256*64
		#self.layer17 = self._conv_layer('layer17', self.layer16, 1, 64, 64, { 'batchnorm': False})

		self.pre_outputs = self._conv_layer('pre_outputs', self.layer16,1, 1, 64, 2, {'activation': 'none', 'batchnorm': True}) # -> 256x256x2

		self.outputs = tf.nn.softmax(self.pre_outputs)[:, :, :, 0]
		self.labels = tf.concat([self.targets, 1 - self.targets], axis=3)
		self.loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=self.labels, logits=self.pre_outputs))

		with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):
			self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)

		self.init_op = tf.initialize_all_variables()
		self.saver = tf.train.Saver(max_to_keep=None)
