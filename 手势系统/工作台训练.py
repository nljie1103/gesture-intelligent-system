"""数据工作台训练。演示训练：不把同一采集场景当独立测试集。"""
from __future__ import annotations
from .版本 import VERSION
import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from .配置 import 类别, 数据目录, 模型目录, 输出目录, 读取配置
from .工作台数据 import 训练样本索引, 创建训练快照
from .模型发布 import 恢复中断发布, 发布模型与来源
from .训练状态 import 文件哈希
from .训练日志编码 import 配置标准流UTF8


def 训练(mode:str,sessions:list[str],target:str='',epochs:int=8,device:str='cpu',data_root:Path=数据目录,model_root:Path=模型目录,output_root:Path=输出目录):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader,WeightedRandomSampler
    from .数据 import 手势数据集
    from .模型 import 轻量卷积网络,加载分类模型
    from .训练 import 设置随机种子
    if mode not in ('all','focus'):raise ValueError('训练模式只能是 all 或 focus')
    if mode=='focus' and target not in 类别:raise ValueError('专项强化只能选择现有六分类中的手势')
    if not 1<=epochs<=200:raise ValueError('训练轮次应在1至200之间')
    if device.startswith('cuda') and not torch.cuda.is_available():raise ValueError('PyTorch CUDA 不可用')
    root=Path(model_root);root.mkdir(parents=True,exist_ok=True)
    恢复中断发布(root)
    sample=训练样本索引(sessions,data_root)
    freq=Counter(y for _,y in sample)
    print('读取有效样本：',dict(zip(类别,[freq[i] for i in range(6)])),flush=True)
    print('注意：当前训练不使用独立验证/测试集，不报告泛化准确率。',flush=True)
    out=Path(output_root);out.mkdir(parents=True,exist_ok=True)
    official=root/'正式模型.pt'
    Set=设置随机种子
    Set(20261016)
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    size=int(读取配置().get('模型输入尺寸',96))
    if mode=='focus':
        if not official.exists():raise ValueError('专项强化需要已有的六分类模型；请先执行全部训练')
        network,loaded_size,_=加载分类模型(official,device)
        size=loaded_size
        print('专项模式：现有六分类网络 + 目标手势增强采样 + 其他五类重放',flush=True)
    else:network=轻量卷积网络(len(类别)).to(device)
    rng=random.Random(20261016)
    # 采样平衡：每类基础权重相当；指定类别提高到2.2倍，同时持续回放其余类别。
    weights=[(2.2 if mode=='focus' and y==类别.index(target) else 1.)/freq[y] for _,y in sample]
    sampler=WeightedRandomSampler(weights,num_samples=len(sample),replacement=True,
                                  generator=torch.Generator().manual_seed(20261016))
    # Snapshot is immutable for the duration of training: UI recycling or external moves
    # cannot invalidate DataLoader reads mid-epoch. Always clean up in finally.
    staging=Path(tempfile.mkdtemp(prefix='.train-',dir=root))
    try:
        sample=创建训练快照(sample,Path(data_root),staging/'数据快照')
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True)
        raise
    try:
        train_data=手势数据集(sample,目录=staging/'数据快照',尺寸=size,增强=True)
        loader=DataLoader(train_data,batch_size=32,sampler=sampler,num_workers=0)
        optimizer=torch.optim.Adam(network.parameters(),lr=.00012 if mode=='focus' else .0008)
        started=time.time();records=[]
        for epoch in range(1,epochs+1):
            network.train();seen=correct=0;loss_sum=0.
            for x,y in loader:
                x=x.to(device);y=y.to(device)
                optimizer.zero_grad(set_to_none=True)
                scores=network(x)
                loss=nn.functional.cross_entropy(scores,y)
                loss.backward();optimizer.step()
                seen+=len(y);correct+=int((scores.argmax(dim=1)==y).sum().item())
                loss_sum+=float(loss.item())*len(y)
            entry={'epoch':epoch,'train_loss':round(loss_sum/max(seen,1),5),
                   'train_acc_not_test':round(correct/max(seen,1),5)}
            records.append(entry)
            print(f'[{epoch}/{epochs}] loss={entry["train_loss"]:.4f} 训练准确率={entry["train_acc_not_test"]:.1%}（非测试）',flush=True)
        checkpoint={'权重':network.state_dict(),'类别':list(类别),'输入尺寸':size,
                    '网络结构':'轻量卷积网络','训练策略':'工作台全部训练' if mode=='all' else f'工作台专项强化：{target}',
                    '版本':VERSION,'用途':'单场景或指定场景训练，无独立验证'}
        staged=staging/'正式模型.pt'
        torch.save(checkpoint,staged)
        verify,ms,meta=加载分类模型(staged,'cpu')
        with torch.inference_mode():
            trial=verify(torch.zeros(1,3,ms,ms))
            if tuple(trial.shape)!=(1,len(类别)) or not torch.isfinite(trial).all():raise ValueError('训练输出自检失败')
        stamp=time.strftime('%Y%m%d-%H%M%S')
        provenance={'模型SHA256':文件哈希(staged),'训练时间':time.strftime('%Y-%m-%d %H:%M:%S'),
                    '场景':list(sessions),'模式':mode,'专项类别':target if mode=='focus' else '',
                    '各类样本数量':dict(zip(类别,[freq[i] for i in range(len(类别))])),
                    '提示':'已训练仅表示该类别参加训练，不代表已通过独立测试'}
        staged_record=staging/'训练来源.json'
        staged_record.write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
        report={'模式':mode,'专项类别':target if mode=='focus' else None,'训练场景':sessions,
                '训练样本数':len(sample),'分类数量':dict(zip(类别,[freq[i] for i in range(6)])),
                '训练记录':records,'独立测试':None,'性质':'仅供演示；需独立采集验证与测试'}
        report_path=out/(f'工作台训练_{stamp}_{time.time_ns()}.json')
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        backup_dir=root/'历史版本';backup_dir.mkdir(parents=True,exist_ok=True)
        old=root/'正式模型.pt'
        if old.is_file():
            dest=backup_dir/(f'{stamp}-{time.time_ns()}-正式模型.pt')
            shutil.copy2(old,dest)
            old_rec=root/'训练来源.json'
            if old_rec.is_file():shutil.copy2(old_rec,dest.with_suffix('.json'))
        # Publish model + provenance together; invalidate the old calibrated threshold.
        发布模型与来源(root,staged,staged_record)
        print('训练成功：新正式模型及来源记录已保存；旧阈值已失效。',flush=True)
        print('报告：',report_path,flush=True)
    finally:
        shutil.rmtree(staging,ignore_errors=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['all','focus'],required=True)
    parser.add_argument('--target',default='')
    parser.add_argument('--sessions',nargs='+',required=True)
    parser.add_argument('--epochs',type=int,default=8)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    arg=parser.parse_args()
    try:训练(arg.mode,arg.sessions,arg.target,arg.epochs,arg.device)
    except (ValueError,OSError,RuntimeError) as e:
        print('训练失败：'+str(e),file=sys.stderr,flush=True)
        raise SystemExit(1)

if __name__=='__main__':
    配置标准流UTF8()
    main()
