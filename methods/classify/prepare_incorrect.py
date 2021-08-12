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
inferred_dir = sys.argv[4]
out_fname = sys.argv[5]

with open(annotation_fname, 'r') as f:
    annotations = json.load(f)
with open(train_csv, 'r') as f:
    train_regions = json.load(f)

examples = []
for annotation_idx, annotation in enumerate(annotations):
    cluster = annotation['Cluster']
    if cluster['Region'] not in train_regions:
        continue
    print(annotation_idx, '/', len(annotations))

    inferred_g = graph.read_graph(os.path.join(inferred_dir, '{}.graph'.format(annotation_idx)))
    base_index = classify_lib.get_graph(graph_dir, cluster['Region'], cluster['Tile'], '_2013-07-01.graph')
    gt_index = classify_lib.get_graph(graph_dir, cluster['Region'], cluster['Tile'], '_2020-07-01.graph')
    extra_index = classify_lib.get_graph(graph_dir, cluster['Region'], cluster['Tile'], '_2020-07-01_all.graph')

    # find correct and incorrect examples of newly inferred roads
    # - newly inferred road means it's in inferred_g but halfway point is far from anything in base_index
    # - correct means it is always close to something in gt_index
    # - incorrect means halfway point is far from anything in extra_index

    road_segments, _ = graph.get_graph_road_segments(inferred_g)
    num_correct = 0
    num_incorrect = 0
    for rs in road_segments:
        points3 = classify_lib.get_points3(rs)
        if not points3:
            continue
        check_points = [points3[len(points3)*1//4], points3[len(points3)*2//4], points3[len(points3)*3//4]]

        # is this newly inferred?
        any_far_from_base = False
        for p in check_points:
            if classify_lib.is_point_close_to_graph(p, base_index, 20):
                continue
            any_far_from_base = True
            break

        if not any_far_from_base:
            continue

        # is it correct?
        is_correct = True
        for p in check_points:
            if classify_lib.is_point_close_to_graph(p, gt_index, 8):
                continue
            is_correct = False
            break

        if is_correct:
            examples.append((cluster['Region'], cluster['Tile'], points3, 0))
            num_correct += 1
            continue

        # is it incorrect?
        is_incorrect = False
        for p in check_points:
            if classify_lib.is_point_close_to_graph(p, extra_index, 20):
                continue
            is_incorrect = True
            break

        if is_incorrect:
            examples.append((cluster['Region'], cluster['Tile'], points3, 1))
            num_incorrect += 1
            continue

    print('got {} correct and {} incorrect'.format(num_correct, num_incorrect))

with open(out_fname, 'w') as f:
    json.dump(examples, f)
