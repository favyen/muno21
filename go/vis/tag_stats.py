import json
import sys

annotation_fname = sys.argv[1]
test_csv = sys.argv[2]

with open(annotation_fname, 'r') as f:
    annotations = json.load(f)
with open(test_csv, 'r') as f:
    test_regions = json.load(f)
test_regions = set(test_regions)

stats = {}
for annot in annotations:
    if annot['Cluster']['Region'] in test_regions:
        split = 'test'
    else:
        split = 'train'
    for tag in annot['Tags'] + ['total']:
        if (split, tag) not in stats:
            stats[(split, tag)] = 0
        stats[(split, tag)] += 1

for split in ['train', 'test']:
    s = split
    for tag in ['nochange', 'constructed', 'was_missing', 'bulldozed', 'was_incorrect', 'total']:
        s += ' & ' + str(stats[(split, tag)])
    print(s)
