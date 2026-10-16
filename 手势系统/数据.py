"""严格按采集轮次划分数据，避免视频相邻帧跨越训练/测试集。"""
from __future__ import annotations
import json
import random
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from .配置 import 类别, 数据目录
from .预处理 import 图像转张量

图片扩展名 = {".jpg", ".jpeg", ".png", ".bmp"}


def 建立划分(目录: Path = 数据目录, 种子: int = 20261016) -> dict:
    """同名采集轮次在六类中必须整体属于同一分区，避免跨类背景/时段泄漏。"""
    划分 = {"训练": [], "验证": [], "测试": []}
    所有轮次 = {}
    for 名称 in 类别:
        文件夹 = 目录 / 名称
        有效 = {}
        if 文件夹.exists():
            for 轮次文件夹 in sorted(文件夹.iterdir()):
                if 轮次文件夹.is_dir():
                    图片 = sorted(p for p in 轮次文件夹.iterdir() if p.is_file() and p.suffix.lower() in 图片扩展名)
                    if 图片:
                        有效[轮次文件夹.name] = 图片
        所有轮次[名称] = 有效
    参考 = set(所有轮次[类别[0]])
    if len(参考) < 3:
        raise ValueError(f'完整采集轮次仅 {len(参考)} 个；至少需要 3 个独立轮次，建议 5 个以上')
    for 名称 in 类别:
        if set(所有轮次[名称]) != 参考:
            缺失 = sorted(参考 - set(所有轮次[名称]))
            额外 = sorted(set(所有轮次[名称]) - 参考)
            raise ValueError(f'{名称} 的轮次与其他类别不一致。缺少：{缺失}，多出：{额外}。请确保所有类别在相同的独立轮次中采集。')
    轮次 = sorted(参考)
    random.Random(种子).shuffle(轮次)
    测试数 = max(1, round(len(轮次) * .2))
    验证数 = max(1, round(len(轮次) * .2))
    if 测试数 + 验证数 >= len(轮次):
        raise ValueError('有效轮次不足以留出训练集')
    分组 = {"测试": 轮次[:测试数], "验证": 轮次[测试数:测试数 + 验证数],
          "训练": 轮次[测试数 + 验证数:]}
    for 编号, 名称 in enumerate(类别):
        for 分区, 轮次名称组 in 分组.items():
            for 轮次名称 in 轮次名称组:
                for 路径 in 所有轮次[名称][轮次名称]:
                    划分[分区].append([str(路径.relative_to(目录)).replace('\\', '/'), 编号])
    for 名, 样本 in 划分.items():
        if not 样本:
            raise ValueError(f'{名}集为空')
    return {"种子": 种子, "类别": list(类别), "采集轮次分组": 分组, "样本": 划分}


def 保存划分(划分: dict, 路径: Path) -> None:
    路径.parent.mkdir(parents=True, exist_ok=True)
    路径.write_text(json.dumps(划分, ensure_ascii=False, indent=2), encoding="utf-8")


def 读取划分(路径: Path) -> dict:
    划分 = json.loads(路径.read_text(encoding="utf-8"))
    if 划分["类别"] != 类别:
        raise ValueError("类别配置发生变化，不能复用旧划分")
    return 划分


class 手势数据集:
    def __init__(self, 样本, 目录: Path = 数据目录, 尺寸=96, 增强=False):
        self.样本 = list(样本)
        self.目录 = Path(目录)
        self.尺寸 = 尺寸
        self.增强 = 增强

    def __len__(self):
        return len(self.样本)

    def __getitem__(self, 索引):
        相对路径, 标签 = self.样本[索引]
        with Image.open(self.目录 / 相对路径) as 图片:
            图片 = 图片.convert("RGB")
        if self.增强:
            # 不做水平镜像，以免改变左右方向性手势的语义。
            图片 = 图片.rotate(random.uniform(-12, 12), resample=Image.Resampling.BILINEAR)
            图片 = ImageEnhance.Brightness(图片).enhance(random.uniform(.7, 1.3))
            图片 = ImageEnhance.Contrast(图片).enhance(random.uniform(.8, 1.2))
        return 图像转张量(图片, self.尺寸), int(标签)
