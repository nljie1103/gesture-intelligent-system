"""Local-only inventory and settings validation for the glass application UI."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from .配置 import 类别

EXT={'.jpg','.jpeg','.png','.bmp','.webp'}


def 统计样本(数据目录:Path)->dict:
    数据目录=Path(数据目录)
    public={};local={};sessions=set();by_session={}
    for name in 类别:
        p=数据目录/'公开训练'/name
        public[name]=sum(x.is_file() and x.suffix.lower() in EXT for x in p.iterdir()) if p.is_dir() else 0
        own=数据目录/name
        count=0
        if own.is_dir():
            for ses in sorted(own.iterdir()):
                if ses.is_dir():
                    n=sum(f.is_file() and f.suffix.lower() in EXT for f in ses.iterdir())
                    if n:
                        sessions.add(ses.name)
                        by_session.setdefault(ses.name,{})[name]=n
                        count+=n
        local[name]=count
    return {'公开':public,'本地':local,'轮次':sorted(sessions),'分轮次':by_session,
            '公开合计':sum(public.values()),'本地合计':sum(local.values())}


def 验证设置(new:dict)->dict:
    try:
        camera=int(new['摄像头编号'])
        roi=float(new['识别区域占画面短边比例'])
        stable=int(new['稳定帧数'])
        release=int(new['解除锁定帧数'])
        cooldown=float(new['触发冷却秒数'])
        refresh=int(new['视频刷新毫秒'])
        raw=new.get('最小置信度')
        threshold=None if raw is None or str(raw).strip()=='' else float(raw)
    except (ValueError,TypeError,KeyError) as exc:
        raise ValueError('存在格式错误的设置项') from exc
    if not 0<=camera<=20:raise ValueError('摄像头编号须在 0～20')
    if not .2<=roi<=1:raise ValueError('识别区域比例须在 0.20～1.00')
    if not 1<=stable<=30 or not 1<=release<=30:raise ValueError('稳定帧数与解锁帧数须在 1～30')
    if not 0<=cooldown<=30:raise ValueError('触发冷却须在 0～30 秒')
    if not 20<=refresh<=1000:raise ValueError('刷新间隔须在 20～1000 毫秒')
    if threshold is not None and not 0<=threshold<=1:raise ValueError('置信度阈值须在 0～1，留空使用模型默认值')
    return {'摄像头编号':camera,'识别区域占画面短边比例':roi,'稳定帧数':stable,
            '解除锁定帧数':release,'触发冷却秒数':cooldown,'视频刷新毫秒':refresh,
            '最小置信度':threshold,'显示候选手部框':bool(new.get('显示候选手部框',True))}


def 安全保存设置(path:Path,data:dict)->None:
    path=Path(path)
    payload=json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
    # Same-directory replace; no partial settings file left on interrupted writes.
    fd,temp=tempfile.mkstemp(prefix='.settings-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
