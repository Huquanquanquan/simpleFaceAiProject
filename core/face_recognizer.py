# -*- coding: utf-8 -*-
"""
# --------------------------------------------------------
# @Author :  bingo
# @E-mail :
# @Date   : 2022-12-31 10:28:46
# --------------------------------------------------------
"""
import os
import traceback
import cv2
from typing import Dict, List
import numpy as np
from core import face_feature, face_detector, face_register
from configs import configs as cfg
from pybaseutils import image_utils, file_utils
from tkinter import Tk, filedialog
import shutil

import sys
import importlib
importlib.reload(sys)

class FaceRecognizer(object):
    def __init__(self, database, det_thresh=cfg.det_thresh, rec_thresh=cfg.rec_thresh, local_load=True):
        """
        @param database: 人脸数据库的路径
        @param det_thresh: 人脸检测阈值，小于该阈值的检测框会被剔除
        @param rec_thresh: 人脸识别阈值，小于该阈值的人脸识别结果为unknown，表示未知
        """
        self.det_thresh = det_thresh
        self.rec_thresh = rec_thresh
        # 初始化人脸检测
        self.faceDet = face_detector.FaceDetector(net_name=cfg.DETECTOR["net_name"],
                                                  input_size=[320, None],
                                                  conf_thresh=self.det_thresh,
                                                  device=cfg.device)
        # 初始化人脸识别特征提取
        self.faceFea = face_feature.FaceFeature(net_name=cfg.FEATURE["net_name"],
                                                input_size=cfg.FEATURE["input_size"],
                                                embedding_size=cfg.FEATURE["embedding_size"],
                                                device=cfg.device)
        # 初始化人脸数据库，用于注册人脸
        self.faceReg = face_register.FaceRegister(database, local_load=True)

    def crop_faces_alignment(self, rgb, boxes, landm):
        """
        裁剪人脸，并进行矫正
        @param rgb:
        @param boxes:
        @param landm:
        @return:
        """
        faces = self.faceDet.crop_faces_alignment(rgb, boxes, landm, alignment=True)
        return faces

    def extract_feature(self, faces: List[np.ndarray]):
        """
        提取人脸特征(不会进行人脸检测和矫正)
        @param faces: 人脸图像列表(BGR格式)
        @return: feature 返回人脸特
        """
        rgb = [cv2.cvtColor(r, cv2.COLOR_BGR2RGB) for r in faces]  # 转换为RGB格式
        feature = self.faceFea.get_faces_embedding(rgb)
        if not isinstance(feature, np.ndarray): feature = feature.numpy()
        return feature

    def detect_extract_feature(self, bgr: np.ndarray, max_face=-1, vis=True):
        """
        进行人脸检测和矫正，同时提取人脸特征
        @param bgr: 输入BGR格式的图像
        @param max_face: 最大人脸个数，默认为-1，表示全部人脸
        @param vis: 是否显示人脸检测框和人脸关键点
        @return: face_info={"boxes": 人脸检测框, "landm": 人脸关键点, "feature": 人脸特征, "face": 人脸图像}
        """
        boxes, score, landm = self.detector(bgr, max_face=max_face, vis=False)
        feature, faces = np.array([]), []
        if len(boxes) > 0 and len(landm) > 0:
            faces = self.crop_faces_alignment(bgr, boxes, landm)
            feature = self.extract_feature(faces)
        face_info = {"boxes": boxes, "landm": landm, "feature": feature, "face": faces}
        if vis: self.draw_result("Detector", image=bgr, face_info=face_info, vis=vis)
        return face_info

    def detector(self, bgr, max_face=-1, vis=False):
        """
        进行人脸检测和关键点检测
        @param bgr: 输入BGR格式的图像
        @param max_face: 图像中最大人脸个数，-1表示全部人脸
        @param vis: 是否可视化检测效果
        @return:
        """
        boxes, score, landm = self.faceDet.detect_face_landmarks(bgr, vis=vis)
        if len(boxes) > 0 and max_face > 0:
            max_face = min(len(boxes), max_face)
            boxes = boxes[:max_face]
            score = score[:max_face]
            landm = landm[:max_face]
        return boxes, score, landm

    def detect_search(self, bgr, max_face=-1, vis=True):
        """
        进行人脸检测,1:N人脸搜索
        @param bgr:
        @param max_face:
        @param vis:
        @return:
        """
        # 人脸检测并提取人脸特征
        face_info: Dict = self.detect_extract_feature(bgr, max_face=max_face, vis=False)
        # 匹配人脸
        label, score = self.search_face(face_fea=face_info["feature"], rec_thresh=self.rec_thresh)
        face_info.update({"label": label, "score": score})
        if vis: self.draw_result("Recognizer", image=bgr, face_info=face_info, vis=vis)
        return face_info

    def create_database(self, portrait, vis=True):
        """
        生成人脸数据库(Face Database)
        @param portrait:人脸数据库目录，要求如下：
                          (1) 图片按照[ID-XXXX.jpg]命名,如:张三-image.jpg，作为人脸识别的底图
                          (2) 人脸肖像照片要求五官清晰且正脸的照片，不能出现多个人脸的情况
        @param vis: 是否可视化人脸检测效果
        @return:
        """
        print(">>>>>>>>>>>>>开始注册人脸<<<<<<<<<<<<<<")
        image_list = file_utils.get_images_list(portrait)
        for image_file in image_list:
            name = os.path.basename(image_file)
            label = name.split("-")[0]
            if len(name) == len(label):
                print("file={},\t图片名称不合法，请将图片按照[ID-XXXX.jpg]命名,如:张三-image.jpg".format(image_file))
                continue
            bgr = image_utils.read_image_ch(image_file)
            print("file={},\t".format(image_file), end="")
            self.add_face(face_id=label, bgr=bgr, vis=vis)
        # 更新人脸数据库并保存
        self.faceReg.update()
        self.faceReg.save()
        print(">>>>>>>>>>>>>完成注册人脸<<<<<<<<<<<<<<")
        return

    def draw_result(self, title, image, face_info, thickness=2, fontScale=1.0, color=(0, 255, 0), delay=0, vis=True):
        """
        @param title:
        @param image:
        @param face_info:
        @param thickness:
        @param fontScale:
        @param delay:
        @param vis:
        @return:
        """
        boxes = face_info["boxes"]
        if "landm" in face_info:
            radius = int(2 * thickness)
            image = image_utils.draw_landmark(image, face_info["landm"], color=color, radius=radius, vis_id=False)
        if "score" in face_info:
            score = face_info["score"].reshape(-1).tolist()
            label = face_info["label"] if "label" in face_info else [""] * len(boxes)
            text = ["{},{:3.3f}".format(l, s) for l, s in zip(label, score)]
        else:
            text = [""] * len(boxes)
        image = image_utils.draw_image_bboxes_text(image, boxes, text, thickness=thickness, fontScale=fontScale,
                                                   color=color, drawType="chinese")
        if vis and "label" in face_info: print("pred label:{}".format(text))
        if vis: image_utils.cv_show_image(title, image, delay=delay)
        return image

    def add_face(self, face_id: str, bgr: np.ndarray, vis=False):
        """
        :param face_id:  人脸ID(如姓名、学号，身份证等标识)
        @param bgr: 原始图像
        @param vis: 是否可视化人脸检测效果
        @return:
        """
        info = self.detect_extract_feature(bgr, max_face=1, vis=vis)
        if len(info["boxes"]) == 0:
            print("Warning:{}".format("no face"))
            return False
        self.faceReg.add_face(face_id, face_fea=info["feature"])
        print("注册人脸:ID={}\t".format(face_id))
        return True

    def del_face(self, face_id: str):
        """
        注销(删除)人脸
        :param face_id:  人脸ID(如姓名、学号，身份证等标识)
        :return:
        """
        return self.faceReg.del_face(face_id)

    def search_face(self, face_fea, rec_thresh):
        """
        1:N人脸搜索，比较人脸特征相似程度,如果相似程度小于rec_thresh的ID,则返回unknown
        :param face_fea: 人脸特征,shape=(nums_face, embedding_size)
        :param rec_thresh: 人脸识别阈值
        :return:返回预测pred_id的ID和距离分数pred_scores
        """
        label, score = self.faceReg.search_face(face_fea=face_fea, score_thresh=rec_thresh)
        return label, score

    def compare_face(self, image1, image2):
        """
        1:1人脸比对，compare pair image
        :param  image1: BGR image
        :param  image2: BGR image
        :return: similarity
        """
        # 进行人脸检测和矫正，同时提取人脸特征
        face_info1 = self.detect_extract_feature(image1, max_face=1, vis=False)
        face_info2 = self.detect_extract_feature(image2, max_face=1, vis=False)
        # 比较人脸特征的相似性(similarity)
        score = 0
        if len(face_info1['face']) > 0 and len(face_info2['face']) > 0:
            score = self.compare_feature(face_fea1=face_info1["feature"], face_fea2=face_info2["feature"])
        return face_info1, face_info2, score

    def compare_feature(self, face_fea1, face_fea2):
        """
        1:1人脸比对，compare two faces vector
        :param  face_fea1: face feature vector
        :param  face_fea2: face feature vector
        :return: similarity
        """
        score = self.faceReg.compare_feature(face_fea1, face_fea2)
        return score

    # def detect_image_dir(self, image_dir, out_dir=None, vis=True):
    #     """
    #     @param image_dir:
    #     @param out_dir:
    #     @param vis:
    #     @return:
    #     """
    #     pred_label = []
    #     image_list = file_utils.get_files_list(image_dir, postfix=["*.jpg"])
    #     for image_file in image_list:
    #         try:
    #             print("image_file:{}\t".format(image_file), end=',', flush=True)
    #             image = image_utils.read_image_ch(image_file)
    #             face_info = self.detect_search(image, max_face=-1, vis=vis)
    #             if "label" in face_info:
    #                 pred_label.extend(face_info["label"])
    #         except:
    #             traceback.print_exc()
    #             print(image_file)
    #     return pred_label

    def detect_image_dir(self, image_dir, out_dir=None, vis=True):
        pred_label = []
        image_list = file_utils.get_files_list(image_dir, postfix=["*.jpg"])
        for image_file in image_list:
            try:
                print("image_file: {}\t".format(image_file), end=',', flush=True)
                image = image_utils.read_image_ch(image_file)
                face_info = self.detect_search(image, max_face=-1, vis=vis)
                if "label" in face_info and "score" in face_info:
                    pred_label.extend(["{},{}".format(l, s) for l, s in zip(face_info["label"], face_info["score"])])
                else:
                    print("Warning: No label or score found for image {}".format(image_file))
            except:
                traceback.print_exc()
                print("Error processing image {}".format(image_file))
        return pred_label

    def getscore(pred_label):
        """
        从预测标签中提取数值部分，并保留小数点后四位
        @param pred_label: 预测标签列表，每个元素为形如"ID,0.123"的字符串
        @return: 包含小数点后四位的数值部分列表
        """
        scores = []
        for label in pred_label:
            try:
                score = float(label.split(",")[1])
                score_rounded = round(score, 4)  # 保留小数点后四位
                scores.append(score_rounded)
            except IndexError:
                scores.append(0.0)  # 如果没有分数，则默认为0.0
            except ValueError:
                scores.append(0.0)  # 如果无法解析成浮点数，则默认为0.0
        return scores


