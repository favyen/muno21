Training
--------

Prepare the datasets for the various approaches.
For `prepare_incorrect.py`, the outputs of another approach are needed.

	python prepare_construct.py /data/annotations.json /data/graphs/graphs/ /data/naip/jpg/ /data/train.json construct_data.json
	python prepare_delroad.py /data/annotations.json /data/graphs/graphs/ /data/train.json delroad_data.json
	python prepare_incorrect.py /data/annotations.json /data/graphs/graphs/ /data/train.json ../roadtracerpp/outputs/30/ incorrect_data.json

Train the models:

	mkdir model_construct model_delroad model_incorrect
	python train.py construct ./ /data/naip/jpg/ /data/train.json model_construct/model
	python train.py delroad ./ /data/naip/jpg/ /data/train.json model_delroad/model
	python train.py incorrect ./ /data/naip/jpg/ /data/train.json model_incorrect/model

Inference (delroad, deconstruct)
--------------------------------

These methods delete roads from the existing map that no longer exist.
`delroad` deletes roads while only looking at the latest aerial image,
while `deconstruct` deletes roads by comparing two images.

For these methods, use a few different threshold settings to obtain a precision-recall tradeoff.

Delete roads that are no longer visible:

	mkdir -p outputs/995
	python apply_delroad.py /data/annotations.json model_delroad/model /data/naip/jpg/ delroad /data/identity/ outputs/995/ 0.995

Delete roads that were bulldozed (visible in earlier image but not in later):

	mkdir -p outputs/90
	python apply_delroad.py /data/annotations.json model_construct/model /data/naip/jpg/ deconstruct /data/identity/ outputs/90/ 0.90

Note: outputs should not be fused with the existing map, since that would add the roads we just pruned back into the map.

Inference (incorrect, construct)
--------------------------------

These methods depend on the outputs of another method (ideally the same method
used with `prepare_incorrect.py`). `incorrect` prunes detected roads that don't
seem to actually be roads, while `construct` prunes any detected road that does
not appear to be newly constructed.

First, prune detected roads from the other method that are already present in the map
(repeat this for every threshold used in the other method):

	cd /path/to/muno21/go/
	go run postprocess/fuse.go /data/annotations.json onlynew /data/identity/ ../roadtracerpp/outputs/30/ ../roadtracerpp/outputs-onlynew/30/

Delete incorrect roads:

	mkdir -p outputs/30
	python apply_incorrect.py /data/annotations.json model_incorrect/model /data/naip/jpg/ incorrect ../roadtracerpp/outputs/30/ outputs/30/

Delete roads that don't seem to have been newly constructed:

	mkdir -p outputs/30
	python apply_incorrect.py /data/annotations.json model_construct/model /data/naip/jpg/ construct ../roadtracerpp/outputs/30/ outputs/30/

Note: the precision-recall tradeoff for these methods comes from the threshold of the other method whose outputs we're pruning.
The confidence threshold for pruning is fixed at 0.5 (we can't expose two thresholds under the benchmark rules).

Note: unlike delroad/deconstruct, outputs from incorrect/construct should be fused into the existing map!
