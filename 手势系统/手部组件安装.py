"""需要用户在设置页主动点击后才下载/安装手部定位组件。"""
from __future__ import annotations
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from .手部定位 import 定位资源,包含定位资源

# 固定上游发布 URL；不是手势公开训练集。
MODEL_URL='https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
MAX_SIZE=16*1024*1024

def 安装(on_progress=None):
    def log(s):
        if on_progress:on_progress(s)
    try:
        import mediapipe as mp
        log('检测到 MediaPipe '+str(mp.__version__))
    except ImportError:
        log('正在安装 MediaPipe Python 组件（只在点击后执行）…')
        cp=subprocess.run([sys.executable,'-m','pip','install','mediapipe>=1.1.1,<1.2'],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',timeout=240)
        if cp.returncode:raise RuntimeError('MediaPipe 安装失败：'+cp.stdout[-650:])
    if 包含定位资源():
        log('手部定位资源已安装，无须重复下载');return
    log('正在从 Google 官方存储下载约 8 MB 手部定位模型…')
    定位资源.parent.mkdir(parents=True,exist_ok=True)
    tmp=定位资源.with_suffix('.download')
    try:
        size=0
        with urllib.request.urlopen(urllib.request.Request(MODEL_URL,headers={'User-Agent':'GestureStudio/2.3.0'}),timeout=45) as response, tmp.open('wb') as f:
            while chunk:=response.read(256*1024):
                size+=len(chunk)
                if size>MAX_SIZE:raise ValueError('手部定位模型下载超过预期上限')
                f.write(chunk)
        if size<1_000_000 or not zipfile.is_zipfile(tmp):raise ValueError('下载内容不是有效的手部定位 .task 模型')
        os.replace(tmp,定位资源)
        log('手部定位组件已安装，开启手部裁剪训练后才会生效')
    finally:tmp.unlink(missing_ok=True)
