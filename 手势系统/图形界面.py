"""v1.2.0 可视化交互：手势大图、动作结果、图片浏览、启停控制与候选手部框。"""
from __future__ import annotations
import sys
import time
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk
import cv2

from .配置 import 模型目录, 素材目录, 读取配置, 建立运行目录
from .控制 import 手势控制器
from .预处理 import 获取识别矩形
from .推理 import 手势推理器
from .运行记录 import 实时运行记录
from .动作资源 import 动作列表, 动作索引, 素材路径
from .手部候选框 import 搜索候选手框, 候选框平滑器

背景 = '#071629'
面板 = '#10243a'
边框 = '#204766'
白色 = '#f4f8ff'
弱色 = '#a3b9d1'
强调 = '#45bdfa'
绿色 = '#16c786'
红色 = '#ff5069'
金色 = '#ffc658'
深灰 = '#0b1b2d'
按钮深 = '#1b3b59'
图片后缀 = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
字体 = 'Microsoft YaHei UI' if sys.platform == 'win32' else 'DejaVu Sans'


def 读取中文字体(字号: int):
    for 名 in ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(名).exists():
            return ImageFont.truetype(名, 字号)
    return ImageFont.load_default()


def 示意图库(编号: int) -> Image.Image:
    """无用户图片时，用动作示意作为待控制图库，不再显示深度学习示例图片。"""
    项 = 动作列表[编号 % 5]
    图 = Image.open(素材路径(项.名称)).convert('RGB')
    板 = Image.new('RGB', (680, 420), '#0e2842')
    画 = ImageDraw.Draw(板)
    画.rounded_rectangle((24, 18, 656, 402), radius=28, fill='#173857', outline='#346482', width=3)
    图片 = ImageOps.fit(图, (280, 242), method=Image.Resampling.LANCZOS)
    板.paste(图片, (52, 86))
    画.text((388, 157), 项.名称, font=读取中文字体(37), fill='#f4f8ff', anchor='mm')
    画.text((395, 239), 项.操作, font=读取中文字体(25), fill='#ffd279', anchor='mm')
    画.text((392, 310), f'示例动作 {编号+1} / 5', font=读取中文字体(16), fill='#c7d8e8', anchor='mm')
    return 板


def 面板块(父, 内边=13):
    return tk.Frame(父, bg=面板, highlightbackground=边框, highlightthickness=1, padx=内边, pady=内边)


def 文字(父, 内容='', 大小=11, 粗=False, 颜色=白色, **kwargs):
    return tk.Label(父, text=内容, bg=父['bg'], fg=颜色,
                    font=(字体, 大小, 'bold' if 粗 else 'normal'), **kwargs)


