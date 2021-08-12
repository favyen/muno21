import json
import math
import os.path
import sys

import classify_lib

sys.path.append('../../python')
from discoverlib import geom, graph

annotation_fname = sys.argv[1]
graph_dir = sys.argv[2]
train_csv = sys.argv[3]
out_fname = sys.argv[4]

with open(annotation_fname, 'r') as f:
    annotations = json.load(f)

with open(train_csv, 'r') as f:
    train_regions = json.load(f)
annotations = [annotation for annotation in annotations if annotation['Cluster']['Region'] in train_regions]

examples = []
for i, annotation in enumerate(annotations):
    if 'bulldozed' not in annotation['Tags'] and 'was_incorrect' not in annotation['Tags']:
        continue

    print('positive', i, '/', len(annotations))

    deleted_segments = []
    cluster = annotation['Cluster']
    for change in cluster['Changes']:
        if not change['Deleted']:
            continue
        for segment in change['Segments']:
            deleted_segments.append(segment)

    if not deleted_segments:
        continue

    # make graph from the segments
    g = classify_lib.make_graph_from_segments(deleted_segments)

    road_segments, _ = graph.get_graph_road_segments(g)
    gt_graph = classify_lib.get_graph(graph_dir, cluster['Region'], cluster['Tile'], '_2020-07-01.graph')
    for rs in road_segments:
        points3 = classify_lib.get_points3(rs)

        # skip this rs if there is edge with similar orientation near 25%/50%/75%
        ok = True
        for p in [points3[len(points3)*1//4], points3[len(points3)*2//4], points3[len(points3)*3//4]]:
            point = geom.Point(p[0], p[1])
            for edge in gt_graph.search(point.bounds().add_tol(16)):
                if edge.segment().distance(point) > 16:
                    continue
                edge_orientation = geom.Point(1, 0).signed_angle(edge.segment().vector())
                angle_difference = min(abs(p[2] - edge_orientation), 2*math.pi - abs(p[2] - edge_orientation))
                if angle_difference < 0.5:
                    ok = False
        if not ok:
            continue

        examples.append((cluster['Region'], cluster['Tile'], points3, 1))

# negative examples
for i, annotation in enumerate(annotations):
    if 'nochange' not in annotation['Tags']:
        continue

    print('negative', i, '/', len(annotations))

    cluster = annotation['Cluster']
    gt_graph = classify_lib.get_graph(graph_dir, cluster['Region'], cluster['Tile'], '_2020-07-01.graph')
    window = cluster['Window']
    rect = geom.Rectangle(
        geom.Point(window[0], window[1]),
        geom.Point(window[2], window[3])
    )
    subg = graph.graph_from_edges(gt_graph.search(rect))
    road_segments, _ = graph.get_graph_road_segments(subg)
    for rs in road_segments:
        points3 = classify_lib.get_points3(rs)
        examples.append((cluster['Region'], cluster['Tile'], points3, 0))

with open(out_fname, 'w') as f:
    json.dump(examples, f)
