"""自己训练分类模型；支持 CPU，也可选 CUDA。"""
import argparse
from 手势系统.训练 import 正式训练

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='六分类轻量 CNN：基线与数据增强改进，对比验证和独立测试')
    p.add_argument('--epochs', type=int, default=12, help='每个模型的训练轮数，默认12')
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--lr', type=float, default=.001)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    p.add_argument('--seed', type=int, default=20261016)
    a = p.parse_args()
    正式训练(a.epochs, a.batch_size, a.lr, a.device, a.seed)
