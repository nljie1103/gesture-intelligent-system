"""公开 ZIP 标注映射、负类隔离、独立轮次与覆盖防护的离线测试。"""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from PIL import Image
from 手势系统.公开数据 import 导入公开子集, 标签映射
from 手势系统.混合训练 import 构建混合划分, 混合数据错误
from 手势系统.配置 import 类别


class 公开数据测试(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=self.root/'数据'
        self.zip=self.root/'preview.zip'
        anns={}
        with zipfile.ZipFile(self.zip,'w') as z:
            for src in list(标签映射)+['no_gesture']:
                anns[src]={}
                for j in range(7):
                    f=f'{src}/{j:04d}.jpg'
                    im=Image.new('RGB',(128,128),(35+j*15,85,155))
                    buf=io.BytesIO();im.save(buf,format='JPEG',quality=95)
                    z.writestr(f,buf.getvalue())
                    anns[src][f'{j:04d}']={'labels':[src],'bboxes':[[.2,.2,.6,.6]],
                                          'user_id':f'person_{src}_{j}'}
            z.writestr('annotations.json',json.dumps(anns))
        self.out=导入公开子集(self.zip,每类最多=5,数据根目录=self.data)

    def test_只导入五类且不能覆盖(self):
        self.assertEqual(set(self.out['各类数量']),set(类别[:5]))
        self.assertEqual(sum(self.out['各类数量'].values()),25)
        self.assertFalse((self.data/'公开训练'/'无手').exists())
        with self.assertRaises(FileExistsError):
            导入公开子集(self.zip,5,数据根目录=self.data)

    def test_三轮数据严格分隔(self):
        for name in 类别:
            for session in ['甲','乙','丙']:
                p=self.data/name/session
                p.mkdir(parents=True)
                for i in range(8):
                    Image.new('RGB',(96,96),(i*20,80,120)).save(p/f'{i}.jpg')
        split=构建混合划分('甲','乙','丙',self.data,最低本地样本=8)
        self.assertEqual(len(split['公开样本']),25)
        self.assertEqual(len(split['基线训练']),33)
        self.assertEqual(len(split['验证']),48)
        self.assertEqual(len(split['测试']),48)
        self.assertTrue(all('乙/' not in p and '丙/' not in p for p,_ in split['基线训练']))
        self.assertTrue(all('丙/' in p for p,_ in split['测试']))
        with self.assertRaises(混合数据错误):
            构建混合划分('甲','甲','丙',self.data)

    def test_清单路径同时兼容Windows和Linux(self):
        # Windows 的 Path 字符串会使用反斜杠，不能用于判断 POSIX 清单前缀。
        src = '公开训练/张开手掌/0000.jpg'
        self.assertTrue(str(PureWindowsPath(src)).startswith('公开训练\\'))
        self.assertEqual(PurePosixPath(src).parts,
                         ('公开训练', '张开手掌', '0000.jpg'))
        # 正式读取仍应把 POSIX 清单路径规范化为当前系统文件路径。
        for name in 类别:
            for session in ['甲','乙','丙']:
                folder=self.data/name/session
                folder.mkdir(parents=True)
                for i in range(8):
                    Image.new('RGB',(96,96),(i*20,80,120)).save(folder/f'{i}.jpg')
        split=构建混合划分('甲','乙','丙',self.data,最低本地样本=8)
        self.assertEqual(len(split['公开样本']),25)
        self.assertTrue(all(p.startswith('公开训练/') for p,_ in split['公开样本']))

    def test_恶意公开清单路径必须拒绝(self):
        for malicious in ['../outside.jpg','公开训练/../secret.jpg',
                          '公开训练\\张开手掌\\0000.jpg','C:/evil.jpg',
                          '公开训练/握拳/0000.jpg', '公开训练/张开手掌/../0000.jpg']:
            manifest_path=self.data/'公开数据清单.json'
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['样本']['张开手掌'][0]['路径']=malicious
            manifest_path.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
            with self.assertRaises(混合数据错误, msg=malicious):
                构建混合划分('甲','乙','丙',self.data,最低本地样本=8)
            manifest['样本']['张开手掌'][0]['路径']='公开训练/张开手掌/0000.jpg'
            manifest_path.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')

    def test_没有完整三轮不能训练(self):
        with self.assertRaises(混合数据错误):
            构建混合划分('甲','乙','丙',self.data)


if __name__=='__main__':
    unittest.main()
