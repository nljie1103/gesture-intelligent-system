"""实时推理共用训练阶段的颜色空间、输入尺度。"""
from __future__ import annotations
import time
import json
from pathlib import Path
import torch
from .模型 import 加载分类模型
from .预处理 import 裁剪手势, 图像转张量
from .配置 import 类别, 模型目录, 读取配置
from .模型发布 import 恢复中断发布
from .训练状态 import 文件哈希


class 手势推理器:
    def __init__(self, 路径=None):
        配置 = 读取配置()
        torch.set_num_threads(max(1, min(torch.get_num_threads(), 4)))
        model_path = Path(路径 or 模型目录 / '正式模型.pt')
        恢复中断发布(model_path.parent)
        self.模型, self.尺寸, self.元信息 = 加载分类模型(model_path, 'cpu')
        from .手部定位 import 读取训练输入策略,策略标识,手部定位器,包含定位资源
        self.输入策略=读取训练输入策略(self.元信息)
        self.需手部定位=self.输入策略==策略标识
        if self.需手部定位 and not 包含定位资源():
            raise FileNotFoundError('模型需要手部关键点定位组件，请在设置页重新安装手部定位模型')
        # Lazy creation in CameraWorker's inference thread, rather than the Qt UI thread.
        self.locator=None
        self.识别区域比例 = float(配置['识别区域占画面短边比例'])
        self.阈值 = .60
        阈值路径 = model_path.parent / '运行阈值.json'
        if 阈值路径.is_file():
            try:
                record = json.loads(阈值路径.read_text(encoding='utf-8'))
                if record.get('模型SHA256') == 文件哈希(model_path):
                    value=float(record['置信度阈值'])
                    if 0 <= value <= 1:self.阈值=value
            except (OSError, ValueError, KeyError, TypeError):
                pass
        if 配置['最小置信度'] is not None:
            self.阈值 = float(配置['最小置信度'])

    def 关闭定位器(self):
        locator,self.locator=self.locator,None
        if locator is not None:locator.close()

    def 预测(self, BGR画面):
        if self.需手部定位 and self.locator is None:
            from .手部定位 import 手部定位器
            self.locator=手部定位器()
        box=None
        if self.locator is not None:
            box=self.locator.find_bgr(BGR画面)
            if box is None:
                return {'原始类别':'无手','有效类别':'无手','置信度':1.0,
                        '推理毫秒':0.,'阈值':self.阈值,'手部框':None,'定位方式':'关键点'}
            import cv2
            from PIL import Image
            图片=Image.fromarray(cv2.cvtColor(BGR画面[box[1]:box[3],box[0]:box[2]],cv2.COLOR_BGR2RGB))
        else:
            图片 = 裁剪手势(BGR画面, self.识别区域比例)
        张量 = 图像转张量(图片, self.尺寸).unsqueeze(0)
        开始 = time.perf_counter()
        with torch.inference_mode():
            概率 = torch.softmax(self.模型(张量), dim=1)[0]
        毫秒 = (time.perf_counter() - 开始) * 1000
        if self.需手部定位:
            # 已定位到手时只在五种手势中分类，“无手”由定位器负责。
            概率=概率[:5]/概率[:5].sum().clamp_min(1e-7)
        概率最高, 编号 = torch.max(概率, dim=0)
        类名, 分数 = 类别[int(编号)], float(概率最高)
        return {'原始类别': 类名, '置信度': 分数, '有效类别': 类名 if 分数 >= self.阈值 else None,
                '推理毫秒': 毫秒, '阈值': self.阈值,'手部框':box,'定位方式':'关键点' if self.需手部定位 else '固定区域'}

