"""v1.3.0 — Liquid Glass inspired four-page desktop UI.

No extra UI dependency beyond standard Tkinter + Pillow.  The glass treatment is
an intentionally approximated, rendered glass aesthetic, not native macOS
refraction/translucency.  Existing CNN/inference/controller are unchanged.
"""
from __future__ import annotations
import json
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
import cv2
from PIL import Image, ImageOps, ImageTk, ImageDraw

from .配置 import (根目录, 模型目录, 数据目录, 输出目录, 配置文件,
                    读取配置, 建立运行目录, 类别)
from .控制 import 手势控制器
from .预处理 import 获取识别矩形
from .推理 import 手势推理器
from .运行记录 import 实时运行记录
from .动作资源 import 动作列表, 动作索引, 素材路径
from .手部候选框 import 搜索候选手框, 候选框平滑器
from .界面数据 import 统计样本, 验证设置, 安全保存设置
from .玻璃主题 import 生成壁纸, INK, SUB, BLUE, BG, CARD, LINE, GREEN, RED

字体='Microsoft YaHei UI' if sys.platform=='win32' else 'DejaVu Sans'
WHITE='#FFFFFF'
SOFT='#F1F6FD'
PALE='#E7EFFA'
PURPLE='#7364C9'
DARK='#263B58'


def 文(父,内容='',size=11,color=INK,bold=False,**kwargs):
    return tk.Label(父,text=内容,bg=父.cget('bg'),fg=color,
                    font=(字体,size,'bold' if bold else 'normal'),**kwargs)


class 玻璃卡片(tk.Frame):
    """Frosted pane with luminous glass edge and high-contrast accessible content."""
    def __init__(self,parent,padx=21,pady=18,bg=CARD):
        super().__init__(parent,bg=bg,bd=0,highlightthickness=0,padx=padx,pady=pady)
        self._glass=None
        self._layer=tk.Label(self,bd=0,bg=bg)
        self._layer.place(x=0,y=0,relwidth=1,relheight=1)
        self._layer.lower()
        self._last_size=(0,0)
        self.bind('<Configure>',self._redraw)
    def _redraw(self,event):
        w,h=event.width,event.height
        if (w,h)==self._last_size or w<16 or h<16:return
        self._last_size=(w,h)
        # Pixel rendering provides a genuinely rounded white rim, specular top
        # highlight and blue-violet color accents without operating-system blur.
        im=Image.new('RGB',(w,h),self.cget('bg'))
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((0,0,w-1,h-1),radius=23,fill=(244,249,255),outline=(253,254,255),width=2)
        d.rounded_rectangle((2,2,w-3,h-3),radius=21,outline=(208,224,247),width=1)
        d.arc((11,8,w-13,h-13),184,340,fill=(255,255,255),width=2)
        d.line((30,4,max(31,w-45),4),fill=(253,254,255),width=2)
        self._glass=ImageTk.PhotoImage(im)
        self._layer.configure(image=self._glass)
        self._layer.lower()


def 卡(父,padx=21,pady=18,bg=CARD):
    return 玻璃卡片(父,padx,pady,bg)


