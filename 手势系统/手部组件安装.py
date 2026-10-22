"""可选手部组件：只在用户明确触发时联网。流式显示 pip 阶段、模型下载字节与错误。"""
from __future__ import annotations
import os
import queue
import threading
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections import deque
from .手部定位 import 定位资源,包含定位资源

MODEL_URL='https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
MAX_SIZE=16*1024*1024

def 安装(on_progress=None,on_bytes=None,on_stage=None):
    def log(s):
        if on_progress:on_progress(s)
    def stage(s):
        if on_stage:on_stage(s)
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as _mp_tasks
        log('检测到 MediaPipe '+str(mp.__version__)+'，无需重新安装依赖')
    except (ImportError,AttributeError):
        stage('pip 安装依赖（下载量未知，显示运行状态）')
        cmd=[sys.executable,'-m','pip','install','--only-binary=:all:','mediapipe>=1.1.1,<1.2']
        log('正在安装 MediaPipe：使用项目虚拟环境中的 Python '+sys.executable)
        process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 text=True,encoding='utf-8',errors='replace',bufsize=1)
        last=deque(maxlen=35)
        q=queue.Queue()
        def collect():
            try:
                for line in process.stdout:q.put(line)
            finally:q.put(None)
        reader=threading.Thread(target=collect,daemon=True)
        reader.start()
        start=time.monotonic();done=False
        try:
            while not done:
                if time.monotonic()-start>360:
                    raise TimeoutError('pip 安装超过 6 分钟（含网络等待）；请检查网络或依赖日志')
                try:line=q.get(timeout=.5)
                except queue.Empty:continue
                if line is None:done=True;continue
                line=line.strip()
                if line:
                    last.append(line)
                    log(line[:260])
            status=process.wait(timeout=15)
            if status!=0:raise RuntimeError('pip 返回码 '+str(status)+'：\n'+'\n'.join(last)[-2000:])
        finally:
            if process.poll() is None:process.kill();process.wait()
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as _mp_tasks
        except Exception as exc:raise RuntimeError('pip 已结束，但 MediaPipe Tasks 仍无法导入：'+str(exc)) from exc
        log('MediaPipe 已安装：'+str(mp.__version__))
    if 包含定位资源():
        stage('已安装')
        log('手部定位资源已存在，无须重复下载')
        return
    stage('下载手部定位模型')
    log('从 Google 官方存储下载手部定位模型…')
    定位资源.parent.mkdir(parents=True,exist_ok=True)
    tmp=定位资源.with_suffix('.download')
    try:
        size=0
        with urllib.request.urlopen(urllib.request.Request(MODEL_URL,headers={'User-Agent':'GestureStudio/2.3.1'}),timeout=45) as response,tmp.open('wb') as f:
            try:total=int(response.headers.get('Content-Length','0'))
            except ValueError:total=0
            if total>MAX_SIZE:raise ValueError('模型文件大于允许大小')
            while True:
                chunk=response.read(256*1024)
                if not chunk:break
                size+=len(chunk)
                if size>MAX_SIZE:raise ValueError('手部定位模型下载超过预期上限')
                f.write(chunk)
                if on_bytes:on_bytes(size,total)
        stage('正在核验手部定位模型')
        if size<1_000_000 or not zipfile.is_zipfile(tmp):raise ValueError('下载内容不是有效的手部定位 .task 模型')
        os.replace(tmp,定位资源)
        stage('已安装')
        log('手部定位组件已安装；启用手部裁剪需使用对应模式重新训练')
    finally:tmp.unlink(missing_ok=True)
