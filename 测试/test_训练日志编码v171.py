"""v1.7.1 旧 Windows CP936 中文及实际子进程混合读取回归。"""
from __future__ import annotations
import os
import random
import subprocess
import sys
import unittest
from pathlib import Path
from 手势系统.训练日志编码 import 训练日志解码器,配置标准流UTF8,配置训练子进程编码

PROJECT=Path(__file__).resolve().parent.parent
REPORT=("读取有效样本： {'张开手掌': 123, '握拳': 130, '点赞': 121, '剪刀手': 136, '食指指向': 129, '无手': 50}\n"
        "注意：当前训练不使用独立验证/测试集，不报告泛化准确率。\n"
        "[1/8] loss=1.5598 训练准确率=32.9%（非测试）\n"
        "训练成功：新正式模型已保存；旧模型已备份（如存在）。\n"
        "报告： C:\\Users\\jack\\Desktop\\niit\\计算机视觉\\基于手势识别的智能系统\\输出\\工作台训练_自检.json\n")


class StreamFake:
    def __init__(self):self.kwargs=[]
    def reconfigure(self,**kw):self.kwargs.append(kw)

class FakeQtEnv:
    def __init__(self):self.map={}
    def insert(self,k,v):self.map[k]=v

class Windows日志回归(unittest.TestCase):
    def test_用户日志样式GBK完整解码(self):
        raw=REPORT.encode('cp936')
        dec=训练日志解码器()
        result=dec.输入(raw,结束=True)
        self.assertEqual(result,REPORT)
        self.assertEqual(dec.检测编码,'GBK/CP936（兼容解码）')
        self.assertNotIn('�',result)

    def test_GBK任何单字节分块可恢复(self):
        raw=REPORT.encode('cp936')
        dec=训练日志解码器()
        got=''.join(dec.输入(bytes([b])) for b in raw)+dec.输入(b'',结束=True)
        self.assertEqual(got,REPORT)

    def test_UTF8任何单字节分块可恢复(self):
        raw=REPORT.encode('utf-8')
        dec=训练日志解码器()
        got=''.join(dec.输入(bytes([b])) for b in raw)+dec.输入(b'',结束=True)
        self.assertEqual(got,REPORT)

    def test_多种随机块尺寸UTF8和GBK(self):
        for enc in ('utf-8','gbk'):
            raw=REPORT.encode(enc)
            for seed in range(15):
                rand=random.Random(seed);dec=训练日志解码器();pieces=[];i=0
                while i<len(raw):
                    n=rand.randrange(1,23);pieces.append(dec.输入(raw[i:i+n]));i+=n
                pieces.append(dec.输入(b'',结束=True))
                self.assertEqual(''.join(pieces),REPORT,(enc,seed))

    def test_主动reconfigure标准流为UTF8(self):
        out=StreamFake();err=StreamFake()
        配置标准流UTF8(out,err)
        self.assertEqual(out.kwargs[0]['encoding'],'utf-8')
        self.assertEqual(err.kwargs[0]['encoding'],'utf-8')
        self.assertTrue(out.kwargs[0]['write_through'])

    def test_QProcess环境有三个编码保险(self):
        env=FakeQtEnv();配置训练子进程编码(env)
        self.assertEqual(env.map['PYTHONIOENCODING'],'utf-8:backslashreplace')
        self.assertEqual(env.map['PYTHONUTF8'],'1')
        self.assertEqual(env.map['PYTHONUNBUFFERED'],'1')

    def test_子进程强行使用CP936仍自行输出UTF8(self):
        env={**os.environ,'PYTHONIOENCODING':'cp936','PYTHONUTF8':'0'}
        p=subprocess.run([sys.executable,'-u','-m','手势系统.训练日志自检'],cwd=PROJECT,
                         env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20,check=True)
        text=p.stdout.decode('utf-8')
        for phrase in ('读取有效样本','剪刀手','食指指向','训练准确率','中文目录','标准错误中文提示'):
            self.assertIn(phrase,text)
        self.assertNotIn('�',text)
        self.assertNotIn('模型已保存',text)

    def test_中文自检不触碰模型目录(self):
        from 手势系统 import 训练日志自检
        source=Path(训练日志自检.__file__).read_text(encoding='utf-8')
        self.assertNotIn('torch',source)
        self.assertNotIn('os.replace',source)
        self.assertNotIn('torch.save',source)

    def test_UI自检与真实训练共用同一日志读取(self):
        source=(PROJECT/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        self.assertIn("'-X','utf8','-u','-m','手势系统.工作台训练'",source)
        self.assertIn("'-X','utf8','-u','-m','手势系统.训练日志自检'",source)
        self.assertEqual(source.count('self.proc.start(sys.executable,args)'),1)
        self.assertIn('self._train_log_plain+=text',source)
        self.assertIn('self.train_selftest=btn',source)

    def test_真实训练入口主动配置编码(self):
        source=(PROJECT/'手势系统'/'工作台训练.py').read_text(encoding='utf-8')
        self.assertIn("if __name__=='__main__':\n    配置标准流UTF8()\n    main()",source)


if __name__=='__main__':unittest.main()
