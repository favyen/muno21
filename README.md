ICCV
----

This code is for review purpose only and should be kept confidential.
We will release the code under BSD or similar license later.

See supplementary.pdf for examples of map update scenarios in MUNO21.


Requirements
------------

Compiler and application requirements include the following. The versions are
what we use and older versions make work as well.

- Go 1.13
- Python 3.5
- [osmium-tool](https://osmcode.org/) 2.16.0
- ImageMagick 6.8

`osmium-tool` and ImageMagick are only needed for dataset pre-processing.

Python requirements include:
- scipy 1.4
- scikit-image 0.15
- numpy

These requirements should be sufficient to run dataset pre-processing,
automatic candidate generation and clustering, visualization, metric
evaluation, and post-processing with removing G_extra and fusing new roads into
the base map.

The individual methods have a range of other requirements.

- TensorFlow 1.15 (not 2.0)
- pytorch 1.7
- OpenCV
- [rdp](https://pypi.org/project/rdp/)


Dataset Pre-processing
----------------------

We preprocess raw NAIP and OSM data using the code in `go/preprocess`. Note
that these steps are not needed unless trying to replicate the dataset from raw
NAIP aerial images from Google EarthEngine and OpenStreetMap history dump.

1. Obtain NAIP images from Google EarthEngine.
2. Obtain us-internal.osh.pbf from https://download.geofabrik.de/north-america/us.html
3. Extract history around individual cities: `go run preprocess/osm_space_filter.go /data/graphs/big/us-internal.osh.pbf /data/graphs/history/`
4. Extract OSM dumps at different times: `python3 preprocess/osm_time_filter.py /data/graphs/history/ /data/graphs/osm/`
5. Convert NAIP images to JPG: `python3 preprocess/tif_to_jpg.py /data/naip/tif/ /data/naip/jpg/`
6. Record the NAIP image sizes (needed for coordinate transforms and such): `python3 preprocess/save_image_sizes.py /data/naip/jpg/ /data/sizes.json`
7. Convert to MUNO21 .graph file format: `go run preprocess/osm_to_graph.go /data/graphs/osm/ /data/graphs/graphs/`
8. Randomly split the cities into train/test: `python3 preprocess/pick_train_test.py /data/graphs/history/ /data/`
9. (Optional) Visualize the graph and image extracted at a tile: `python3 vis/vis.py /data/naip/jpg/ny_1_0_2019.jpg /data/graphs/graphs/ny_1_0_2018-07-01.graph out.jpg`


Candidate Generation and Clustering
-----------------------------------

1. Candidate generation: `go run annotate/find_changed_roads.go /data/graphs/graphs/ /data/changes/`
2. Clustering: `go run annotate/cluster_changes.go /data/changes/ /data/cluster/`
3. No-change windows: `go run annotate/find_nochange.go /data/graphs/graphs/ /data/cluster-nochange/`
4. Output visualizations for annotation: `go run annotate/visualize_clusters.go /data/cluster/ /data/naip/jpg/ /data/graphs/graphs/ /data/vis/`


Annotation Post-processing
--------------------------

1. Convert annotation data to JSON: `go run process_annotations.go /data/cluster/ /data/annotations.txt /data/cluster-nochange/ /data/annotations.json`


Infer Road Networks
-------------------

Refer to the documentation in methods/{classify,recurrentunet,road_connectivity,roadtracerpp,sat2graph}.

Each method besides `classify` is taken from a publicly available
implementation (see README-mapupdate in each method directory.) We make minor
changes to make them work with MUNO21. We also find many bugs in
road_connectivity which we have to manually fix, and we adapt Sat2Graph to work
with Python3. road_connectivity and recurrentunet will only work with Python 2.7.


Post-process Inferred Road Networks
-----------------------------------

1. Remove inferred roads that correspond to edges in G_extra: `go run remove_ignore_segments.go /data/annotations.json /data/graphs/graphs/ /data/maid/out/ /data/maid/out-remove/`
2. Fuse inferred road network into the base map: `go run fuse.go /data/annotations.json normal /data/graphs/graphs/ /data/maid/out-remove/ /data/maid/out-remove-fuse/`
3. (Optional) Visualize an inferred road network (change 6 to any annotation index): `go run visualize_inferred.go /data/annotations.json 6 /data/naip/jpg/ /data/graphs/graphs/ /data/roadtracerpp/out/ out.jpg`


Evaluation
----------

- APLS (takes a long time): `python3 metrics/apls.py /data/annotations.json /data/maid/out-remove-fuse/ /data/graphs/graphs/ /data/test.csv`
- PixelF1 (aka GEO): `go run metrics/geo.go /data/annotations.json /data/maid/out-remove-fuse/ /data/graphs/graphs/ /data/test.csv`
- Score breakdown: `python3 metrics/score_details.py /data/annotations.json  /data/maid/out-remove-fuse/geo.json` (or scores.json)
- Error rate: `go run metrics/error_rate.go /data/annotations.json /data/maid/out-remove-fuse/ /data/graphs/graphs/ /data/test.csv`
