"""快速诊断依赖、PyTorch 与摄像头基础状况。"""
import sys
from pathlib import Path
import numpy
import cv2
import PIL
import torch
from 手势系统.配置 import 读取配置, 建立运行目录, 模型目录, 类别

if __name__ == '__main__':
    建立运行目录()
    print('Python: ', sys.version)
    print('Python 解释器: ', sys.executable)
    print('NumPy: ', numpy.__version__)
    print('OpenCV: ', cv2.__version__)
    print('Pillow: ', PIL.__version__)
    print('PyTorch: ', torch.__version__)
    print('CUDA 可用: ', torch.cuda.is_available())
    print('类别: ', '、'.join(类别))
    print('正式模型: ', '已存在' if (模型目录 / '正式模型.pt').is_file() else '尚未训练')
    print('配置: ', 读取配置())
    编号 = int(读取配置()['摄像头编号'])
    摄像头 = cv2.VideoCapture(编号, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
    try:
        print(f'摄像头 #{编号}: ', '可打开' if 摄像头.isOpened() else '不可打开（需检查权限/占用/编号）')
        if 摄像头.isOpened():
            正常, 画面 = 摄像头.read()
            print('首帧读取: ', '成功' if 正常 else '失败')
    finally:
        摄像头.release()
