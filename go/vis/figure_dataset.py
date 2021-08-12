import os.path
import skimage.io

inp = '''austin_0_0/18/;2012,2018;100,87,400,387
atlanta_0_0/16/;2013,2019;100,200,580,680
ny_0_0/9/;2013,2019;0,40,426,466
houston_0_0/12/;2012,2018;105,85,505,485
atlanta_0_0/15/;2013,2019;90,45,440,395'''
inp = '''austin_0_0/18/;2012,2018;100,87,400,312
atlanta_0_0/16/;2013,2019;100,200,580,560
ny_0_0/9/;2013,2019;0,40,426,360
houston_0_0/12/;2012,2018;105,185,505,485
atlanta_0_0/15/;2013,2019;90,45,440,308'''

for i, line in enumerate(inp.split("\n")):
	parts = line.strip().split(';')
	path = parts[0]
	years = parts[1].split(',')
	window = [int(s) for s in parts[2].split(',')]

	path = os.path.join('/tmp/b/', path)
	im1 = skimage.io.imread(os.path.join(path, 'summary_{}.jpg'.format(years[0])))
	im2 = skimage.io.imread(os.path.join(path, 'summary_{}.jpg'.format(years[1])))
	im3 = skimage.io.imread(os.path.join(path, 'road.png'))

	im1 = im1[window[1]:window[3], window[0]:window[2], :]
	im2 = im2[window[1]:window[3], window[0]:window[2], :]
	im3 = im3[window[1]:window[3], window[0]:window[2], :]
	skimage.io.imsave('/tmp/d/{}_old.jpg'.format(i), im1)
	skimage.io.imsave('/tmp/d/{}_new.jpg'.format(i), im2)
	skimage.io.imsave('/tmp/d/{}_road.jpg'.format(i), im3)
