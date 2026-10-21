"""固定数据划分的 CNN 训练、验证和最终独立测试。"""
from __future__ import annotations
from .版本 import VERSION
import csv
import json
import random
import shutil
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from .配置 import 类别, 数据目录, 模型目录, 输出目录, 建立运行目录, 读取配置
from .数据 import 建立划分, 保存划分, 手势数据集
from .模型 import 轻量卷积网络, 加载分类模型
from .指标 import 计算分类指标, 选择验证阈值


def 设置随机种子(种子: int):
    random.seed(种子)
    np.random.seed(种子)
    torch.manual_seed(种子)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(种子)


def 批量评估(模型, 加载器, 设备):
    模型.eval()
    真值, 预测, 概率记录 = [], [], []
    损失和, 样本数 = 0., 0
    with torch.inference_mode():
        for 图像, 标签 in 加载器:
            图像, 标签 = 图像.to(设备), 标签.to(设备)
            logits = 模型(图像)
            损失和 += float(nn.functional.cross_entropy(logits, 标签, reduction='sum'))
            概率 = torch.softmax(logits, dim=1)
            真值.extend(标签.cpu().tolist())
            预测.extend(logits.argmax(1).cpu().tolist())
            概率记录.extend(概率.cpu().numpy().tolist())
            样本数 += len(标签)
    return 计算分类指标(真值, 预测), 损失和 / max(样本数, 1), 真值, 概率记录


def 保存图表(结果目录: Path, 历史记录: list, 测试指标: dict, 文件前缀: str):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    # Linux 集成测试环境有 CJK 字体但 Matplotlib 可能没有索引；Windows 优先微软雅黑。
    for 字体路径 in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
        if Path(字体路径).exists():
            font_manager.fontManager.addfont(字体路径)
    for 字体 in ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]:
        if any(x.name == 字体 for x in font_manager.fontManager.ttflist):
            plt.rcParams['font.sans-serif'] = [字体, 'DejaVu Sans']
            break
    plt.rcParams['axes.unicode_minus'] = False
    图, 轴 = plt.subplots(figsize=(8, 4))
    轴.plot([x['轮次'] for x in 历史记录], [x['训练损失'] for x in 历史记录], label='Train loss')
    轴.plot([x['轮次'] for x in 历史记录], [x['验证损失'] for x in 历史记录], label='Validation loss')
    轴.set_xlabel('Epoch'); 轴.set_ylabel('Loss'); 轴.grid(alpha=.2); 轴.legend()
    图.tight_layout(); 图.savefig(结果目录 / f'{文件前缀}-损失曲线.png', dpi=150); plt.close(图)
    图, 轴 = plt.subplots(figsize=(7, 6))
    矩阵 = np.asarray(测试指标['混淆矩阵'])
    轴.imshow(矩阵, cmap='Blues')
    轴.set_xticks(range(len(类别)), 类别, rotation=45, ha='right')
    轴.set_yticks(range(len(类别)), 类别)
    for i in range(len(类别)):
        for j in range(len(类别)):
            轴.text(j, i, str(矩阵[i, j]), ha='center', va='center', fontsize=10)
    轴.set_xlabel('预测类别'); 轴.set_ylabel('实际类别')
    图.tight_layout(); 图.savefig(结果目录 / f'{文件前缀}-混淆矩阵.png', dpi=150); plt.close(图)


def 训练一次(名称: str, 划分: dict, 设备: str, 轮数: int, 批大小: int, 学习率: float, 种子: int, 图像尺寸: int):
    设置随机种子(种子)
    训练集 = 手势数据集(划分['样本']['训练'], 尺寸=图像尺寸, 增强=(名称 == '改进'))
    验证集 = 手势数据集(划分['样本']['验证'], 尺寸=图像尺寸)
    训练加载器 = DataLoader(训练集, batch_size=批大小, shuffle=True, num_workers=0)
    验证加载器 = DataLoader(验证集, batch_size=批大小, shuffle=False, num_workers=0)
    模型 = 轻量卷积网络(len(类别)).to(设备)
    优化器 = torch.optim.Adam(模型.parameters(), lr=学习率)
    损失函数 = nn.CrossEntropyLoss()
    最高分 = (-1., -1.)
    历史记录 = []
    权重路径 = 模型目录 / f'{名称}模型.pt'
    for ep in range(1, 轮数 + 1):
        模型.train()
        总损失, 总正确, 总数 = 0., 0, 0
        for 输入, 真值 in 训练加载器:
            输入, 真值 = 输入.to(设备), 真值.to(设备)
            优化器.zero_grad(set_to_none=True)
            输出 = 模型(输入)
            损失 = 损失函数(输出, 真值)
            损失.backward(); 优化器.step()
            总损失 += 损失.item() * len(真值)
            总正确 += int((输出.argmax(1) == 真值).sum().item())
            总数 += len(真值)
        验证指标, 验证损失, _, _ = 批量评估(模型, 验证加载器, 设备)
        行 = {'轮次': ep, '训练损失': round(总损失 / 总数, 6), '训练准确率': round(总正确 / 总数, 5),
              '验证损失': round(验证损失, 6), '验证准确率': 验证指标['准确率'], '验证宏平均F1': 验证指标['宏平均F1']}
        历史记录.append(行)
        分数 = (验证指标['宏平均F1'], 验证指标['准确率'])
        if 分数 > 最高分:
            最高分 = 分数
            torch.save({'权重': 模型.state_dict(), '类别': list(类别), '输入尺寸': 图像尺寸,
                        '网络结构': '轻量卷积网络', '训练策略': 名称, '最佳轮次': ep,
                        '验证宏平均F1': 分数[0], '版本': VERSION}, 权重路径)
        print(f"[{名称}] {ep}/{轮数} 训练acc={行['训练准确率']:.3f} 验证acc={行['验证准确率']:.3f} 验证F1={行['验证宏平均F1']:.3f}", flush=True)
    模型, _, 记录 = 加载分类模型(权重路径, 设备)
    验证指标, _, 真实, 预测概率 = 批量评估(模型, 验证加载器, 设备)
    阈值评估 = 选择验证阈值(真实, 预测概率)
    return 模型, 记录, 历史记录, 验证指标, 阈值评估


