import sys
import json
import mapdriver as md
import mapbox as md2
import graph_ops as graphlib
import math
import pickle

import os
import skimage.io

sys.path.append('../../python')
from discoverlib import geom, graph

train_csv = sys.argv[1]
jpg_dir = sys.argv[2]
graph_dir = sys.argv[3]
out_dir = sys.argv[4]

TRAIN_YEARS = ['2019', '2018']
TRAIN_GRAPH_SUFFIX = '_2020-07-01.graph'

with open(train_csv, 'r') as f:
	train_regions = json.load(f)

counter = 0
for jpg_fname in os.listdir(jpg_dir):
	if not jpg_fname.endswith('.jpg'):
		continue
	parts = jpg_fname.split('.jpg')[0].split('_')
	label = '_'.join(parts[0:3])
	region = parts[0]
	year = parts[3].split('-')[0]
	if year not in TRAIN_YEARS:
		continue
	if region not in train_regions:
		continue

	print('load', jpg_fname)
	im = skimage.io.imread(os.path.join(jpg_dir, jpg_fname))
	graph_fname = os.path.join(graph_dir, label+TRAIN_GRAPH_SUFFIX)
	print('load', graph_fname)
	g = graph.read_graph(graph_fname)
	grid_index = g.edge_grid_index(128)

	for i in range(im.shape[1]//2048):
		for j in range(im.shape[0]//2048):
			cur_im = im[j*2048:(j+1)*2048, i*2048:(i+1)*2048, :]
			rect = geom.Rectangle(geom.Point(i*2048, j*2048), geom.Point((i+1)*2048, (j+1)*2048))
			cur_g = graph.graph_from_edges(grid_index.search(rect))

			skimage.io.imsave(os.path.join(out_dir, 'region_{}_sat.jpg'.format(counter)), cur_im)

			node_neighbor = {}
			for vertex in cur_g.vertices:
				lat = -vertex.point.y/100000.0
				lon = vertex.point.x/100000.0
				n1key = (lat, lon)
				neighbors = []
				for edge in vertex.out_edges:
					lat = -edge.dst.point.y/100000.0
					lon = edge.dst.point.x/100000.0
					n2key = (lat, lon)
					node_neighbor = graphlib.graphInsert(node_neighbor, n1key, n2key)

			lat_st = -2048*(j+1)/100000.0
			lon_st = 2048*i/100000.0
			lat_ed = -2048*j/100000.0
			lon_ed = 2048*(i+1)/100000.0

			# interpolate the graph (20 meters interval)
			node_neighbor = graphlib.graphDensify(node_neighbor)
			node_neighbor_region = graphlib.graph2RegionCoordinate(node_neighbor, [lat_st,lon_st,lat_ed,lon_ed])
			prop_graph = out_dir+"/region_%d_graph_gt.pickle" % counter
			pickle.dump(node_neighbor_region, open(prop_graph, "wb"))

			#graphlib.graphVis2048(node_neighbor,[lat_st,lon_st,lat_ed,lon_ed], "dense.png")
			graphlib.graphVis2048Segmentation(node_neighbor, [lat_st,lon_st,lat_ed,lon_ed], out_dir+"/region_%d_" % counter + "gt.png")

			node_neighbor_refine, sample_points = graphlib.graphGroundTruthPreProcess(node_neighbor_region)

			refine_graph = out_dir+"/region_%d_" % counter + "refine_gt_graph.p"
			pickle.dump(node_neighbor_refine, open(refine_graph, "wb"))
			json.dump(sample_points, open(out_dir+"/region_%d_" % counter + "refine_gt_graph_samplepoints.json", "w"), indent=2)

			counter += 1
