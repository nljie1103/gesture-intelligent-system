import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from 手势系统.配置 import 类别
from 手势系统.数据 import 建立划分
from 手势系统.指标 import 计算分类指标, 选择验证阈值
from 手势系统.预处理 import 获取识别矩形, 图像转张量


class 数据测试(unittest.TestCase):
    def test_不同轮次不泄漏(self):
        with tempfile.TemporaryDirectory() as 目录:
            根 = Path(目录)
            for 名称 in 类别:
                for 轮次 in ('a', 'b', 'c', 'd', 'e'):
                    子目录 = 根 / 名称 / 轮次
                    子目录.mkdir(parents=True)
                    for n in range(2):
                        Image.new('RGB', (10, 10), (n, 20, 30)).save(子目录 / f'{n}.jpg')
            划分 = 建立划分(根)
            所有路径 = []
            for 分区 in ('训练', '验证', '测试'):
                路径 = {(r.split('/')[0], r.split('/')[1]) for r, _ in 划分['样本'][分区]}
                self.assertTrue(路径)
                所有路径.append(路径)
            self.assertFalse(所有路径[0] & 所有路径[1])
            self.assertFalse(所有路径[0] & 所有路径[2])
            self.assertFalse(所有路径[1] & 所有路径[2])
            self.assertEqual(划分, 建立划分(根))
            self.assertEqual(set(划分['采集轮次分组']['测试']), {x[1] for x in 所有路径[2]})

    def test_帧裁剪与张量格式(self):
        r = 获取识别矩形(np.zeros((200, 300, 3), dtype='uint8'))
        self.assertEqual(r[2] - r[0], r[3] - r[1])
        a = 图像转张量(Image.new('RGB', (10, 20), 'red'), 96)
        self.assertEqual(tuple(a.shape), (3, 96, 96))
        self.assertAlmostEqual(float(a[0].mean()), 1.0)

    def test_指标与阈值(self):
        结果 = 计算分类指标([0, 1, 5], [0, 1, 5])
        self.assertEqual(结果['准确率'], 1.0)
        概率 = np.asarray([[.95, .01, .01, .01, .01, .01], [.01, .95, .01, .01, .01, .01],
                           [.05, .05, .05, .05, .05, .75]])
        t = 选择验证阈值([0, 1, 5], 概率)
        self.assertGreaterEqual(t['阈值'], .60)


if __name__ == '__main__':
    unittest.main()
