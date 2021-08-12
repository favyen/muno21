import os.path
import skimage.io

inp = '''407 100,127,500,500'''
inp = '''1220 57,22,400,400'''

for i, line in enumerate(inp.split("\n")):
	parts = line.strip().split(' ')
	label = parts[0]
	xywh = [int(s) for s in parts[1].split(',')]
	window = [xywh[0], xywh[1], xywh[0]+xywh[2], xywh[1]+xywh[3]]

	prefix = os.path.join('/tmp/b/', label+'_')
	ims = [
	 	#('old', skimage.io.imread(prefix+'old.png')),
	 	('new', skimage.io.imread(prefix+'new.png')),
	 	('gt', skimage.io.imread(prefix+'gt.png')),
	 	#('delroad', skimage.io.imread(prefix+'0.png')),
	 	('maid', skimage.io.imread(prefix+'3.png')),
	]
	ims = map(lambda t: (t[0], t[1][window[1]:window[3], window[0]:window[2], :]), ims)

	for suffix, im in ims:
		if suffix == 'old' or suffix == 'new':
			ext = '.jpg'
		else:
			im[:2, :, :] = [0, 0, 0]
			im[:, :2, :] = [0, 0, 0]
			im[-2:, :, :] = [0, 0, 0]
			im[:, -2:, :] = [0, 0, 0]
			ext = '.png'
		skimage.io.imsave('/tmp/d/{}_{}{}'.format(i, suffix, ext), im)
