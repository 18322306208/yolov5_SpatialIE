import cv2 as cv, math
import cv2
import numpy as np
import random
import os

file = ''  # Input path to the image folder



def demo():
    for file_img in os.listdir(file):  # Folders to process
        print(file_img)
        img_path = os.path.join(file, file_img)

        img = cv.imread(img_path) 
        print(img_path)


        img_f = img / 255.0 
        (row, col, chs) = img.shape

        A = 0.5  
        beta = 0.14  # This is the concentration of the fog. It's adjustable.
        size = math.sqrt(max(row, col))  
        center = (row // 2, col // 2)  
        for j in range(row):
            for l in range(col):
                d = -0.04 * math.sqrt((j - center[0]) ** 2 + (l - center[1]) ** 2) + size
                td = math.exp(-beta * d)
                img_f[j][l][:] = img_f[j][l][:] * td + A * (1 - td)
        cv2.imwrite(file_img, img_f*255) 
        cv2.imshow("src", img)
        cv2.imshow("dst", img_f) 

if __name__ == '__main__':
    demo()
