"""训练来源的可核验状态。老模型的类别来源不能凭文件存在就判断。"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .配置 import 类别,模型目录
from .模型发布 import TXN_NAME


def 文件哈希(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def 训练记录状态(model_path:Path=None,record_path:Path=None)->dict:
    model_path=Path(model_path or (模型目录/'正式模型.pt'))
    if (model_path.parent/TXN_NAME).exists():
        return {'状态':'模型发布中，请稍候','类别':{k:'更新中' for k in 类别},'场景':[]}
    record_path=Path(record_path or (模型目录/'训练来源.json'))
    unknown={k:'来源未记录' for k in 类别}
    if not model_path.is_file():return {'状态':'未训练','类别':{k:'未训练' for k in 类别},'场景':[]}
    if not record_path.is_file():return {'状态':'模型存在，训练来源未知','类别':unknown,'场景':[]}
    try:
        rec=json.loads(record_path.read_text(encoding='utf-8'))
        if rec.get('模型SHA256')!=文件哈希(model_path):
            return {'状态':'训练记录与模型不匹配','类别':unknown,'场景':[]}
        raw=rec.get('各类样本数量',{})
        return {'状态':'已记录','类别':{k:'已训练' if int(raw.get(k,0))>0 else '未训练' for k in 类别},
                '场景':rec.get('场景',[]),'模式':rec.get('模式',''),'专项类别':rec.get('专项类别',''),
                '训练时间':rec.get('训练时间','')}
    except (OSError,ValueError,TypeError,KeyError):
        return {'状态':'训练记录不可读','类别':unknown,'场景':[]}
