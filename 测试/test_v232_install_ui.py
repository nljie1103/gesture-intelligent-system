"""v2.3.2 regression: avoid installing OpenCV while GUI process holds cv2.pyd;
settings fields must not share compressed grid rows with their labels.
"""
from __future__ import annotations
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class InstallationAndLayoutTests(unittest.TestCase):
    def test_gui_install_phase_only_downloads_wheels(self):
        from 手势系统 import 手部组件安装 as module
        calls=[]
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(module,'_dependencies_available',return_value=False), \
             patch.object(module,'WHEEL_DIR',Path(folder)), \
             patch.object(module,'包含定位资源',return_value=True), \
             patch.object(module,'_run_download',side_effect=lambda cmd,log: calls.append(cmd)):
            self.assertTrue(module.安装())
        self.assertEqual(len(calls),2)
        self.assertTrue(all('download' in c for c in calls))
        self.assertTrue(all('install' not in c for c in calls))

    def test_installed_dependencies_do_not_reinstall(self):
        from 手势系统 import 手部组件安装 as module
        with patch.object(module,'_dependencies_available',return_value=True), \
             patch.object(module,'包含定位资源',return_value=True), \
             patch.object(module,'_run_download',side_effect=AssertionError('should not download')):
            self.assertFalse(module.安装())

    def test_independent_installer_waits_for_parent_before_pip(self):
        source=(ROOT/'手势系统'/'手部组件离线安装.py').read_text(encoding='utf-8')
        node=ast.parse(source)
        fn=next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name=='main')
        seg=ast.get_source_segment(source,fn)
        self.assertLess(seg.index('wait_for_parent(args.parent_pid)'),seg.index('install_offline(args.wheel_dir,log)'))
        self.assertIn('OpenProcess',source)
        self.assertIn('WaitForSingleObject',source)

    def test_opencv_pinned_and_recovery_available(self):
        from 手势系统 import 手部组件安装 as module
        self.assertIn('<5.0',module.OPENCV_REQUIREMENT)
        source=(ROOT/'手势系统'/'手部组件离线安装.py').read_text(encoding='utf-8')
        self.assertIn('opencv-python>=4.10,<5.0',source)
        self.assertIn('force-reinstall',source)

    def test_settings_uses_scrollable_separate_cards(self):
        source=(ROOT/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        beg=source.index('    def make_settings(self):')
        end=source.index('    def install_hand_component(self):',beg)
        section=source[beg:end]
        self.assertIn('v=self._scroll_content(base)',section)
        self.assertIn('cell=QWidget()',section)
        self.assertIn('col.addWidget(caption);col.addWidget(w)',section)
        self.assertIn('w.setMinimumHeight(45)',section)
        self.assertIn('component=panel();v.addWidget(component)',section)
        self.assertNotIn('grid.addWidget(lbl,i//2*2',section)

    def test_install_action_does_not_pip_install_inside_gui(self):
        source=(ROOT/'手势系统'/'现代界面.py').read_text(encoding='utf-8')
        self.assertIn('self._launch_hand_setup_after_exit',source)
        self.assertIn("self.close()",source[source.index('    def _launch_hand_setup_after_exit'):source.index('    def load_settings(self):')])
        self.assertIn("Signal(bool)",source)


if __name__=='__main__':unittest.main()
