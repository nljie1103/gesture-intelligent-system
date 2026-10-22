"""基于 MediaPipe Hand Landmarker 的可选真实手部定位（与肤色轮廓红框不同）。

只有明确安装组件并选择手部裁剪模式才会使用；本文件不会在导入时联网。
"""
from __future__ import annotations
import numpy as np
from pathlib import Path
from .配置 import 模型目录

定位资源 = 模型目录 / '手部定位' / 'hand_landmarker.task'
策略标识 = 'hand-landmarker-v1'


def 包含定位资源(path=None):
    path=Path(path or 定位资源)
    return path.is_file() and path.stat().st_size>1_000_000


def 框到方形(box,width:int,height:int,scale:float=1.8):
    x1,y1,x2,y2=box
    if width<1 or height<1 or x1>=x2 or y1>=y2:return None
    cx=(x1+x2)/2;cy=(y1+y2)/2
    side=max(x2-x1,y2-y1)*scale
    side=min(side,float(min(width,height)))
    x1=max(0,min(width-side,cx-side/2));y1=max(0,min(height-side,cy-side/2))
    return tuple(map(int,(round(x1),round(y1),round(x1+side),round(y1+side))))


class 手部定位器:
    def __init__(self,path=None):
        self.path=Path(path or 定位资源)
        if not 包含定位资源(self.path):
            raise FileNotFoundError('尚未安装手部定位模型，请到设置页点击“安装手部定位组件”')
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError as e:
            raise RuntimeError('未安装 mediapipe；请在设置页安装手部定位组件') from e
        self.mp=mp
        options=vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_buffer=self.path.read_bytes()),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,min_hand_detection_confidence=.55,
            min_hand_presence_confidence=.5)
        self.detector=vision.HandLandmarker.create_from_options(options)
    def find_rgb(self,rgb):
        """输入 RGB numpy 数组，返回真实关键点外接的方形裁剪框或 None。"""
        if not isinstance(rgb,np.ndarray) or rgb.ndim!=3 or rgb.shape[2]!=3:return None
        h,w=rgb.shape[:2]
        img=self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                          data=np.ascontiguousarray(rgb,dtype=np.uint8))
        result=self.detector.detect(img)
        if not result.hand_landmarks:return None
        pts=result.hand_landmarks[0]
        xs=[p.x*w for p in pts];ys=[p.y*h for p in pts]
        return 框到方形((min(xs),min(ys),max(xs),max(ys)),w,h)
    def find_bgr(self,bgr):
        import cv2
        return self.find_rgb(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
    def close(self):
        self.detector.close()


def 读取训练输入策略(meta):
    strategy=meta.get('输入策略','fixed-roi-v1') if isinstance(meta,dict) else 'fixed-roi-v1'
    if strategy not in ('fixed-roi-v1',策略标识):
        raise ValueError('模型采用未知输入策略，拒绝猜测裁剪方式')
    return strategy
