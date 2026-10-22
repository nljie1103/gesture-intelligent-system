"""只有用户在界面明确触发时才执行公网下载，避免静默导入 402MB 公开数据。"""
from __future__ import annotations
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path
from .公开数据 import 导入公开子集

HAGRID_URL = 'https://huggingface.co/datasets/GestureDetectionConnoisseurs/hagrid_subsets/resolve/main/hagrid-export_100_images.zip'
HAGRID_SHA256 = '72ada2959c117d23e98c8c4da2c9009580554d12163a6db8f78de50312cbdc47'
MAX_BYTES = 480 * 1024 * 1024

def 下载并导入(根目录, 回报=None, 取消=None, 下载函数=None):
    """文件完整验证后调用原始安全导入器；网络或导入异常时清理临时压缩包。"""
    root=Path(根目录)
    if (root/'公开训练').exists() or (root/'公开数据清单.json').exists():
        raise FileExistsError('已有公开数据，避免覆盖；如需重新导入请先手动备份原数据。')
    root.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='hagrid-download-',suffix='.zip',dir=root)
    os.close(fd)
    archive=Path(tmp)
    try:
        if 取消 and 取消():raise InterruptedError('已取消下载')
        h=hashlib.sha256();size=0
        if 下载函数 is not None:
            source=下载函数(HAGRID_URL)
        else:
            source=urllib.request.urlopen(urllib.request.Request(HAGRID_URL,headers={'User-Agent':'GestureStudio/2.3'}),timeout=45)
        with source,archive.open('wb') as writer:
            while True:
                if 取消 and 取消():raise InterruptedError('已取消下载')
                data=source.read(1024*1024)
                if not data:break
                size+=len(data)
                if size>MAX_BYTES:raise ValueError('超出公开数据预期下载大小，终止')
                writer.write(data);h.update(data)
                if 回报:回报(size)
        if h.hexdigest()!=HAGRID_SHA256:raise ValueError('下载数据的 SHA256 与上游原始归档不一致，拒绝导入')
        if 取消 and 取消():raise InterruptedError('已取消下载')
        return 导入公开子集(archive,每类最多=100,数据根目录=root)
    finally:
        archive.unlink(missing_ok=True)
