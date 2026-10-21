"""v1.7.1: 在 GUI 使用与真实训练一致的 QProcess 管道验证中文显示，无需训练。"""
from __future__ import annotations
import sys
import time
from pathlib import Path
from .训练日志编码 import 配置标准流UTF8


def main():
    配置标准流UTF8()
    print("读取有效样本： {'张开手掌': 123, '握拳': 130, '点赞': 121, '剪刀手': 136, '食指指向': 129, '无手': 50}",flush=True)
    time.sleep(.08)
    print('注意：本次是中文日志自检，不进行模型训练，不修改任何权重。',flush=True)
    time.sleep(.08)
    print('[1/8] loss=1.2345 训练准确率=65.2%（非测试）',flush=True)
    print('中文目录：'+str(Path.cwd()/'输出'/'工作台训练_自检.json'),flush=True)
    print('标准错误中文提示：日志正常',file=sys.stderr,flush=True)

if __name__=='__main__':main()
