import unittest
from 手势系统.控制 import 手势控制器


class 控制器测试(unittest.TestCase):
    def test_持续识别只执行一次(self):
        c = 手势控制器(稳定帧数=3, 解除帧数=2, 冷却时间=.5)
        self.assertEqual([c.处理('张开手掌', i * .1) for i in range(10)].count('下一张'), 1)
        self.assertIsNone(c.处理(None, 1.0))
        self.assertIsNone(c.处理(None, 1.1))
        self.assertIsNone(c.处理('张开手掌', 1.2))
        self.assertIsNone(c.处理('张开手掌', 1.3))
        self.assertEqual(c.处理('张开手掌', 1.4), '下一张')

    def test_暂停后只能执行恢复(self):
        c = 手势控制器(稳定帧数=2, 解除帧数=2, 冷却时间=0)
        c.处理('食指指向', 0)
        self.assertEqual(c.处理('食指指向', .1), '已暂停')
        c.处理(None, .2); c.处理(None, .3)
        self.assertIsNone(c.处理('张开手掌', .4))
        self.assertIsNone(c.处理('张开手掌', .5))
        c.处理(None, .6); c.处理(None, .7)
        c.处理('食指指向', .8)
        self.assertEqual(c.处理('食指指向', .9), '已恢复')

    def test_未满足稳定帧不触发(self):
        c = 手势控制器(稳定帧数=4, 解除帧数=3, 冷却时间=0)
        for i in range(3):
            self.assertIsNone(c.处理('点赞', i))
        self.assertEqual(c.处理('点赞', 4), '放大')


if __name__ == '__main__':
    unittest.main()
