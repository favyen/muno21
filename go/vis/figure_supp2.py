import os.path
import skimage.io

inp = '''666 auto
934 0,0,632,632
1012 auto
1247 auto
733 auto
670 auto
1187 auto
783 auto
918 auto
927 auto
1185 auto
1249 auto
742 auto
995 auto
1009 auto
723 auto
753 auto
669 auto
1088 auto
978 auto
1215 auto
663 auto
1203 auto
728 auto
1244 auto
943 auto
1183 auto
1242 auto
1251 auto
946 auto
639 auto
990 auto
1051 auto
1045 auto
1016 auto
662 auto
949 auto
1220 0,20,569,569
924 auto
774 auto
773 auto
935 auto
1224 auto
1052 auto
926 auto
1005 0,241,576,576
749 auto
668 auto'''

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
