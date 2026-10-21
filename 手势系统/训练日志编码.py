"""训练日志的可靠 Unicode 管道：仅调整训练子进程编码，保留跨读取分块的 UTF-8 状态。"""
from __future__ import annotations
import codecs


class 训练日志解码器:
    """QProcess 管道分块可能截断多字节字符；独立实例只服务于一次训练任务。"""
    def __init__(self):
        self._decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
        self._done=False

    def 输入(self, data: bytes, *, 结束: bool=False) -> str:
        if self._done:
            if data:raise RuntimeError('已结束的日志解码器不可重复输入')
            return ''
        result=self._decoder.decode(data,final=结束)
        if 结束:self._done=True
        return result


def 配置训练子进程编码(process_environment):
    """只作用于 QProcess 的环境，不更改宿主 Qt 或其他应用的系统环境。"""
    process_environment.insert('PYTHONIOENCODING','utf-8')
    process_environment.insert('PYTHONUTF8','1')
    return process_environment
