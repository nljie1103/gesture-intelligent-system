"""v2.1.0: Version single-source and clean-main regression."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from 手势系统 import __version__
from 手势系统.版本 import VERSION,DISPLAY_VERSION,SHORT_VERSION,APP_TITLE
import 手势系统.配置 as config

ROOT=Path(__file__).resolve().parents[1]

class 版本与仓库整洁测试(unittest.TestCase):
    def test_版本常量对齐所有展示(self):
        self.assertEqual(__version__,VERSION)
        self.assertRegex(VERSION,r'^\d+\.\d+\.\d+$')
        self.assertEqual(DISPLAY_VERSION,'v'+VERSION)
        self.assertEqual(SHORT_VERSION,'.'.join(VERSION.split('.')[:2]))
        self.assertIn(DISPLAY_VERSION,APP_TITLE)
        self.assertTrue((ROOT/'版本.txt').read_text('utf-8').startswith(DISPLAY_VERSION))

    def test_实际Qt窗口与标题栏不再硬编码旧版本(self):
        source=(ROOT/'手势系统/现代界面.py').read_text('utf-8')
        self.assertIn('self.setWindowTitle(APP_TITLE)',source)
        self.assertIn('label(DISPLAY_VERSION,dim=True)',source)
        self.assertIn("'版本':VERSION",source)
        self.assertNotIn('v1.7.0',source)
        self.assertNotIn('v2.0.0',source)
        self.assertEqual(source.count('label(DISPLAY_VERSION,dim=True)'),2)

    def test_旧本地配置不篡改其他设置(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'设置.json'
            data={'版本':'1.1.0','摄像头编号':3,'触发冷却秒数':1.5,'用户备注':'自己的配置'}
            raw=json.dumps(data,ensure_ascii=False)
            f.write_text(raw,encoding='utf-8')
            with patch.object(config,'配置文件',f): loaded=config.读取配置()
            self.assertEqual(loaded['版本'],VERSION)
            self.assertEqual(loaded['摄像头编号'],3)
            self.assertEqual(loaded['用户备注'],'自己的配置')
            self.assertEqual(f.read_text('utf-8'),raw)

    def test_配置示例与主版本对齐(self):
        sample=json.loads((ROOT/'设置.example.json').read_text('utf-8'))
        self.assertEqual(sample['版本'],VERSION)
        self.assertIn('/设置.json',(ROOT/'.gitignore').read_text('utf-8'))
        self.assertIn('from 手势系统.版本 import DISPLAY_VERSION',(ROOT/'工具/首次安装.ps1').read_text('utf-8-sig'))
        # Existing personal settings may remain locally even after untracking on GitHub.

    def test_过时界面退出当前版本(self):
        self.assertFalse((ROOT/'手势系统/玻璃界面.py').exists())
        self.assertFalse((ROOT/'手势系统/玻璃主题.py').exists())
        self.assertTrue((ROOT/'手势系统/现代界面.py').exists())

if __name__=='__main__':unittest.main()
