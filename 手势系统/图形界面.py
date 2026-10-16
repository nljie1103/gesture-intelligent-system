"""Tkinter 主界面：摄像头 + 自建图片浏览应用 + 手势状态。"""
from __future__ import annotations
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
from .配置 import 模型目录, 素材目录, 读取配置, 建立运行目录
from .控制 import 手势控制器
from .预处理 import 获取识别矩形
from .推理 import 手势推理器
from .运行记录 import 实时运行记录

背景 = '#101827'
面板 = '#1c2940'
白色 = '#edf3fb'
弱色 = '#a8b9d2'
强调 = '#55c3e6'
图片后缀 = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}


def 读取中文字体(字号: int):
    for 名 in ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(名).exists():
            return ImageFont.truetype(名, 字号)
    return ImageFont.load_default()


def 示例图片(编号: int) -> Image.Image:
    """无素材时生成占位演示图片；不作为训练数据。"""
    配色 = [(34, 107, 158), (25, 138, 117), (122, 91, 164), (174, 98, 79), (125, 112, 55)]
    标题 = ['几何与空间', '视觉与色彩', '深度学习', '智能交互', '计算机视觉']
    画布 = Image.new('RGB', (720, 500), 配色[编号 % len(配色)])
    绘图 = ImageDraw.Draw(画布)
    for n in range(6):
        x, y = int((n * 143 + 33) % 720), int((n * 91 + 78) % 500)
        半径 = 24 + (n * 19) % 68
        绘图.ellipse((x-半径, y-半径, x+半径, y+半径), outline=(226, 232, 246), width=4)
    绘图.rounded_rectangle((95, 177, 625, 323), radius=22, fill=(19, 35, 59))
    绘图.text((360, 226), 标题[编号 % len(标题)], font=读取中文字体(46), fill='white', anchor='mm')
    绘图.text((360, 290), f'演示图片 {编号+1} / 5', font=读取中文字体(20), fill=(178, 225, 245), anchor='mm')
    return 画布


