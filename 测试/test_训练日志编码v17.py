"""v1.7.0 日志乱码回归测试：不依赖摄像头、模型、Qt GUI 或 Windows 窗口。"""
import os
import random
import subprocess
import sys
import unittest
from pathlib import Path
from 手势系统.训练日志编码 import 训练日志解码器,配置训练子进程编码


class FakeProcessEnvironment:
    def __init__(self):self.values={}
    def insert(self,key,value):self.values[key]=value


class 日志编码测试(unittest.TestCase):
    def test_训练环境明确指定UTF8(self):
        fake=FakeProcessEnvironment()
        self.assertIs(配置训练子进程编码(fake),fake)
        self.assertEqual(fake.values['PYTHONIOENCODING'],'utf-8')
        self.assertEqual(fake.values['PYTHONUTF8'],'1')

    def test_每个字节独立到达仍无乱码(self):
        expected='[1/8] 读取有效样本：剪刀手、食指指向、无手 ✅\n训练准确率=78.4%（非测试）\n'
        dec=训练日志解码器()
        out=''.join(dec.输入(bytes([c])) for c in expected.encode('utf-8'))
        out+=dec.输入(b'',结束=True)
        self.assertEqual(out,expected)
        self.assertNotIn('\ufffd',out)

    def test_任意块边界正确拼接(self):
        s='开始训练：公开数据与场景01\n'+'[8/8] 模型已保存 ✨\n'
        raw=s.encode('utf-8')
        for seed in range(20):
            randomizer=random.Random(seed)
            dec=训练日志解码器();parts=[];i=0
            while i<len(raw):
                n=randomizer.randint(1,8);parts.append(dec.输入(raw[i:i+n]));i+=n
            parts.append(dec.输入(b'',结束=True))
            self.assertEqual(''.join(parts),s)

    def test_结束时只有真正残缺字符才替换(self):
        dec=训练日志解码器()
        self.assertEqual(dec.输入('指'.encode('utf-8')[:1]),'')
        self.assertEqual(dec.输入(b'',结束=True),'\ufffd')

    def test_每轮训练解码器彼此隔离(self):
        a,b=训练日志解码器(),训练日志解码器()
        data='剪刀手'.encode('utf-8')
        self.assertEqual(a.输入(data[:2]),'')
        self.assertEqual(b.输入(data,结束=True),'剪刀手')
        self.assertEqual(a.输入(data[2:],结束=True),'剪刀手')

    def test_训练子进程在默认非UTF8环境下仍输出UTF8(self):
        fake=FakeProcessEnvironment();配置训练子进程编码(fake)
        env=os.environ.copy();env['PYTHONIOENCODING']='cp936';env.update(fake.values)
        result=subprocess.run([sys.executable,'-u','-c',"import sys;print('训练中：点赞 剪刀手 ✅');print('结束：无手',file=sys.stderr)"],
                              env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20,check=True)
        # Windows 使用 CRLF，Unix 使用 LF；只校验 UTF-8 中文内容与两条日志均完整出现。
        self.assertCountEqual(result.stdout.decode('utf-8').splitlines(), ['训练中：点赞 剪刀手 ✅', '结束：无手'])

    def test_GUI真正接入编码和分块解码(self):
        ui=(Path(__file__).resolve().parent.parent/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        self.assertIn('配置训练子进程编码(process_env)',ui)
        self.assertIn('self.proc.setProcessEnvironment(process_env)',ui)
        self.assertIn('训练日志解码器()',ui)
        self.assertIn('self._train_log_decoder.输入(data,结束=final)',ui)
        self.assertIn('self.read_training(final=True)',ui)
        self.assertNotIn("self.proc.readAllStandardOutput()).decode('utf-8'",ui)


if __name__=='__main__':unittest.main()
