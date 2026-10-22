"""手部组件分阶段安装：运行中的 GUI 只下载，不修改它已加载的 OpenCV DLL。

点击安装由 GUI 工作线程下载所有轮子和模型；主窗口退出后，独立进程进行 pip 安装。
"""
from __future__ import annotations
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from collections import deque
from pathlib import Path
from .配置 import 根目录
from .手部定位 import 定位资源, 包含定位资源

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
MAX_SIZE = 16 * 1024 * 1024
WHEEL_DIR = 根目录 / '.发布' / '手部组件依赖缓存-v2.3.2'
MEDIA_PIPE_REQUIREMENT = 'mediapipe>=1.1.1,<1.2'
OPENCV_REQUIREMENT = 'opencv-contrib-python>=4.11,<5.0'
FALLBACK_CV_REQUIREMENT = 'opencv-python>=4.10,<5.0'


def _dependencies_available():
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as _tasks
        return bool(mp.__version__)
    except Exception:
        # A previous interrupted pip install can raise more than ImportError.
        return False


def _run_download(command, log, timeout=720):
    proc = subprocess.Popen(command, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1,
        env={**os.environ, 'PYTHONUTF8':'1', 'PYTHONUNBUFFERED':'1'})
    q = queue.Queue()
    def pump():
        try:
            for line in proc.stdout: q.put(line)
        finally: q.put(None)
    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    start = time.monotonic()
    tail = deque(maxlen=24)
    try:
        while True:
            if time.monotonic() - start > timeout:
                raise TimeoutError('下载安装包超过 12 分钟，请检查网络或代理')
            try: line=q.get(timeout=.5)
            except queue.Empty: continue
            if line is None: break
            line = line.strip()
            if line:
                tail.append(line)
                log(line[:300])
        rc=proc.wait(timeout=30)
        if rc:
            raise RuntimeError('pip 下载失败（退出码 '+str(rc)+'）：\n'+'\n'.join(tail)[-1800:])
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait()


def 安装(on_progress=None, on_bytes=None, on_stage=None):
    """准备离线安装包；返回 True 表示必须在关闭软件后安装 Python 依赖。"""
    log = on_progress or (lambda message: None)
    stage = on_stage or (lambda message: None)
    need_pip = not _dependencies_available()
    if need_pip:
        WHEEL_DIR.mkdir(parents=True, exist_ok=True)
        stage('下载并缓存 Python 依赖（安装将在软件退出后进行）')
        log('只下载，不修改运行中的 OpenCV 文件。下载大小由 pip 实时日志显示。')
        # Keep version 4.x: Gesture Studio is tested with OpenCV >=4.10,<5.
        _run_download([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
            '--dest', str(WHEEL_DIR), MEDIA_PIPE_REQUIREMENT, OPENCV_REQUIREMENT], log)
        # Also cache a working original OpenCV for failure recovery.
        stage('缓存 OpenCV 恢复包')
        _run_download([sys.executable, '-m', 'pip', 'download', '--no-deps',
            '--only-binary=:all:', '--dest', str(WHEEL_DIR), FALLBACK_CV_REQUIREMENT], log)
        log('Python 依赖已下载。安装会在本软件完全关闭后自动执行。')
    else:
        log('MediaPipe Python 依赖已安装，检查模型文件…')
    if not 包含定位资源():
        stage('下载手部关键点定位模型')
        定位资源.parent.mkdir(parents=True, exist_ok=True)
        temporary=定位资源.with_suffix('.download')
        try:
            total_bytes=0
            request=urllib.request.Request(MODEL_URL, headers={'User-Agent':'GestureStudio/2.3.2'})
            with urllib.request.urlopen(request, timeout=45) as resp, temporary.open('wb') as f:
                try: total=int(resp.headers.get('Content-Length','0'))
                except ValueError: total=0
                if total > MAX_SIZE: raise ValueError('模型文件大于允许大小')
                while True:
                    part=resp.read(256*1024)
                    if not part: break
                    total_bytes+=len(part)
                    if total_bytes>MAX_SIZE: raise ValueError('模型超过预期上限')
                    f.write(part)
                    if on_bytes: on_bytes(total_bytes,total)
            if total_bytes<1_000_000 or not zipfile.is_zipfile(temporary):
                raise ValueError('下载内容不是有效的 Hand Landmarker .task 模型')
            os.replace(temporary, 定位资源)
        finally:
            temporary.unlink(missing_ok=True)
    if need_pip:
        stage('下载完成 · 退出后安装 Python 组件')
    else:
        stage('已安装')
    return need_pip
