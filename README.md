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
*   **FloW-image:** Download Flow-image dataset in https://orca-tech.cn/datasets/FloW/FloW-Img. And convert format from PASCAL_VOC to YOLO.
*   **WSODD:**
