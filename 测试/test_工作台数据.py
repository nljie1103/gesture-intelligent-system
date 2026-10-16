from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from PIL import Image
from 手势系统.配置 import 类别
from 手势系统.工作台数据 import (验证轮次,验证快捷键,导入图片,回收本地场景,样本汇总,
                                       训练样本索引)


class WorkbenchDataTests(unittest.TestCase):
    def test_session_names_and_hotkeys(self):
        self.assertEqual(验证轮次('场景03'),'场景03')
        for name in ('../x','C:/x','公开训练','回收站',''):
            with self.assertRaises(ValueError):验证轮次(name)
        self.assertEqual(验证快捷键('s','e'),('S','E'))
        with self.assertRaises(ValueError):验证快捷键('S','s')

    def test_import_dedup_and_recycle(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/'数据'
            image=Path(temp)/'test.jpg'
            Image.new('RGB',(64,64),'red').save(image)
            res=导入图片([image,image],类别[0],'场景01',root)
            self.assertEqual((res['新增'],res['重复']),(1,1))
            stats=样本汇总(root)
            self.assertEqual(stats['本地'][类别[0]],1)
            dest=回收本地场景(类别[0],'场景01',root)
            self.assertTrue(dest.is_dir())
            self.assertEqual(样本汇总(root)['本地'][类别[0]],0)

    def test_public_and_private_are_separate(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            for i,c in enumerate(类别):
                src=root/c/'场景01';src.mkdir(parents=True)
                Image.new('RGB',(40,40),color=(i*25,5,40)).save(src/'local.png')
            public=root/'公开训练'/类别[0];public.mkdir(parents=True)
            Image.new('RGB',(40,40)).save(public/'public.jpg')
            stats=样本汇总(root)
            self.assertEqual((stats['本地合计'],stats['公开合计']),(6,1))
            entries=训练样本索引(['场景01'],root)
            self.assertEqual(len(entries),7)
            self.assertEqual({idx for _,idx in entries},set(range(6)))
            with self.assertRaises(ValueError):训练样本索引(['../other'],root)

    def test_import_bad_image_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/'data';src=Path(tmp)/'notjpg.jpg';src.write_text('broken')
            stats=导入图片([src],类别[0],'场景02',root)
            self.assertEqual((stats['新增'],stats['无效']),(0,1))

if __name__=='__main__':unittest.main()
