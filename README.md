# SpatialIE: Towards Adaptive Floating Waste Detection in Unpredictable Weather
This project is the code of SpatialIE, based on YOLOv5. We will give an overview of the installation of the environment and the adaptation experiment.
## Installation of the Environment
```python
# create conda env
conda create -n yolov5 python=3.8 -y
# activate the environment
conda activate yolov5
# install pytorch
pip install torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html
# install
cd yolov5_SpatialIE
pip install -r requirements.txt
```
## Dataset Download and Convert dataset format
1. Dataset Download
*   **FloW-image:** Download the Flow-image dataset at https://orca-tech.cn/datasets/FloW/FloW-Img. And convert the format from PASCAL_VOC to YOLO. According to image_fog_effect.py, image_lowlight_effect.py, and image_rain_effect.py, fog, low-light, and rain effects are applied to the selected images, respectively.
*   **WSODD:** Download the WSODD dataset at https://github.com/sunjiaen/WSODD?tab=readme-ov-file. Please note, we cleaned this dataset and only used images containing the categories rubbish, animal, and ball for the experiments in this paper.
2. Organizing the Dataset as following (the dataset format follow YOLO format.):
> yolov5_SpatialIE
>> datasets
>>> Annotations
>>>> 000001.xml
   
>>> Images  
>>>> 000001.jpg

>>> ImageSets  
>>>> train.txt  
>>>> val.txt  
>>>> test.txt
  
>>> labels  
>>>> 000001.txt

>>> hyps

>>> bottle_foggy.yaml

>>> train.txt

>>> val.txt

>>> test.txt
## Training
```python
python train.py --data bottle_foggy.yaml --cfg yolov5s.yaml --weights '' --epochs 300 --device 0
```

















