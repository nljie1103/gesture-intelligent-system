"""将 HaGRIDv2 五个正样本类别导入本地训练目录，不连接 GitHub，也不上传人像。"""
import argparse
from pathlib import Path
from 手势系统.公开数据 import 导入公开子集

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='导入 HaGRIDv2 精简 ZIP（必须包含 annotations.json）')
    p.add_argument('--zip', type=Path, required=True, help='下载的 hagrid-export_100_images.zip 的完整路径')
    p.add_argument('--limit', type=int, default=100, help='每个类最多导入多少张，默认100')
    p.add_argument('--context', type=float, default=2.6, help='手部框边长倍率，默认2.6')
    a = p.parse_args()
    print('开始筛选公开数据，只导入五种指定手势，不导入 no_gesture。', flush=True)
    result = 导入公开子集(a.zip, a.limit, a.context)
    for k,v in result.items(): print(k, v)
    print('导入完成。原始数据及处理后照片默认不会提交 GitHub。')
