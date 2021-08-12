import multiprocessing
import os, os.path
import subprocess
import sys

in_dir = sys.argv[1]
out_dir = sys.argv[2]
nthreads = 0
if len(sys.argv) >= 4:
    nthreads = int(sys.argv[3])

timestamps = ['{}-07-01'.format(year) for year in range(2012, 2021)]

def f(fname):
    if not fname.endswith('.pbf'):
        return
    label = fname.split('.pbf')[0]
    for timestamp in timestamps:
        in_fname = os.path.join(in_dir, fname)
        out_fname = os.path.join(out_dir, label+'_'+timestamp+'.pbf')
        if os.path.exists(out_fname):
            continue
        timestamp_arg = timestamp+'T00:00:00Z'
        print(in_fname, '->', out_fname)
        subprocess.call(['osmium', 'time-filter', in_fname, timestamp_arg, '-o', out_fname])

fnames = os.listdir(in_dir)
if nthreads == 0:
    for fname in fnames:
        f(fname)
else:
    p = multiprocessing.Pool(nthreads)
    p.map(f, fnames)
    p.close()
