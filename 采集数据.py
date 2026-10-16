"""摄像头自采集：每轮每类独立保存，严禁将同一轮的视频帧跨训练/测试集。"""
import argparse
import time
from pathlib import Path
import cv2
from 手势系统.配置 import 类别, 数据目录, 读取配置, 建立运行目录
from 手势系统.预处理 import 获取识别矩形, 裁剪手势


def 采集一类(摄像头, 手势, 轮次, 数量, 比例, 间隔):
    目录 = 数据目录 / 手势 / 轮次
    if 目录.exists() and any(目录.iterdir()):
        raise FileExistsError(f'{目录} 已有文件，禁止覆盖采集轮次。请换 --session 名称。')
    目录.mkdir(parents=True, exist_ok=True)
    print(f'\n当前手势【{手势}】。准备好后在摄像头窗口按 S 开始；按 Q 中止。')
    print('无手类别：让识别框中完全没有手。不要把手只留在边缘。')
    保存数, 正采集, 上次保存 = 0, False, 0.0
    while 保存数 < 数量:
        成功, 画面 = 摄像头.read()
        if not 成功:
            raise RuntimeError('摄像头读取失败，请检查其他软件是否占用摄像头')
        画面 = cv2.flip(画面, 1)
        左, 上, 右, 下 = 获取识别矩形(画面, 比例)
        # 保存未绘制识别框的原始画面，防止边界标记泄漏到训练图像。
        原始画面 = 画面.copy()
        cv2.rectangle(画面, (左, 上), (右, 下), (0, 230, 0) if 正采集 else (0, 170, 255), 2)
        cv2.putText(画面, f'Class: {类别.index(手势)+1}/6  Session: {轮次}', (12, 28), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2)
        cv2.putText(画面, f'Count: {保存数}/{数量} | S: start/pause | Q: quit', (12, 58), cv2.FONT_HERSHEY_SIMPLEX, .54, (255, 255, 255), 2)
        cv2.imshow('Gesture data capture', 画面)
        键 = cv2.waitKey(1) & 0xff
        if 键 in (ord('q'), 27):
            raise KeyboardInterrupt('用户取消采集')
        if 键 == ord('s'):
            正采集 = not 正采集
            print('正在录制' if 正采集 else '已暂停')
        if 正采集 and time.monotonic() - 上次保存 >= 间隔:
            局部 = 裁剪手势(原始画面, 比例)
            路径 = 目录 / f'{保存数:04d}.jpg'
            局部.save(路径, quality=92)
            保存数 += 1
            上次保存 = time.monotonic()
    print(f'已保存 {保存数} 张图像至 {目录}')


def main():
    p = argparse.ArgumentParser(description='独立采集轮次；每轮拍摄 5 种手势及“无手”负样本')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--all', action='store_true', help='按顺序采集全部6类')
    g.add_argument('--gesture', choices=类别, help='仅采集某一类别')
    p.add_argument('--session', required=True, help='独立采集轮次名（例如 场景01），不同轮次换背景/光照/时段')
    p.add_argument('--count', type=int, default=80, help='每类保存多少张，默认80')
    p.add_argument('--interval', type=float, default=.15, help='每张间隔秒数，默认0.15')
    p.add_argument('--camera', type=int, default=None, help='摄像头编号，默认设置文件')
    a = p.parse_args()
    if not 1 <= a.count <= 10000 or a.interval < .08:
        p.error('count 需在 1~10000，interval 需至少0.08秒')
    if not a.session.strip() or a.session in ('.', '..') or '/' in a.session or '\\' in a.session or ':' in a.session:
        p.error('轮次名称不能包含路径分隔符或冒号')
    建立运行目录()
    设置 = 读取配置()
    摄像头 = cv2.VideoCapture(a.camera if a.camera is not None else int(设置['摄像头编号']), cv2.CAP_DSHOW if __import__('sys').platform == 'win32' else cv2.CAP_ANY)
    if not 摄像头.isOpened():
        raise RuntimeError('无法打开摄像头；检查权限、编号或占用情况')
    try:
        for 手势 in (类别 if a.all else [a.gesture]):
            采集一类(摄像头, 手势, a.session, a.count, float(设置['识别区域占画面短边比例']), a.interval)
    except KeyboardInterrupt:
        print('采集已由用户取消，已写入的图像保留。')
    finally:
        摄像头.release(); cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
