import json
import os
import os.path
import sys

sys.path.append('../python')
from discoverlib import geom, graph

# Run this on "identity" outputs to see how many meters of roads the
# no-change scenarios contain.

annotation_fname = sys.argv[1]
identity_dir = sys.argv[2]

with open(annotation_fname, 'r') as f:
    annotations = json.load(f)

meters = 0
count = 0
for annotation_idx, annotation in enumerate(annotations):
    if 'nochange' not in annotation['Tags']:
        continue
    print(annotation_idx)
    count += 1
    g = graph.read_graph(os.path.join(identity_dir, '{}.graph'.format(annotation_idx)))
    window = annotation['Cluster']['Window']
    rect = geom.Rectangle(
        geom.Point(window[0], window[1]),
        geom.Point(window[2], window[3])
    ).add_tol(128)
    graph.densify(g, 5)
    g = graph.graph_from_edges(g.edge_grid_index(128).search(rect))
    for edge in g.edges:
        # divide by two since we have one edge in each direction
        meters += edge.segment().length()/2
print(meters, count)
