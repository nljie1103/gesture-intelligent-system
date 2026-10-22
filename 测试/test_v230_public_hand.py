"""v2.3.0 optional public import and hand-crop contracts; no network/Qt required."""
import ast
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from 手势系统.工作台数据 import 训练样本索引
from 手势系统.配置 import 类别
from 手势系统.公开资源下载 import 下载并导入
from 手势系统.手部定位 import 框到方形,读取训练输入策略,策略标识
from 手势系统.版本 import VERSION

ROOT=Path(__file__).resolve().parents[1]

class PublicDataControlTests(unittest.TestCase):
    def test_optional_public_defaults_off(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i,cls in enumerate(类别):
                dest=root/cls/'场景01';dest.mkdir(parents=True)
                Image.new('RGB',(64,64),color=(i*27,10,10)).save(dest/'one.jpg')
            pub=root/'公开训练'/类别[0];pub.mkdir(parents=True)
            Image.new('RGB',(64,64),'white').save(pub/'public.jpg')
            self.assertEqual(len(训练样本索引(['场景01'],root)),6)
            self.assertEqual(len(训练样本索引(['场景01'],root,include_public=True)),7)
    def test_checksum_fails_without_import(self):
        with tempfile.TemporaryDirectory() as d:
            class Source:
                def __init__(self):self.f=io.BytesIO(b'not the expected archive')
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self,n):return self.f.read(n)
            with self.assertRaisesRegex(ValueError,'SHA256'):
                下载并导入(d,下载函数=lambda url:Source())
            self.assertFalse(list(Path(d).glob('hagrid-download-*')))
            self.assertFalse((Path(d)/'公开训练').exists())
    def test_explicit_cancel_cleans_temp(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(InterruptedError):
                下载并导入(d,取消=lambda:True,下载函数=lambda _:None)
            self.assertEqual(list(Path(d).glob('hagrid-download-*')),[])
    def test_no_network_at_import(self):
        src=(ROOT/'手势系统/公开资源下载.py').read_text(encoding='utf-8')
        ast.parse(src)
        self.assertIn('def 下载并导入(',src)
        ui=(ROOT/'手势系统/现代界面.py').read_text(encoding='utf-8')
        self.assertIn('QCheckBox(\'本轮训练包含已手动导入',ui)
        self.assertIn('def download_public(self):',ui)
        self.assertIn('def import_public_zip(self):',ui)
        self.assertIn("if use_public:args+=['--include-public']",ui)

class HandCropTests(unittest.TestCase):
    def test_square_box_bounded(self):
        box=框到方形((30,40,90,135),640,480)
        x1,y1,x2,y2=box
        self.assertTrue(0<=x1<x2<=640)
        self.assertTrue(0<=y1<y2<=480)
        self.assertEqual(x2-x1,y2-y1)
    def test_invalid_boxes(self):
        self.assertIsNone(框到方形((2,2,1,1),640,480))
        self.assertIsNone(框到方形((2,2,20,20),0,480))
    def test_strategy_backward_compatible_and_fails_closed(self):
        self.assertEqual(读取训练输入策略({}),'fixed-roi-v1')
        self.assertEqual(读取训练输入策略({'输入策略':策略标识}),策略标识)
        with self.assertRaisesRegex(ValueError,'未知'):
            读取训练输入策略({'输入策略':'fake'})
    def test_train_and_infer_consistency(self):
        t=(ROOT/'手势系统/工作台训练.py').read_text('utf-8')
        i=(ROOT/'手势系统/推理.py').read_text('utf-8')
        self.assertIn("'输入策略':('hand-landmarker-v1' if hand_crop else 'fixed-roi-v1')",t)
        self.assertIn("self.输入策略=读取训练输入策略(self.元信息)",i)
        self.assertIn("from_scratch:bool=False",t)
        self.assertIn("and not from_scratch:",t)
        self.assertIn('marker=original.parent',t)
    def test_capture_avoids_labeled_nohand_with_visible_hand(self):
        ui=(ROOT/'手势系统/现代界面.py').read_text('utf-8')
        self.assertIn("gesture=='无手' and hand_box is not None",ui)
        self.assertIn("gesture!='无手' and hand_box is None",ui)
    def test_version(self):
        self.assertEqual(VERSION,'2.3.2')

if __name__=='__main__':unittest.main()
