import json
import math
import multiprocessing
import numpy
import os
import os.path
import subprocess
import sys

sys.path.append('../python')
from discoverlib import geom, graph

annotation_fname = sys.argv[1]
inferred_dir = sys.argv[2]
graph_dir = sys.argv[3]
test_csv = sys.argv[4]

annotation_idx = None
if len(sys.argv) >= 6:
	annotation_idx = int(sys.argv[5])

BaseGraphSuffix = '_2013-07-01.graph'
GTGraphSuffix = '_2020-07-01.graph'
ExtraGraphSuffix = '_2020-07-01_extra.graph'

with open(test_csv, 'r') as f:
	test_regions = json.load(f)

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)
annotations = [(idx, annotation) for idx, annotation in enumerate(annotations)]

if annotation_idx is not None:
	annotations = annotations[annotation_idx:annotation_idx+1]
else:
	annotations = [(idx, annot) for (idx, annot) in annotations if 'nochange' not in annot['Tags'] and annot['Cluster']['Region'] in test_regions]

lat_top_left = 41.0
lon_top_left = -71.0

def xy2latlon(x, y, rect):
	lat = lat_top_left - (y-rect.start.y) * 1.0 / 111111.0
	lon = lon_top_left + ((x-rect.start.x) * 1.0 / 111111.0) / math.cos(math.radians(lat_top_left))
	return lat, lon

def convert_graph(g, rect, fname):
	nodes = []
	edges = []
	nodemap = {}
	edge_map = {}

	for vertex in g.vertices:
		lat, lon = xy2latlon(vertex.point.x, vertex.point.y, rect)
		nodes.append([lat, lon])

	for edge in g.edges:
		edges.append([edge.src.id, edge.dst.id])

	with open(fname, 'w') as f:
		json.dump([nodes,edges], f, indent=2)

def get_apls(gt_g, inferred_g, extra_g, rect):
	pid = os.getpid()
	gt_fname = '/tmp/apls-{}-gt.json'.format(pid)
	inferred_fname = '/tmp/apls-{}-inferred.json'.format(pid)
	extra_fname = '/tmp/apls-{}-extra.json'.format(pid)
	convert_graph(gt_g, rect, gt_fname)
	convert_graph(inferred_g, rect, inferred_fname)
	convert_graph(extra_g, rect, extra_fname)
	#subprocess.call(['go', 'run', '../methods/sat2graph/metrics/apls3/main.go', gt_fname, inferred_fname, extra_fname, str(rect.end.x-rect.start.x), str(rect.end.y-rect.start.y)])
	#return 0
	output = subprocess.check_output(['go', 'run', '../methods/sat2graph/metrics/apls3/main.go', gt_fname, inferred_fname, extra_fname, str(rect.end.x-rect.start.x), str(rect.end.y-rect.start.y)])
	#output = subprocess.check_output(['go', 'run', '../methods/sat2graph/metrics/apls/main.go', gt_fname, inferred_fname, str(rect.end.x-rect.start.x), str(rect.end.y-rect.start.y)])

	lines = [line.strip() for line in output.decode().split("\n") if line.strip()]
	apls_line = lines[-1]
	score = float(apls_line.split('apls: ')[1])
	print(apls_line)
	if math.isnan(score):
		score = 0
	return score

def get_improvement_score(idx, annotation, base_idx, gt_idx, extra_idx):
	cluster = annotation['Cluster']
	inferred_fname = os.path.join(inferred_dir, '{}.graph'.format(idx))

	window = cluster['Window']
	rect = geom.Rectangle(
		geom.Point(window[0], window[1]),
		geom.Point(window[2], window[3])
	).add_tol(192)

	inferred_g = graph.read_graph(inferred_fname)
	inferred_g = graph.graph_from_edges(inferred_g.edge_grid_index(128).search(rect))
	base_g = graph.graph_from_edges(base_idx.search(rect))
	gt_g = graph.graph_from_edges(gt_idx.search(rect))
	extra_g = graph.graph_from_edges(extra_idx.search(rect))

	base_gt = get_apls(gt_g, base_g, extra_g, rect)
	inferred_gt = get_apls(gt_g, inferred_g, extra_g, rect)
	score = max((inferred_gt - base_gt) / (1 - base_gt), -1)
	print('score at {} is {} (base_gt={}, inferred_gt={})'.format(idx, score, base_gt, inferred_gt))
	return score

def process_tile(group):
	region, tile, annotations = group
	# load base/gt graphs
	label = '{}_{}_{}'.format(region, tile[0], tile[1])
	base_fname = os.path.join(graph_dir, label+BaseGraphSuffix)
	gt_fname = os.path.join(graph_dir, label+GTGraphSuffix)
	extra_fname = os.path.join(graph_dir, label+ExtraGraphSuffix)
	print('load', base_fname)
	base_idx = graph.read_graph(base_fname).edge_grid_index(128)
	print('load', gt_fname)
	gt_idx = graph.read_graph(gt_fname).edge_grid_index(128)
	print('load', extra_fname)
	extra_idx = graph.read_graph(extra_fname).edge_grid_index(128)
	scores = []
	for i, (idx, annotation) in enumerate(annotations):
		print('{} ({}/{})'.format(idx, i, len(annotations)))
		score = get_improvement_score(idx, annotation, base_idx, gt_idx, extra_idx)
		scores.append((idx, score))
	return scores

# group annotations by tile
print('group')
groups = {}
for idx, annotation in annotations:
	cluster = annotation['Cluster']
	k = (cluster['Region'], (cluster['Tile'][0], cluster['Tile'][1]))
	if k not in groups:
		groups[k] = []
	groups[k].append((idx, annotation))
groups = [(region, tile, annotation_list) for ((region, tile), annotation_list) in groups.items()]

print('start')
p = multiprocessing.Pool(24)
scores = p.map(process_tile, groups)
p.close()
scores = [(idx, score) for score_list in scores for (idx, score) in score_list]
with open(os.path.join(inferred_dir, 'scores.json'), 'w') as f:
	json.dump(scores, f)
print(numpy.mean([score for idx, score in scores]))
