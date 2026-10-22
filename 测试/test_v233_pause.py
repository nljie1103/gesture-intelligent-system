"""v2.3.3: pause controls default off, Windows sidecar hotfix regression."""
import ast
import json
import unittest
from pathlib import Path
from 手势系统.版本 import VERSION
from 手势系统.配置 import 默认配置
from 手势系统.控制 import 手势控制器

ROOT=Path(__file__).resolve().parents[1]

class GesturePauseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'手势系统/现代界面.py').read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source)
        cls.ui=next(c for c in cls.tree.body if isinstance(c,ast.ClassDef) and c.name=='GestureWindow')
    def func(self,name):
        return ast.get_source_segment(self.source,next(n for n in self.ui.body if isinstance(n,ast.FunctionDef) and n.name==name))
    def test_default_disabled_in_config_and_example(self):
        self.assertEqual(VERSION,'2.3.4')
        self.assertIs(默认配置['允许食指手势暂停'],False)
        settings=json.loads((ROOT/'设置.example.json').read_text(encoding='utf-8'))
        self.assertIs(settings['允许食指手势暂停'],False)
        self.assertEqual(settings['版本'],VERSION)
    def test_UI_setting_is_persisted_and_displayed(self):
        self.assertIn('self.gesture_pause_box=QCheckBox(',self.func('make_settings'))
        self.assertIn("self.settings.get('允许食指手势暂停',False)",self.func('load_settings'))
        self.assertIn("'允许食指手势暂停':bool(self.gesture_pause_box.isChecked())",self.func('save_settings'))
    def test_finger_not_forwarded_to_control_without_optin(self):
        body=self.func('on_frame')
        self.assertIn("candidate=='食指指向'",body)
        self.assertIn("not self.settings.get('允许食指手势暂停',False)",body)
        self.assertIn('candidate=None',body)
        self.assertIn('self.ctrl.处理(candidate,now)',body)
        self.assertIn("self.update_gesture(detected if detected is not None",body)
    def test_pause_message_explains_camera_remains_active(self):
        self.assertNotIn('Ⅱ 手势暂停中 · 点击结束',self.source)
        self.assertIn('指令已暂停，摄像头仍在识别',self.source)
        self.assertIn('■ 结束识别（指令已暂停）',self.source)
        self.assertIn('当前识别已停止，请点击开始识别',self.source)
    def test_control_still_supports_explicit_finger_pause(self):
        ctl=手势控制器(稳定帧数=2,解除帧数=2,冷却时间=0)
        self.assertIsNone(ctl.处理('食指指向',1))
        self.assertEqual(ctl.处理('食指指向',2),'已暂停')
        ctl.处理(None,3);ctl.处理(None,4)
        self.assertIsNone(ctl.处理('食指指向',5))
        self.assertEqual(ctl.处理('食指指向',6),'已恢复')
    def test_windows_time_shadow_not_reintroduced(self):
        code=(ROOT/'手势系统/手部组件离线安装.py').read_text('utf-8')
        node=ast.parse(code)
        wait=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='wait_for_parent')
        self.assertFalse(any(isinstance(n,ast.Import) and any(x.name=='time' for x in n.names) for n in ast.walk(wait)))

if __name__=='__main__':unittest.main()
