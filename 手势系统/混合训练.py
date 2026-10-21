"""公开数据基础训练 + 自采集场景微调：只允许独立轮次进入验证和测试。"""
from __future__ import annotations
from .版本 import VERSION
import csv
import json
import math
import random
import shutil
import time
from collections import Counter
from pathlib import Path, PurePosixPath
import torch
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from .配置 import 类别, 数据目录, 模型目录, 输出目录, 读取配置, 建立运行目录
from .数据 import 手势数据集
from .模型 import 轻量卷积网络, 加载分类模型
from .指标 import 选择验证阈值
from .训练 import 设置随机种子, 批量评估, 保存图表


class 混合数据错误(ValueError):
    pass


def 构建混合划分(适配轮次: str, 验证轮次: str, 测试轮次: str,
           数据根: Path = 数据目录, 公共每类最多: int = 2000, 最低本地样本: int = 8) -> dict:
    数据根 = Path(数据根)
    if len({适配轮次, 验证轮次, 测试轮次}) != 3 or not all((适配轮次, 验证轮次, 测试轮次)):
        raise 混合数据错误('适配、验证、测试必须使用三个名称不同的独立采集轮次')
    if any('/' in x or '\\' in x or x in {'.', '..'} for x in [适配轮次,验证轮次,测试轮次]):
        raise 混合数据错误('采集轮次名称无效')
    清单 = 数据根 / '公开数据清单.json'
    if not 清单.is_file():
        raise 混合数据错误('找不到公开数据清单。请先使用 导入公开数据.py')
    原始 = json.loads(清单.read_text(encoding='utf-8'))
    公开样本 = []
    for 编号, 名称 in enumerate(类别[:5]):
        records = 原始['样本'].get(名称, [])
        if not records:
            raise 混合数据错误(f'公开训练数据缺少 {名称}')
        for r in records[:公共每类最多]:
            # 清单中的路径永远使用 POSIX 的“/”；不能把系统 Path 的字符串形式
            # 拿来匹配“公开训练/”，否则 Windows 会变成反斜杠并误报非法路径。
            raw = r.get('路径') if isinstance(r, dict) else None
            if not isinstance(raw, str) or not raw or '\\' in raw or '\x00' in raw or ':' in raw:
                raise 混合数据错误('公开数据清单含非法路径')
            relative = PurePosixPath(raw)
            if (relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 3
                    or relative.parts[0] != '公开训练' or relative.parts[1] != 名称
                    or relative.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp'}
                    or relative.as_posix() != raw):
                raise 混合数据错误('公开数据清单含非法路径')
            # Path(*parts) 生成本机合法的文件路径；清单和报告仍统一保存“/”。
            native_path = 数据根.joinpath(*relative.parts)
            if not native_path.is_file():
                raise 混合数据错误(f'公开样本不存在：{raw}')
            公开样本.append([relative.as_posix(), 编号])
    组 = {'适配': [], '验证': [], '测试': []}
    命名 = {'适配':适配轮次, '验证':验证轮次,'测试':测试轮次}
    允许扩展 = {'.jpg','.jpeg','.png','.bmp'}
    for 编号, 名称 in enumerate(类别):
        for 划分名, 轮次名 in 命名.items():
            local = 数据根 / 名称 / 轮次名
            photos = sorted(p for p in local.iterdir() if p.is_file() and p.suffix.lower() in 允许扩展) if local.is_dir() else []
            if len(photos) < 最低本地样本:
                raise 混合数据错误(f'{名称}/{轮次名} 有效样本只有 {len(photos)}，最低 {最低本地样本} 张')
            组[划分名].extend([[p.relative_to(数据根).as_posix(),编号] for p in photos])
    测试路径 = {p for p,_ in 组['测试']}
    验证路径 = {p for p,_ in 组['验证']}
    适配路径 = {p for p,_ in 组['适配']}
    if (测试路径 & 验证路径) or (测试路径 & 适配路径) or (适配路径 & 验证路径):
        raise 混合数据错误('发现不同独立轮次出现路径重叠')
    # 公开集仅训练。基础模型为 5 种手势 + 自采集的无手样本（没有用测试集）。
    无手编号 = 类别.index('无手')
    公开基线训练 = 公开样本 + [x for x in 组['适配'] if x[1] == 无手编号]
    return {'模式':'公开数据预训练+本地微调', '类别':list(类别),
            '来源SHA256': 原始['来源ZIP_SHA256'], '本地轮次': 命名,
            '公开样本':公开样本, '基线训练':公开基线训练,
            '本地适配':组['适配'], '验证':组['验证'], '测试':组['测试'],
            '样本数量': {'公开':len(公开样本),'基线训练':len(公开基线训练), **{k:len(v) for k,v in 组.items()}}}


