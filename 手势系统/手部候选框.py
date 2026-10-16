"""摄像头 ROI 内基于肤色与轮廓的启发式候选手部框。

这不是深度学习目标检测模型，不提供定位精度保证。
只在已有分类模型明确识别为非“无手”手势时尝试画框，
找不到候选时不画，避免把固定 ROI 当成真正定位结果。
"""
from __future__ import annotations
import cv2
import numpy as np
from .预处理 import 获取识别矩形


def 搜索候选手框(画面: np.ndarray, 比例: float = .78) -> tuple[int,int,int,int] | None:
    if not isinstance(画面, np.ndarray) or 画面.ndim != 3 or 画面.shape[2] != 3:
        return None
    x1,y1,x2,y2 = 获取识别矩形(画面, 比例)
    roi = 画面[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    ycc = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
    # RGB 摄像头上的通用肤色阈值，光照/肤色/背景变化会导致漏检或误检。
    hsv_mask = cv2.inRange(hsv, (0, 22, 43), (25, 255, 255))
    ycc_mask = cv2.inRange(ycc, (0, 128, 75), (255, 183, 137))
    mask = cv2.bitwise_and(hsv_mask, ycc_mask)
    size = max(3, int(min(roi.shape[:2]) / 85) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(size,size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    area_roi = roi.shape[0]*roi.shape[1]
    scored=[]
    for c in contours:
        area=cv2.contourArea(c)
        bx,by,bw,bh=cv2.boundingRect(c)
        box_area=bw*bh
        if area < area_roi * 0.014 or box_area > area_roi*.83:
            continue
        if bw < roi.shape[1]*.10 or bh < roi.shape[0]*.10:
            continue
        if area / max(1,box_area) < .18:
            continue
        scored.append((area,(x1+bx,y1+by,x1+bx+bw,y1+by+bh)))
    return max(scored, key=lambda a:a[0])[1] if scored else None


class 候选框平滑器:
    def __init__(self, 平滑=.38):
        self.平滑=平滑
        self.历史=None
        self.连续未检=0

    def 更新(self, 当前: tuple[int,int,int,int] | None):
        if 当前 is None:
            self.连续未检+=1
            if self.连续未检 >= 2: self.历史=None
            return None  # 本帧无法定位时不显示旧框
        self.连续未检=0
        if self.历史 is None:
            self.历史=tuple(map(float,当前))
        else:
            self.历史=tuple((1-self.平滑)*a+self.平滑*b for a,b in zip(self.历史,当前))
        return tuple(round(a) for a in self.历史)

    def 重置(self):
        self.历史=None
        self.连续未检=0
