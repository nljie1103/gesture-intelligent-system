"""公开数据手动下载/导入，QThread 异步更新进度和阶段。"""
from __future__ import annotations
import threading
from PySide6.QtCore import QThread,Signal
from .公开资源下载 import 下载并导入
from .配置 import 数据目录
from .公开数据 import 导入公开子集

class PublicImportWorker(QThread):
    progress=Signal(int,int)
    phase=Signal(str)
    success=Signal(object)
    failed=Signal(str)
    def __init__(self,parent=None,local_zip=None):
        super().__init__(parent)
        self.local_zip=local_zip
        self.cancel=threading.Event()
    def run(self):
        try:
            if self.local_zip:
                self.phase.emit('正在核验本地 ZIP、裁剪并导入公开数据')
                result=导入公开子集(self.local_zip,每类最多=100,数据根目录=数据目录)
            else:
                result=下载并导入(数据目录,回报=lambda n,t:self.progress.emit(n,t),
                                     取消=self.cancel.is_set,阶段=self.phase.emit)
            self.success.emit(result)
        except Exception as e:self.failed.emit(str(e))
    def request_cancel(self):self.cancel.set()
