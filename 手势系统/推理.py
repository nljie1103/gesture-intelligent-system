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
        self.识别区域比例 = float(配置['识别区域占画面短边比例'])
        self.阈值 = .85
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

    def 预测(self, BGR画面):
        图片 = 裁剪手势(BGR画面, self.识别区域比例)
        张量 = 图像转张量(图片, self.尺寸).unsqueeze(0)
        开始 = time.perf_counter()
        with torch.inference_mode():
            概率 = torch.softmax(self.模型(张量), dim=1)[0]
        毫秒 = (time.perf_counter() - 开始) * 1000
        概率最高, 编号 = torch.max(概率, dim=0)
        类名, 分数 = 类别[int(编号)], float(概率最高)
        return {'原始类别': 类名, '置信度': 分数, '有效类别': 类名 if 分数 >= self.阈值 else None,
                '推理毫秒': 毫秒, '阈值': self.阈值}
