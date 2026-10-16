"""v1.3.0: navigation/data/settings isolation and genuine values."""
import tempfile
import json
import unittest
from pathlib import Path
from 手势系统.界面数据 import 统计样本, 验证设置, 安全保存设置
from 手势系统.配置 import 类别


class 四页管理测试(unittest.TestCase):
    def test_空目录没有编造数据(self):
        with tempfile.TemporaryDirectory() as d:
            data=统计样本(Path(d))
            self.assertEqual(data['公开合计'],0)
            self.assertEqual(data['本地合计'],0)
            self.assertEqual(data['轮次'],[])

    def test_公开与私人图片严格分开统计(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for i in range(2):
                p=root/'公开训练'/类别[0]/f'{i:04d}.jpg'
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'x')
            local=root/类别[0]/'场景01'/'0001.jpg'
            local.parent.mkdir(parents=True,exist_ok=True);local.write_bytes(b'x')
            (local.parent/'notes.txt').write_text('not an image')
            data=统计样本(root)
            self.assertEqual(data['公开合计'],2)
            self.assertEqual(data['本地合计'],1)
            self.assertEqual(data['轮次'],['场景01'])

    def test_设置校验拒绝不合理参数(self):
        base={'摄像头编号':'0','识别区域占画面短边比例':'0.78',
              '稳定帧数':'4','解除锁定帧数':'4','触发冷却秒数':'1',
              '视频刷新毫秒':'30','最小置信度':''}
        self.assertIsNone(验证设置(base)['最小置信度'])
        for field,bad in [('摄像头编号','-1'),('稳定帧数','0'),
                          ('最小置信度','2'),('识别区域占画面短边比例','1.5'),
                          ('视频刷新毫秒','10'),('触发冷却秒数','-1')]:
            corrupted={**base,field:bad}
            with self.subTest(field=field),self.assertRaises(ValueError):
                验证设置(corrupted)

    def test_设置原子写入_并且保留中文(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'设置.json'
            安全保存设置(p,{'版本':'1.3.0','备注':'中文'})
            self.assertEqual(json.loads(p.read_text('utf-8'))['备注'],'中文')
            self.assertEqual(len(list(Path(d).glob('*.tmp'))),0)

    def test_导航四页且主页没有独立图片浏览面板(self):
        from 手势系统.玻璃界面 import 手势系统界面
        self.assertEqual(手势系统界面.页面映射,
                         {'首页':'home','数据':'data','模型':'model','设置':'settings'})
        import inspect
        src=inspect.getsource(手势系统界面.构建首页)
        self.assertNotIn('图片浏览 · 动作演示',src)
        self.assertNotIn('暂停按钮',src)
        self.assertIn('self.主按钮',src)

    def test_原模型类别数量保持六个(self):
        self.assertEqual(len(类别),6)
        from 手势系统.动作资源 import 动作列表
        self.assertEqual(sum(x.已训练 for x in 动作列表),6)
        self.assertEqual(len(动作列表),10)

if __name__=='__main__': unittest.main()
