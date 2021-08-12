import json
import numpy
import sys

annotation_fname = sys.argv[1]
scores_fname = sys.argv[2]

with open(annotation_fname, 'r') as f:
	annotations = json.load(f)
with open(scores_fname, 'r') as f:
	scores = json.load(f)

scores_by_tag = {}
for idx, score in scores:
	if score < -1:
		score = -1
	annotation = annotations[idx]
	for tag in annotation['Tags'] + ['all']:
		if tag not in scores_by_tag:
			scores_by_tag[tag] = []
		scores_by_tag[tag].append(score)

summary = []
for tag in ['all', 'constructed', 'was_missing', 'bulldozed', 'was_incorrect']:
	avg_score = int(round(numpy.mean(scores_by_tag[tag])*100))
	print(tag, avg_score)
	summary.append(avg_score)

def to_str(x):
	if x > 0:
		return '+'+str(x)
	else:
		return str(x)
print(' & '.join([to_str(score) for score in summary]))