class 玻璃按钮(tk.Canvas):
    """Actual single canvas control: responsive rounded pill, keyboard focus, hover."""
    def __init__(self,parent,text,command,bg=BLUE,fg=WHITE,size=11,width=None,pady=12):
        self._parent_bg=parent.cget('bg')
        self._color=bg;self._fg=fg;self._text=text
        self._size=size;self._wide=width;self._pad=pady
        self._anchor='center';self._hover=False;self._cmd=command
        default_w=int((width or max(6,len(text)+1))*14+25)
        super().__init__(parent,bd=0,bg=self._parent_bg,highlightthickness=0,
                         width=default_w,height=24+2*pady,takefocus=1,cursor='hand2')
        self.bind('<Configure>',lambda e:self._paint())
        self.bind('<Enter>',lambda e:self._set_hover(True))
        self.bind('<Leave>',lambda e:self._set_hover(False))
        self.bind('<Button-1>',lambda e:self._click())
        self.bind('<Return>',lambda e:self._click())
        self.bind('<space>',lambda e:self._click())
    def _click(self):
        self.focus_set()
        self._cmd()
    def _set_hover(self,value):
        self._hover=value;self._paint()
    def configure(self,cnf=None,**kwargs):
        if cnf is not None and isinstance(cnf,dict):kwargs={**cnf,**kwargs}
        if 'text' in kwargs:self._text=kwargs.pop('text')
        if 'bg' in kwargs:self._color=kwargs.pop('bg')
        if 'fg' in kwargs:self._fg=kwargs.pop('fg')
        if 'width' in kwargs:kwargs['width']=int(kwargs.pop('width')*14+25)
        if 'anchor' in kwargs:self._anchor=kwargs.pop('anchor')
        kwargs.pop('activebackground',None)
        kwargs.pop('activeforeground',None)
        r=super().configure(**kwargs) if kwargs else None
        self._paint()
        return r
    config=configure
    def _paint(self):
        w=self.winfo_width();h=self.winfo_height()
        if w<20 or h<15:return
        self.delete('all')
        from PIL import ImageColor
        color=ImageColor.getrgb(self._color)
        base=Image.new('RGB',(w,h),self._parent_bg)
        d=ImageDraw.Draw(base)
        # gradient lens + reflective border; no sharp rectangular Tk buttons.
        for y in range(h):
            t=y/max(1,h-1)
            rate=(.14 if self._hover else .09)*(1-t)-.06*t
            tone=tuple(round(max(0,min(255,v+(255-v)*rate if rate>=0 else v*(1+rate)))) for v in color)
            d.line((2,y,w-3,y),fill=tone)
        # Mask to pill radius to retain its rounded silhouette.
        mask=Image.new('L',(w,h),0);md=ImageDraw.Draw(mask)
        md.rounded_rectangle((2,2,w-3,h-3),radius=min(19,h//2-1),fill=255)
        result=Image.new('RGB',(w,h),self._parent_bg)
        result.paste(base,(0,0),mask)
        di=ImageDraw.Draw(result)
        di.rounded_rectangle((2,2,w-3,h-3),radius=min(19,h//2-1),outline=(255,255,255),width=2)
        di.arc((7,5,w-8,h-7),190,325,fill=(255,255,255),width=1)
        self._visual=ImageTk.PhotoImage(result)
        self.create_image(0,0,image=self._visual,anchor='nw')
        x=22 if self._anchor=='w' else w//2
        self.create_text(x,h//2,text=self._text,anchor='w' if self._anchor=='w' else 'center',
                         font=(字体,self._size,'bold'),fill=self._fg)


def 按钮(父,名称,回调,颜色=BLUE,文字色=WHITE,size=11,宽=None,pady=12):
    return 玻璃按钮(父,名称,回调,颜色,文字色,size,宽,pady)


class 手势系统界面:
    页面映射={'首页':'home','数据':'data','模型':'model','设置':'settings'}

    def __init__(self):
        建立运行目录()
        self.配置=读取配置()
        self.窗口=tk.Tk()
        self.窗口.title('基于手势识别的智能系统 · v1.3.0')
        self.窗口.geometry('1390x860')
        self.窗口.minsize(1120,710)
        self.窗口.configure(bg=BG)
        self.运行中=True
        # New rule: recognizer starts only after explicit user action.
        self.识别开启=False
        self.当前页='home'
        self.导航展开=False
        self.视频引用=None
        self.主图引用={}
        self.模型名称='未加载'
        self.摄像头=None
        self.推理器=None
        self.错误累计=0
        self.控制器=self.新控制器()
        self.候选平滑=候选框平滑器()
        self.累计帧=0
        self.帧率起点=time.monotonic()
        self.最近帧率=0.
        self.最近推理耗时=0.
        self.最近阈值=None
        self.最近类别=None
        self.最近提示='尚未开始识别'
        self.最近动作='尚未触发'
        self.最近动作类别=None
        self.最近动作时间=float('-inf')
        self.页面序号=0
        self.缩放=1.
        self.图库数量=self.获取图库数量()
        self.日志=实时运行记录()
        self.缓存动作图片()
        self.界面变量()
        self.构建应用框架()
        self.初始化推理()
        self.打开摄像头()
        self.切换页面('home')
        self.同步主按钮()
        self.刷新顶部状态()
        self.窗口.protocol('WM_DELETE_WINDOW',self.关闭)
        self.窗口.bind('<Escape>',lambda e:self.关闭())
        self.窗口.bind('<space>',lambda e:self.键盘启停(e))
        self.窗口.bind('<p>',lambda e:self.键盘启停(e))
        self.窗口.bind('<r>',lambda e:self.重置状态() if self.当前页=='home' else None)
        self.窗口.bind('<Right>',lambda e:self.键盘操作(e,'下一张'))
        self.窗口.bind('<Left>',lambda e:self.键盘操作(e,'上一张'))
        self.窗口.bind('<plus>',lambda e:self.键盘操作(e,'放大'))
        self.窗口.bind('<minus>',lambda e:self.键盘操作(e,'缩小'))
        self.窗口.after(100,self.更新画面)

    def 新控制器(self):
        return 手势控制器(int(self.配置['稳定帧数']),
                        int(self.配置['解除锁定帧数']),float(self.配置['触发冷却秒数']))

    def 界面变量(self):
        self.顶部连接=tk.StringVar(value='检测摄像头与模型中')
        self.导航标题=tk.StringVar(value='首页')
        self.顶部副标题=tk.StringVar(value='实时手势交互工作台')
        self.视频副状态=tk.StringVar(value='等待启动 · 摄像头仅预览')
        self.运行状态=tk.StringVar(value='点击开始识别，启动实时分类')
        self.检测数值=tk.StringVar(value='置信度  --   ·   FPS  --')
        self.识别名称=tk.StringVar(value='等待开始')
        self.识别操作=tk.StringVar(value='将手势放入摄像头识别区域')
        self.结果置信=tk.StringVar(value='--')
        self.结果状态=tk.StringVar(value='未开始')
        self.触发信息=tk.StringVar(value='完成一次稳定识别后，动作会显示在这里')
        self.底部说明=tk.StringVar(value='v1.3.0  ·  本地推理  ·  摄像头画面不会上传')

    def 缓存动作图片(self):
        for item in 动作列表:
            with Image.open(素材路径(item.名称)) as original:
                src=ImageOps.fit(original.convert('RGBA'),(280,252),Image.Resampling.LANCZOS)
            self.主图引用[item.名称]=ImageTk.PhotoImage(src)

    def 获取图库数量(self):
        directory=根目录/'素材'/'图片'
        if not directory.exists():return 5
        n=sum(p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png','.bmp','.webp') for p in directory.iterdir())
        return n or 5

    def 构建应用框架(self):
        # Ambient wallpaper on the root provides continuous soft colored light.
        self.壁纸=tk.Label(self.窗口,bd=0,bg=BG)
        self.壁纸.place(x=0,y=0,relwidth=1,relheight=1)
        self.壁纸图片=None
        self.壁纸尺寸=(0,0)
        self.窗口.bind('<Configure>',self.窗口大小变化,add='+')
        self.shell=tk.Frame(self.窗口,bg=BG)
        self.shell.pack(fill='both',expand=True,padx=16,pady=15)
        # Deliberately collapsed hamburger / icon-only sidebar at launch.
        self.nav=tk.Frame(self.shell,bg='#E8F1FC',width=68,
                          highlightbackground=WHITE,highlightthickness=2)
        self.nav.pack(side='left',fill='y',padx=(0,14))
        self.nav.pack_propagate(False)
        self.nav_header=tk.Frame(self.nav,bg=self.nav.cget('bg'))
        self.nav_header.pack(fill='x',pady=(14,22))
        self.hamburger=按钮(self.nav_header,'☰',self.切换导航,SOFT,INK,size=17,宽=2,pady=9)
        self.hamburger.pack(anchor='center')
        self.nav_caption=文(self.nav,'GESTURE',9,SUB,True)
        self.导航按钮={}
        for title,ic in [('首页','⌂'),('数据','▦'),('模型','◉'),('设置','⚙')]:
            b=按钮(self.nav,ic,lambda page=self.页面映射[title]:self.切换页面(page),
                 '#F8FBFF',DARK,14,宽=3,pady=12)
            b.pack(fill='x',padx=9,pady=5)
            self.导航按钮[title]=(b,ic)
        tk.Frame(self.nav,bg=self.nav.cget('bg')).pack(fill='both',expand=True)
        self.nav_bottom=文(self.nav,'1.3',9,SUB,True)
        self.nav_bottom.pack(pady=(0,16))
        self.body=tk.Frame(self.shell,bg=BG)
        self.body.pack(side='left',fill='both',expand=True)
        self.top=tk.Frame(self.body,bg=BG,height=65)
        self.top.pack(fill='x')
        self.top.pack_propagate(False)
        title_block=tk.Frame(self.top,bg=BG)
        title_block.pack(side='left',fill='y')
        文(title_block,'GESTURE STUDIO',10,BLUE,True).pack(anchor='w',pady=(1,1))
        文(title_block,size=20,bold=True,textvariable=self.导航标题).pack(anchor='w')
        badge=卡(self.top,padx=15,pady=9,bg='#F8FBFF')
        badge.pack(side='right',pady=(5,6))
        文(badge,textvariable=self.顶部连接,size=10,color=DARK,bold=True).pack()
        self.pagehost=tk.Frame(self.body,bg=BG)
        self.pagehost.pack(fill='both',expand=True,pady=(9,7))
        self.pages={}
        self.构建首页()
        self.构建数据页()
        self.构建模型页()
        self.构建设置页()
        self.foot=tk.Frame(self.body,bg=BG,height=28)
        self.foot.pack(fill='x')
        文(self.foot,textvariable=self.底部说明,size=9,color=SUB).pack(side='left')
        文(self.foot,'● PRIVATE  /  LOCAL',9,GREEN,True).pack(side='right')

    def 窗口大小变化(self,event):
        if event.widget is not self.窗口:return
        size=(self.窗口.winfo_width(),self.窗口.winfo_height())
        if abs(size[0]-self.壁纸尺寸[0])<60 and abs(size[1]-self.壁纸尺寸[1])<60:return
        self.壁纸尺寸=size
        self.壁纸图片=ImageTk.PhotoImage(生成壁纸(*size))
        self.壁纸.configure(image=self.壁纸图片)

    def 切换导航(self):
        self.导航展开=not self.导航展开
        self.nav.configure(width=198 if self.导航展开 else 68)
        self.hamburger.configure(text='☰   收起' if self.导航展开 else '☰',
                                width=10 if self.导航展开 else 2)
        if self.导航展开:
            self.nav_caption.pack(before=next(iter(self.导航按钮.values()))[0],pady=(0,12))
            self.nav_bottom.configure(text='GESTURE STUDIO  1.3.0')
        else:
            self.nav_caption.pack_forget()
            self.nav_bottom.configure(text='1.3')
        for name,(b,ic) in self.导航按钮.items():
            b.configure(text=f'{ic}    {name}' if self.导航展开 else ic,
                        width=12 if self.导航展开 else 3,
                        anchor='w' if self.导航展开 else 'center')

    def 切换页面(self,page):
        if page not in ('home','data','model','settings'):return
        # Recognition is never left active invisibly on non-home pages.
        if page!='home' and self.识别开启:
            self.暂停识别()
        self.当前页=page
        for key,frame in self.pages.items():frame.pack_forget()
        self.pages[page].pack(fill='both',expand=True)
        name={v:k for k,v in self.页面映射.items()}[page]
        self.导航标题.set(name)
        for title,(btn,_) in self.导航按钮.items():
            chosen=(self.页面映射[title]==page)
            btn.configure(bg='#DBEAFE' if chosen else '#F8FBFF',
                          fg=BLUE if chosen else DARK)
        if page=='data':self.更新数据页()
        elif page=='model':self.更新模型页()
        elif page=='settings':self.载入设置控件()

    def 构建首页(self):
        page=tk.Frame(self.pagehost,bg=BG)
        self.pages['home']=page
        desc=tk.Frame(page,bg=BG)
        desc.pack(fill='x',pady=(3,13))
        文(desc,'用手势直接控制 · 清晰看到每一次识别',12,SUB).pack(side='left')
        self.主按钮=按钮(desc,'开始识别  ▶',self.切换启停,BLUE,WHITE,12,宽=13,pady=13)
        self.主按钮.pack(side='right')
        self.重置按钮=按钮(desc,'↺  重置',self.重置状态,SOFT,DARK,10,pady=13)
        self.重置按钮.pack(side='right',padx=(0,10))

        main=tk.Frame(page,bg=BG)
        main.pack(fill='both',expand=True)
        main.grid_columnconfigure(0,weight=60,uniform='main')
        main.grid_columnconfigure(1,weight=40,uniform='main')
        main.grid_rowconfigure(0,weight=1)

        left=卡(main,padx=17,pady=16)
        left.grid(row=0,column=0,sticky='nsew',padx=(0,8))
        h=tk.Frame(left,bg=CARD)
        h.pack(fill='x',pady=(0,12))
        文(h,'实时画面',15,INK,True).pack(side='left')
        self.视频活跃=文(h,'●  PREVIEW',10,GREEN,True)
        self.视频活跃.pack(side='right')
        # Camera space scales with the window instead of fixed oversized widgets.
        camera_frame=tk.Frame(left,bg='#DFE9F6',highlightbackground=LINE,highlightthickness=1)
        camera_frame.pack(fill='both',expand=True)
        self.视频画布=tk.Label(camera_frame,bg='#15263D',fg=WHITE,
                               text='正在打开摄像头…',font=(字体,15))
        self.视频画布.pack(fill='both',expand=True,padx=5,pady=5)
        status=tk.Frame(left,bg=CARD)
        status.pack(fill='x',pady=(12,0))
        文(status,textvariable=self.视频副状态,size=11,color=DARK,bold=True).pack(anchor='w')
        文(status,textvariable=self.检测数值,size=10,color=SUB).pack(anchor='w',pady=(5,0))
        文(status,'细蓝框为分类区域，红框为图像算法估计的候选手部位置',9,SUB).pack(anchor='w',pady=(7,0))

        right=卡(main,padx=19,pady=16)
        right.grid(row=0,column=1,sticky='nsew',padx=(8,0))
        rh=tk.Frame(right,bg=CARD)
        rh.pack(fill='x')
        文(rh,'当前识别结果',15,INK,True).pack(side='left')
        self.右状态=文(rh,'等待中',10,SUB,True)
        self.右状态.pack(side='right')
        hero=tk.Frame(right,bg='#EAF3FE',highlightthickness=1,highlightbackground=WHITE)
        hero.pack(fill='both',expand=True,pady=(13,13))
        self.手势大图=tk.Label(hero,bg='#EAF3FE',image=self.主图引用['无手'])
        self.手势大图.pack(fill='both',expand=True,padx=14,pady=10)
        文(right,textvariable=self.识别名称,size=25,bold=True).pack(anchor='w')
        文(right,textvariable=self.识别操作,size=13,color=DARK).pack(anchor='w',pady=(4,8))
        rs=tk.Frame(right,bg=CARD)
        rs.pack(fill='x',pady=(1,3))
        文(rs,'置信度',10,SUB).pack(side='left')
        文(rs,textvariable=self.结果置信,size=12,color=BLUE,bold=True).pack(side='right')
        self.进度=tk.Canvas(right,bg='#E5EFF9',height=9,bd=0,highlightthickness=0)
        self.进度.pack(fill='x',pady=(3,14))
        self.进度.bind('<Configure>',lambda e:self.画进度条())
        self.当前置信度=0.
        outcome=tk.Frame(right,bg='#E8F5F0',padx=13,pady=12)
        outcome.pack(fill='x')
        文(outcome,'最近一次动作',9,GREEN,True).pack(anchor='w')
        文(outcome,textvariable=self.触发信息,size=11,color=INK,bold=True,
          anchor='w',wraplength=330,justify='left').pack(anchor='w',pady=(5,0))
        self.识别态=文(right,textvariable=self.结果状态,size=10,color=SUB)
        self.识别态.pack(anchor='w',pady=(13,0))
        # No permanent image browser and no 10-thumbnail wall on Home.

    def _page(self,key,subtitle):
        page=tk.Frame(self.pagehost,bg=BG)
        self.pages[key]=page
        文(page,subtitle,12,SUB).pack(anchor='w',pady=(4,16))
        return page

    def 构建数据页(self):
        p=self._page('data','公开训练图与本地采集数据，按类别和采集轮次统一查看')
        upper=tk.Frame(p,bg=BG)
        upper.pack(fill='x',pady=(0,12))
        self.公开量=tk.StringVar(value='--')
        self.本地量=tk.StringVar(value='--')
        self.轮次数=tk.StringVar(value='--')
        for name,var in [('公开训练样本',self.公开量),('本地采集样本',self.本地量),('采集轮次',self.轮次数)]:
            c=卡(upper,padx=18,pady=15)
            c.pack(side='left',fill='both',expand=True,padx=(0,10))
            文(c,name,10,SUB).pack(anchor='w')
            文(c,textvariable=var,size=25,color=INK,bold=True).pack(anchor='w',pady=(5,0))
        按钮(upper,'↻ 刷新',self.更新数据页,SOFT,BLUE,10,pady=11).pack(side='right',anchor='n')
        section=卡(p,padx=20,pady=17)
        section.pack(fill='both',expand=True)
        head=tk.Frame(section,bg=CARD)
        head.pack(fill='x',pady=(0,8))
        文(head,'类别与样本分布',14,INK,True).pack(side='left')
        文(head,'公开 / 本地分别统计',10,SUB).pack(side='right')
        table=tk.Frame(section,bg=CARD)
        table.pack(fill='x')
        self.数据行={}
        header=tk.Frame(table,bg='#EAF2FC',height=36)
        header.pack(fill='x',pady=(0,5))
        for text_,wid in [('类别',20),('公开数据',13),('本地数据',13),('合计',11)]:
            文(header,text_,10,SUB,True,width=wid,anchor='w').pack(side='left',padx=12,pady=8)
        for item in 动作列表[:6]:
            row=tk.Frame(table,bg=CARD,height=47)
            row.pack(fill='x',pady=2)
            vals=[]
            for text_,wid in [(item.名称,20),('—',13),('—',13),('—',11)]:
                v=tk.StringVar(value=text_)
                文(row,textvariable=v,size=11,color=INK,width=wid,anchor='w').pack(side='left',padx=12,pady=8)
                vals.append(v)
            self.数据行[item.名称]=vals
        self.轮次说明=tk.StringVar(value='正在读取数据…')
        文(section,'采集轮次',12,INK,True).pack(anchor='w',pady=(17,6))
        文(section,textvariable=self.轮次说明,size=10,color=SUB,
          anchor='w',justify='left',wraplength=880).pack(anchor='w')
        foot=tk.Frame(p,bg=BG)
        foot.pack(fill='x',pady=(12,0))
        文(foot,'隐私：本地场景照片不会随 GitHub 代码发布；公开训练样本独立管理。',10,SUB).pack(side='left')
        按钮(foot,'打开数据文件夹',lambda:self.打开目录(数据目录),SOFT,BLUE,10,pady=9).pack(side='right')

    def 构建模型页(self):
        p=self._page('model','查看真实模型状态、推理配置与已训练类别；不会显示虚构的测试成绩')
        top=tk.Frame(p,bg=BG)
        top.pack(fill='x',pady=(0,13))
        self.模型状态=tk.StringVar(value='正在检查')
        self.模型文件=tk.StringVar(value='—')
        self.模型信息=tk.StringVar(value='—')
        self.模型阈值=tk.StringVar(value='—')
        for title,var in [('模型状态',self.模型状态),('权重文件',self.模型文件),('输入与类别',self.模型信息),('识别阈值',self.模型阈值)]:
            c=卡(top,padx=16,pady=17)
            c.pack(side='left',fill='both',expand=True,padx=(0,10))
            文(c,title,10,SUB).pack(anchor='w')
            文(c,textvariable=var,size=13,color=INK,bold=True,wraplength=210).pack(anchor='w',pady=(10,0))
        center=卡(p,padx=20,pady=17)
        center.pack(fill='both',expand=True)
        文(center,'手势类别清单',15,INK,True).pack(anchor='w')
        文(center,'当前 CNN 仅输出 6 个类别；其余 4 个动作已预留素材，但不能进行真实识别。',10,SUB).pack(anchor='w',pady=(6,16))
        grid=tk.Frame(center,bg=CARD)
        grid.pack(fill='both',expand=True)
        for idx,item in enumerate(动作列表):
            itemrow=tk.Frame(grid,bg='#EDF5FC' if item.已训练 else '#F4F5F9',padx=11,pady=9)
            itemrow.grid(row=idx//5,column=idx%5,sticky='nsew',padx=5,pady=6)
            grid.grid_columnconfigure(idx%5,weight=1,uniform='gestures')
            icon=tk.Label(itemrow,image=self.主图引用[item.名称],bg=itemrow.cget('bg'))
            # Image size reduced by subsampling? separate cached small previews.
            iconimg=Image.open(素材路径(item.名称)).convert('RGB')
            iconimg=ImageOps.fit(iconimg,(88,75),Image.Resampling.LANCZOS)
            icon.thumb=ImageTk.PhotoImage(iconimg)
            icon.configure(image=icon.thumb)
            icon.pack()
            文(itemrow,item.名称,10,INK,True).pack(pady=(6,2))
            文(itemrow,'已训练' if item.已训练 else '预留 · 未训练',9,
              GREEN if item.已训练 else SUB).pack()
        bottom=tk.Frame(p,bg=BG)
        bottom.pack(fill='x',pady=(14,0))
        文(bottom,'单轮演示模型不能当作独立测试结果；正式评估仍需独立采集轮次。',10,SUB).pack(side='left')
        按钮(bottom,'↻ 重新加载模型',self.重新载入模型,BLUE,WHITE,10,pady=10).pack(side='right')
        按钮(bottom,'打开模型文件夹',lambda:self.打开目录(模型目录),SOFT,BLUE,10,pady=10).pack(side='right',padx=(0,8))

    def 构建设置页(self):
        p=self._page('settings','所有修改都保存至项目设置.json，应用后立即影响后续识别')
        container=tk.Frame(p,bg=BG)
        container.pack(fill='both',expand=True)
        container.grid_columnconfigure(0,weight=1,uniform='set')
        container.grid_columnconfigure(1,weight=1,uniform='set')
        container.grid_rowconfigure(0,weight=1)
        left=卡(container,padx=22,pady=17)
        left.grid(row=0,column=0,sticky='nsew',padx=(0,9))
        right=卡(container,padx=22,pady=17)
        right.grid(row=0,column=1,sticky='nsew',padx=(9,0))
        文(left,'摄像头与检测',15,INK,True).pack(anchor='w',pady=(0,7))
        文(left,'摄像头或识别区域调整后自动重新连接 / 应用。',9,SUB).pack(anchor='w',pady=(0,9))
        文(right,'识别与交互',15,INK,True).pack(anchor='w',pady=(0,7))
        文(right,'阈值留空将使用模型附带的运行阈值。',9,SUB).pack(anchor='w',pady=(0,9))
        fields_left=[('摄像头编号','摄像头编号','0～20'),
                     ('识别区域比例','识别区域占画面短边比例','0.20～1.00'),
                     ('刷新间隔（毫秒）','视频刷新毫秒','20～1000')]
        fields_right=[('最小置信度','最小置信度','留空或 0～1'),
                      ('稳定帧数','稳定帧数','1～30'),
                      ('解锁帧数','解除锁定帧数','1～30'),
                      ('触发冷却（秒）','触发冷却秒数','0～30')]
        self.设置输入={}
        for parent,fields in [(left,fields_left),(right,fields_right)]:
            for label,key,hint in fields:
                r=tk.Frame(parent,bg=CARD)
                r.pack(fill='x',pady=(10,3))
                文(r,label,10,INK,True).pack(side='left')
                文(r,hint,9,SUB).pack(side='right')
                v=tk.StringVar()
                entry=tk.Entry(parent,textvariable=v,bg='#F1F6FC',fg=INK,
                               insertbackground=BLUE,font=(字体,12),relief='flat',bd=0,
                               highlightbackground='#DDE8F5',highlightthickness=1)
                entry.pack(fill='x',ipady=8)
                self.设置输入[key]=v
        switch=tk.Frame(right,bg=CARD)
        switch.pack(fill='x',pady=(20,8))
        self.显示框=tk.BooleanVar(value=True)
        box=tk.Checkbutton(switch,text='显示红色候选手部框',variable=self.显示框,
                           bg=CARD,fg=INK,activebackground=CARD,
                           selectcolor='#E6F1FF',font=(字体,11),cursor='hand2')
        box.pack(side='left')
        文(right,'红框只是辅助估计位置，不参与 CNN 分类。',10,SUB).pack(anchor='w',pady=(1,0))
        buttons=tk.Frame(p,bg=BG)
        buttons.pack(fill='x',pady=(16,0))
        self.保存提示=tk.StringVar(value='修改后点击保存并应用')
        文(buttons,textvariable=self.保存提示,size=10,color=SUB).pack(side='left')
        按钮(buttons,'恢复未保存的修改',self.载入设置控件,SOFT,DARK,10,pady=11).pack(side='right',padx=(0,9))
        按钮(buttons,'保存并应用',self.保存设置,BLUE,WHITE,11,pady=11).pack(side='right')

    def 更新数据页(self):
        result=统计样本(数据目录)
        self.公开量.set(str(result['公开合计']))
        self.本地量.set(str(result['本地合计']))
        self.轮次数.set(str(len(result['轮次'])))
        for name,arr in self.数据行.items():
            pub=result['公开'][name];local=result['本地'][name]
            for var,val in zip(arr,[name,str(pub),str(local),str(pub+local)]):var.set(val)
        sessions=[]
        for name in result['轮次']:
            total=sum(result['分轮次'][name].values())
            sessions.append(f'{name}  ·  {total} 张 / {len(result["分轮次"][name])} 类')
        self.轮次说明.set('      |      '.join(sessions) if sessions else '暂无本地采集轮次')

    def 更新模型页(self):
        path=模型目录/'正式模型.pt'
        exists=path.is_file()
        self.模型状态.set('✓ 已加载' if self.推理器 else ('未能加载' if exists else '尚无正式模型'))
        self.模型文件.set(f'{path.stat().st_size/1024/1024:.2f} MiB' if exists else '未找到权重')
        self.模型信息.set(f'{self.推理器.尺寸} × {self.推理器.尺寸} · {len(类别)} 类' if self.推理器 else 'CNN · 六分类')
        self.模型阈值.set(f'{self.推理器.阈值:.2f}' if self.推理器 else '—')

    def 载入设置控件(self):
        for key,var in self.设置输入.items():
            value=self.配置.get(key)
            var.set('' if value is None else str(value))
        self.显示框.set(bool(self.配置.get('显示候选手部框',True)))
        self.保存提示.set('设置来自当前项目，可修改后保存')

    def 保存设置(self):
        try:
            fields={key:var.get() for key,var in self.设置输入.items()}
            fields['显示候选手部框']=self.显示框.get()
            fixed=验证设置(fields)
        except ValueError as exc:
            messagebox.showerror('设置校验失败',str(exc),parent=self.窗口);return
        old=dict(self.配置)
        new=dict(self.配置);new.update(fixed);new['版本']='1.3.0'
        try:安全保存设置(配置文件,new)
        except OSError as exc:
            messagebox.showerror('无法保存设置',str(exc),parent=self.窗口);return
        self.配置=new
        # Reset stability gates; no stale event can cross a settings change.
        self.控制器=self.新控制器()
        self.候选平滑.重置()
        self.识别开启=False
        self.同步主按钮()
        if int(old['摄像头编号'])!=int(new['摄像头编号']):self.打开摄像头()
        if self.推理器 is not None:
            self.推理器.识别区域比例=float(new['识别区域占画面短边比例'])
            if new['最小置信度'] is not None:
                self.推理器.阈值=float(new['最小置信度'])
            else:
                self.初始化推理()
        self.保存提示.set('✓ 保存成功，识别已暂停；返回首页启动即可')
        self.刷新顶部状态()

    def 打开目录(self,path):
        path=Path(path);path.mkdir(exist_ok=True,parents=True)
        try:
            if sys.platform=='win32':os.startfile(str(path))
            else:messagebox.showinfo('目录路径',str(path),parent=self.窗口)
        except OSError as exc:messagebox.showerror('打开失败',str(exc),parent=self.窗口)

    def 初始化推理(self):
        self.推理器=None
        if not (模型目录/'正式模型.pt').exists():
            self.模型名称='未找到正式模型.pt'
            return
        try:
            self.推理器=手势推理器()
            self.模型名称='模型已加载'
        except Exception as exc:
            self.模型名称=f'加载错误：{str(exc)[:70]}'

    def 重新载入模型(self):
        self.暂停识别()
        self.初始化推理()
        self.更新模型页()
        self.刷新顶部状态()

    def 打开摄像头(self):
        if self.摄像头 is not None:self.摄像头.release()
        self.摄像头=None
        device=int(self.配置['摄像头编号'])
        backends=[cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_ANY] if sys.platform=='win32' else [cv2.CAP_ANY]
        for b in backends:
            cam=cv2.VideoCapture(device,b)
            if cam.isOpened():
                ok,_=cam.read()
                if ok:
                    self.摄像头=cam
                    break
            cam.release()
        self.错误累计=0
        if self.摄像头 is not None:
            self.摄像头.set(cv2.CAP_PROP_FRAME_WIDTH,640)
            self.摄像头.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        self.刷新顶部状态()

    def 刷新顶部状态(self):
        cam='● 摄像头正常' if self.摄像头 else '○ 摄像头未连接'
        model='模型就绪' if self.推理器 else '模型未就绪'
        self.顶部连接.set(f'{cam}    ·    {model}')

    def 当前控制激活(self):
        return self.识别开启 and not self.控制器.已暂停

    def 同步主按钮(self):
        if not hasattr(self,'主按钮'):return
        active=self.当前控制激活()
        self.主按钮.configure(text='暂停识别  Ⅱ' if active else '开始识别  ▶',
                            bg='#374A70' if active else BLUE,
                            activebackground='#374A70' if active else BLUE)
        self.视频活跃.configure(text='●  RUNNING' if active else '○  PREVIEW',
                              fg=GREEN if active else SUB)
        self.右状态.configure(text='识别中' if active else '已暂停',
                             fg=GREEN if active else SUB)

    def 切换启停(self):
        if self.当前控制激活():self.暂停识别()
        else:self.开始识别()

    def 开始识别(self):
        if self.当前页!='home':self.切换页面('home')
        if self.推理器 is None:
            messagebox.showwarning('模型不可用','模型目录没有可加载的正式模型。请先训练或重新加载模型。',parent=self.窗口)
            return
        if self.摄像头 is None:
            messagebox.showwarning('摄像头不可用','请在设置页面检查摄像头编号及 VMware 设备映射。',parent=self.窗口)
            return
        self.识别开启=True
        self.控制器.已暂停=False
        self.控制器.处理(None,time.monotonic())
        self.候选平滑.重置()
        self.视频副状态.set('实时识别已启动 · 保持手势稳定后触发')
        self.结果状态.set('识别中')
        self.同步主按钮()

    def 暂停识别(self):
        self.识别开启=False
        self.控制器.处理(None,time.monotonic())
        self.候选平滑.重置()
        self.视频副状态.set('已暂停识别 · 摄像头预览保持开启')
        self.结果状态.set('已暂停')
        self.同步主按钮()

    def 键盘启停(self,event):
        if isinstance(event.widget,(tk.Entry,tk.Text)):return
        if self.当前页=='home':self.切换启停()

    def 键盘操作(self,event,action):
        if isinstance(event.widget,(tk.Entry,tk.Text)):return
        if self.当前页=='home' and self.当前控制激活():self.执行指令(action,'键盘')

    def 重置状态(self):
        self.暂停识别()
        self.控制器=self.新控制器()
        self.页面序号=0
        self.缩放=1.
        self.最近动作='尚未触发'
        self.最近动作时间=float('-inf')
        self.最近动作类别=None
        self.更新反馈('无手',0,'已重置，等待开始',True)
        self.触发信息.set('已重置 · 等待手势交互')

    def 执行指令(self,action,来源='手势'):
        # The former image viewer panel is intentionally removed. Keep the same
        # gesture action semantics and expose the resulting state in the hero.
        if action=='下一张':self.页面序号=(self.页面序号+1)%self.图库数量
        elif action=='上一张':self.页面序号=(self.页面序号-1)%self.图库数量
        elif action=='放大':self.缩放=min(2.5,round(self.缩放+.2,3))
        elif action=='缩小':self.缩放=max(.5,round(self.缩放-.2,3))
        else:return
        self.最近动作=action
        self.最近动作时间=time.monotonic()
        self.最近动作类别=self.控制器.当前手势 if 来源=='手势' else None
        if action in ('下一张','上一张'):
            text=f'✓ {action}  ·  图片 {self.页面序号+1} / {self.图库数量}（{来源}）'
        else:
            text=f'✓ {action}  ·  缩放 {self.缩放:.0%}（{来源}）'
        self.触发信息.set(text)

    def 画进度条(self):
        cv=self.进度
        cv.delete('all');w=cv.winfo_width();h=cv.winfo_height()
        if w<=1 or h<=1:return
        cv.create_rectangle(0,0,w,h,fill='#E4EBF6',outline='')
        width=int(max(0.,min(1.,self.当前置信度))*w)
        if width:cv.create_rectangle(0,0,width,h,fill=BLUE,outline='')

    def 更新反馈(self,category,confidence,reason,force=False):
        if self.当前页!='home':return
        item=动作索引.get(category or '无手',动作索引['无手'])
        if category!=self.最近类别 or force:
            self.手势大图.configure(image=self.主图引用[item.名称])
            self.识别名称.set(item.名称 if category else '等待识别')
            self.识别操作.set(item.操作 if category else '请将手放在识别区域内')
            self.最近类别=category
        self.当前置信度=max(0.,min(1.,float(confidence)))
        self.结果置信.set(f'{confidence:.1%}' if category else '--')
        self.结果状态.set(reason)
        self.画进度条()

    def 标注画面(self,frame,valid):
        x1,y1,x2,y2=获取识别矩形(frame,float(self.配置['识别区域占画面短边比例']))
        cv2.rectangle(frame,(x1,y1),(x2,y2),(222,164,80),2)
        if self.当前控制激活() and valid not in (None,'无手') and self.配置.get('显示候选手部框',True):
            box=self.候选平滑.更新(搜索候选手框(frame,float(self.配置['识别区域占画面短边比例'])))
            if box:
                a,b,c,d=box
                cv2.rectangle(frame,(a,b),(c,d),(52,67,239),3)
                cv2.rectangle(frame,(a,max(0,b-25)),(min(frame.shape[1],a+170),b),(52,67,239),-1)
                cv2.putText(frame,'HAND CANDIDATE',(a+4,max(15,b-7)),
                            cv2.FONT_HERSHEY_SIMPLEX,.41,(255,255,255),1,cv2.LINE_AA)
        else:self.候选平滑.重置()

    def 更新画面(self):
        if not self.运行中:return
        try:
            if self.摄像头 is not None:
                good,frame=self.摄像头.read()
                if not good:
                    self.错误累计+=1
                    self.控制器.处理(None,time.monotonic())
                    if self.当前页=='home':self.视频副状态.set('摄像头读取失败 · 已停止动作触发')
                    if self.错误累计>=10:
                        self.暂停识别();self.摄像头.release();self.摄像头=None;self.刷新顶部状态()
                else:
                    self.错误累计=0
                    frame=cv2.flip(frame,1)
                    now=time.monotonic()
                    valid=None
                    if self.当前页=='home' and self.识别开启 and self.推理器 is not None:
                        result=self.推理器.预测(frame)
                        valid=result['有效类别']
                        event=self.控制器.处理(valid if valid!='无手' else None,now)
                        self.最近推理耗时=result['推理毫秒']
                        self.最近阈值=result['阈值']
                        self.日志.写入(**{'原始类别':result['原始类别'],
                            '有效类别':valid or '低置信度','置信度':round(result['置信度'],5),
                            '阈值':result['阈值'],'实际帧率':round(self.最近帧率,2),
                            '推理毫秒':round(result['推理毫秒'],2),'执行操作':event or '',
                            '是否暂停':self.控制器.已暂停,'摄像头状态':'正常'})
                        if event in ('已暂停','已恢复'):
                            self.最近动作=event
                            self.最近动作类别=valid
                            self.最近动作时间=now
                            self.触发信息.set('✓ 手势控制'+event)
                            self.同步主按钮()
                        elif event:self.执行指令(event,'手势')
                        if valid is None:note='低置信度 · 暂不执行动作'
                        elif valid=='无手':note='无手 · 等待手势'
                        elif self.控制器.已暂停:note='控制已暂停 · 食指可恢复'
                        elif now-self.最近动作时间<1.4 and valid==self.最近动作类别:
                            note='✓ 已触发动作'
                        else:note='等待连续稳定识别'
                        self.更新反馈(valid,result['置信度'],note)
                        self.视频副状态.set('当前模型：'+result['原始类别']+'  ·  '+note)
                        self.检测数值.set(f'置信度 {result["置信度"]:.1%}   ·   FPS {self.最近帧率:.1f}   ·   推理 {result["推理毫秒"]:.1f} ms   ·   阈值 {result["阈值"]:.2f}')
                    else:
                        self.控制器.处理(None,now)
                    if self.当前页=='home':
                        self.标注画面(frame,valid)
                        w=max(260,self.视频画布.winfo_width()-10)
                        h=max(210,self.视频画布.winfo_height()-10)
                        photo=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                        photo.thumbnail((w,h),Image.Resampling.BILINEAR)
                        self.视频引用=ImageTk.PhotoImage(photo)
                        self.视频画布.configure(image=self.视频引用,text='')
                    self.累计帧+=1
                    if now-self.帧率起点>=1.:
                        self.最近帧率=self.累计帧/(now-self.帧率起点)
                        self.累计帧=0;self.帧率起点=now
            elif self.当前页=='home':
                self.视频画布.configure(text='摄像头尚未连接\n请在设置页检查摄像头编号',image='')
                self.更新反馈(None,0,'摄像头不可用')
        except Exception as exc:
            self.控制器.处理(None,time.monotonic())
            self.暂停识别()
            if self.当前页=='home':
                self.视频副状态.set('识别已安全停止：'+str(exc)[:120])
                self.更新反馈(None,0,'发生异常 · 不执行动作')
        if self.运行中:
            delay=int(self.配置.get('视频刷新毫秒',30))
            self.窗口.after(max(30,delay) if self.当前页=='home' else max(120,delay),self.更新画面)

    def 关闭(self):
        if not self.运行中:return
        self.运行中=False
        if self.摄像头 is not None:
            self.摄像头.release();self.摄像头=None
        self.日志.关闭()
        self.窗口.destroy()

    def 运行(self):self.窗口.mainloop()
