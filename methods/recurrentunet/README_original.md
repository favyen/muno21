This is the code for "Road Detection and Centerline Extraction via Deep Recurrent Convolutional Neural Network U-Net".

You will first need to follow dataset preparation instructions from RoadTracer code. You will also need to copy discoverlib folder from RoadTracer code.

Suppose the imagery is in `/data/imagery` and the masks are in `/data/masks`. First, train the model:

	mkdir /data/rcnnunet_model/
	mkdir /data/rcnnunet_model/model_latest
	mkdir /data/rcnnunet_model/model_best
	cd roadtracer-master/
	python ./rcnnunet/train.py ./data/imagery/ ./data/masks/ ./data/rcnnunet_model/

Then, you can run inference on the test regions:

	mkdir outputs
	python infer.py /data/imagery/ /data/rcnnunet_model/

The latest step is to transfer the segmentation to graph(if it's needed)
Extract graphs from the segmentation outputs:

	python ../utils/mapextract.py outputs/boston.png 50 outputs/boston.graph

Correct the coordinates of the graph vertices by adding an offset (which depends on the region). mapextract.py outputs coordinates corresponding to the imagery. However, the origin of the test image may not be at (0, 0), and fix.py accounts for this.

	python ../utils/fix.py boston outputs/boston.graph outputs/boston.fix.graph
Reference
RoadTracer: Automatic Extraction of Road Networks from Aerial Images:https://roadmaps.csail.mit.edu/roadtracer.pdf

