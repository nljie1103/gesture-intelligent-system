"""v2.3.4: media model binary buffer, Windows GUI handoff and runtime safeguards."""
import ast
import unittest
from pathlib import Path
from 手势系统.版本 import VERSION

ROOT=Path(__file__).resolve().parents[1]

class HandInstallerV234Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, '2.3.4')

    def test_unicode_model_is_loaded_as_bytes(self):
        src=(ROOT/'手势系统/手部定位.py').read_text(encoding='utf-8')
        self.assertIn('model_asset_buffer=self.path.read_bytes()',src)
        self.assertNotIn('model_asset_path=str(self.path)',src)
        self.assertIn('HandLandmarker.create_from_options(options)',src)

    def test_gui_exit_before_sidecar_spawn(self):
        src=(ROOT/'手势系统/现代界面.py').read_text(encoding='utf-8')
        node=ast.parse(src)
        ui=next(x for x in node.body if isinstance(x,ast.ClassDef) and x.name=='GestureWindow')
        launch=next(x for x in ui.body if isinstance(x,ast.FunctionDef) and x.name=='_launch_hand_setup_after_exit')
        body=ast.get_source_segment(src,launch)
        self.assertIn('self._pending_hand_setup_command=command',body)
        self.assertIn('self.close()',body)
        self.assertNotIn('subprocess.Popen(',body)
        runner=next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name=='run')
        end=ast.get_source_segment(src,runner)
        self.assertLess(end.index('app.exec()'),end.index('subprocess.Popen(command'))
        self.assertLess(end.index('subprocess.Popen(command'),end.index('os._exit(0)'))

    def test_legacy_version_pins_migrated(self):
        for name in ('test_v230_public_hand.py','test_v233_pause.py','test_场景累计训练v220.py'):
            src=(ROOT/'测试'/name).read_text(encoding='utf-8')
            self.assertNotIn("self.assertEqual(VERSION,'2.3.3')",src)
            self.assertIn("self.assertEqual(VERSION,'2.3.4')",src)

    def test_parent_wait_bounded_and_heartbeat(self):
        src=(ROOT/'手势系统/手部组件离线安装.py').read_text(encoding='utf-8')
        self.assertIn('WAIT_TIMEOUT = 258',src)
        self.assertIn('等待主程序 PID',src)
        self.assertIn('wait_for_parent(args.parent_pid)',src)
        self.assertIn('60 秒',src)
        self.assertIn('time.sleep(1.0)',src)

if __name__=='__main__':unittest.main()
