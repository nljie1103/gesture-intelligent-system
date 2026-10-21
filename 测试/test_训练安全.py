"""2.0.0 behavioral regression tests (no camera/Qt required)."""
from __future__ import annotations
import ast
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from 手势系统.工作台数据 import 文件图片可读,创建训练快照,导入图片
from 手势系统.模型发布 import 发布模型与来源,恢复中断发布,TXN_NAME
from 手势系统.配置 import 类别
from 手势系统.控制 import 手势控制器
from 手势系统.训练状态 import 文件哈希

BASE=Path(__file__).resolve().parents[1]


class 模型发布回归(unittest.TestCase):
    def prepare(self,folder):
        root=Path(folder)
        (root/'正式模型.pt').write_bytes(b'old model')
        (root/'训练来源.json').write_text('old record',encoding='utf-8')
        (root/'运行阈值.json').write_text('old threshold',encoding='utf-8')
        staged=root/'new.pt';staged.write_bytes(b'new model')
        rec=root/'new.json';rec.write_text('new record',encoding='utf-8')
        return root,staged,rec

    def test_成功提交删除过期阈值(self):
        with tempfile.TemporaryDirectory() as t:
            root,staged,rec=self.prepare(t)
            发布模型与来源(root,staged,rec)
            self.assertEqual((root/'正式模型.pt').read_bytes(),b'new model')
            self.assertEqual((root/'训练来源.json').read_text(), 'new record')
            self.assertFalse((root/'运行阈值.json').exists())
            self.assertFalse((root/TXN_NAME).exists())

    def test_第二个文件写入失败恢复所有旧文件(self):
        with tempfile.TemporaryDirectory() as t:
            root,staged,rec=self.prepare(t)
            original=os.replace;state={'failed':False}
            def fault(src,dst):
                if Path(src)==rec and not state['failed']:
                    state['failed']=True
                    raise OSError('simulated disk write error')
                return original(src,dst)
            with patch('手势系统.模型发布.os.replace',side_effect=fault):
                with self.assertRaisesRegex(OSError,'simulated'):发布模型与来源(root,staged,rec)
            self.assertEqual((root/'正式模型.pt').read_bytes(),b'old model')
            self.assertEqual((root/'训练来源.json').read_text(), 'old record')
            self.assertEqual((root/'运行阈值.json').read_text(), 'old threshold')
            self.assertFalse((root/TXN_NAME).exists())

    def test_断电后带事务记录可恢复(self):
        with tempfile.TemporaryDirectory() as t:
            root,_,_=self.prepare(t)
            tx=root/TXN_NAME;tx.mkdir()
            for name in ('正式模型.pt','训练来源.json','运行阈值.json'):
                (tx/name).write_bytes((root/name).read_bytes())
            (tx/'journal.json').write_text(json.dumps({'state':'pending','original':{
                '正式模型.pt':True,'训练来源.json':True,'运行阈值.json':True}}),encoding='utf-8')
            (root/'正式模型.pt').write_bytes(b'half-committed')
            (root/'训练来源.json').unlink()
            self.assertTrue(恢复中断发布(root))
            self.assertEqual((root/'正式模型.pt').read_bytes(),b'old model')
            self.assertEqual((root/'训练来源.json').read_text(),'old record')
            self.assertFalse(tx.exists())

    def test_仅准备中或空事务无需还原旧文件(self):
        with tempfile.TemporaryDirectory() as t:
            root,_,_=self.prepare(t)
            tx=root/TXN_NAME;tx.mkdir()
            self.assertTrue(恢复中断发布(root))
            self.assertEqual((root/'正式模型.pt').read_bytes(),b'old model')

    def test_旧阈值和新模型不应匹配(self):
        import 手势系统.推理 as inference
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);model=root/'正式模型.pt';model.write_bytes(b'new weight bytes')
            (root/'运行阈值.json').write_text(json.dumps({'置信度阈值':.61,'模型SHA256':'outdated'}))
            with patch.object(inference,'读取配置',return_value={'识别区域占画面短边比例':.78,'最小置信度':None}),\
                 patch.object(inference,'加载分类模型',return_value=(object(),96,{})):
                self.assertAlmostEqual(inference.手势推理器(model).阈值,.85)
                (root/'运行阈值.json').write_text(json.dumps({'置信度阈值':.61,'模型SHA256':文件哈希(model)}))
                self.assertAlmostEqual(inference.手势推理器(model).阈值,.61)


