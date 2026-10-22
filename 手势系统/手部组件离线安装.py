"""运行在独立 Python 进程中的 Windows 离线安装器。

本进程不能从运行中的 Gesture Studio 导入或使用 cv2。
等待父进程退出后才允许修改 venv 下的 cv2.pyd。
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


def wait_for_parent(pid:int, timeout_ms=180000):
    if not pid or pid==os.getpid():raise RuntimeError('无效的父进程编号')
    if os.name=='nt':
        import ctypes
        kernel=ctypes.windll.kernel32
        kernel.OpenProcess.argtypes=(ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=(ctypes.c_void_p,ctypes.c_ulong)
        kernel.WaitForSingleObject.restype=ctypes.c_ulong
        kernel.CloseHandle.argtypes=(ctypes.c_void_p,)
        handle=kernel.OpenProcess(0x00100000, False, pid)
        if handle:
            try:
                status=kernel.WaitForSingleObject(handle,timeout_ms)
                if status!=0:raise TimeoutError('主程序关闭超时或进程等待失败：'+str(status))
            finally:kernel.CloseHandle(handle)
    else:
        import time
        for _ in range(int(timeout_ms/1000)):
            try:os.kill(pid,0)
            except ProcessLookupError:break
            time.sleep(1)
        else:raise TimeoutError('主程序未退出')
    time.sleep(1.0)  # Allow Windows to release DLL handles.


def run_pip(args, log):
    cmd=[sys.executable, '-m', 'pip', *args]
    log('执行：python -m pip '+' '.join(args))
    process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1'})
    for line in process.stdout:log(line.rstrip())
    result=process.wait(timeout=360)
    if result:raise RuntimeError('pip 退出码：'+str(result))


def install_offline(folder:Path, log):
    if not folder.is_dir() or not list(folder.glob('*.whl')):
        raise FileNotFoundError('依赖缓存不存在或为空：'+str(folder))
    base=['--no-index', '--find-links',str(folder),'--only-binary=:all:']
    # OpenCV variants share the same cv2 package; ensure there is only one owner.
    run_pip(['uninstall','-y','opencv-python','opencv-python-headless','opencv-contrib-python-headless'], log)
    try:
        run_pip(['install',*base,'mediapipe>=1.1.1,<1.2','opencv-contrib-python>=4.11,<5.0'],log)
        import mediapipe
        import cv2
        from mediapipe.tasks import python as _tasks
        log('MediaPipe '+mediapipe.__version__+'；OpenCV '+cv2.__version__+' 已通过导入检查')
        return True
    except Exception:
        log('组件安装失败，尝试恢复可用的 OpenCV 4.x…')
        try:
            run_pip(['install','--force-reinstall','--no-deps',*base,'opencv-python>=4.10,<5.0'],log)
        except Exception as restore_exc:log('OpenCV 自动恢复失败：'+str(restore_exc))
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent-pid', type=int,required=True)
    parser.add_argument('--wheel-dir',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    logfile=args.root/'.发布'/'手部组件最近安装.log'
    logfile.parent.mkdir(parents=True,exist_ok=True)
    def log(message):
        message=str(message)
        print(message,flush=True)
        with logfile.open('a',encoding='utf-8') as out:out.write(message+'\n')
    result=0
    log('Gesture Studio 手部组件独立安装 · v2.3.2')
    try:
        log('等待主程序完全关闭，以解除 cv2.pyd 文件占用…')
        wait_for_parent(args.parent_pid)
        log('主程序已退出；开始安装，进度将在本窗口显示。')
        install_offline(args.wheel_dir,log)
        log('组件安装成功，准备重新启动 Gesture Studio。')
    except Exception:
        result=1
        log('安装失败：\n'+traceback.format_exc()[-4000:])
        log('完整日志：'+str(logfile))
    finally:
        marker=args.root/'.发布'/'手部组件安装状态.json'
        marker.write_text(json.dumps({'成功':result==0,'时间':time.strftime('%Y-%m-%d %H:%M:%S'),
                          '日志路径':str(logfile)},ensure_ascii=False,indent=2),encoding='utf-8')
        # Relaunch also after failure: the application still works in fixed ROI mode.
        launcher=args.root/'启动系统.py'
        if launcher.is_file():
            try:
                subprocess.Popen([sys.executable,str(launcher)],cwd=str(args.root),
                    creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
            except OSError as exc:log('无法自动重启软件：'+str(exc))
        time.sleep(2)
    return result


if __name__=='__main__':raise SystemExit(main())
