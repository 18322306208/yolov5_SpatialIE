import os
import cv2
import numpy as np


folder_path = ""
output_folder = ""



def get_noise(img, value=10):
    # Generating Noisy Images
    noise = np.random.uniform(0, 256, img.shape[0:2])
    # Control the noise level by taking a floating point number and keeping only the largest portion as noise
    v = value * 0.01
    noise[np.where(noise < (256 - v))] = 0

    # Do noise initial blur
    k = np.array([[0, 0.1, 0],
                  [0.1, 8, 0.1],
                  [0, 0.1, 0]])

    noise = cv2.filter2D(noise, -1, k)

    '''cv2.imshow('img',noise)
    cv2.waitKey()
    cv2.destroyWindow('img')'''
    return noise


def rain_blur(noise, length=10, angle=0, w=1):
    # Add motion blur to the noise to mimic raindrops.

   
    trans = cv2.getRotationMatrix2D((length / 2, length / 2), angle - 45, 1 - length / 100.0)
    dig = np.diag(np.ones(length))  # Generate focus matrix
    k = cv2.warpAffine(dig, trans, (length, length))  # Generate Blur Kernel
    k = cv2.GaussianBlur(k, (w, w), 0)  # Apply Gaussian blur to the rotated diagonal kernel to give the rain width.

    # k = k / length                        

    blurred = cv2.filter2D(noise, -1, k)  # Use the rotated kernel obtained earlier to perform filtering.

    # Convert to the 0-255 range.
    cv2.normalize(blurred, blurred, 0, 255, cv2.NORM_MINMAX)
    blurred = np.array(blurred, dtype=np.uint8)
    '''
    cv2.imshow('img',blurred)
    cv2.waitKey()
    cv2.destroyWindow('img')'''

    return blurred


def alpha_rain(rain, img, beta=0.8):
   
    # beta = 0.8   #results weight
    # expand dimensin
    # Expand the 2D rain noise to a 3D single channel.
    # Combine it with the image to form a 4-channel image with an alpha channel.
    rain = np.expand_dims(rain, 2)
    rain_effect = np.concatenate((img, rain), axis=2)  # add alpha channel

    rain_result = img.copy()  # Copy a mask.
    rain = np.array(rain, dtype=np.float32)  # 
    rain_result[:, :, 0] = rain_result[:, :, 0] * (255 - rain[:, :, 0]) / 255.0 + beta * rain[:, :, 0]
    rain_result[:, :, 1] = rain_result[:, :, 1] * (255 - rain[:, :, 0]) / 255 + beta * rain[:, :, 0]
    rain_result[:, :, 2] = rain_result[:, :, 2] * (255 - rain[:, :, 0]) / 255 + beta * rain[:, :, 0]
   



    #cv2.imshow('rain_effct_result', rain_result)
    #cv2.waitKey()
    #cv2.destroyAllWindows()

    return rain_result


def add_rain(rain, img, alpha=0.9):
    

    # chage rain into  3-dimenis
    # Expand the 2D rain noise into a 3-channel image matching the original image.
    rain = np.expand_dims(rain, 2)
    rain = np.repeat(rain, 3, 2)

    # Perform weighted composition of the new image.
    result = cv2.addWeighted(img, alpha, rain, 1 - alpha, 1)
    #cv2.imshow('rain_effct', result)
    #cv2.waitKey()
    #cv2.destroyWindow('rain_effct')
    return result



image_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

# Iterate over each image file for processing.
for image_file in image_files:
    # Load the image.
    img = cv2.imread(os.path.join(folder_path, image_file), cv2.IMREAD_COLOR)

    noise = get_noise(img, value=500)

    length = np.random.randint(50, 80)
    angle = np.random.randint(-50, 51)

    rain = rain_blur(noise, length, angle, w=5)
    #rain_result = alpha_rain(rain, img, beta=0.6)  # Method 1: Assign transparency values.
    rain_result = add_rain(rain, img)  # Method 2: After weighting, achieve an effect as if viewed from outside a glass.

    output_file = os.path.join(output_folder, image_file)
    cv2.imwrite(output_file, rain_result)







