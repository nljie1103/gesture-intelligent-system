"""从零定义的轻量级卷积神经网络，支持 CPU 推理。"""
from __future__ import annotations
import torch
from torch import nn
from .配置 import 类别


class 轻量卷积网络(nn.Module):
    def __init__(self, 类别数: int = len(类别)):
        super().__init__()
        self.特征 = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(64, 96, 3, padding=1), nn.BatchNorm2d(96), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((3, 3)),
        )
        self.分类器 = nn.Sequential(nn.Flatten(), nn.Linear(96 * 3 * 3, 128), nn.ReLU(inplace=True),
                                     nn.Dropout(.25), nn.Linear(128, 类别数))

    def forward(self, 输入):
        return self.分类器(self.特征(输入))


def 加载分类模型(路径, 设备: str = "cpu"):
    """只读取权重字典，避免反序列化任意 Python 对象。"""
    检查点 = torch.load(路径, map_location=设备, weights_only=True)
    if 检查点.get("类别") != 类别:
        raise ValueError("模型类别定义与程序不一致，请重新训练")
    模型 = 轻量卷积网络(len(类别)).to(设备)
    模型.load_state_dict(检查点["权重"])
    模型.eval()
    return 模型, int(检查点["输入尺寸"]), 检查点