def _载入器(样本: list, 尺寸: int, 批大小: int, 增强: bool, 平衡: bool, 种子: int, 数据根: Path):
    数据 = 手势数据集(样本, 目录=数据根, 尺寸=尺寸, 增强=增强)
    if 平衡:
        频数 = Counter(类别编号 for _, 类别编号 in 样本)
        权重 = [1.0 / 频数[y] for _, y in 样本]
        gen = torch.Generator().manual_seed(种子)
        sampler = WeightedRandomSampler(权重, len(样本), replacement=True, generator=gen)
        return DataLoader(数据, batch_size=批大小, sampler=sampler, num_workers=0)
    return DataLoader(数据, batch_size=批大小, shuffle=False, num_workers=0)


def _单阶段(名称: str, 初始模型, 训练样本: list, 验证样本: list, 文件: Path,
         设备: str, 轮数: int, 批大小: int, 学习率: float, 图像尺寸: int, 种子: int, 数据根: Path):
    设置随机种子(种子)
    model = 初始模型 if 初始模型 is not None else 轻量卷积网络(len(类别))
    model.to(设备)
    训练集 = _载入器(训练样本, 图像尺寸, 批大小, 增强=名称 == '本地微调', 平衡=True, 种子=种子, 数据根=数据根)
    验证集 = _载入器(验证样本, 图像尺寸, 批大小, 增强=False, 平衡=False, 种子=种子, 数据根=数据根)
    optim = torch.optim.Adam(model.parameters(), lr=学习率)
    best = (-1., -1.)
    history = []
    for epoch in range(1, 轮数+1):
        model.train()
        total, correct, loss_sum = 0,0,0.0
        for x,y in 训练集:
            x,y = x.to(设备),y.to(设备)
            optim.zero_grad(set_to_none=True)
            logits = model(x)
            loss = nn.functional.cross_entropy(logits,y)
            loss.backward()
            optim.step()
            total += len(y)
            correct += int((logits.argmax(dim=1) == y).sum().item())
            loss_sum += float(loss.item())*len(y)
        metrics,v_loss,_,_ = 批量评估(model, 验证集,设备)
        row = {'轮次':epoch,'训练损失':round(loss_sum/max(total,1),5),
               '训练准确率':round(correct/max(total,1),5),'验证损失':round(v_loss,5),
               '验证准确率':metrics['准确率'],'验证宏平均F1':metrics['宏平均F1']}
        history.append(row)
        score = (metrics['宏平均F1'],metrics['准确率'])
        if score > best:
            best = score
            torch.save({'权重':model.state_dict(),'类别':list(类别),'输入尺寸':图像尺寸,
                        '网络结构':'轻量卷积网络','训练策略':名称,'最佳轮次':epoch,
                        '验证宏平均F1':score[0],'版本':VERSION},文件)
        print(f'[{名称}] Epoch {epoch}/{轮数} | 训练acc={row["训练准确率"]:.3f} | 验证F1={metrics["宏平均F1"]:.3f}', flush=True)
    best_model, _, meta = 加载分类模型(文件, 设备)
    val_metric, _, val_y, val_prob = 批量评估(best_model, 验证集, 设备)
    threshold = 选择验证阈值(val_y, val_prob)
    return best_model, meta, history, val_metric, threshold


