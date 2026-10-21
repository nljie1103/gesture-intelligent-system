"""v1.7.1: Windows 训练日志双向防乱码。

主路径强制子进程 UTF-8；兼容旧进程错误输出的 GBK/CP936。
每次训练独立建立解码器，能够处理 Qt 事件跨字节截断。
"""
from __future__ import annotations
import codecs
import sys


def 配置训练子进程编码(process_environment):
    """仅调整训练 QProcess 的环境变量，不修改操作系统全局设置。"""
    process_environment.insert('PYTHONIOENCODING', 'utf-8:backslashreplace')
    process_environment.insert('PYTHONUTF8', '1')
    process_environment.insert('PYTHONUNBUFFERED', '1')
    return process_environment


def 配置标准流UTF8(stdout=None, stderr=None):
    """由训练程序主入口主动执行，覆盖 Windows 重定向管道默认 CP936。"""
    for stream in (sys.stdout if stdout is None else stdout, sys.stderr if stderr is None else stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            reconfigure(encoding='utf-8', errors='backslashreplace', write_through=True)


class 训练日志解码器:
    """自动识别 UTF-8 与 GBK/CP936，并按流增量解码。

    优先使用 UTF-8。只有发现不符合 UTF-8 的字节时才回退 GBK。
    若开头只有 ASCII，可立即展示，不会影响后续判断。编码在首次
    中文字节判定后锁定，避免单次训练期间反复切换导致文字损坏。
    """
    def __init__(self):
        self._codec = None
        self._decoder = None
        self._pending = bytearray()
        self._done = False
        self.检测编码 = '等待首段中文'

    def _choose(self, name):
        self._codec = name
        self._decoder = codecs.getincrementaldecoder(name)(errors='replace')
        self.检测编码 = 'UTF-8' if name == 'utf-8' else 'GBK/CP936（兼容解码）'
        data = bytes(self._pending)
        self._pending.clear()
        return self._decoder.decode(data, final=False)

    def 输入(self, data: bytes, *, 结束: bool = False) -> str:
        if self._done:
            if data:raise RuntimeError('训练日志已结束，不能再输入数据')
            return ''
        if self._codec is not None:
            result = self._decoder.decode(data, final=结束)
        else:
            self._pending.extend(data)
            raw = bytes(self._pending)
            if not raw:
                result = ''
            elif raw.isascii():
                # ASCII 在 UTF-8 和 CP936 中一致；及时显示进度数字。
                result = raw.decode('ascii')
                self._pending.clear()
            else:
                probe = codecs.getincrementaldecoder('utf-8')(errors='strict')
                try:
                    decoded = probe.decode(raw, final=结束)
                except UnicodeDecodeError:
                    # GBK/CP936 输出不是损坏的 UTF-8，应正确读取两字节汉字。
                    # 单字节 CP936 最后还没到达时继续等待另一半。
                    gbk = codecs.getincrementaldecoder('gbk')(errors='strict')
                    try:
                        candidate = gbk.decode(raw, final=结束)
                    except UnicodeDecodeError:
                        # 短块异常先等待下一次；任务结束才输出可见替换标记。
                        if not 结束 and len(raw) < 4096:
                            result = ''
                        else:
                            result = self._choose('gbk')
                    else:
                        # 未读完的双字节汉字要等后续数据，避免误判。
                        if not 结束 and not candidate:
                            result = ''
                        else:
                            result = self._choose('gbk')
                else:
                    if decoded and any(ord(c) > 127 for c in decoded):
                        result = self._choose('utf-8')
                    elif 结束:
                        result = self._choose('utf-8')
                    else:
                        result = ''
            if 结束 and self._codec is not None:
                result += self._decoder.decode(b'', final=True)
            elif 结束 and self._pending:
                # 残缺字节仅在真正结束时才显示替代字符。
                result += bytes(self._pending).decode('utf-8', errors='replace')
                self._pending.clear()
        if 结束:self._done = True
        return result
