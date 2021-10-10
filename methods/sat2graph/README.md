Source
------

We adapt the [original code](https://github.com/songtaohe/Sat2Graph) for MUNO21.


Training
--------

Convert the dataset to the format expected by Sat2Graph:

	mkdir dataset/
	python prepare_dataset/download.py /data/train.json /data/naip/jpg/ /data/graphs/graphs/ dataset/

Train the model:

	python model/train.py -model_save mymodel -instance_id mymodel -image_size 352 -osmdataset dataset/


Inference
---------

Replace mymodelmymodel_352_8__channel12 with the path that Sat2Graph saved the model.

	mkdir outputs
	python model/infer_muno.py mymodelmymodel_352_8__channel12/model130000 /data/naip/jpg/ /data/annotations.json /data/test.json outputs/
