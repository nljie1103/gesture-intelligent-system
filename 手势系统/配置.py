"""集中管理项目路径、类别、配置。"""
from __future__ import annotations
import json
from pathlib import Path
from .版本 import VERSION

根目录 = Path(__file__).resolve().parent.parent
配置文件 = 根目录 / "设置.json"
数据目录 = 根目录 / "数据"
模型目录 = 根目录 / "模型"
输出目录 = 根目录 / "输出"
素材目录 = 根目录 / "素材" / "图片"

# 顺序固定：模型权重与训练时类别编号一致；不能随意交换。
类别 = ["张开手掌", "握拳", "点赞", "剪刀手", "食指指向", "无手"]
操作映射 = {
    "张开手掌": "下一张",
    "握拳": "上一张",
    "点赞": "放大",
    "剪刀手": "缩小",
    "食指指向": "切换暂停",
}
默认配置 = {
    "版本": VERSION, "摄像头编号": 0, "识别区域占画面短边比例": .78,
    "模型输入尺寸": 96, "最小置信度": None, "稳定帧数": 4,
    "解除锁定帧数": 4, "触发冷却秒数": 1., "视频刷新毫秒": 30,
    "允许食指手势暂停": False,
}


def 读取配置() -> dict:
    配置 = dict(默认配置)
    if 配置文件.exists():
        载入 = json.loads(配置文件.read_text(encoding="utf-8-sig"))
        配置.update(载入)
    # 旧用户设置中的版本只是历史记录，不能覆盖当前程序版本。
    配置["版本"] = VERSION
    if not (0.2 <= float(配置["识别区域占画面短边比例"]) <= 1.0):
        raise ValueError("识别区域比例应处于 0.2~1.0")
    if 配置["最小置信度"] is not None and not (0.0 <= float(配置["最小置信度"]) <= 1.0):
        raise ValueError("最小置信度应处于 0~1")
    if int(配置["稳定帧数"]) < 1 or int(配置["解除锁定帧数"]) < 1:
        raise ValueError("稳定帧数和解除锁定帧数至少为 1")
    return 配置


def 建立运行目录() -> None:
    for 目录 in (数据目录, 模型目录, 输出目录, 素材目录):
        目录.mkdir(parents=True, exist_ok=True)
