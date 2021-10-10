Source
------

We adapt the [original code](https://github.com/anilbatra2185/road_connectivity) for MUNO21.


Training
--------

Prepare the dataset:

	mkdir tmp-deepglobe/ /data/deepglobe/
	export GO111MODULE=off
	go get github.com/mitroadmaps/gomapinfer/common
	go run muno_prepare_data.go /data/graphs/graphs/ ../../go/sizes.json /data/train.json tmp-deepglobe/
	(Copy the most recent aerial images to tmp-deepglobe/ renamed to be like the generated PNG files but as JPEG)
	bash split_data.sh tmp-deepglobe/ /data/deepglobe/ .jpg .png
	python create_crops.py --base_dir /data/deepglobe/ --crop_size 512 --crop_overlap 256 --im_suffix .jpg --gt_suffix .png

Train the model:

	python train_mtl.py --config config.json --dataset deepglobe --model_name "StackHourglassNetMTL" --exp dg_stak_mtl


Inference
---------

Apply the model:

	mkdir -p outputs/{60,80,100,120,140,160,180}
	python infer_muno.py /data/naip/jpg/ /data/annotations.json /data/test.json outputs/ /ssd_scratch/cvit/anil.k/exp/deepglobe100/dg_stak_mtl/model_best.pth.tar
