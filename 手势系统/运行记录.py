"""仅记录数值与类别，不保存摄像头视频/人脸图像。"""
from __future__ import annotations
import csv
from datetime import datetime
from .配置 import 输出目录


class 实时运行记录:
    字段 = ['时间', '原始类别', '有效类别', '置信度', '阈值', '实际帧率', '推理毫秒', '执行操作', '是否暂停', '摄像头状态']

    def __init__(self):
        目录 = 输出目录 / '真实摄像头运行日志'
        目录.mkdir(parents=True, exist_ok=True)
        self.文件路径 = 目录 / f'运行_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.csv'
        self.文件 = self.文件路径.open('w', newline='', encoding='utf-8-sig')
        self.写入器 = csv.DictWriter(self.文件, fieldnames=self.字段)
        self.写入器.writeheader()
        self.次数 = 0

    def 写入(self, **项目):
        行 = {k: 项目.get(k, '') for k in self.字段}
        行['时间'] = datetime.now().isoformat(timespec='milliseconds')
        self.写入器.writerow(行)
        self.次数 += 1
        if self.次数 % 30 == 0:
            self.文件.flush()

    def 关闭(self):
        if not self.文件.closed:
            self.文件.flush()
            self.文件.close()
