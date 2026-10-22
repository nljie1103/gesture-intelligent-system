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


def 训练(mode:str,sessions:list[str],target:str='',epochs:int=8,device:str='cpu',data_root:Path=数据目录,model_root:Path=模型目录,output_root:Path=输出目录,include_public:bool=False,from_scratch:bool=False,hand_crop:bool=False):
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
    sample=训练样本索引(sessions,data_root,include_public=include_public)
    freq=Counter(y for _,y in sample)
    print('读取有效样本：',dict(zip(类别,[freq[i] for i in range(6)])),flush=True)
    print('公开数据：'+('已手动选择参与训练' if include_public else '本轮未使用公开数据')+'；该设置不会删除本地任何照片。',flush=True)
    print('注意：当前训练不使用独立验证/测试集，不报告泛化准确率。',flush=True)
    out=Path(output_root);out.mkdir(parents=True,exist_ok=True)
    official=root/'正式模型.pt'
    Set=设置随机种子
    Set(20261016)
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    size=int(读取配置().get('模型输入尺寸',96))
    prior_sha=文件哈希(official) if official.is_file() else None
    if mode=='focus' and (not prior_sha or from_scratch):raise ValueError('专项强化需要已有的六分类模型；且不能选择从零训练')
    if prior_sha and not from_scratch:
        network,loaded_size,old_meta=加载分类模型(official,device)
        from .手部定位 import 读取训练输入策略,策略标识
        if (读取训练输入策略(old_meta)==策略标识) != bool(hand_crop):
            raise ValueError('当前模型与所选的手部裁剪策略不一致：请勾选“从零训练”，防止输入分布混用。')
        size=loaded_size
        print('继续训练：加载已有六分类权重，并使用本轮选择的本地场景及可选公开数据。',flush=True)
    else:
        network=轻量卷积网络(len(类别)).to(device)
        print('从零初始化：本轮不加载旧模型权重。',flush=True)
    if mode=='focus':print('专项模式：目标手势增强采样 + 其他五类重放',flush=True)
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
        if hand_crop:
            from .手部定位 import 手部定位器
            from PIL import Image
            import numpy as np
            print('手部定位模式：先将正样本裁剪到真实关键点手框；无手样本保持背景画面。',flush=True)
            locator=手部定位器()
            normalized=[];failed={}
            try:
                for relative,y in sample:
                    if y==类别.index('无手'):
                        normalized.append((relative,y));continue
                    picture=staging/'数据快照'/relative
                    original=Path(data_root)/relative
                    marker=original.parent/'.输入策略.json'
                    if marker.is_file():
                        try:mode_record=json.loads(marker.read_text(encoding='utf-8'))
                        except (OSError,ValueError) as e:raise ValueError('采集模式标记不可读：'+str(marker)) from e
                        if mode_record.get('输入策略')== 'hand-landmarker-v1':
                            normalized.append((relative,y));continue
                    if relative.startswith('公开训练/'):
                        # HaGRID importer used its annotated hand bboxes, not the whole person frame.
                        normalized.append((relative,y));continue
                    with Image.open(picture) as im:
                        rgb=np.asarray(im.convert('RGB'))
                    box=locator.find_rgb(rgb)
                    if box is None:
                        failed[类别[y]]=failed.get(类别[y],0)+1
                        continue
                    crop=Image.fromarray(rgb).crop(box)
                    crop.save(picture.with_suffix('.jpg') if picture.suffix.lower()!='.jpg' else picture,format='JPEG',quality=93)
                    target_path=picture.with_suffix('.jpg') if picture.suffix.lower()!='.jpg' else picture
                    normalized.append((target_path.relative_to(staging/'数据快照').as_posix(),y))
            finally:locator.close()
            sample=normalized
            if failed:print('未检测到手而跳过的正样本：',failed,flush=True)
            present={y for _,y in sample}
            if len(present)!=len(类别):raise ValueError('手部定位后至少一个类别无有效训练样本；请调整采集姿态或关闭手部模式')
            freq=Counter(y for _,y in sample)
            weights=[(2.2 if mode=='focus' and y==类别.index(target) else 1.)/freq[y] for _,y in sample]
            sampler=WeightedRandomSampler(weights,num_samples=len(sample),replacement=True,
                                          generator=torch.Generator().manual_seed(20261016))
        train_data=手势数据集(sample,目录=staging/'数据快照',尺寸=size,增强=True)
        loader=DataLoader(train_data,batch_size=32,sampler=sampler,num_workers=0)
        optimizer=torch.optim.Adam(network.parameters(),lr=.00012 if mode=='focus' else (.00015 if prior_sha and not from_scratch else .0008))
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
                    '输入策略':('hand-landmarker-v1' if hand_crop else 'fixed-roi-v1'),'网络结构':'轻量卷积网络','训练策略':('累计继续训练' if prior_sha and not from_scratch else '初始训练') if mode=='all' else f'累计专项强化：{target}',
                    '版本':VERSION,'用途':'单场景或指定场景训练，无独立验证'}
        staged=staging/'正式模型.pt'
        torch.save(checkpoint,staged)
        verify,ms,meta=加载分类模型(staged,'cpu')
        with torch.inference_mode():
            trial=verify(torch.zeros(1,3,ms,ms))
            if tuple(trial.shape)!=(1,len(类别)) or not torch.isfinite(trial).all():raise ValueError('训练输出自检失败')
        stamp=time.strftime('%Y%m%d-%H%M%S')
        provenance={'模型SHA256':文件哈希(staged),'训练时间':time.strftime('%Y-%m-%d %H:%M:%S'),
                    '场景':list(sessions),'包含公开数据':bool(include_public),'从零训练':bool(from_scratch),'输入策略':('hand-landmarker-v1' if hand_crop else 'fixed-roi-v1'),'模式':mode,'专项类别':target if mode=='focus' else '',
                    '初始化模型SHA256':None if from_scratch else prior_sha,'累计训练':len(sessions)>1,'有效图像数':len(sample),
                    '各类样本数量':dict(zip(类别,[freq[i] for i in range(len(类别))])),
                    '提示':'已训练仅表示该类别参加训练，不代表已通过独立测试'}
        staged_record=staging/'训练来源.json'
        staged_record.write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
        report={'模式':mode,'专项类别':target if mode=='focus' else None,'训练场景':sessions,
                '训练样本数':len(sample),'包含公开数据':bool(include_public),'从零训练':bool(from_scratch),'输入策略':('hand-landmarker-v1' if hand_crop else 'fixed-roi-v1'),'初始化模型SHA256':None if from_scratch else prior_sha,'分类数量':dict(zip(类别,[freq[i] for i in range(6)])),
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
    parser.add_argument('--include-public',action='store_true',help='只有明确选择时才将已导入的公开数据用于训练')
    parser.add_argument('--from-scratch',action='store_true',help='重新初始化，不从已有训练权重续训')
    parser.add_argument('--hand-crop',action='store_true',help='先提取定位到的手部区域再训练')
    arg=parser.parse_args()
    try:训练(arg.mode,arg.sessions,arg.target,arg.epochs,arg.device,include_public=arg.include_public,from_scratch=arg.from_scratch,hand_crop=arg.hand_crop)
    except (ValueError,OSError,RuntimeError) as e:
        print('训练失败：'+str(e),file=sys.stderr,flush=True)
        raise SystemExit(1)

if __name__=='__main__':
    配置标准流UTF8()
    main()
