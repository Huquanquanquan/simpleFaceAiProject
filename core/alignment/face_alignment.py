# -*- coding: utf-8 -*-
"""
# --------------------------------------------------------
# @Author :  bingo
# @E-mail :
# @Date   : 2022-12-31 10:28:46
# --------------------------------------------------------
"""

import os, sys
import numpy as np
import cv2
from tkinter import Tk, filedialog
import shutil
from pybaseutils import image_utils
from core.detection.light_detector.light_detector import UltraLightFaceDetector
import core.detection.light_detector.light_detector

sys.path.insert(0, os.path.dirname(__file__))
from core.alignment.alignment import cv_face_alignment
from pybaseutils import image_utils
import torch
import ui4


def show_landmark_boxes(title, image, landmarks, boxes, color=(0, 255, 0)):
    '''
    显示landmark和boxes
    :param title:
    :param image:
    :param landmarks: [[x1, y1], [x2, y2]]
    :param boxes:     [[ x1, y1, x2, y2],[ x1, y1, x2, y2]]
    :return:
    '''
    point_size = 1
    thickness = 8  # 可以为 0 、4、8
    for lm in landmarks:
        for landmark in lm:
            # 要画的点的坐标
            point = (int(landmark[0]), int(landmark[1]))
            cv2.circle(image, point, point_size, color, thickness * 2)
    for box in boxes:
        x1, y1, x2, y2 = box
        point1 = (int(x1), int(y1))
        point2 = (int(x2), int(y2))
        cv2.rectangle(image, point1, point2, color, thickness=thickness)
    image_utils.cv_show_image(title, image, delay=0)


def face_alignment(image, landmarks, vis=False):
    """
    face alignment and crop face ROI
    :param image:输入RGB/BGR图像
    :param landmarks:人脸关键点landmarks(5个点)
    :param vis: 可视化矫正效果
    :return:
    """
    output_size = [112, 112]
    alig_faces = []
    kpts_ref = cv_face_alignment.get_reference_facial_points(square=True, vis=vis)
    # kpts_ref = align_trans.get_reference_facial_points(output_size, default_square=True)
    for landmark in landmarks:
        warped_face = cv_face_alignment.alignment_and_crop_face(np.array(image), output_size, kpts=landmark,
                                                                kpts_ref=kpts_ref)
        alig_faces.append(warped_face)
    if vis:
        for face in alig_faces: image_utils.cv_show_image("face_alignment", face)
    return alig_faces

def facealirun():
    image_file = core.detection.light_detector.light_detector.selectimage()  # 选择要处理的图片文件
    if not image_file:
        print("No image selected!")
        sys.exit(0)

    # 读取图片
    image = cv2.imread(image_file)
    if image is None:
        print("Failed to load image!")
        sys.exit(0)

    # Initialize the face detector
    input_size = [320, None]
    device = torch.device('cpu')
    detector = UltraLightFaceDetector(net_name="RFB", input_size=input_size, device=device)

    # Detect faces in the image
    bboxes, landms = detector.detect(image)

    # print("bboxes:\n{}\nlandms:\n{}".format(bboxes, landms))

    # 进行反射变换
    alig_faces = face_alignment(image, landms, vis=True)
    # Show the landmarks and boxes on the image
    show_landmark_boxes("face", image, landms, bboxes)


if __name__ == "__main__":

    facealirun()