import ast
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from 手势系统.工作台数据 import 场景明细, 回收本地场景, 回收整个场景
from 手势系统.配置 import 类别
from 手势系统.训练状态 import 训练记录状态, 文件哈希
import json

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'手势系统/现代界面.py').read_text(encoding='utf-8')
AST=ast.parse(UI)

def get_method(name):
    c=next(x for x in AST.body if isinstance(x,ast.ClassDef) and x.name=='GestureWindow')
    m=next(x for x in c.body if isinstance(x,ast.FunctionDef) and x.name==name)
    return ast.get_source_segment(UI,m)

class UIV16Tests(unittest.TestCase):
    def test_圆点为独立绘制不使用普通按钮样式(self):
        self.assertIn('class TrafficLight(QAbstractButton)',UI)
        self.assertIn('p.drawEllipse(QRectF(3,3,14,14))',UI)
        self.assertNotIn("b=QPushButton('');b.setFixedSize(15,15)",UI)
    def test_窗口原生裁剪覆盖物理四角(self):
        src=get_method('_set_native_corner_region')
        self.assertIn('CreateRoundRectRgn',src)
        self.assertIn('SetWindowRgn',src)
        self.assertIn('GetDpiForWindow',src)
        self.assertIn('GetWindowRect',src)
        self.assertNotIn('QSizeGrip(self)',UI)
    def test_数据和训练分栏职责(self):
        data=get_method('make_data');train=get_method('make_train')
        self.assertIn('self.capture',data)
        self.assertIn('self.batch_table',data)
        self.assertIn('self.clear_scene',data)
        self.assertNotIn('self.capture',train)
        self.assertIn('self.start_training',train)
    def test_单场景选定校验(self):
        start=get_method('start_training')
        self.assertIn('missing=[c for c in 类别',start)
        self.assertIn('combined[focus]==0',start)
        self.assertIn('sessions=all_scenes',start)
    def test_场景矩阵和单手势回收不影响其它类别(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for c in 类别:
                f=root/c/'场景01';f.mkdir(parents=True)
                Image.new('RGB',(8,8)).save(f/'one.jpg')
            matrix=场景明细(root)
            self.assertEqual(len(matrix),1)
            self.assertEqual(matrix[0]['合计'],6)
            removed=回收本地场景(类别[0],'场景01',root)
            self.assertTrue(removed.is_dir())
            self.assertEqual(场景明细(root)[0]['合计'],5)
            self.assertTrue((root/类别[1]/'场景01'/'one.jpg').exists())
            all_deleted=回收整个场景('场景01',root)
            self.assertEqual(all_deleted['回收类别数'],5)
            self.assertFalse(场景明细(root))
            self.assertTrue((root/'回收站').exists())
    def test_公开数据绝不移动(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            pub=root/'公开训练'/类别[0];pub.mkdir(parents=True)
            Image.new('RGB',(8,8)).save(pub/'pub.jpg')
            with self.assertRaises(FileNotFoundError):回收整个场景('场景01',root)
            self.assertTrue((pub/'pub.jpg').is_file())
    def test_来源未知不伪造已训练(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);model=root/'m.pt';info=root/'status.json'
            self.assertEqual(训练记录状态(model,info)['状态'],'未训练')
            model.write_bytes(b'existing weights')
            self.assertTrue(all(v=='来源未记录' for v in 训练记录状态(model,info)['类别'].values()))
            rec={'模型SHA256':文件哈希(model),'各类样本数量':{c:1 for c in 类别},'场景':['场景01']}
            info.write_text(json.dumps(rec,ensure_ascii=False),encoding='utf-8')
            status=训练记录状态(model,info)
            self.assertTrue(all(v=='已训练' for v in status['类别'].values()))
            model.write_bytes(b'model changed')
            self.assertNotEqual(训练记录状态(model,info)['状态'],'已记录')
    def test_路径穿越无法回收(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for bad in ('..','../x','公开训练'):
                with self.assertRaises(ValueError):回收整个场景(bad,root)

if __name__=='__main__':unittest.main()
