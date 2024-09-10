import os
import cv2
import numpy as np


# 定义 gamma 变换函数
def gamma_transform(img, gamma):
    gamma_corrected = np.uint8(cv2.pow(img / 255.0, gamma) * 255)
    return gamma_corrected


# 文件夹路径
folder_path = "D:\dataset/trash_data\low-light\images"
folder_path_out = "D:\dataset/trash_data\low-light\images_corrected"

# 获取文件夹中的所有图片文件
image_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]


# 循环处理每个图片文件
for image_file in image_files:
    # 加载图像
    img = cv2.imread(os.path.join(folder_path, image_file), cv2.IMREAD_COLOR)

    # 随机生成 gamma 值
    gamma = np.random.uniform(1.5, 5)

    # 应用 gamma 变换
    gamma_corrected_img = gamma_transform(img, gamma)

    # 保存处理后的图像
    output_file = os.path.join(folder_path_out, image_file)
    cv2.imwrite(output_file, gamma_corrected_img)

print("Gamma correction completed for all images.")
