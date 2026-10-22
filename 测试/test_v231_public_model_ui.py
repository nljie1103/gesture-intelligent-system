"""v2.3.1 公开数据状态、残留回收和 UI 阈值回归。"""
from __future__ import annotations
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from 手势系统.公开数据管理 import 公开数据状态,回收公开数据,五类
from 手势系统.公开资源下载 import 下载并导入

ROOT=Path(__file__).resolve().parents[1]

class DatasetStateTest(unittest.TestCase):
    def test_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(公开数据状态(d)['状态'],'未安装')
            self.assertIsNone(回收公开数据(d))
    def test_manifest_only_is_residue_and_can_recover(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'公开数据清单.json').write_text('{}',encoding='utf-8')
            self.assertEqual(公开数据状态(root)['状态'],'残留或不完整')
            saved=回收公开数据(root)
            self.assertTrue((saved/'公开数据清单.json').is_file())
            self.assertEqual(公开数据状态(root)['状态'],'未安装')
    def test_old_dataset_with_five_classes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'公开训练'
            manifest={'样本':{}}
            for c in 五类:
                dest=folder/c;dest.mkdir(parents=True)
                Image.new('RGB',(64,64),'yellow').save(dest/'0000.jpg')
                manifest['样本'][c]=[{'路径':f'公开训练/{c}/0000.jpg'}]
            (root/'公开数据清单.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
            self.assertEqual(公开数据状态(root)['状态'],'已安装')
            self.assertEqual(公开数据状态(root)['合计'],5)
            recycle=回收公开数据(root)
            self.assertTrue((recycle/'公开训练'/五类[0]/'0000.jpg').is_file())
            self.assertEqual(公开数据状态(root)['状态'],'未安装')
    def test_private_data_left_intact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            original=root/'张开手掌'/'场景01'/'myself.jpg';original.parent.mkdir(parents=True)
            original.write_bytes(b'private photo')
            (root/'公开数据清单.json').write_text('old marker')
            回收公开数据(root)
            self.assertEqual(original.read_bytes(),b'private photo')
    def test_no_download_when_broken_state(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'公开数据清单.json').write_text('{}')
            with self.assertRaisesRegex(FileExistsError,'残留或不完整'):
                下载并导入(root,下载函数=lambda _:self.fail('should not download'))
    def test_symlink_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);outside=root/'other';outside.mkdir()
            link=root/'公开训练'
            try:link.symlink_to(outside,target_is_directory=True)
            except (OSError,NotImplementedError):self.skipTest('no symlink')
            with self.assertRaisesRegex(ValueError,'符号链接'):回收公开数据(root)
            self.assertTrue(outside.is_dir())

class UIBindingsTest(unittest.TestCase):
    def test_distinguishes_rejection_from_nohand(self):
        src=(ROOT/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        ast.parse(src)
        self.assertIn("'未达阈值'",src)
        self.assertIn("'无手'",src)
        self.assertIn('def refresh_public_state',src)
        self.assertIn('def delete_public',src)
        self.assertIn('self.public_progress=QProgressBar()',src)
        self.assertIn('self.hand_setup_progress=QProgressBar()',src)
    def test_inference_threshold(self):
        src=(ROOT/'手势系统'/'推理.py').read_text(encoding='utf-8')
        self.assertIn('self.阈值 = .60',src)
        self.assertIn("if 配置['最小置信度'] is not None",src)
    def test_gui_can_init_before_train_proc(self):
        src=(ROOT/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        self.assertIn("getattr(self,'proc',None)",src)
    def test_worker_progress_types(self):
        src=(ROOT/'手势系统'/'公开资源线程.py').read_text(encoding='utf-8')
        self.assertIn('progress=Signal(int,int)',src)
        self.assertIn('phase=Signal(str)',src)

if __name__=='__main__':unittest.main()
