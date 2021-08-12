# get the sizes of each satellite image
import json
import os, os.path
import subprocess
import sys

in_dir = sys.argv[1]
out_fname = sys.argv[2]

sizes = {}
for fname in os.listdir(in_dir):
    if not fname.endswith('.jpg'):
        continue
    output = subprocess.check_output(['file', os.path.join(in_dir, fname)])
    dims = output.split(b'precision 8, ')[1].split(b', frames')[0]
    dims = dims.split(b'x')
    width = int(dims[0])
    height = int(dims[1])
    parts = fname.split('.')[0].split('_')
    label = '_'.join(parts[0:3])
    sizes[label] = [width, height]

with open(out_fname, 'w') as f:
    json.dump(sizes, f)
