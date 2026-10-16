"""纯逻辑事件门控：稳定帧、冷却、离开手势后才允许再次触发。"""
from __future__ import annotations
from .配置 import 操作映射


class 手势控制器:
    def __init__(self, 稳定帧数=4, 解除帧数=4, 冷却时间=1.0):
        if min(稳定帧数, 解除帧数) < 1 or 冷却时间 < 0:
            raise ValueError("门控参数不合法")
        self.稳定帧数 = 稳定帧数
        self.解除帧数 = 解除帧数
        self.冷却时间 = 冷却时间
        self.已暂停 = False
        self.已解锁 = True
        self.当前手势 = None
        self.连续帧 = 0
        self.空白帧 = 0
        self.上次触发 = float('-inf')

    def 处理(self, 手势: str | None, 时间: float) -> str | None:
        """输入已经通过置信度检查的类别；返回操作或 None。"""
        if 手势 not in 操作映射:
            self.空白帧 += 1
            self.当前手势 = None
            self.连续帧 = 0
            if self.空白帧 >= self.解除帧数:
                self.已解锁 = True
            return None
        self.空白帧 = 0
        if 手势 == self.当前手势:
            self.连续帧 += 1
        else:
            self.当前手势, self.连续帧 = 手势, 1
        if (not self.已解锁 or self.连续帧 < self.稳定帧数
                or 时间 - self.上次触发 < self.冷却时间):
            return None
        if self.已暂停 and 手势 != "食指指向":
            return None
        操作 = 操作映射[手势]
        self.已解锁 = False
        self.上次触发 = 时间
        if 操作 == "切换暂停":
            self.已暂停 = not self.已暂停
            return "已暂停" if self.已暂停 else "已恢复"
        return 操作

    def 键盘切换暂停(self):
        self.已暂停 = not self.已暂停
        self.当前手势, self.连续帧, self.已解锁 = None, 0, False
        self.空白帧 = 0
        return "已暂停" if self.已暂停 else "已恢复"
