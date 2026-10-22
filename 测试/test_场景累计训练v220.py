"""v2.2: capture, training and hot-reload regression tests (Qt static + pure data)."""
import ast
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from 手势系统.配置 import 类别
from 手势系统.工作台数据 import 推荐新场景名称,训练样本索引

ROOT=Path(__file__).resolve().parents[1]

class 场景与累计训练测试(unittest.TestCase):
    def test_空场景选择01(self):
        with tempfile.TemporaryDirectory() as t:self.assertEqual(推荐新场景名称(Path(t)),'场景01')

    def test_跨六类最大数字递增(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for c,session in [(类别[0],'场景01'),(类别[1],'场景02'),(类别[4],'场景04')]:
                d=root/c/session;d.mkdir(parents=True);Image.new('RGB',(40,40)).save(d/'one.jpg')
            self.assertEqual(推荐新场景名称(root),'场景05')

    def test_累计全部场景与公开数据(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for i,c in enumerate(类别):
                for scene in ['场景01','场景02','场景03']:
                    d=root/c/scene;d.mkdir(parents=True);Image.new('RGB',(48,48)).save(d/'a.jpg')
            pub=root/'公开训练'/类别[0];pub.mkdir(parents=True);Image.new('RGB',(48,48)).save(pub/'a.jpg')
            sample=训练样本索引(['场景01','场景02','场景03'],root,include_public=True)
            self.assertEqual(len(sample),19)
            self.assertEqual(len({x.split('/')[1] for x,_ in sample if not x.startswith('公开训练/')}),3)

    def test_捕获开始前必须倒计时_每组都需启动(self):
        s=(ROOT/'手势系统/现代界面.py').read_text('utf-8')
        self.assertIn('self.scene=QLineEdit(推荐新场景名称(数据目录))',s)
        self.assertIn('self._begin_countdown()',s)
        self.assertIn('self.countdown_end=time.monotonic()+3.0',s)
        self.assertIn('if self.active and self.index<len(self.seq)',s)
        self.assertIn('self.active=True;self.last_saved=0',s)
        self.assertIn('self.done_btn.setVisible(True)',s)
        self.assertIn('下一组',s)

    def test_原始帧在画绿色框之前复制(self):
        s=(ROOT/'手势系统/相机线程.py').read_text('utf-8')
        self.assertLess(s.index('raw=frame.copy() if self.capture_mode else None'),s.index('cv2.rectangle(frame,(x,y),(x2,y2)'))

    def test_模型更新和状态回显路径完整(self):
        s=(ROOT/'手势系统/现代界面.py').read_text('utf-8')
        self.assertIn('此场景未参与当前模型训练',s)
        self.assertIn('self._pending_after_training=True',s)
        self.assertIn('self.reload_model();self.refresh_training_status()',s)
        self.assertIn('新模型已热加载，无需重启',s)

    def test_训练继续使用旧权重(self):
        s=(ROOT/'手势系统/工作台训练.py').read_text('utf-8')
        self.assertIn('prior_sha=文件哈希(official)',s)
        self.assertIn('network,loaded_size,old_meta=加载分类模型(official,device)',s)
        self.assertIn("'初始化模型SHA256':None if from_scratch else prior_sha",s)

    def test_版本统一(self):
        from 手势系统.版本 import VERSION
        self.assertEqual(VERSION,'2.3.4')

if __name__=='__main__':unittest.main()
