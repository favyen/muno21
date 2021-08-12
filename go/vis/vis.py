import skimage.io
import sys

sys.path.append('../python/')
from discoverlib import geom, graph

im_fname = sys.argv[1]
graph_fname = sys.argv[2]
out_fname = sys.argv[3]

im = skimage.io.imread(im_fname)
g = graph.read_graph(graph_fname, fpoint=True)
for i, edge in enumerate(g.edges):
    if i%1000 == 0:
        print(i, len(g.edges))
    src = geom.Point(edge.src.point.x, edge.src.point.y)
    dst = geom.Point(edge.dst.point.x, edge.dst.point.y)
    for p in geom.draw_line(src, dst, geom.Point(im.shape[1], im.shape[0])):
        im[p.y, p.x, :] = [255, 0, 0]
skimage.io.imsave(out_fname, im)
