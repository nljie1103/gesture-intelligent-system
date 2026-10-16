"""真正执行两阶段 CNN 训练；三轮自采样本严格隔离。"""
import argparse
from 手势系统.混合训练 import 训练混合模型

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='HaGRIDv2 公开基线 + 三轮独立本地数据微调、验证及测试')
    parser.add_argument('--adapt',required=True,help='只用于微调的本地轮次，例如 场景01')
    parser.add_argument('--val',required=True,help='只用于调参与选择模型的独立轮次，例如 场景02')
    parser.add_argument('--test',required=True,help='只用于最终评估的独立轮次，例如 场景03')
    parser.add_argument('--epochs-public',type=int,default=8)
    parser.add_argument('--epochs-adapt',type=int,default=6)
    parser.add_argument('--batch-size',type=int,default=32)
    parser.add_argument('--lr-public',type=float,default=.001)
    parser.add_argument('--lr-adapt',type=float,default=.0002)
    parser.add_argument('--replay',type=float,default=.2,help='微调重放公开训练图片的比例；默认0.2')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--seed',type=int,default=20261016)
    a=parser.parse_args()
    训练混合模型(a.adapt,a.val,a.test,a.epochs_public,a.epochs_adapt,a.batch_size,
             a.lr_public,a.lr_adapt,a.device,a.seed,a.replay)
