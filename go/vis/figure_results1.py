import os.path
import skimage.io

inp = '''278 164,477,500,500 constructed
189 158,1914,500,500 was-missing
470 0,59,378,378 deconstructed
479 131,25,500,500 was-incorrect
511 40,5,410,410 constructed,deconstructed'''

for i, line in enumerate(inp.split("\n")):
	parts = line.strip().split(' ')
	label = parts[0]
	xywh = [int(s) for s in parts[1].split(',')]
	window = [xywh[0], xywh[1], xywh[0]+xywh[2], xywh[1]+xywh[3]]

	prefix = os.path.join('/tmp/b/', label+'_')
	ims = [
	 	('old', skimage.io.imread(prefix+'old.png')),
	 	('new', skimage.io.imread(prefix+'new.png')),
	 	('gt', skimage.io.imread(prefix+'gt.png')),
	 	('roadtracer', skimage.io.imread(prefix+'0.png')),
	 	('recurrentunet', skimage.io.imread(prefix+'1.png')),
	 	('sat2graph', skimage.io.imread(prefix+'2.png')),
	 	#('roadconnectivity', skimage.io.imread(prefix+'2.png')),
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
