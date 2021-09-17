MUNO21
------

MUNO21 is a dataset and benchmark for machine learning methods that automatically update and maintain digital street map datasets.
Previous datasets focus on road extraction, and measure how well a method can infer a road network from aerial or satellite imagery.
In contrast, MUNO21 measures how well a method can modify the road network data in an existing digital map dataset to make it reflect the latest physical road network visible from imagery.
This task is more practical, since it doesn't throw away the existing map, but also more challenging, as physical roads may be constructed, bulldozed, or otherwise modified.

For more details, see https://favyen.com/muno21/.

This repository contains the code that was used to create MUNO21, as well as code for working with the dataset and computing evaluation metrics.


Requirements
------------

Compiler and application requirements include the following. The versions are
what we use and older versions make work as well.

- Go 1.16+ (with older versions, module-aware mode must be enabled)
- Python 3.5
- [osmium-tool](https://osmcode.org/) 2.16.0 (only needed for dataset pre-processing)
- ImageMagick 6.8 (only needed for dataset pre-processing)

Python requirements are in requirements.txt, and can be installed with:

	pip install -r requirements.txt

These requirements should be sufficient to run dataset pre-processing,
automatic candidate generation and clustering, visualization, metric
evaluation, and post-processing with removing G_extra and fusing new roads into
the base map.

To run the included map update methods, a range of additional requirements are
needed, depending on the particular method:

- TensorFlow 1.15 (not 2.0)
- pytorch 1.7
- scipy 1.4
- OpenCV
- [rdp](https://pypi.org/project/rdp/)


Obtain the MUNO21 Dataset
-------------------------

Download and extract the MUNO21 dataset:

	wget https://favyen.com/files/muno21.zip
	unzip muno21.zip

In the commands below, we may assume that you have placed the dataset in /data/:

	mv mapupdate/ /data/

The dataset includes aerial image and road network data in large tiles around
several cities, along with annotations that specify the map update scenarios.
Some steps below will require road network data to be extracted in windows
corresponding to the scenarios:

	cd muno21/go/
	mkdir /data/identity
	export PYTHONPATH=../python/
	python ../methods/identity/run.py /data/graphs/graphs/ /data/annotations.json /data/identity/

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

Applying a method to infer road networks should yield a directory containing
subdirectories (corresponding to different confidence thresholds) that each
contain .graph files. Most methods require post-processing under our map fusion
approach before evaluation.

Suppose that you have computed the outputs of MAiD in `/data/maid/out/`.
Then, for each confidence threshold:

	mkdir /data/maid/fuse/
	mkdir /data/maid/fuse/10/
	go run postprocess/fuse.go /data/annotations.json normal /data/identity/ /data/maid/out/10/ /data/maid/fuse/10/

Optionally, visualize an inferred road network. Below, 6 can be changed to any
annotation index corresponding to `/data/annotations.json`.

	go run vis/visualize_inferred.go /data/annotations.json 6 /data/naip/jpg/ /data/graphs/graphs/ /data/maid/fuse/10/ default ./

The command above should produce an image `./6.jpg`.


Evaluation
----------

For each confidence threshold, run e.g.:

	python metrics/apls.py /data/annotations.json /data/maid/fuse/10/ /data/graphs/graphs/ /data/test.json
	go run metrics/geo.go /data/annotations.json /data/maid/fuse/10/ /data/graphs/graphs/ /data/test.json

Above, the first command computes APLS (which takes a long time to run) while
the second computes PixelF1 (aka GEO metric). These commands produce
`scores.json` and `geo.json` files respectively in the /data/maid/fuse/10/
directory containing metric outputs for each test scenario.

To obtain error rate:

	go run metrics/error_rate.go /data/annotations.json /data/maid/fuse/10/ /data/graphs/graphs/ /data/test.json

To produce a precision-recall curve from the scores across multiple confidence
thresholds, run:

	python metrics/score_details.py /data/annotations.json /data/maid/fuse/{10,20,30,40,50}/geo.json


Building the Dataset
-------------------

The documentation below outlines how the dataset was built. You do not need
to follow these steps unless you are trying to replicate the dataset from
raw NAIP aerial images from Google EarthEngine and OpenStreetMap history dumps.

### Dataset Pre-processing

We preprocess raw NAIP and OSM data using the code in `go/preprocess`.

1. Obtain NAIP images from Google EarthEngine.
2. Obtain us-internal.osh.pbf from https://download.geofabrik.de/north-america/us.html
3. Extract history around individual cities: `go run preprocess/osm_space_filter.go /data/graphs/big/us-internal.osh.pbf /data/graphs/history/`
4. Extract OSM dumps at different times: `python3 preprocess/osm_time_filter.py /data/graphs/history/ /data/graphs/osm/`
5. Convert NAIP images to JPG: `python3 preprocess/tif_to_jpg.py /data/naip/tif/ /data/naip/jpg/`
6. Record the NAIP image sizes (needed for coordinate transforms and such): `python3 preprocess/save_image_sizes.py /data/naip/jpg/ /data/sizes.json`
7. Convert to MUNO21 .graph file format: `go run preprocess/osm_to_graph.go /data/graphs/osm/ /data/graphs/graphs/`
8. Randomly split the cities into train/test: `python3 preprocess/pick_train_test.py /data/graphs/history/ /data/`
9. (Optional) Visualize the graph and image extracted at a tile: `python3 vis/vis.py /data/naip/jpg/ny_1_0_2019.jpg /data/graphs/graphs/ny_1_0_2018-07-01.graph out.jpg`


### Candidate Generation and Clustering

We then generate and cluster candidates.

1. Candidate generation: `go run annotate/find_changed_roads.go /data/graphs/graphs/ /data/changes/`
2. Clustering: `go run annotate/cluster_changes.go /data/changes/ /data/cluster/`
3. No-change windows: `go run annotate/find_nochange.go /data/graphs/graphs/ /data/cluster-nochange/`
4. Output visualizations for annotation: `go run annotate/visualize_clusters.go /data/cluster/ /data/naip/jpg/ /data/graphs/graphs/ /data/vis/`


### Annotation Post-processing

After using the annotation tools like `go/annotate`, we process the output annotations into JSON file:

1. Convert annotation data to JSON: `go run process_annotations.go /data/cluster/ /data/annotations.txt /data/cluster-nochange/ /data/annotations.json`
