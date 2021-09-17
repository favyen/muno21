import json
import numpy
import os.path
import sys

annotation_fname = sys.argv[1]
scores_fnames = sys.argv[2:]

TAGS = ['all', 'constructed', 'was_missing', 'bulldozed', 'was_incorrect']

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)

points_by_tag = [[] for _ in TAGS]

for scores_fname in scores_fnames:
	with open(scores_fname, 'r') as f:
		scores = json.load(f)
	inferred_dir = os.path.dirname(scores_fname)
	with open(os.path.join(inferred_dir, 'error.json'), 'r') as f:
		error_rate = json.load(f)

	# helper function to get average improvement under each tag
	def get_summary(scores):
		scores_by_tag = {}
		for idx, score in scores:
			annotation = annotations[idx]
			for tag in annotation['Tags'] + ['all']:
				if tag not in scores_by_tag:
					scores_by_tag[tag] = []
				scores_by_tag[tag].append(score)

		summary = []
		for tag in TAGS:
			avg_score = numpy.mean(scores_by_tag[tag])
			summary.append(avg_score)

		return summary

	summary = get_summary(scores)

	for i, score in enumerate(summary):
		points_by_tag[i].append((1-error_rate, score))
	#print(scores_fname, 1-error_rate, summary[0])

for tag_idx, points in enumerate(points_by_tag):
	# Obtain Pareto-optimal curve from the points.
	while True:
		need_to_delete = []
		for i, (p1, r1) in enumerate(points):
			for j, (p2, r2) in enumerate(points):
				if p1 > p2 and r1 > r2 and j not in need_to_delete:
					need_to_delete.append(j)
		if not need_to_delete:
			break
		for i in reversed(sorted(need_to_delete)):
			del points[i]

	points.sort(key=lambda x: x[0])
	print(TAGS[tag_idx])
	for precision, recall in points:
		print('{}\t{}'.format(precision, recall))
