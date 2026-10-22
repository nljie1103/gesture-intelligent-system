"""手动下载公开训练数据的后台线程；不会在导入模块时联网。"""
from __future__ import annotations
import threading
from PySide6.QtCore import QThread, Signal
from .公开资源下载 import 下载并导入
from .配置 import 数据目录
from .公开数据 import 导入公开子集

class PublicImportWorker(QThread):
    progress=Signal(int)
    success=Signal(object)
    failed=Signal(str)
    def __init__(self,parent=None,local_zip=None):
        super().__init__(parent)
        self.local_zip=local_zip
        self.cancel=threading.Event()
    def run(self):
        try:
            if self.local_zip:
                result=导入公开子集(self.local_zip,每类最多=100,数据根目录=数据目录)
            else:
                result=下载并导入(数据目录,回报=lambda n:self.progress.emit(n),取消=self.cancel.is_set)
            self.success.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
    def request_cancel(self):self.cancel.set()
