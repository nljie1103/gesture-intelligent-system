"""v1.2.0 新增动作映射与候选手部定位测试。"""
import unittest
import numpy as np
import cv2
from 手势系统.动作资源 import 动作列表, 动作索引, 素材路径, 验证动作资源
from 手势系统.手部候选框 import 搜索候选手框, 候选框平滑器

class 动作与定位测试(unittest.TestCase):
    def test_图标和类别资源齐全(self):
        验证动作资源()
        self.assertEqual(len(动作列表),10)
        self.assertEqual(sum(x.已训练 for x in 动作列表),6)
        for x in 动作列表:
            self.assertGreater(素材路径(x.名称).stat().st_size, 3000)

    def test_未训练的动作绝不可映射为当前有效类别(self):
        for x in 动作列表[6:]:
            self.assertFalse(x.已训练)
            self.assertEqual(x.操作,'预留动作')

    def test_空白画面不应该产生红框(self):
        self.assertIsNone(搜索候选手框(np.zeros((480,640,3),np.uint8)))

    def test_候选检测局限在中心ROI(self):
        a=np.zeros((480,640,3),np.uint8)
        # 构造符合 HSV 与 YCrCb 范围的肤色色块。
        skin=cv2.cvtColor(np.uint8([[[12,105,218]]]),cv2.COLOR_HSV2BGR)[0,0]
        a[180:330,260:365]=skin
        rect=搜索候选手框(a)
        self.assertIsNotNone(rect)
        self.assertTrue(250 <= rect[0] <= 270)
        self.assertTrue(350 <= rect[2] <= 375)

    def test_无新候选时不重画旧框(self):
        smoother=候选框平滑器()
        self.assertIsNotNone(smoother.更新((20,30,80,100)))
        self.assertIsNone(smoother.更新(None))
        self.assertIsNone(smoother.更新(None))
        self.assertIsNone(smoother.历史)

if __name__=='__main__': unittest.main()
