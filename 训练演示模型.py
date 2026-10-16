# -*- coding: utf-8 -*-
"""用 HaGRID 公开训练集 + 场景01 完成临时实时演示训练。

这是功能验收用模型，不进行独立验证或报告泛化准确率，不取代三轮正式实验。
使用项目 v1.1.0 已安装的轻量 CNN、预处理以及六种固定类别。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path, PurePosixPath


def main() -> int:
    parser = argparse.ArgumentParser(description='HaGRID 公开数据 + 场景01：训练六分类临时演示模型')
    parser.add_argument('--project', type=Path, default=Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统')
    parser.add_argument('--session', default='场景01', help='已有的本地采集轮次；默认场景01')
    parser.add_argument('--epochs-public', type=int, default=10, help='公共基础训练轮数，默认10')
    parser.add_argument('--epochs-local', type=int, default=8, help='本地微调轮数，默认8')
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--min-local', type=int, default=20, help='每个本地类别最低图片数')
    parser.add_argument('--threshold', type=float, default=0.85, help='演示固定阈值；没有验证集，默认0.85')
    parser.add_argument('--check-only', action='store_true', help='只检查数据是否齐全，不训练、不生成模型')
    args = parser.parse_args()

    if args.epochs_public < 1 or args.epochs_local < 1 or args.batch_size < 1:
        parser.error('轮数与批大小必须大于零')
    if args.min_local < 1 or not 0.5 <= args.threshold <= 0.99:
        parser.error('min-local 至少1；threshold 必须在0.50~0.99')
    if '/' in args.session or '\\' in args.session or args.session in ('', '.', '..'):
        parser.error('session 不允许路径分隔符或空名称')
    project = args.project.resolve()
    if not (project / '手势系统' / '模型.py').is_file() or not (project / '训练混合模型.py').is_file():
        raise SystemExit('[错误] 未找到已安装的 v1.1.0 工程：' + str(project))
    sys.path.insert(0, str(project))

    from 手势系统.配置 import 类别, 数据目录, 模型目录, 输出目录, 读取配置
    if project != Path(数据目录).parent.resolve():
        raise SystemExit('[错误] 项目路径与 Python 载入的源码路径不一致，请避免安装了两份项目。')

    manifest_path = 数据目录 / '公开数据清单.json'
    if not manifest_path.is_file():
        raise SystemExit('[错误] 缺少公开数据清单，请先运行 导入公开数据.py')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    public = []
    for idx, label in enumerate(类别[:5]):
        records = manifest.get('样本', {}).get(label, [])
        if not records:
            raise SystemExit(f'[错误] 公开集缺少 {label}，请检查导入清单')
        for record in records:
            raw = record.get('路径') if isinstance(record, dict) else None
            if not isinstance(raw, str) or not raw or '\\' in raw or ':' in raw or '\x00' in raw:
                raise SystemExit('[错误] 清单包含不合规相对路径')
            relative = PurePosixPath(raw)
            if (relative.is_absolute() or '..' in relative.parts or len(relative.parts) != 3 or
                relative.parts[0] != '公开训练' or relative.parts[1] != label or
                relative.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp'} or
                relative.as_posix() != raw):
                raise SystemExit('[错误] 清单中发现非法或错类的公开数据路径')
            if not 数据目录.joinpath(*relative.parts).is_file():
                raise SystemExit('[错误] 公开样本不存在：' + raw)
            public.append((raw, idx))
    allowed = {'.jpg', '.jpeg', '.png', '.bmp'}
    local = []
    local_counts = {}
    for idx, label in enumerate(类别):
        folder = 数据目录 / label / args.session
        if not folder.is_dir():
            raise SystemExit(f'[错误] 尚未采集 {label}/{args.session}。本模式仅需这一轮，但六类都必须完成。')
        images = sorted(x for x in folder.iterdir() if x.is_file() and x.suffix.lower() in allowed)
        if len(images) < args.min_local:
            raise SystemExit(f'[错误] {label}/{args.session} 只有 {len(images)} 张，需至少 {args.min_local} 张。')
        local_counts[label] = len(images)
        local.extend((x.relative_to(数据目录).as_posix(), idx) for x in images)
    print('========== 临时演示训练：数据检查 ==========', flush=True)
    print('公开训练：', dict(Counter(类别[y] for _,y in public)), flush=True)
    print('本地单轮：', local_counts, flush=True)
    print('公开来源 SHA256：', manifest.get('来源ZIP_SHA256', '清单未记录'), flush=True)
    print('本次只用这些数据训练，不提供独立验证/测试准确率。', flush=True)
    if args.check_only:
        print('[成功] 数据检查通过；尚未开始训练，也没有写入模型。')
        return 0

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from 手势系统.数据 import 手势数据集
    from 手势系统.模型 import 轻量卷积网络, 加载分类模型
    from 手势系统.训练 import 设置随机种子

    torch.set_num_threads(min(4, max(1, os.cpu_count() or 1)))
    设置随机种子(20261016)
    img_size = int(读取配置()['模型输入尺寸'])
    if img_size < 32 or img_size > 512:
        raise SystemExit('[错误] 模型输入尺寸不在合理范围。')
    output_file = 模型目录 / '正式模型.pt'
    threshold_file = 模型目录 / '运行阈值.json'
    for name in ('正式模型.pt', '运行阈值.json', '混合基线模型.pt', '混合微调模型.pt'):
        if (模型目录 / name).exists():
            raise SystemExit(f'[错误] 模型/{name} 已存在，拒绝覆盖原有模型；请先备份并明确处理。')
    out_dir = 输出目录 / '临时演示训练'
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit('[错误] 输出/临时演示训练 已存在训练记录，拒绝覆盖。')
    out_dir.mkdir(parents=True, exist_ok=True)
    模型目录.mkdir(parents=True, exist_ok=True)

    # 演示模式：公开五类 + 场景01 的“无手”训练第一个六分类网络。
    baseline = public + [(p, y) for p, y in local if y == len(类别)-1]
    # 微调：场景01 全部六类 + 少量公开图片重放，避免忘记基本手势。
    rng = random.Random(20261016)
    replay = []
    for idx in range(5):
        members = [(p, y) for p, y in public if y == idx]
        rng.shuffle(members)
        replay.extend(members[:max(1, round(len(members) * .25))])
    adapt = local + replay

    def loader(items, augmentation, seed):
        data = 手势数据集(items, 目录=数据目录, 尺寸=img_size, 增强=augmentation)
        counts = Counter(y for _, y in items)
        weights = [1.0 / counts[y] for _, y in items]
        sampler = WeightedRandomSampler(weights, num_samples=len(items), replacement=True,
                                         generator=torch.Generator().manual_seed(seed))
        return DataLoader(data, batch_size=args.batch_size, sampler=sampler, num_workers=0)

    history = []
    started = time.perf_counter()
    network = 轻量卷积网络(len(类别)).to('cpu')

    def train_phase(name, items, epochs, lr, augment, seed):
        dl = loader(items, augment, seed)
        optimizer = torch.optim.Adam(network.parameters(), lr=lr)
        for epoch in range(1, epochs+1):
            network.train()
            seen = right = 0
            sumloss = 0.0
            for x,y in dl:
                optimizer.zero_grad(set_to_none=True)
                prediction = network(x)
                loss = nn.functional.cross_entropy(prediction, y)
                loss.backward()
                optimizer.step()
                count = len(y)
                seen += count
                right += int((prediction.argmax(1) == y).sum().item())
                sumloss += loss.item() * count
            row = {
                '阶段':name, 'Epoch':epoch, '训练样本数':len(items),
                '训练损失':round(sumloss/max(1,seen),5),
                '训练准确率_非独立评估':round(right/max(1,seen),5)
            }
            history.append(row)
            print(f'[{name}] {epoch}/{epochs} | loss={row["训练损失"]:.4f} | '
                  f'训练acc={row["训练准确率_非独立评估"]:.1%} （不是测试准确率）', flush=True)

    staging = Path(tempfile.mkdtemp(prefix='.demo-stage-', dir=模型目录))
    try:
        train_phase('公开基础训练',baseline,args.epochs_public,0.001,False,20261016)
        torch.save({'权重':network.state_dict(),'类别':list(类别),'输入尺寸':img_size,
                    '网络结构':'轻量卷积网络','训练策略':'临时演示-公开基础训练',
                    '版本':'1.1.0','用途':'仅供功能调试，无独立验证'},staging / '公开基础模型.pt')
        train_phase('本地单轮微调',adapt,args.epochs_local,0.0003,True,20261017)
        torch.save({'权重':network.state_dict(),'类别':list(类别),'输入尺寸':img_size,
                    '网络结构':'轻量卷积网络','训练策略':'临时演示-单轮微调',
                    '版本':'1.1.0','用途':'仅供功能调试，无独立验证'},staging / '正式模型.pt')
        # 在正式模型落地前实际检查加载、输入张量尺寸、输出维度以及有限概率。
        reloaded, size, meta = 加载分类模型(staging / '正式模型.pt', 'cpu')
        reloaded.eval()
        with torch.inference_mode():
            out = reloaded(torch.zeros((1, 3, size, size), dtype=torch.float32))
            assert out.shape == (1, 6) and torch.isfinite(out).all(), '权重自检失败'
        note = {
            '用途':'临时软件功能验证，尚未进行独立验证及测试',
            '不可用于正式实验报告准确率':True,
            '来源':'HaGRIDv2 公开精简集 + 仅场景01',
            '来源ZIP_SHA256':manifest.get('来源ZIP_SHA256'),
            '本地轮次':args.session,
            '各类别本地数量':local_counts,
            '公开样本总数':len(public),
            '公开基础训练样本数':len(baseline),
            '微调样本数_包含重放':len(adapt),
            '基线轮数':args.epochs_public,
            '微调轮数':args.epochs_local,
            '固定置信度阈值':args.threshold,
            '阈值来源':'演示预设，未使用验证集进行校准',
            '时间':time.strftime('%Y-%m-%d %H:%M:%S'),
            '训练历史':history,
        }
        (staging / '运行阈值.json').write_text(json.dumps({
            '置信度阈值':args.threshold, '来自':'演示固定值，非验证集调参',
            '正式模型':'临时演示单轮微调','训练方式':'公开+场景01',
            '仅供演示':True
        },ensure_ascii=False,indent=2),encoding='utf-8')
        with (staging / '训练历史.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=history[0].keys())
            writer.writeheader();writer.writerows(history)
        (staging / '演示训练记录.json').write_text(json.dumps(note,ensure_ascii=False,indent=2),encoding='utf-8')
        # 保证正式模型按现有 GUI 的契约放置；不修改受 Git 跟踪的源码。
        if output_file.exists() or threshold_file.exists():
            raise FileExistsError('训练期间正式模型或阈值文件出现，拒绝覆盖。')
        os.replace(staging/'正式模型.pt',output_file)
        os.replace(staging/'运行阈值.json',threshold_file)
        for name in ('公开基础模型.pt','训练历史.csv','演示训练记录.json'):
            shutil.move(str(staging/name),str(out_dir/name))
        print('\n========== 临时演示模型已就绪 ==========', flush=True)
        print('保存：', output_file, flush=True)
        print('阈值：', threshold_file, f'（固定 {args.threshold:.2f}，未校准）', flush=True)
        print('耗时：', round(time.perf_counter()-started,1), '秒', flush=True)
        print('下一步请关闭采集程序，然后执行：',flush=True)
        print(f'cd "{project}"',flush=True)
        print(r'.\.venv\Scripts\python.exe 启动系统.py',flush=True)
        print('此模型只用于摄像头和交互功能调试，不能作为正式独立测试结果。',flush=True)
        return 0
    finally:
        shutil.rmtree(staging,ignore_errors=True)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n[取消] 用户停止训练。')
        sys.exit(130)
    except Exception as e:
        print(f'[错误] {type(e).__name__}: {e}',file=sys.stderr)
        sys.exit(1)
