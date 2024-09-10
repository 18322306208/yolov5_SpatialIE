import os
import cv2
import numpy as np


# Define the gamma transform function
def gamma_transform(img, gamma):
    gamma_corrected = np.uint8(cv2.pow(img / 255.0, gamma) * 255)
    return gamma_corrected


# Folder Path
folder_path = ""
folder_path_out = ""

# Get all image files in a folder
image_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]


# Iterate over each image file for processing.
for image_file in image_files:
    # Load Image
    img = cv2.imread(os.path.join(folder_path, image_file), cv2.IMREAD_COLOR)

    # Randomly generated gamma values
    gamma = np.random.uniform(1.5, 5)

    # Applying the gamma transform
    gamma_corrected_img = gamma_transform(img, gamma)

    # Saving processed images
    output_file = os.path.join(folder_path_out, image_file)
    cv2.imwrite(output_file, gamma_corrected_img)

print("Gamma correction completed for all images.")
