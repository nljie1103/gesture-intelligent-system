"""本地 HaGRID 公开数据的安装状态、残留修复和安全回收。绝不触及私人类别目录。"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from datetime import datetime

五类 = ('张开手掌','握拳','点赞','剪刀手','食指指向')


def 公开数据状态(root:Path):
    root=Path(root)
    folder=root/'公开训练';manifest=root/'公开数据清单.json'
    present=folder.exists() or folder.is_symlink() or manifest.exists() or manifest.is_symlink()
    counts={k:0 for k in 五类}
    invalid=[]
    if folder.exists() and folder.is_dir() and not folder.is_symlink():
        for category in 五类:
            d=folder/category
            if d.is_dir() and not d.is_symlink():
                counts[category]=sum(1 for p in d.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.jpg','.jpeg','.png'))
    if folder.is_symlink() or manifest.is_symlink():invalid.append('不接受符号链接')
    if manifest.is_file() and not manifest.is_symlink():
        try:
            data=json.loads(manifest.read_text(encoding='utf-8-sig'))
            if not isinstance(data.get('样本'),dict):invalid.append('清单缺少样本索引')
        except (OSError,ValueError,TypeError):invalid.append('清单无法解析')
    elif folder.exists():invalid.append('缺少公开数据清单')
    if manifest.exists() and not folder.is_dir():invalid.append('公开训练目录不存在')
    if folder.exists() and any(n==0 for n in counts.values()):invalid.append('公开数据五类不齐全')
    if not present:status='未安装'
    elif not invalid and all(counts.values()) and manifest.is_file() and folder.is_dir():status='已安装'
    else:status='残留或不完整'
    return {'状态':status,'数量':counts,'合计':sum(counts.values()),'原因':invalid,
            '目录':str(folder),'清单':str(manifest)}


def 回收公开数据(root:Path):
    """把公开训练目录及清单移动到本地回收站；若第二项失败，恢复第一项。"""
    root=Path(root);folder=root/'公开训练';manifest=root/'公开数据清单.json'
    items=[p for p in (folder,manifest) if p.exists() or p.is_symlink()]
    if not items:return None
    if any(p.is_symlink() for p in items):raise ValueError('公开数据包含符号链接，请人工核查后再操作')
    if folder.exists() and not folder.is_dir():raise ValueError('公开训练路径不是目录，拒绝回收')
    recycle=root/'回收站'/('公开数据-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    recycle.mkdir(parents=True,exist_ok=False)
    moved=[]
    try:
        for p in items:
            dest=recycle/p.name
            os.replace(p,dest)
            moved.append((p,dest))
    except Exception:
        for old,new in reversed(moved):
            if new.exists():os.replace(new,old)
        try:recycle.rmdir()
        except OSError:pass
        raise
    return recycle
