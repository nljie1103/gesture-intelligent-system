"""用户手动触发公开数据下载；支持字节进度、取消及完整性校验。"""
from __future__ import annotations
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path
from .公开数据 import 导入公开子集
from .公开数据管理 import 公开数据状态

HAGRID_URL = 'https://huggingface.co/datasets/GestureDetectionConnoisseurs/hagrid_subsets/resolve/main/hagrid-export_100_images.zip'
HAGRID_SHA256 = '72ada2959c117d23e98c8c4da2c9009580554d12163a6db8f78de50312cbdc47'
MAX_BYTES = 480 * 1024 * 1024

def 下载并导入(根目录, 回报=None, 取消=None, 下载函数=None, 阶段=None):
    root=Path(根目录)
    state=公开数据状态(root)
    if state['状态']!='未安装':
        raise FileExistsError('公开数据状态为 '+state['状态']+'，请在数据页先清理残留或删除旧数据。')
    root.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='hagrid-download-',suffix='.zip',dir=root)
    os.close(fd)
    archive=Path(tmp)
    try:
        if 取消 and 取消():raise InterruptedError('已取消下载')
        h=hashlib.sha256();size=0
        if 阶段:阶段('下载公开数据压缩包')
        if 下载函数 is not None:
            source=下载函数(HAGRID_URL)
        else:
            source=urllib.request.urlopen(urllib.request.Request(HAGRID_URL,headers={'User-Agent':'GestureStudio/2.3.1'}),timeout=45)
        with source,archive.open('wb') as writer:
            raw_length=getattr(source,'headers',{}).get('Content-Length')
            try:total=int(raw_length)
            except (ValueError,TypeError):total=0
            if total<0 or total>MAX_BYTES:total=0
            while True:
                if 取消 and 取消():raise InterruptedError('已取消下载')
                data=source.read(1024*1024)
                if not data:break
                size+=len(data)
                if size>MAX_BYTES:raise ValueError('超出公开数据预期下载大小，终止')
                writer.write(data);h.update(data)
                if 回报:回报(size,total)
        if 阶段:阶段('下载完成，正在验证文件 SHA256')
        if h.hexdigest()!=HAGRID_SHA256:raise ValueError('下载数据的 SHA256 与上游原始归档不一致，拒绝导入')
        if 取消 and 取消():raise InterruptedError('已取消下载')
        if 阶段:阶段('已验证，正在安全裁剪并导入公开样本')
        return 导入公开子集(archive,每类最多=100,数据根目录=root)
    finally:
        archive.unlink(missing_ok=True)