def 训练混合模型(适配: str, 验证: str, 测试: str,
             公开轮数: int = 8, 微调轮数: int = 6, 批大小: int = 32,
             公开学习率: float = .001, 微调学习率: float = .0002,
             设备: str = 'cpu', 种子: int = 20261016, 重放比例: float = .2,
             数据根目录: Path = 数据目录, 模型根目录: Path = 模型目录,
             输出根目录: Path = 输出目录):
    if any(x < 1 for x in (公开轮数, 微调轮数, 批大小)):
        raise ValueError('Epoch 或批量尺寸不能低于 1')
    if 公开学习率 <= 0 or 微调学习率 <= 0 or not 0 <= 重放比例 <= 1:
        raise ValueError('学习率或重放比例不正确')
    if 设备.startswith('cuda') and not torch.cuda.is_available():
        raise RuntimeError('当前 PyTorch 不支持 CUDA，请改用 CPU')
    if str(设备) == 'cpu':
        torch.set_num_threads(min(4,max(1,torch.get_num_threads())))
    建立运行目录()
    模型根目录 = Path(模型根目录)
    输出根目录 = Path(输出根目录)
    模型根目录.mkdir(parents=True, exist_ok=True)
    结果目录 = 输出根目录 / '混合训练实验'
    结果目录.mkdir(parents=True, exist_ok=True)
    已有文件 = [模型根目录 / x for x in ('正式模型.pt','混合数据划分.json','混合基线模型.pt','混合微调模型.pt')]
    if any(p.exists() for p in 已有文件):
        raise FileExistsError('已经存在正式模型或本次混合训练产物。为保护旧实验请先备份，不会自动覆盖。')
    split = 构建混合划分(适配,验证,测试,Path(数据根目录))
    尺寸 = int(读取配置()['模型输入尺寸'])
    设置随机种子(种子)
    base_file = 模型根目录 / '混合基线模型.pt'
    tune_file = 模型根目录 / '混合微调模型.pt'
    base, base_meta, bh,bv, bt = _单阶段('公开基线',None,split['基线训练'],split['验证'],base_file,
                            设备,公开轮数,批大小,公开学习率,尺寸,种子,Path(数据根目录))
    # 防遗忘：微调阶段仅重放一小部分公开数据，而且永远不碰本地验证/测试样本。
    rng = random.Random(种子)
    replay = []
    for idx in range(5):
        files = [x for x in split['公开样本'] if x[1] == idx]
        rng.shuffle(files)
        replay.extend(files[:max(1,round(len(files)*重放比例))] if 重放比例 else [])
    tune_examples = split['本地适配'] + replay
    fine, fine_meta,fh,fv,ft = _单阶段('本地微调',base, tune_examples,split['验证'],tune_file,
                             设备,微调轮数,批大小,微调学习率,尺寸,种子+1,Path(数据根目录))
    candidate = {'公开基线':{'model':base_file,'history':bh,'validation':bv,'threshold':bt,'epoch':base_meta['最佳轮次']},
                 '本地微调':{'model':tune_file,'history':fh,'validation':fv,'threshold':ft,'epoch':fine_meta['最佳轮次']}}
    chosen = max(candidate,key=lambda k:(candidate[k]['validation']['宏平均F1'],
                                          candidate[k]['validation']['准确率'],k=='公开基线'))
    # 测试集仅在确定正式模型后被读取；双方在相同的冻结测试集上做一次性对比。
    test_loader = _载入器(split['测试'],尺寸,批大小,False,False,种子,Path(数据根目录))
    report={'版本':VERSION,'实验日期':time.strftime('%Y-%m-%d %H:%M:%S'),
            '训练方式':'公开基线 + 本地微调','训练设备':设备,'类别':list(类别),'随机种子':种子,
            '参数':{'公开轮数':公开轮数,'微调轮数':微调轮数,'批大小':批大小,
                  '公开学习率':公开学习率,'微调学习率':微调学习率,'重放比例':重放比例},
            '独立轮次':split['本地轮次'],'数据数量':split['样本数量'],
            '选择依据':'仅依据本地验证集宏F1和准确率选择正式模型；独立测试集不参与训练、调参或选择',
            '正式模型':chosen,'对照方案':{}}
    for name, val in candidate.items():
        trained,_,_=加载分类模型(val['model'],设备)
        started=time.perf_counter()
        results,loss,_,_=批量评估(trained,test_loader,设备)
        seconds=round(time.perf_counter()-started,4)
        report['对照方案'][name]={'最佳轮次':val['epoch'],'验证指标':val['validation'],
                                '验证阈值':val['threshold'],'独立测试指标':results,
                                '测试损失':round(loss,5),'测试总耗时秒':seconds}
        保存图表(结果目录,val['history'],results,name)
        with (结果目录 / f'{name}-训练历史.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=val['history'][0].keys())
            writer.writeheader();writer.writerows(val['history'])
        print(f'{name} 独立测试：Acc={results["准确率"]:.3f}，F1={results["宏平均F1"]:.3f}')
    shutil.copy2(candidate[chosen]['model'],模型根目录 / '正式模型.pt')
    runtime={'置信度阈值':candidate[chosen]['threshold']['阈值'],'来自':'本地验证集',
             '正式模型':chosen,'训练方式':'公开+微调'}
    (模型根目录 / '运行阈值.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
    (模型根目录 / '混合数据划分.json').write_text(json.dumps(split,ensure_ascii=False,indent=2),encoding='utf-8')
    (结果目录 / '混合训练对比结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (结果目录 / '实验记录待补充.txt').write_text(
        '本报告的数值来自程序真实计算，未虚构模型准确率。\n'
        '公开数据采用 HaGRIDv2 精简子集，五种手势；无手仅来自本地空白视频。\n'
        f'独立轮次：{split["本地轮次"]}\n验证集选择：{chosen}\n'
        '请手动记录现场帧率、识别延迟、未知手势误触发、摄像头型号、光照条件等。\n'
        '注意：对照评估的离线测试集不等于真实演示完整系统的稳定性。\n',encoding='utf-8')
    print(f'最终正式模型：{chosen}；验证阈值={runtime["置信度阈值"]}；输出在：{结果目录}')
    return report