def 正式训练(轮数=12, 批大小=32, 学习率=.001, 设备='cpu', 种子=20261016):
    if 轮数 < 1 or 批大小 < 1 or 学习率 <= 0:
        raise ValueError('训练参数不合理')
    if 设备.startswith('cuda') and not torch.cuda.is_available():
        raise RuntimeError('当前 PyTorch 没有可用的 CUDA，请改用 --device cpu')
    建立运行目录()
    设置随机种子(种子)
    配置 = 读取配置()
    图像尺寸 = int(配置['模型输入尺寸'])
    if 图像尺寸 < 32:
        raise ValueError('模型输入尺寸不能小于32')
    划分 = 建立划分(数据目录, 种子)
    保存划分(划分, 模型目录 / '数据划分.json')
    结果目录 = 输出目录 / '实验分析'
    结果目录.mkdir(parents=True, exist_ok=True)
    总结果 = {}
    for 名称 in ['基线', '改进']:
        模型, 最佳轮次, 历史, 验证指标, 阈值 = 训练一次(名称, 划分, 设备, 轮数, 批大小, 学习率, 种子, 图像尺寸)
        with (结果目录 / f'{名称}-训练历史.csv').open('w', encoding='utf-8-sig', newline='') as f:
            写入 = csv.DictWriter(f, fieldnames=list(历史[0])); 写入.writeheader(); 写入.writerows(历史)
        总结果[名称] = {'模型': 模型, '最佳轮次': 最佳轮次['最佳轮次'], '验证指标': 验证指标,
                        '阈值评估': 阈值, '训练历史': 历史}
    # 仅根据验证集来确定正式模型与阈值，测试集不参与调参。
    选择 = max(['基线', '改进'], key=lambda n: (
        总结果[n]['验证指标']['宏平均F1'], 总结果[n]['验证指标']['准确率'], n == '基线'))
    shutil.copy2(模型目录 / f'{选择}模型.pt', 模型目录 / '正式模型.pt')
    正式阈值 = 总结果[选择]['阈值评估']['阈值']
    测试加载器 = DataLoader(手势数据集(划分['样本']['测试'], 尺寸=图像尺寸), batch_size=批大小, num_workers=0)
    导出结果 = {
        '版本': VERSION, '实验日期': time.strftime('%Y-%m-%d %H:%M:%S'), '设备': 设备,
        '轮数': 轮数, '批大小': 批大小, '学习率': 学习率, '随机种子': 种子,
        '类别': list(类别), '样本数量': {k: len(v) for k, v in 划分['样本'].items()},
        '正式模型': 选择, '正式置信度阈值': 正式阈值, '说明': '先由验证集选模型/阈值，后对独立测试集评估；未知手势没有开放集准确率保证。',
        '方案': {},
    }
    for 名称 in ['基线', '改进']:
        开始 = time.perf_counter()
        测试指标, _, _, _ = 批量评估(总结果[名称]['模型'], 测试加载器, 设备)
        总时间 = time.perf_counter() - 开始
        导出结果['方案'][名称] = {'最佳训练轮次': 总结果[名称]['最佳轮次'], '验证指标': 总结果[名称]['验证指标'],
                             '验证阈值评估': 总结果[名称]['阈值评估'], '测试指标': 测试指标,
                             '测试集整体推理秒数': round(总时间, 4)}
        保存图表(结果目录, 总结果[名称]['训练历史'], 测试指标, 名称)
        print(f"{名称}测试：准确率 {测试指标['准确率']:.4f}，宏平均F1 {测试指标['宏平均F1']:.4f}")
    (模型目录 / '运行阈值.json').write_text(json.dumps({'置信度阈值': 正式阈值, '来自': '验证集', '正式模型': 选择}, ensure_ascii=False, indent=2), encoding='utf-8')
    (结果目录 / '训练与对比结果.json').write_text(json.dumps(导出结果, ensure_ascii=False, indent=2), encoding='utf-8')
    (结果目录 / '实验报告草稿.txt').write_text(
        f'基于手势识别的智能系统 v{VERSION} 实验记录\n'
        f'采集轮次请见 模型/数据划分.json。样本数：{导出结果["样本数量"]}\n'
        f'基础 CNN 测试准确率：{导出结果["方案"]["基线"]["测试指标"]["准确率"]}\n'
        f'增强 CNN 测试准确率：{导出结果["方案"]["改进"]["测试指标"]["准确率"]}\n'
        f'依据验证集选择正式模型：{选择}；阈值：{正式阈值}\n'
        '【以下必须自行填写真实测试】摄像头帧率：___；平均单帧耗时：___；\n'
        '真实场景无手测试：___；误识别案例：___；设备型号：___；采集背景/光照：___。\n'
        '注意：本报告草稿只是自动整理离线统计，不能当作已完成现场实验。\n', encoding='utf-8')
    print(f"已选正式模型：{选择}；验证集阈值={正式阈值}。输出路径：{结果目录}")
    return 导出结果
