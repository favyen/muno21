import multiprocessing
import os, os.path
import subprocess
import sys

tif_dir = sys.argv[1]
jpg_dir = sys.argv[2]
nthreads = 0
if len(sys.argv) >= 4:
    nthreads = int(sys.argv[3])

def f(fname):
    if not fname.endswith('.tif'):
        return
    label = fname.split('.tif')[0]
    tif_path = os.path.join(tif_dir, fname)
    jpg_path = os.path.join(jpg_dir, label+'.jpg')
    if os.path.exists(jpg_path):
        return
    print(tif_path, '->', jpg_path)
    subprocess.call(['convert', tif_path, jpg_path])

fnames = os.listdir(tif_dir)
if nthreads == 0:
    for fname in fnames:
        f(fname)
else:
    p = multiprocessing.Pool(nthreads)
    p.map(f, fnames)
    p.close()
