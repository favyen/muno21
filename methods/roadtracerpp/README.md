Source
------

We adapt the [original code](https://github.com/mitroadmaps/MAiD/tree/master/ml) for MUNO21.


Training
--------

Prepare road directionality targets (replace 16 with desired number of threads):

	mkdir angles/
	export GO111MODULE=off
	go get github.com/mitroadmaps/gomapinfer/common
	go run mk_angles.go /data/graphs/graphs/ ../../go/sizes.json angles/ 16

Train the model:

	mkdir model/
	python train.py /data/train.json /data/naip/jpg/ angles/ model/model

Inference
---------

RoadTracer++ (repeat for multiple thresholds):

	mkdir -p outputs/30/
	python infer.py model/model /data/naip/jpg/ /data/graphs/graphs/ /data/annotations.json /data/test.json outputs/30/ infer 0.30

MAiD (repeat for multiple thresholds):

	mkdir -p outputs/30/
	python infer.py model/model /data/naip/jpg/ /data/graphs/graphs/ /data/annotations.json /data/test.json outputs/30/ extend 0.30
