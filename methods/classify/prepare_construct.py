import json
import math
import os.path
import random
import sys

import classify_lib

sys.path.append('../../python')
from discoverlib import geom, graph

# find examples for constructed/deconstructed road classifier
# each example is a road segment plus two image years, where
#   road is not visible in first year but visible in second
# when we create example for deconstructed road, the second year
#   is actually earlier than the first

annotation_fname = sys.argv[1]
graph_dir = sys.argv[2]
jpg_dir = sys.argv[3]
train_csv = sys.argv[4]
out_fname = sys.argv[5]

with open(annotation_fname, 'r') as f:
    annotations = json.load(f)
with open(train_csv, 'r') as f:
    train_regions = json.load(f)
annotations = [annotation for annotation in annotations if annotation['Cluster']['Region'] in train_regions]

examples = []
for i, annotation in enumerate(annotations):
    if 'constructed' not in annotation['Tags'] and 'bulldozed' not in annotation['Tags']:
        continue

    print(i, '/', len(annotations))

    constructed_segments = []
    deconstructed_segments = []
    cluster = annotation['Cluster']
    for change in cluster['Changes']:
        if change['Deleted']:
            deconstructed_segments.extend(change['Segments'])
        else:
            constructed_segments.extend(change['Segments'])

    years = classify_lib.get_image_years(jpg_dir, cluster['Region'], cluster['Tile'])

    for segments, is_constructed in [(constructed_segments, True), (deconstructed_segments, False)]:
        if is_constructed:
            cur_years = years
        else:
            cur_years = [years[1], years[0]]

        g = classify_lib.make_graph_from_segments(segments)
        road_segments, _ = graph.get_graph_road_segments(g)
        gt_graph = classify_lib.get_graph(graph_dir, cluster['Region'], cluster['Tile'], '_2020-07-01.graph')
        for rs in road_segments:
            points3 = classify_lib.get_points3(rs)
            examples.append((cluster['Region'], cluster['Tile'], points3, 1, cur_years))

# negative examples
for i, annotation in enumerate(annotations):
    if 'nochange' not in annotation['Tags']:
        continue

    print('negative', i, '/', len(annotations))

    cluster = annotation['Cluster']
    years = classify_lib.get_image_years(jpg_dir, cluster['Region'], cluster['Tile'])
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
        cur_years = list(years)
        random.shuffle(cur_years)
        examples.append((cluster['Region'], cluster['Tile'], points3, 0, cur_years))

with open(out_fname, 'w') as f:
    json.dump(examples, f)
