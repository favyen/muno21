import json
import os, os.path
import random
import sys

history_dir = sys.argv[1]
out_dir = sys.argv[2]

regions = [fname.split('.pbf')[0] for fname in os.listdir(history_dir) if fname.endswith('.pbf')]
random.shuffle(regions)
train_set = regions[0:10]
test_set = regions[10:]

with open(os.path.join(out_dir, 'train.json'), 'w') as f:
    json.dump(train_set, f)
with open(os.path.join(out_dir, 'test.json'), 'w') as f:
    json.dump(test_set, f)
