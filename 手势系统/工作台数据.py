"""数据工作台：安全导入、回收站、自动统计与训练数据索引。无 Qt 依赖。"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from PIL import Image
from .配置 import 类别, 数据目录

图片后缀={'.jpg','.jpeg','.png','.bmp','.webp'}
轮次格式=re.compile(r'^[\w\u4e00-\u9fff\-]{1,36}$',re.UNICODE)


def 验证轮次(name:str)->str:
    if not 轮次格式.fullmatch(name or '') or name in {'.','..','公开训练','回收站'}:
        raise ValueError('场景名只能包含中英文、数字、下划线或连字符，最多36字')
    return name


def 文件图片可读(path:Path)->bool:
    try:
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in 图片后缀:return False
        if path.stat().st_size > 24*1024*1024:return False
        with Image.open(path) as im:
            if im.width*im.height>24_000_000 or min(im.size)<16:return False
            im.verify()
        return True
    except (OSError,ValueError,SyntaxError,Image.DecompressionBombError,MemoryError):return False


def 样本汇总(root:Path=数据目录)->dict:
    root=Path(root)
    result={'公开':{},'本地':{},'场景':{},'错误文件':0}
    for label in 类别:
        pub=root/'公开训练'/label
        result['公开'][label]=sum(1 for x in pub.iterdir() if x.is_file() and x.suffix.lower() in 图片后缀) if pub.is_dir() else 0
        own=root/label
        count=0
        if own.is_dir():
            for session in own.iterdir():
                if not session.is_dir() or session.is_symlink():continue
                n=sum(1 for x in session.iterdir() if x.is_file() and x.suffix.lower() in 图片后缀)
                if n:
                    result['场景'].setdefault(session.name,{})[label]=n
                count+=n
        result['本地'][label]=count
    result['公开合计']=sum(result['公开'].values())
    result['本地合计']=sum(result['本地'].values())
    return result


def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def 导入图片(files:list[Path],category:str,session:str,root:Path=数据目录)->dict:
    if category not in 类别:raise ValueError('未知手势类别，不能导入')
    验证轮次(session)
    target=Path(root)/category/session
    if Path(root).is_symlink():raise ValueError('禁止在符号链接数据根目录下导入图片')
    if target.is_symlink() or (Path(root)/category).is_symlink():raise ValueError('禁止向符号链接目录导入图片')
    target.mkdir(parents=True,exist_ok=True)
    existing={_sha(p) for p in target.iterdir() if p.is_file() and p.suffix.lower() in 图片后缀}
    added=duplicate=invalid=0
    for source in files:
        source=Path(source)
        if not 文件图片可读(source):invalid+=1;continue
        digest=_sha(source)
        if digest in existing:duplicate+=1;continue
        name=f'import_{time.time_ns()}_{digest[:14]}{source.suffix.lower()}'
        dest=target/name
        tmp=target/(name+'.part')
        try:
            shutil.copyfile(source,tmp)
            if _sha(tmp)!=digest:raise OSError('复制过程中校验未通过')
            os.replace(tmp,dest)
        finally:
            tmp.unlink(missing_ok=True)
        existing.add(digest);added+=1
    return {'新增':added,'重复':duplicate,'无效':invalid,'位置':str(target)}


def 回收本地场景(category:str,session:str,root:Path=数据目录)->Path:
    if category not in 类别:raise ValueError('只能回收私人手势类别')
    验证轮次(session)
    root=Path(root)
    src=root/category/session
    if not src.is_dir() or src.is_symlink():raise FileNotFoundError('所选场景不存在或不是正常目录')
    trash=root/'回收站'/(time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()))/category
    destination=trash/session
    if destination.exists():raise FileExistsError('回收目录存在同名冲突，请稍后重试')
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(str(src),str(destination))
    return destination


def 训练样本索引(sessions:list[str],root:Path=数据目录,include_public:bool=False):
    root=Path(root)
    sessions=list(dict.fromkeys(验证轮次(x) for x in sessions))
    if not sessions:raise ValueError('至少选择一个训练场景')
    sample=[]
    for i,label in enumerate(类别):
        for scene in sessions:
            folder=root/label/scene
            if folder.is_dir() and not folder.is_symlink():
                for p in sorted(folder.iterdir()):
                    if 文件图片可读(p):sample.append((p.relative_to(root).as_posix(),i))
        if include_public:
            pub=root/'公开训练'/label
            if pub.is_dir() and not pub.is_symlink():
                for p in sorted(pub.iterdir()):
                    if 文件图片可读(p):sample.append((p.relative_to(root).as_posix(),i))
    missing=[c for i,c in enumerate(类别) if not any(y==i for _,y in sample)]
    if missing:raise ValueError('这些类别没有任何训练图片：'+', '.join(missing))
    return sample


def 推荐新场景名称(root:Path=数据目录,prefix:str='场景')->str:
    """Find the next never-currently-used numbered capture scene across all six gestures."""
    root=Path(root)
    pattern=re.compile(r'^'+re.escape(prefix)+r'(\d+)$')
    maximum=0;width=2
    for item in 场景明细(root):
        match=pattern.fullmatch(item['场景'])
        if match:
            maximum=max(maximum,int(match.group(1)))
            width=max(width,len(match.group(1)))
    return f'{prefix}{maximum+1:0{width}d}'


def 验证快捷键(start:str,stop:str):
    valid=re.compile(r'^(?:[A-Z0-9]|F(?:[1-9]|1[0-2]))$')
    if not valid.fullmatch(start.upper()) or not valid.fullmatch(stop.upper()) or start.upper()==stop.upper():
        raise ValueError('快捷键须为不同的字母、数字或 F1~F12')
    return start.upper(),stop.upper()


def 场景明细(root:Path=数据目录)->list[dict]:
    """按场景列出各手势图片数；只统计本地私有数据，不扫描公开集或回收站。"""
    root=Path(root)
    per_scene={}
    for gesture in 类别:
        folder=root/gesture
        if not folder.is_dir() or folder.is_symlink():continue
        for scene in folder.iterdir():
            if not scene.is_dir() or scene.is_symlink():continue
            try:验证轮次(scene.name)
            except ValueError:continue
            count=sum(1 for file in scene.iterdir()
                      if file.is_file() and not file.is_symlink() and file.suffix.lower() in 图片后缀)
            per_scene.setdefault(scene.name,{key:0 for key in 类别})[gesture]=count
    return [{'场景':scene,'手势':counts,'合计':sum(counts.values())}
            for scene,counts in sorted(per_scene.items())]


def 回收整个场景(session:str,root:Path=数据目录)->dict:
    """按类别将同名场景移到本地回收站的同一批次；不触及公开训练图。"""
    验证轮次(session);root=Path(root)
    sources=[]
    for gesture in 类别:
        parent=root/gesture;source=parent/session
        if parent.is_symlink() or source.is_symlink():raise ValueError('发现符号链接，拒绝移动')
        if source.is_dir():sources.append((gesture,source))
    if not sources:raise FileNotFoundError('所选场景不存在')
    base=root/'回收站'/(time.strftime('%Y%m%d-%H%M%S')+'-'+str(time.time_ns()))
    moved={}
    try:
        for gesture,source in sources:
            dest=base/gesture/session;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(str(source),str(dest));moved[gesture]=str(dest)
    except Exception:
        # 同一磁盘内移动目录通常是原子操作；若出现异常，优先恢复已经移动的类别。
        for gesture,destination in list(moved.items())[::-1]:
            original=root/gesture/session
            if not original.exists() and Path(destination).exists():
                shutil.move(destination,original)
        raise
    return {'场景':session,'各类回收位置':moved,'回收类别数':len(moved),'回收目录':str(base)}


def 创建训练快照(sample:list[tuple[str,int]], data_root:Path, snapshot_root:Path)->list[tuple[str,int]]:
    """Copy input images into a stable private staging directory before DataLoader opens them."""
    data_root=Path(data_root).resolve();snapshot_root=Path(snapshot_root)
    output=[]
    for relative,label in sample:
        source=data_root/relative
        resolved=source.resolve()
        if not resolved.is_relative_to(data_root) or source.is_symlink() or not 文件图片可读(source):
            raise ValueError('训练图片已移动或不可读：'+str(relative))
        destination=snapshot_root/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        before=_sha(source)
        shutil.copyfile(source,destination)
        if _sha(destination)!=before:raise OSError('采样时图片被外部程序修改：'+str(relative))
        output.append((relative,label))
    return output
