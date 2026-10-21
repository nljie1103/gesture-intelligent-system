"""v1.5 UI regression checks that run without Qt/window server."""
import ast
import re
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
SOURCE=(BASE/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
TREE=ast.parse(SOURCE)


def extract(name):
    cls=next(x for x in TREE.body if isinstance(x,ast.ClassDef) and x.name=='GestureWindow')
    node=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
    return ast.get_source_segment(SOURCE,node)


class 界面修复测试(unittest.TestCase):
    def test_版本与五页面保持(self):
        self.assertIn('1.7.1',(BASE/'手势系统'/'__init__.py').read_text(encoding='utf-8'))
        self.assertIn("tabs=['首页','数据','训练','模型','设置']",SOURCE)
        self.assertIn('v1.7.0',SOURCE)

    def test_真正透明窗口禁用矩形系统底色(self):
        s=extract('apply_backdrop')
        self.assertIn('off=ctypes.c_int(1)',s)
        self.assertIn('DwmSetWindowAttribute(hwnd,38',s)
        self.assertIn('WA_TranslucentBackground,True',SOURCE)
        self.assertIn('WA_NoSystemBackground,True',SOURCE)
        self.assertIn('CompositionMode_Source',SOURCE)
        self.assertIn('p.setClipPath(path)',SOURCE)
        self.assertNotIn('value=ctypes.c_int(3)',s)

    def test_侧栏动画不即时设宽(self):
        s=extract('toggle_nav')
        self.assertNotIn('setFixedWidth',s)
        self.assertIn('self.nav_transition.start()',s)
        self.assertIn('QParallelAnimationGroup(self)',SOURCE)
        self.assertIn('self.nav_transition.finished.connect(self._sync_navigation)',SOURCE)
        self.assertIn('self.nav_transition.state()==QAbstractAnimation.State.Running:return',extract('on_frame'))

    def test_图标只有一个矢量设计体系(self):
        icons=next(x for x in TREE.body if isinstance(x,ast.Assign) and any(isinstance(y,ast.Name) and y.id=='ICONS' for y in x.targets))
        value=ast.literal_eval(icons.value)
        self.assertEqual(set(value),{'menu','home','data','train','model','settings'})
        self.assertIn('QSvgRenderer(QByteArray(',SOURCE)
        self.assertNotIn("zip(['⌂','▦'",SOURCE)

    def test_按钮和训练文字完整(self):
        self.assertIn('min-height:42px',SOURCE)
        self.assertIn('min-height:46px',SOURCE)
        self.assertIn('fontMetrics().horizontalAdvance(button.text())+60',SOURCE)
        self.assertIn('self.train_all=btn(',SOURCE)
        self.assertIn('self.train_one=btn(',SOURCE)

    def test_自定义下拉及弹出选项(self):
        self.assertIn('class GlassComboBox(QComboBox)',SOURCE)
        self.assertIn('QListView#glassOptions',SOURCE)
        self.assertIn('QComboBox::down-arrow {image:none;',SOURCE)
        self.assertEqual(SOURCE.count('=GlassComboBox()'),6)
        self.assertIn('def paintEvent(self,event):',SOURCE)

    def test_训练逻辑只做界面修复(self):
        self.assertIn('def start_training(self,mode)',SOURCE)
        self.assertIn("self.start_training('all')",SOURCE)
        self.assertIn("self.start_training('focus')",SOURCE)
        self.assertIn('def import_directory(self)',SOURCE)
        self.assertIn('def capture(self)',SOURCE)


if __name__=='__main__':unittest.main()