class 手势系统界面:
    def __init__(self):
        建立运行目录()
        self.配置 = 读取配置()
        self.窗口 = tk.Tk()
        self.窗口.title(f'基于手势识别的智能系统  ·  v{self.配置["版本"]}')
        self.窗口.geometry('1440x900')
        self.窗口.minsize(1360, 850)
        self.窗口.configure(bg=背景)
        self.运行中 = True
        self.识别开启 = True
        self.日志 = 实时运行记录()
        self.摄像头 = None
        self.推理器 = None
        self.控制器 = 手势控制器(int(self.配置['稳定帧数']),
                                  int(self.配置['解除锁定帧数']),
                                  float(self.配置['触发冷却秒数']))
        self.候选平滑 = 候选框平滑器()
        self.页面序号 = 0
        self.缩放 = 1.0
        self.累计帧 = 0
        self.帧率起点 = time.monotonic()
        self.最近帧率 = 0.0
        self.错误累计 = 0
        self.照片引用 = None
        self.图片引用 = None
        self.大图引用 = None
        self.本次显示类别 = None
        self.本次显示状态 = None
        self.最近动作 = '尚未触发动作'
        self.最近动作类别 = None
        self.最近动作时间 = float('-inf')
        self.大图资源 = {}
        self.缩略资源 = {}
        self.原始图片 = self.加载图库()
        self.载入动作图片()
        self.构建界面()
        self.初始化推理()
        self.打开摄像头()
        self.绘制图片()
        self.刷新手势反馈('无手', 0.0, '等待摄像头识别', 强制=True)
        self.刷新按钮状态()
        self.窗口.after(80, self.更新画面)
        self.窗口.protocol('WM_DELETE_WINDOW', self.关闭)
        self.窗口.bind('<Escape>', lambda _e: self.关闭())
        self.窗口.bind('<Right>', lambda _e: self.执行指令('下一张', '键盘'))
        self.窗口.bind('<Left>', lambda _e: self.执行指令('上一张', '键盘'))
        self.窗口.bind('<plus>', lambda _e: self.执行指令('放大', '键盘'))
        self.窗口.bind('<minus>', lambda _e: self.执行指令('缩小', '键盘'))
        self.窗口.bind('<space>', lambda _e: self.手动暂停())
        self.窗口.bind('<p>', lambda _e: self.手动暂停())
        self.窗口.bind('<r>', lambda _e: self.重置状态())

    def 载入动作图片(self):
        for 项 in 动作列表:
            with Image.open(素材路径(项.名称)) as img:
                画 = img.convert('RGB')
            # 启动时预先解码与缩放，循环里只切换 PhotoImage 对象。
            self.大图资源[项.名称] = ImageTk.PhotoImage(ImageOps.fit(画, (290, 232), Image.Resampling.LANCZOS))
            self.缩略资源[项.名称] = ImageTk.PhotoImage(ImageOps.fit(画, (80, 62), Image.Resampling.LANCZOS))

    def 加载图库(self):
        图库=[]
        for p in sorted(素材目录.iterdir()):
            if p.is_file() and p.suffix.lower() in 图片后缀:
                try:
                    with Image.open(p) as src:
                        图库.append((p.name, ImageOps.exif_transpose(src).convert('RGB')))
                except (OSError,ValueError):
                    print('跳过无法读取的图片：',p)
        return 图库 or [(f'手势动作示例 {i+1}', 示意图库(i)) for i in range(5)]

    def 构建界面(self):
        # 顶部导航 + 运行状态
        head = tk.Frame(self.窗口,bg='#0b2038',height=74)
        head.pack(fill='x')
        head.pack_propagate(False)
        文字(head,'✋  基于手势识别的智能系统',20,True).pack(side='left',padx=(22,12))
        文字(head,'v1.2.0',12,True,强调).pack(side='left')
        self.顶部状态 = tk.StringVar(value='● 摄像头：连接中    ● 模型：检查中    FPS：--')
        文字(head,颜色=弱色,大小=11,textvariable=self.顶部状态).pack(side='right',padx=25)

        # 中间摄像头与大图反馈，预留较大的可视空间。
        middle = tk.Frame(self.窗口,bg=背景)
        middle.pack(fill='both',expand=True,padx=16,pady=(14,9))
        middle.grid_columnconfigure(0,weight=6,uniform='main')
        middle.grid_columnconfigure(1,weight=5,uniform='main')
        middle.grid_rowconfigure(0,weight=1)
        camera_panel=面板块(middle,12)
        camera_panel.grid(row=0,column=0,sticky='nsew',padx=(0,8))
        camera_panel.grid_rowconfigure(1,weight=1)
        camera_panel.grid_columnconfigure(0,weight=1)
        文字(camera_panel,'▣   摄像头实时画面',13,True).grid(row=0,column=0,sticky='w',pady=(0,8))
        self.视频画布=tk.Label(camera_panel,text='正在连接摄像头...',bg='#07111f',fg=弱色,font=(字体,15))
        self.视频画布.grid(row=1,column=0,sticky='nsew')
        self.识别状态=tk.StringVar(value='等待摄像头画面...')
        文字(camera_panel,颜色=强调,大小=12,粗=True,textvariable=self.识别状态,anchor='w').grid(row=2,column=0,sticky='ew',pady=(9,4))
        self.运行信息=tk.StringVar(value='置信度 --   |   FPS --   |   推理 --')
        文字(camera_panel,颜色=弱色,大小=10,textvariable=self.运行信息,anchor='w').grid(row=3,column=0,sticky='ew')
        文字(camera_panel,'青色框：固定识别区域     红色框：肤色分割候选位置（可能有误差）',9,False,弱色,anchor='w').grid(row=4,column=0,sticky='ew',pady=(4,0))

        panel = 面板块(middle,12)
        panel.grid(row=0,column=1,sticky='nsew',padx=(8,0))
        文字(panel,'◈   当前识别结果',13,True).pack(anchor='w',pady=(0,8))
        hero=tk.Frame(panel,bg=面板)
        hero.pack(fill='x')
        self.大图画布=tk.Label(hero,bg='#dbeeff',width=290,height=232)
        self.大图画布.pack(side='left',padx=(0,14),pady=3)
        hero_info=tk.Frame(hero,bg=面板)
        hero_info.pack(side='left',fill='both',expand=True)
        self.手势名称=tk.StringVar(value='等待识别')
        文字(hero_info,大小=24,粗=True,颜色=白色,textvariable=self.手势名称,anchor='w',wraplength=210).pack(fill='x',pady=(8,10))
        self.动作说明=tk.StringVar(value='请在识别框内摆放手势')
        文字(hero_info,'对应操作',9,False,弱色,anchor='w').pack(fill='x')
        文字(hero_info,大小=17,粗=True,颜色=金色,textvariable=self.动作说明,anchor='w',wraplength=195).pack(fill='x',pady=(3,12))
        文字(hero_info,'识别置信度',9,False,弱色,anchor='w').pack(fill='x')
        self.置信度字样=tk.StringVar(value='--')
        文字(hero_info,大小=13,粗=True,颜色=绿色,textvariable=self.置信度字样,anchor='w').pack(fill='x')
        self.置信度进度=tk.Canvas(hero_info,height=10,bg='#1b354d',bd=0,highlightthickness=0)
        self.置信度进度.pack(fill='x',pady=(4,0))
        self.置信度进度.bind('<Configure>',lambda _e:self.更新置信度条())
        self.置信度数值=0.0
        self.反馈状态=tk.StringVar(value='等待识别')
        self.反馈框=tk.Label(panel,textvariable=self.反馈状态,bg='#183b50',fg='#52e0a6',
                              font=(字体,13,'bold'),anchor='w',padx=13,pady=10)
        self.反馈框.pack(fill='x',pady=(12,9))
        # 真实图片浏览功能保留为较小区域，不再主导右侧内容。
        browser=tk.Frame(panel,bg=深灰,highlightbackground=边框,highlightthickness=1,padx=10,pady=8)
        browser.pack(fill='both',expand=True)
        browsehead=tk.Frame(browser,bg=深灰)
        browsehead.pack(fill='x')
        文字(browsehead,'图片浏览 · 动作演示',11,True).pack(side='left')
        self.图片信息=tk.StringVar(value='图片载入中')
        文字(browsehead,大小=9,颜色=弱色,textvariable=self.图片信息).pack(side='right')
        preview=tk.Frame(browser,bg=深灰)
        preview.pack(fill='both',expand=True,pady=(6,6))
        self.图片画布=tk.Label(preview,bg='#081725',fg=弱色)
        self.图片画布.pack(side='left',fill='both',expand=True)
        browse_controls=tk.Frame(browser,bg=深灰)
        browse_controls.pack(fill='x')
        for title, action in [('◀ 上一张','上一张'),('下一张 ▶','下一张'),('＋ 放大','放大'),('－ 缩小','缩小')]:
            tk.Button(browse_controls,text=title,command=lambda a=action:self.执行指令(a,'按钮'),
                      bg=按钮深,fg=白色,activebackground='#305b7a',activeforeground=白色,
                      font=(字体,10),relief='flat',bd=0,padx=9,pady=5,cursor='hand2').pack(side='left',padx=(0,6))

        # 当前六类 + 四类占位素材；扩展训练前不可触发动作。
        gallery=面板块(self.窗口,9)
        gallery.pack(fill='x',padx=16,pady=(0,8))
        line=tk.Frame(gallery,bg=面板)
        line.pack(fill='x')
        文字(line,'动作图鉴',12,True).pack(side='left',padx=(3,10))
        文字(line,'6 种当前类别  ·  4 个扩展预留（未训练）',9,False,弱色).pack(side='left')
        icons=tk.Frame(gallery,bg=面板)
        icons.pack(fill='x',pady=(6,0))
        self.卡片=[]
        for k,item in enumerate(动作列表):
            icons.grid_columnconfigure(k,weight=1,uniform='actions')
            c=tk.Frame(icons,bg='#183750' if item.已训练 else '#18283a',padx=3,pady=3)
            c.grid(row=0,column=k,sticky='nsew',padx=3)
            label=tk.Label(c,image=self.缩略资源[item.名称],bg='#d8e8f5' if item.已训练 else '#8392a4')
            label.pack(anchor='center')
            文字(c,item.名称,9,True,白色 if item.已训练 else 弱色).pack()
            detail=item.操作 if item.已训练 else '尚未训练'
            文字(c,detail,8,False,item.颜色 if item.已训练 else 弱色).pack()
            self.卡片.append(c)

        # 显著的启停按钮：暂停后仍可点击开始继续。
        bottom=tk.Frame(self.窗口,bg=背景)
        bottom.pack(fill='x',padx=16,pady=(0,6))
        self.开始按钮=tk.Button(bottom,text='▶  开始识别',command=self.开始识别,bg='#05a86a',fg=白色,
                               activebackground='#12cc86',activeforeground=白色,
                               font=(字体,15,'bold'),relief='flat',bd=0,pady=11,cursor='hand2')
        self.开始按钮.pack(side='left',fill='x',expand=True,padx=(0,7))
        self.暂停按钮=tk.Button(bottom,text='Ⅱ  暂停识别',command=self.手动暂停,bg='#e74159',fg=白色,
                               activebackground='#ff647a',activeforeground=白色,
                               font=(字体,15,'bold'),relief='flat',bd=0,pady=11,cursor='hand2')
        self.暂停按钮.pack(side='left',fill='x',expand=True,padx=(0,7))
        tk.Button(bottom,text='↻  重置状态',command=self.重置状态,bg='#126bd6',fg=白色,
                  activebackground='#338be9',activeforeground=白色,
                  font=(字体,14,'bold'),relief='flat',bd=0,pady=12,cursor='hand2').pack(side='left',fill='x',expand=True,padx=(0,7))
        tk.Button(bottom,text='✕  退出程序',command=self.关闭,bg='#40556b',fg=白色,
                  activebackground='#526d87',activeforeground=白色,
                  font=(字体,14,'bold'),relief='flat',bd=0,pady=12,cursor='hand2').pack(side='left',fill='x',expand=True)
        self.控制状态=tk.StringVar(value='运行中')
        文字(self.窗口,大小=9,颜色=弱色,textvariable=self.控制状态,anchor='w').pack(fill='x',padx=20,pady=(0,5))
        self.窗口.update_idletasks()

    def 更新置信度条(self):
        canvas=self.置信度进度
        canvas.delete('all')
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if w <= 1 or h <= 1: return
        canvas.create_rectangle(0,0,w,h,fill='#24435b',outline='')
        fill=round(w*max(0,min(1,self.置信度数值)))
        if fill>0:
            canvas.create_rectangle(0,0,fill,h,fill=绿色 if self.置信度数值 >= .8 else 金色,outline='')

    def 刷新手势反馈(self, 类别: str | None, 置信度=0.0, 提示='', 强制=False):
        项=动作索引.get(类别 or '无手',动作索引['无手'])
        显示状态=提示
        if 强制 or self.本次显示类别!=项.名称:
            self.大图画布.configure(image=self.大图资源[项.名称],text='')
            self.大图引用=self.大图资源[项.名称]
            self.手势名称.set(项.名称 if 类别 else '未知 / 待机')
            self.动作说明.set(项.操作 if 类别 else '请调整手势')
            for i,card in enumerate(self.卡片):
                current=(动作列表[i].名称==项.名称)
                card.configure(highlightthickness=2 if current else 0,
                               highlightbackground=强调 if current else 边框)
            self.本次显示类别=项.名称
        value=max(0,min(1,float(置信度)))
        self.置信度数值=value
        self.置信度字样.set(f'{value:.1%}' if 类别 else '--')
        self.更新置信度条()
        if 显示状态 != self.本次显示状态:
            self.反馈状态.set(显示状态)
            self.本次显示状态=显示状态
        self.反馈框.configure(fg=红色 if ('暂停' in 提示 or '低置信' in 提示) else '#52e0a6')

    def 初始化推理(self):
        if not (模型目录/'正式模型.pt').exists():
            self.识别状态.set('尚无模型 · 可以使用按钮与键盘体验图片浏览')
            return
        try:
            self.推理器=手势推理器()
            self.识别状态.set(f'模型已加载 · 阈值 {self.推理器.阈值:.2f}')
        except Exception as e:
            self.推理器=None
            self.识别状态.set(f'模型加载失败：{e}')

    def 打开摄像头(self):
        if self.摄像头 is not None: self.摄像头.release()
        self.摄像头=None
        设备=int(self.配置['摄像头编号'])
        backends=[cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_ANY] if sys.platform=='win32' else [cv2.CAP_ANY]
        for backend in backends:
            cam=cv2.VideoCapture(设备,backend)
            if cam.isOpened():
                ok,frame=cam.read()
                if ok:
                    self.摄像头=cam
                    break
            cam.release()
        self.错误累计=0
        if self.摄像头 is None:
            self.识别状态.set('摄像头未连接：检查 VMware USB 映射、权限或设备编号')
        else:
            self.摄像头.set(cv2.CAP_PROP_FRAME_WIDTH,640)
            self.摄像头.set(cv2.CAP_PROP_FRAME_HEIGHT,480)

    def 标注画面(self,画面,有效类别):
        x1,y1,x2,y2=获取识别矩形(画面,float(self.配置['识别区域占画面短边比例']))
        cv2.rectangle(画面,(x1,y1),(x2,y2),(245,195,75),2)
        if self.识别开启 and self.推理器 is not None and 有效类别 not in (None,'无手') and self.配置.get('显示候选手部框',True):
            # 原画面推理后再定位：定位只是视觉辅助，不影响类别或触发。
            box=self.候选平滑.更新(搜索候选手框(画面,float(self.配置['识别区域占画面短边比例'])))
            if box:
                a,b,c,d=box
                cv2.rectangle(画面,(a,b),(c,d),(50,50,255),3)
                cv2.rectangle(画面,(a,max(0,b-25)),(min(画面.shape[1],a+176),b),(50,50,255),-1)
                cv2.putText(画面,'HAND CANDIDATE',(a+4,max(15,b-7)),cv2.FONT_HERSHEY_SIMPLEX,.42,(255,255,255),1,cv2.LINE_AA)
        else:
            self.候选平滑.重置()

    def 更新画面(self):
        if not self.运行中: return
        try:
            if self.摄像头 is None:
                self.顶部状态.set(f'● 摄像头：未连接    ● 模型：{"已加载" if self.推理器 else "未加载"}    FPS：--')
                self.刷新手势反馈(None,0,'摄像头未连接')
            else:
                ok,画面=self.摄像头.read()
                if not ok:
                    self.错误累计+=1
                    self.控制器.处理(None,time.monotonic())
                    self.识别状态.set(f'摄像头读取失败 {self.错误累计} 次，禁止控制')
                    self.刷新手势反馈(None,0,'摄像头读取失败')
                    if self.错误累计 >= 10:
                        self.摄像头.release()
                        self.摄像头=None
                else:
                    self.错误累计=0
                    画面=cv2.flip(画面,1)
                    有效类别=None
                    时间=time.monotonic()
                    if self.推理器 and self.识别开启:
                        结果=self.推理器.预测(画面)
                        有效类别=结果['有效类别']
                        控制类别=有效类别 if 有效类别!='无手' else None
                        事件=self.控制器.处理(控制类别,时间)
                        self.日志.写入(**{'原始类别':结果['原始类别'],'有效类别':有效类别 or '低置信度',
                            '置信度':round(结果['置信度'],5),'阈值':结果['阈值'],
                            '实际帧率':round(self.最近帧率,2),'推理毫秒':round(结果['推理毫秒'],2),
                            '执行操作':事件 or '', '是否暂停':self.控制器.已暂停,'摄像头状态':'正常'})
                        if 事件:
                            if 事件 in ('已暂停','已恢复'):
                                self.最近动作=事件
                                self.最近动作类别=有效类别
                                self.最近动作时间=时间
                            else:
                                self.执行指令(事件,'手势')
                        if 有效类别 is None:
                            self.刷新手势反馈(None,结果['置信度'],'低置信度 · 不执行动作')
                        elif 有效类别=='无手':
                            self.刷新手势反馈('无手',结果['置信度'],'无手 · 等待手势')
                        else:
                            if 时间-self.最近动作时间 < 1.4 and 有效类别==self.最近动作类别:
                                state=f'✓ 已触发：{self.最近动作}'
                            elif self.控制器.已暂停:
                                state='手势控制已暂停 · 食指可恢复'
                            else:
                                state='识别成功 · 等待稳定触发'
                            self.刷新手势反馈(有效类别,结果['置信度'],state)
                        self.识别状态.set(f'当前识别：{结果["原始类别"]}   |   {"手势控制暂停" if self.控制器.已暂停 else "手势控制运行中"}')
                        self.运行信息.set(f'置信度 {结果["置信度"]:.1%}   |   FPS {self.最近帧率:.1f}   |   推理 {结果["推理毫秒"]:.1f}ms   |   阈值 {结果["阈值"]:.2f}')
                    else:
                        self.控制器.处理(None,时间)
                        self.刷新手势反馈(None,0,'已暂停识别' if not self.识别开启 else '尚无模型 · 请先训练')
                        self.识别状态.set('识别已暂停，摄像头仍在预览' if not self.识别开启 else '尚无模型 · 可用键盘与按钮浏览')
                        self.运行信息.set(f'FPS {self.最近帧率:.1f}   |   {"暂停" if not self.识别开启 else "无模型"}')
                        self.日志.写入(**{'摄像头状态':'正常（暂停或无模型）'})
                    self.标注画面(画面,有效类别)
                    w=max(320,self.视频画布.winfo_width()-8)
                    h=max(260,self.视频画布.winfo_height()-8)
                    图=Image.fromarray(cv2.cvtColor(画面,cv2.COLOR_BGR2RGB))
                    图.thumbnail((w,h),Image.Resampling.BILINEAR)
                    self.照片引用=ImageTk.PhotoImage(图)
                    self.视频画布.configure(image=self.照片引用,text='')
                    self.累计帧+=1
                    if 时间-self.帧率起点 >= 1:
                        self.最近帧率=self.累计帧/(时间-self.帧率起点)
                        self.帧率起点,self.累计帧=时间,0
                    self.顶部状态.set(f'● 摄像头：已连接    ● 模型：{"已加载" if self.推理器 else "未加载"}    FPS：{self.最近帧率:.0f}')
        except Exception as e:
            self.控制器.处理(None,time.monotonic())
            self.识别状态.set(f'当前帧异常：{e}，已禁止手势操作')
            self.刷新手势反馈(None,0,'当前帧异常 · 不执行动作')
        if self.运行中:
            self.窗口.after(max(20,int(self.配置['视频刷新毫秒'])),self.更新画面)

    def 绘制图片(self):
        名称,原图=self.原始图片[self.页面序号]
        # 紧凑小预览，图像控制仍能在这里观察。
        capw,caph=350,135
        ratio=min(capw/max(1,原图.width),caph/max(1,原图.height))*self.缩放
        nw=max(1,int(原图.width*ratio));nh=max(1,int(原图.height*ratio))
        img=原图.resize((nw,nh),Image.Resampling.LANCZOS)
        board=Image.new('RGB',(capw,caph),'#081725')
        board.paste(img,((capw-nw)//2,(caph-nh)//2))
        self.图片引用=ImageTk.PhotoImage(board)
        self.图片画布.configure(image=self.图片引用,text='')
        self.图片信息.set(f'{self.页面序号+1}/{len(self.原始图片)}  ·  {self.缩放:.0%}  ·  {名称}')

    def 执行指令(self,操作:str,来源='手势'):
        if 操作=='上一张': self.页面序号=(self.页面序号-1)%len(self.原始图片)
        elif 操作=='下一张': self.页面序号=(self.页面序号+1)%len(self.原始图片)
        elif 操作=='放大': self.缩放=min(2.5,round(self.缩放+.2,3))
        elif 操作=='缩小': self.缩放=max(.5,round(self.缩放-.2,3))
        else: return
        self.绘制图片()
        self.最近动作=操作
        if 来源 == '手势':
            self.最近动作类别 = self.控制器.当前手势
        self.最近动作时间=time.monotonic()
        self.控制状态.set(f'图片 {self.页面序号+1}/{len(self.原始图片)}  |  缩放 {self.缩放:.0%}  |  上次操作：{操作}（{来源}）  |  Esc 退出')

    def 刷新按钮状态(self):
        self.开始按钮.configure(bg='#05a86a' if not self.识别开启 else '#08794d')
        self.暂停按钮.configure(bg='#e74159' if self.识别开启 else '#8f3848')
        if not self.识别开启:
            self.控制状态.set('识别已暂停  |  摄像头预览保持运行  |  点击绿色按钮继续')

    def 开始识别(self):
        self.识别开启=True
        self.控制器.已暂停=False
        self.控制器.处理(None,time.monotonic())
        self.候选平滑.重置()
        self.刷新按钮状态()
        self.控制状态.set('识别已开启  |  动作需连续稳定识别后触发')

    def 手动暂停(self):
        if not self.识别开启:
            self.开始识别()
            return
        self.识别开启=False
        self.候选平滑.重置()
        self.控制器.处理(None,time.monotonic())
        self.刷新按钮状态()
        self.刷新手势反馈(None,0,'已暂停识别')

    def 重置状态(self):
        self.识别开启=True
        self.控制器=手势控制器(int(self.配置['稳定帧数']),int(self.配置['解除锁定帧数']),float(self.配置['触发冷却秒数']))
        self.候选平滑.重置()
        self.页面序号=0
        self.缩放=1.0
        self.最近动作='尚未触发动作'
        self.最近动作类别=None
        self.最近动作时间=float('-inf')
        self.绘制图片()
        self.刷新手势反馈('无手',0,'已重置 · 等待手势',强制=True)
        self.刷新按钮状态()
        self.控制状态.set('已重置 · 图片 1 / {} · 缩放 100%'.format(len(self.原始图片)))

    def 关闭(self):
        if not self.运行中: return
        self.运行中=False
        if self.摄像头 is not None:
            self.摄像头.release()
            self.摄像头=None
        self.日志.关闭()
        self.窗口.destroy()

    def 运行(self):
        self.窗口.mainloop()