# 添加图片到database_test中，实现随意添加
def selectface():
    root = Tk()
    root.withdraw()  # 隐藏主窗口

    # 让用户选择一个文件
    file_path = filedialog.askopenfilename(
        title='选择人脸识别的图片', filetypes=[("Image files", "*.jpg;*.jpeg;*.png")]
    )

    if file_path:
        # 获取脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 定义保存重命名后图片的目标文件夹
        target_dir = os.path.join(script_dir, "../data/database-test")

        # 如果目标文件夹不存在，则创建它
        os.makedirs(target_dir, exist_ok=True)

        # 构建新的文件名格式
        new_file_name = "test"
        file_counter = 1

        while True:
            new_file_path = os.path.join(target_dir, f"{new_file_name}{file_counter:04d}.jpg")
            if not os.path.exists(new_file_path):
                break
            file_counter += 1

        # 将选择的文件复制到目标文件夹，并使用新的文件名
        shutil.copy(file_path, new_file_path)

        print(f"已将选择的文件复制并重命名为：{os.path.basename(new_file_path)}")

    faceshibie()

def faceshibie():

    script_dir = os.path.dirname(__file__)
    portrait = os.path.join(script_dir, "../data/database/portrait")
    test_dir = os.path.join(script_dir, "../data/database-test")

    data_name = os.path.join(os.path.dirname(portrait), "data.json")
    fr = FaceRecognizer(data_name)
    fr.create_database(portrait, vis=False)
    pred_label = fr.detect_image_dir(test_dir, vis=True)
    scores = FaceRecognizer.getscore(pred_label)
    return scores

# 获取识别度
def faceshibie2():
    script_dir = os.path.dirname(__file__)
    portrait = os.path.join(script_dir, "../data/database/portrait")
    test_dir = os.path.join(script_dir, "../data/database-test")

    data_name = os.path.join(os.path.dirname(portrait), "data.json")
    fr = FaceRecognizer(data_name)
    fr.create_database(portrait, vis=False)
    pred_label = fr.detect_image_dir(test_dir, vis=False)
    scores = FaceRecognizer.getscore(pred_label)

    # 如果scores是一个包含数字的列表，返回第一个数字
    if scores:
        return scores[0]  # 返回列表中的第一个元素（数字）
    else:
        return None  # 如果scores为空列表，则返回None或者适当的错误处理


if __name__ == "__main__":

    #selectface()
    #faceshibie()
    faceshibie2()