class 数据与控制回归(unittest.TestCase):
    def test_异常图片不会使导入崩溃(self):
        with tempfile.TemporaryDirectory() as t:
            fake=Path(t)/'bomb.png'
            # Small but malicious PNG dimensions. Pillow raises DecompressionBombError.
            import struct,zlib
            header=b'\x89PNG\r\n\x1a\n'
            payload=struct.pack('>IIBBBBB',20000,20000,8,2,0,0,0)
            chunk=b'IHDR'+payload
            fake.write_bytes(header+struct.pack('>I',len(payload))+chunk+struct.pack('>I',zlib.crc32(chunk)))
            self.assertFalse(文件图片可读(fake))
            data=Path(t)/'data'
            result=导入图片([fake],类别[0],'场景01',data)
            self.assertEqual(result['无效'],1)

    def test_训练快照被删除原图后仍能读取(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'data';shot=Path(t)/'snapshot'
            path=root/类别[0]/'场景01'/'one.png';path.parent.mkdir(parents=True)
            Image.new('RGB',(64,64),'blue').save(path)
            index=[(f'{类别[0]}/场景01/one.png',0)]
            self.assertEqual(创建训练快照(index,root,shot),index)
            path.unlink()
            with Image.open(shot/index[0][0]) as img:self.assertEqual(img.size,(64,64))

    def test_单独控制器暂停后再次食指可恢复(self):
        controller=手势控制器(2,2,0)
        self.assertIsNone(controller.处理('食指指向',1.0))
        self.assertEqual(controller.处理('食指指向',1.1),'已暂停')
        controller.处理(None,1.2);controller.处理(None,1.3)
        self.assertIsNone(controller.处理('食指指向',1.4))
        self.assertEqual(controller.处理('食指指向',1.5),'已恢复')


class UI静态契约(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(BASE/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source)
        cls.window=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and n.name=='GestureWindow')

    def func(self,name):
        return ast.get_source_segment(self.source,next(n for n in self.window.body if isinstance(n,ast.FunctionDef) and n.name==name))

    def test_摄像头推理在后台且有背压机制(self):
        worker=(BASE/'手势系统'/'相机线程.py').read_text(encoding='utf-8')
        self.assertIn('class CameraWorker(QThread)',worker)
        self.assertIn('self.infer.预测(frame)',worker)
        self.assertIn('self._ack.clear()',worker)
        self.assertIn('self._ack.set()',worker)
        self.assertNotIn('cv2.VideoCapture(',self.func('on_frame'))
        self.assertIn('worker.acknowledge()',self.func('on_frame'))

    def test_界面暂停不关闭推理回路(self):
        source=self.func('on_frame')
        self.assertIn('self.ctrl.处理(',source)
        self.assertNotIn("self.running=(event=='已恢复')",source)
        self.assertIn('self.camera_worker.recognizing=True',self.func('toggle_run'))

    def test_独立图片窗口有真实操作(self):
        source=(BASE/'手势系统'/'图片交互.py').read_text(encoding='utf-8')
        self.assertIn("self.index=下一索引",source)
        self.assertIn('self.zoom=缩放倍率',source)
        self.assertIn('self.image_dialog.operate(event)',self.func('on_frame'))
        self.assertNotIn('图片浏览',self.func('make_home'))

    def test_训练期间禁止回收及采集(self):
        for name in ('clear_selected','clear_scene','clear_all','_do_import','capture'):
            self.assertIn('self.training_active()',self.func(name))

    def test_版本正确(self):
        self.assertIn('self.setWindowTitle(APP_TITLE)',self.source)
        self.assertIn("'版本':VERSION",self.func('save_settings'))
        self.assertNotIn("self.camera_timer",self.source)


if __name__=='__main__':unittest.main()
