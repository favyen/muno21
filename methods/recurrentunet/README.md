Source
------

We adapt the [original code](https://github.com/xiachangxue/Road-detection/) for MUNO21.


Training
--------

Prepare the dataset per instructions for road_connectivity approach. Then train the model:

	mkdir model
	python train.py /data/deepglobe/train_crops/images/ /data/deepglobe/train_crops/gt/ model/model

Inference
---------

Apply the model:

	mkdir -p outputs/{60,80,100,120,140,160,180}
	python infer_muno.py model/model /data/naip/jpg/ /data/annotations.json /data/test.json outputs/
