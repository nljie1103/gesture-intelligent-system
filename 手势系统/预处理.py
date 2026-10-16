"""采集、训练、推理使用一致的裁剪/颜色空间。"""
from __future__ import annotations
import numpy as np
from PIL import Image


def 获取识别矩形(画面: np.ndarray, 比例: float = .78) -> tuple[int, int, int, int]:
    高, 宽 = 画面.shape[:2]
    边长 = max(16, min(int(min(高, 宽) * 比例), 高, 宽))
    左, 上 = (宽 - 边长) // 2, (高 - 边长) // 2
    return 左, 上, 左 + 边长, 上 + 边长


def 裁剪手势(画面: np.ndarray, 比例: float = .78) -> Image.Image:
    """输入为 OpenCV BGR，返回 RGB PIL 图像；画面应事先执行镜像。"""
    import cv2
    左, 上, 右, 下 = 获取识别矩形(画面, 比例)
    局部 = 画面[上:下, 左:右]
    if 局部.size == 0:
        raise ValueError("识别区域为空")
    return Image.fromarray(cv2.cvtColor(局部, cv2.COLOR_BGR2RGB))


def 图像转张量(图像: Image.Image, 尺寸: int):
    """训练和推理统一转换为 [0,1] RGB / CHW。"""
    import torch
    重采样 = getattr(Image, "Resampling", Image).BILINEAR
    数组 = np.asarray(图像.convert("RGB").resize((尺寸, 尺寸), 重采样), dtype=np.float32) / 255.0
    return torch.from_numpy(np.ascontiguousarray(数组.transpose(2, 0, 1)))
