import os.path
import skimage.io

inp = '''210 61,87,600,600
512 0,224,340,340
103 90,0,620,620
203 0,80,383,383
205 auto
215 auto
480 0,0,351,351
482 auto
300 38,161,375,375
206 auto
123 61,37,500,500
289 auto
272 50,128,450,450
473 auto
285 0,0,388,388
207 auto
297 634,444,450,450
186 auto
226 63,100,600,600
410 90,0,464,464
204 auto
223 0,82,350,350
290 0,0,360,360
423 auto
513 auto
483 auto
299 122,69,638,638
282 auto
293 auto
124 auto
298 263,0,474,474
472 44,282,500,500
304 auto
406 25,65,500,500
415 182,77,500,500
99 1910,275,600,600
222 auto
470 28,30,350,350
475 auto
469 auto
419 4,30,440,440
275 38,56,750,750
224 auto
229 auto
416 auto
92 auto
391 auto
227 auto
127 auto
402 760,538,600,600'''

for i, line in enumerate(inp.split("\n")):
	parts = line.strip().split(' ')
	label = parts[0]
	prefix = os.path.join('/tmp/b/', label+'_')
	ims = [
	 	('old', skimage.io.imread(prefix+'old.png')),
	 	('new', skimage.io.imread(prefix+'new.png')),
	 	('gt', skimage.io.imread(prefix+'gt.png')),
	 	('roadtracer', skimage.io.imread(prefix+'0.png')),
	 	('recurrentunet', skimage.io.imread(prefix+'1.png')),
	 	('sat2graph', skimage.io.imread(prefix+'2.png')),
	 	('roadconnect', skimage.io.imread(prefix+'3.png')),
	 	('maid', skimage.io.imread(prefix+'4.png')),
	 	('maidprune', skimage.io.imread(prefix+'5.png')),
	 	('delroad', skimage.io.imread(prefix+'6.png')),
	]
	if parts[1] == 'auto':
		im = ims[0][1]
		smaller_dim = min(im.shape[0], im.shape[1])
		window = [im.shape[1]//2-smaller_dim//2, im.shape[0]//2-smaller_dim//2, im.shape[1]//2+smaller_dim//2, im.shape[0]//2+smaller_dim//2]
	else:
		xywh = [int(s) for s in parts[1].split(',')]
		window = [xywh[0], xywh[1], xywh[0]+xywh[2], xywh[1]+xywh[3]]

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
