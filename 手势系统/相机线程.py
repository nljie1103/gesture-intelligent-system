"""v2.0.0: camera read, inference and candidate search away from Qt GUI thread."""
from __future__ import annotations
import sys
import time
import threading
import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from .预处理 import 获取识别矩形
from .手部候选框 import 搜索候选手框,候选框平滑器


class CameraWorker(QThread):
    frame_ready=Signal(QImage, object)
    camera_state=Signal(bool, str)

    def __init__(self, camera_id:int, interval_ms:int, roi:float, infer=None, capture_mode=False, draw_candidate=True, parent=None):
        super().__init__(parent)
        self.camera_id=int(camera_id)
        self.interval_ms=max(20,int(interval_ms))
        self.roi=roi
        self.infer=infer
        self.capture_mode=capture_mode
        self.draw_candidate=draw_candidate
        self.recognizing=False
        self.preview_enabled=True
        self._ack=threading.Event();self._ack.set()

    def acknowledge(self):self._ack.set()

    def run(self):
        cam=None
        try:
            backends=[cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_ANY] if sys.platform=='win32' else [cv2.CAP_ANY]
            for backend in backends:
                if self.isInterruptionRequested():return
                candidate=cv2.VideoCapture(self.camera_id,backend)
                if candidate.isOpened() and candidate.read()[0]:
                    cam=candidate;break
                candidate.release()
            if cam is None:
                self.camera_state.emit(False,'摄像头不可用；请检查 VMware 映射或占用')
                return
            cam.set(cv2.CAP_PROP_FRAME_WIDTH,640)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
            self.camera_state.emit(True,'摄像头已连接')
            smoother=候选框平滑器()
            while not self.isInterruptionRequested():
                started=time.monotonic()
                ok,frame=cam.read()
                if not ok:
                    self.camera_state.emit(False,'摄像头读取失败，请检查连接')
                    break
                if not self._ack.is_set() or (not self.preview_enabled and not self.capture_mode):
                    QThread.msleep(30 if not self.preview_enabled else 5)
                    continue
                frame=cv2.flip(frame,1)
                result=None;detected=None
                try:
                    if self.recognizing and self.infer is not None:
                        result=self.infer.预测(frame)
                        detected=result['有效类别']
                    x,y,x2,y2=获取识别矩形(frame,self.roi)
                    if self.capture_mode or self.recognizing:
                        cv2.rectangle(frame,(x,y),(x2,y2),(45,207,114) if self.capture_mode else (231,160,54),2)
                    if self.draw_candidate and self.recognizing and detected and detected!='无手':
                        candidate=smoother.更新(搜索候选手框(frame,self.roi))
                        if candidate:
                            a,b,c,d=candidate
                            cv2.rectangle(frame,(a,b),(c,d),(55,67,239),3)
                    else:smoother.重置()
                    raw=frame.copy() if self.capture_mode else None
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    h,w=rgb.shape[:2]
                    qimg=QImage(rgb.data,w,h,rgb.strides[0],QImage.Format.Format_RGB888).copy()
                    if self._ack.is_set():
                        self._ack.clear()
                        self.frame_ready.emit(qimg,{'inference':result,'raw_frame':raw,'t':time.monotonic()})
                except (ValueError,RuntimeError,OSError) as exc:
                    self.camera_state.emit(False,'摄像头处理失败：'+str(exc)[:140])
                    break
                elapsed=(time.monotonic()-started)*1000
                if elapsed<self.interval_ms:
                    QThread.msleep(max(1,round(self.interval_ms-elapsed)))
        finally:
            if cam is not None:cam.release()
