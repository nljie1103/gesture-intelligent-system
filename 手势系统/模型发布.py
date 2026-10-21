"""v2.0.0: crash-recoverable model/metadata publication; no stale calibration."""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path

TXN_NAME='.训练发布事务'


def _atomic_json(path: Path, data: dict):
    part=path.with_name(path.name+'.part')
    try:
        with part.open('w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.flush();os.fsync(f.fileno())
        os.replace(part,path)
    finally:part.unlink(missing_ok=True)


def 恢复中断发布(model_root: Path):
    """Called before loading/training; an interrupted transaction restores the previous coherent triple."""
    root=Path(model_root);tx=root/TXN_NAME
    if not tx.exists():return False
    manifest=tx/'journal.json'
    if not manifest.is_file():
        # Model replacement cannot begin before a durable pending journal exists.
        shutil.rmtree(tx)
        return True
    status=json.loads(manifest.read_text(encoding='utf-8'))
    if status.get('state') in ('committed','preparing'):
        shutil.rmtree(tx)
        return True
    for name,existed in status['original'].items():
        dest=root/name
        if existed:
            saved=tx/name
            if not saved.is_file():raise RuntimeError('缺少恢复模型的备份：'+str(saved))
            restore=tx/(name+'.restore')
            shutil.copy2(saved,restore)
            os.replace(restore,dest)
        else:dest.unlink(missing_ok=True)
    shutil.rmtree(tx)
    return True


def 发布模型与来源(model_root:Path,staged_model:Path,staged_record:Path):
    """Never leave a newly trained model with a stale provenance or threshold on an ordinary failure.
    A journal allows recovery after process termination or OS interruption on next launch.
    Caller prepares and verifies both files before committing.
    """
    root=Path(model_root);root.mkdir(parents=True,exist_ok=True)
    恢复中断发布(root)
    tx=root/TXN_NAME
    tx.mkdir(exist_ok=False)
    names=['正式模型.pt','训练来源.json','运行阈值.json']
    existed={n:(root/n).is_file() for n in names}
    try:
        _atomic_json(tx/'journal.json',{'state':'preparing','original':existed})
        for n in names:
            if existed[n]:shutil.copy2(root/n,tx/n)
        _atomic_json(tx/'journal.json',{'state':'pending','original':existed})
        os.replace(staged_model,root/'正式模型.pt')
        os.replace(staged_record,root/'训练来源.json')
        # Existing calibration was attached to old weights. Never use it on new weights.
        (root/'运行阈值.json').unlink(missing_ok=True)
        _atomic_json(tx/'journal.json',{'state':'committed','original':existed})
    except BaseException:
        if (tx/'journal.json').exists():恢复中断发布(root)
        else:shutil.rmtree(tx,ignore_errors=True)
        raise
    shutil.rmtree(tx)