class 手势系统界面:
    def __init__(self):
        建立运行目录()
        self.配置 = 读取配置()
        self.窗口 = tk.Tk()
        self.窗口.title('手势识别智能交互系统 · v' + str(self.配置['版本']))
        self.窗口.geometry('1250x760')
        self.窗口.minsize(980, 650)
        self.窗口.configure(bg=背景)
        self.运行中 = True
        self.日志 = 实时运行记录()
        self.摄像头 = None
        self.推理器 = None
        self.控制器 = 手势控制器(int(self.配置['稳定帧数']), int(self.配置['解除锁定帧数']), float(self.配置['触发冷却秒数']))
        self.页面序号 = 0
        self.缩放 = 1.0
        self.累计帧 = 0
        self.帧率起点 = time.monotonic()
        self.最近帧率 = 0.0
        self.错误累计 = 0
        self.照片引用 = None
        self.图片引用 = None
        self.原始图片 = self.加载图库()
        self.构建界面()
        self.初始化推理()
        self.打开摄像头()
        self.绘制图片()
        self.窗口.after(60, self.更新画面)
        self.窗口.protocol('WM_DELETE_WINDOW', self.关闭)
        self.窗口.bind('<Escape>', lambda _e: self.关闭())
        self.窗口.bind('<Right>', lambda _e: self.执行指令('下一张', '键盘'))
        self.窗口.bind('<Left>', lambda _e: self.执行指令('上一张', '键盘'))
        self.窗口.bind('<plus>', lambda _e: self.执行指令('放大', '键盘'))
        self.窗口.bind('<minus>', lambda _e: self.执行指令('缩小', '键盘'))
        self.窗口.bind('<space>', lambda _e: self.手动暂停())

    def 加载图库(self):
        图片 = []
        for 路径 in sorted(素材目录.iterdir()):
            if 路径.is_file() and 路径.suffix.lower() in 图片后缀:
                try:
                    with Image.open(路径) as 来源:
                        图片.append((路径.name, ImageOps.exif_transpose(来源).convert('RGB')))
                except (OSError, ValueError):
                    print('跳过损坏或不支持的图片：', 路径)
        return 图片 or [(f'内置演示图片{i+1}', 示例图片(i)) for i in range(5)]

    def 构建界面(self):
        头部 = tk.Frame(self.窗口, bg=背景, pady=15)
        头部.pack(fill='x', padx=24)
        tk.Label(头部, text='手势智能控制', font=('Microsoft YaHei UI', 21, 'bold'), fg=白色, bg=背景).pack(side='left')
        tk.Label(头部, text='  手势识别智能交互系统  /  ' + str(self.配置['版本']), font=('Microsoft YaHei UI', 11), fg=弱色, bg=背景).pack(side='left', padx=12)
        tk.Label(头部, text='固定区域 · 自训练 CNN · CPU 推理', font=('Microsoft YaHei UI', 10), fg=强调, bg=背景).pack(side='right')
        主体 = tk.Frame(self.窗口, bg=背景)
        主体.pack(fill='both', expand=True, padx=24)
        左 = tk.Frame(主体, bg=面板, padx=14, pady=12)
        左.pack(side='left', fill='both', expand=True, padx=(0, 12))
        右 = tk.Frame(主体, bg=面板, padx=14, pady=12, width=440)
        右.pack(side='right', fill='both')
        右.pack_propagate(False)
        tk.Label(左, text='摄像头实时识别', font=('Microsoft YaHei UI', 13, 'bold'), fg=白色, bg=面板).pack(anchor='w', pady=(0, 10))
        self.视频画布 = tk.Label(左, text='准备开启摄像头…', fg=弱色, bg='#0b1320', font=('Microsoft YaHei UI', 13), width=55, height=20)
        self.视频画布.pack(fill='both', expand=True)
        self.识别状态 = tk.StringVar(value='等待模型和摄像头…')
        tk.Label(左, textvariable=self.识别状态, font=('Microsoft YaHei UI', 12, 'bold'), fg=强调, bg=面板, anchor='w', pady=10).pack(fill='x')
        self.运行信息 = tk.StringVar(value='置信度 --  |  FPS --  |  推理 --')
        tk.Label(左, textvariable=self.运行信息, fg=弱色, bg=面板, anchor='w', font=('Consolas', 11)).pack(fill='x')
        tk.Label(右, text='智能图片浏览', font=('Microsoft YaHei UI', 13, 'bold'), fg=白色, bg=面板).pack(anchor='w', pady=(0, 10))
        self.图片画布 = tk.Label(右, bg='#101b2e', fg=弱色, width=38, height=16)
        self.图片画布.pack(fill='both', expand=True)
        self.图片信息 = tk.StringVar()
        tk.Label(右, textvariable=self.图片信息, fg=弱色, bg=面板, pady=7).pack()
        按钮行 = tk.Frame(右, bg=面板)
        按钮行.pack(pady=6)
        for 标题, 操作 in [('◀ 上一张', '上一张'), ('下一张 ▶', '下一张'), ('＋ 放大', '放大'), ('－ 缩小', '缩小')]:
            tk.Button(按钮行, text=标题, command=lambda a=操作: self.执行指令(a, '按钮'), bg='#2b405d', fg=白色,
                      relief='flat', padx=8, pady=8, font=('Microsoft YaHei UI', 9)).pack(side='left', padx=3)
        操作行 = tk.Frame(右, bg=面板)
        操作行.pack(pady=7)
        self.暂停按钮 = tk.Button(操作行, text='暂停识别控制', command=self.手动暂停, bg='#184c63', fg='white', relief='flat', padx=15, pady=7)
        self.暂停按钮.pack(side='left', padx=6)
        tk.Button(操作行, text='重新连接摄像头', command=self.打开摄像头, bg='#2b405d', fg='white', relief='flat', padx=12, pady=7).pack(side='left', padx=6)
        self.控制状态 = tk.StringVar(value='应用状态：启用')
        tk.Label(右, textvariable=self.控制状态, fg=强调, bg=面板, font=('Microsoft YaHei UI', 11, 'bold')).pack(pady=4)
        tk.Label(右, text='张开手掌→下一张   握拳→上一张   点赞→放大\n剪刀手→缩小   食指指向→暂停/恢复\n手势离开识别框后才能再次触发同一动作',
                 bg=面板, fg=弱色, justify='left', font=('Microsoft YaHei UI', 10)).pack(anchor='w', pady=8)
        底部 = tk.Label(self.窗口, text='快捷键：←/→ 切图    +/− 缩放    空格 暂停/恢复    Esc 退出    |    未训练时仅可使用按钮和键盘',
                       font=('Microsoft YaHei UI', 10), fg=弱色, bg=背景, pady=12)
        底部.pack(fill='x')

    def 初始化推理(self):
        if not (模型目录 / '正式模型.pt').exists():
            self.识别状态.set('尚无训练好的正式模型：请先采集数据并运行“训练模型.py”')
            return
        try:
            self.推理器 = 手势推理器()
            self.识别状态.set(f'模型已加载 | 生效阈值 {self.推理器.阈值:.2f}')
        except Exception as e:
            self.识别状态.set(f'模型加载失败：{e}')
            self.推理器 = None

    def 打开摄像头(self):
        if self.摄像头 is not None:
            self.摄像头.release()
        设备编号 = int(self.配置['摄像头编号'])
        self.摄像头 = cv2.VideoCapture(设备编号, cv2.CAP_DSHOW if __import__('sys').platform == 'win32' else cv2.CAP_ANY)
        self.错误累计 = 0
        if not self.摄像头.isOpened():
            self.摄像头.release()
            self.摄像头 = None
            self.识别状态.set('无法打开摄像头：请检查设备编号、系统权限和摄像头占用')
        else:
            self.摄像头.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.摄像头.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def 更新画面(self):
        if not self.运行中:
            return
        try:
            if self.摄像头 is not None:
                成功, 画面 = self.摄像头.read()
                if 成功:
                    self.错误累计 = 0
                    画面 = cv2.flip(画面, 1)
                    左, 上, 右, 下 = 获取识别矩形(画面, float(self.配置['识别区域占画面短边比例']))
                    if self.推理器:
                        结果 = self.推理器.预测(画面)
                        标签 = 结果['有效类别']
                        if 标签 == '无手':
                            标签 = None
                        操作 = self.控制器.处理(标签, time.monotonic())
                        self.日志.写入(**{'原始类别': 结果['原始类别'], '有效类别': 结果['有效类别'] or '低置信度', '置信度': round(结果['置信度'], 5), '阈值': 结果['阈值'], '实际帧率': round(self.最近帧率, 2), '推理毫秒': round(结果['推理毫秒'], 2), '执行操作': 操作 or '', '是否暂停': self.控制器.已暂停, '摄像头状态': '正常'})
                        if 操作:
                            if 操作 in ('已暂停', '已恢复'):
                                self.刷新暂停状态()
                            else:
                                self.执行指令(操作, '手势')
                        显示 = 结果['原始类别'] if 结果['有效类别'] else '未知/低置信度'
                        self.识别状态.set(f'当前识别：{显示}  |  状态：{"暂停" if self.控制器.已暂停 else "启用"}')
                        self.运行信息.set(f'置信度 {结果["置信度"]:.1%}  |  FPS {self.最近帧率:.1f}  |  推理 {结果["推理毫秒"]:.1f}ms  |  阈值 {结果["阈值"]:.2f}')
                    else:
                        self.运行信息.set(f'置信度 --  |  FPS {self.最近帧率:.1f}  |  推理 --')
                        self.日志.写入(**{'实际帧率': round(self.最近帧率, 2), '摄像头状态': '正常（模型未加载）'})
                    cv2.rectangle(画面, (左, 上), (右, 下), (80, 220, 120) if self.推理器 else (25, 170, 250), 2)
                    图片 = Image.fromarray(cv2.cvtColor(画面, cv2.COLOR_BGR2RGB))
                    图片.thumbnail((760, 520), Image.Resampling.BILINEAR)
                    self.照片引用 = ImageTk.PhotoImage(图片)
                    self.视频画布.configure(image=self.照片引用, text='')
                    self.累计帧 += 1
                    时间 = time.monotonic()
                    if 时间 - self.帧率起点 >= 1:
                        self.最近帧率 = self.累计帧 / (时间 - self.帧率起点)
                        self.帧率起点, self.累计帧 = 时间, 0
                else:
                    self.错误累计 += 1
                    self.日志.写入(**{'摄像头状态': '读取失败'})
                    self.控制器.处理(None, time.monotonic())
                    self.识别状态.set(f'摄像头帧读取失败（{self.错误累计}），已禁止执行手势操作')
                    if self.错误累计 >= 10:
                        self.摄像头.release()
                        self.摄像头 = None
        except Exception as e:
            self.控制器.处理(None, time.monotonic())
            self.日志.写入(**{'摄像头状态': '推理异常', '执行操作': ''})
            self.识别状态.set(f'本帧推理失败，未执行操作：{e}')
        if self.运行中:
            self.窗口.after(max(10, int(self.配置['视频刷新毫秒'])), self.更新画面)

    def 绘制图片(self):
        名称, 原图 = self.原始图片[self.页面序号]
        基准比例 = min(400 / 原图.width, 360 / 原图.height)
        预览宽 = max(1, int(原图.width * 基准比例 * self.缩放))
        预览高 = max(1, int(原图.height * 基准比例 * self.缩放))
        预览 = 原图.resize((预览宽, 预览高), Image.Resampling.BILINEAR)
        画布 = Image.new('RGB', (420, 390), (16, 27, 46))
        # 大于窗口的图片裁切显示，小于窗口则居中。
        左 = (420 - 预览宽) // 2
        上 = (390 - 预览高) // 2
        画布.paste(预览, (左, 上))
        self.图片引用 = ImageTk.PhotoImage(画布)
        self.图片画布.configure(image=self.图片引用)
        self.图片信息.set(f'{名称}   |   {self.页面序号+1}/{len(self.原始图片)}   |   缩放 {self.缩放:.0%}')

    def 执行指令(self, 操作: str, 来源='手势'):
        if 操作 == '上一张':
            self.页面序号 = (self.页面序号 - 1) % len(self.原始图片)
        elif 操作 == '下一张':
            self.页面序号 = (self.页面序号 + 1) % len(self.原始图片)
        elif 操作 == '放大':
            self.缩放 = min(2.5, round(self.缩放 + .2, 3))
        elif 操作 == '缩小':
            self.缩放 = max(.5, round(self.缩放 - .2, 3))
        else:
            return
        self.绘制图片()
        self.控制状态.set(f'应用状态：{"暂停" if self.控制器.已暂停 else "启用"}  |  上次操作：{操作}（{来源}）')

    def 刷新暂停状态(self):
        已暂停 = self.控制器.已暂停
        self.暂停按钮.configure(text='恢复识别控制' if 已暂停 else '暂停识别控制')
        self.控制状态.set(f'应用状态：{"暂停" if 已暂停 else "启用"}')

    def 手动暂停(self):
        self.控制器.键盘切换暂停()
        self.刷新暂停状态()

    def 关闭(self):
        self.运行中 = False
        if self.摄像头 is not None:
            self.摄像头.release()
            self.摄像头 = None
        self.日志.关闭()
        self.窗口.destroy()

    def 运行(self):
        self.窗口.mainloop()
