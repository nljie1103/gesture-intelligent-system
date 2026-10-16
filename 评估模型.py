"""在训练时冻结的独立测试集上重新评估，不重新随机划分。"""
import argparse
import json
import time
from torch.utils.data import DataLoader
from 手势系统.配置 import 模型目录, 输出目录, 读取配置
from 手势系统.数据 import 读取划分, 手势数据集
from 手势系统.模型 import 加载分类模型
from 手势系统.训练 import 批量评估


def main():
    p = argparse.ArgumentParser(description='评估已训练模型；使用保存的独立测试集分组')
    p.add_argument('--model', choices=['正式', '基线', '改进'], default='正式')
    a = p.parse_args()
    划分 = 读取划分(模型目录 / '数据划分.json')
    模型, 尺寸, 元信息 = 加载分类模型(模型目录 / f'{a.model}模型.pt')
    测试数据 = 手势数据集(划分['样本']['测试'], 尺寸=尺寸)
    测试载入 = DataLoader(测试数据, batch_size=32, shuffle=False, num_workers=0)
    开始 = time.perf_counter()
    指标, 损失, _, _ = 批量评估(模型, 测试载入, 'cpu')
    指标['交叉熵损失'] = round(损失, 5)
    指标['全部样本推理秒数'] = round(time.perf_counter() - 开始, 3)
    输出 = 输出目录 / '实验分析'
    输出.mkdir(parents=True, exist_ok=True)
    结果文件 = 输出 / f'{a.model}模型-独立测试结果.json'
    结果文件.write_text(json.dumps(指标, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'测试样本 {指标["样本数"]}，准确率 {指标["准确率"]:.4f}，宏平均F1 {指标["宏平均F1"]:.4f}')
    print(f'已保存至：{结果文件}')

if __name__ == '__main__':
    main()
