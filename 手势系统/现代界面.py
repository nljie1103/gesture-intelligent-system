"""Gesture Studio 1.4: PySide6 macOS-inspired Windows workbench.

This imitates macOS traffic-light window controls and translucent panels; it is
not Apple's system Liquid Glass compositor. No synthetic detection results.
"""
from __future__ import annotations
import ctypes
import json
import os
import sys
import time
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QPoint, QTimer, QProcess, QFileSystemWatcher, QSize, QRectF
from PySide6.QtGui import (QColor,QFont,QIcon,QImage,QKeySequence,QLinearGradient,
                           QPainter,QPainterPath,QPixmap,QRadialGradient,QShortcut,QPen)
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFrame,QLabel,QPushButton,
    QStackedWidget,QScrollArea,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QProgressBar,
    QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QMessageBox,QDialog,QTextEdit,
    QGraphicsDropShadowEffect,QSizePolicy,QGridLayout,QSizeGrip)

from .配置 import 根目录,数据目录,模型目录,输出目录,配置文件,类别,读取配置,建立运行目录
from .控制 import 手势控制器
from .推理 import 手势推理器
from .预处理 import 获取识别矩形,裁剪手势
from .手部候选框 import 搜索候选手框,候选框平滑器
from .动作资源 import 素材路径,动作索引,动作列表
from .界面数据 import 验证设置,安全保存设置
from .工作台数据 import (样本汇总,导入图片,回收本地场景,验证轮次,验证快捷键,图片后缀)

NAVY='#25334C'; MUTED='#63718B'; BLUE='#3978EF'; GREEN='#1DAA79'

STYLES='''
* {font-family:"Segoe UI","Microsoft YaHei UI"; color:#263149; font-size:13px;}
QWidget#windowShell {background:transparent;}
QFrame#glass {background-color:rgba(255,255,255,194); border:1px solid rgba(255,255,255,232); border-radius:24px;}
QFrame#inner {background-color:rgba(247,249,255,210); border:1px solid rgba(220,228,246,150); border-radius:17px;}
QFrame#side {background-color:rgba(250,250,255,155); border:1px solid rgba(255,255,255,230); border-radius:22px;}
QPushButton {background-color:rgba(255,255,255,180); border:1px solid rgba(212,225,244,205); border-radius:13px; padding:10px 14px; font-weight:600;}
QPushButton:hover {background-color:rgba(255,255,255,245); border-color:#A4BFEF;}
QPushButton:pressed {background-color:#DDE9FF;}
QPushButton:disabled {color:#9FAEC4; background-color:#E8EDF5;}
QPushButton#primary {background:#3978EF; color:white; border:none; border-radius:15px; padding:14px 22px; font-size:14px;}
QPushButton#primary:hover {background:#2568DF;}
QPushButton#danger {color:#BB465B; border-color:#F0CBD2;}
QPushButton#navButton {background:transparent; border:0px; border-radius:13px; text-align:left; padding:12px 12px;}
QPushButton#navButton:checked {background-color:rgba(226,238,255,230); color:#1E65CE;}
QLabel#title {font-size:25px; font-weight:700; color:#273752;}
QLabel#h2 {font-size:17px; font-weight:700; color:#263750;}
QLabel#meta {color:#708097; font-size:12px;}
QLabel#hero {font-size:32px; font-weight:700; color:#24334D;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:rgba(255,255,255,218); border:1px solid #D3E0F0; border-radius:12px; padding:8px; min-height:22px;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus {border:1px solid #538BEF;}
QTableWidget {background:rgba(255,255,255,160); border:0px; border-radius:12px; gridline-color:#E4ECF4; alternate-background-color:#F2F7FD;}
QHeaderView::section {background:#EAF2FE; border:0; padding:9px; font-weight:700;}
QProgressBar {border:0; background:#DEE8F7; border-radius:7px; height:11px; text-align:center;}
QProgressBar::chunk {background:#4D91F1; border-radius:7px;}
QTextEdit {background:rgba(246,249,255,210); border:1px solid #D7E3F5; border-radius:12px; padding:10px;}
QCheckBox {spacing:8px;}
'''


def label(text='',size=None,dim=False,title=False):
    w=QLabel(text)
    w.setWordWrap(True)
    if title:w.setObjectName('h2')
    elif dim:w.setObjectName('meta')
    if size:
        f=w.font();f.setPointSize(size);w.setFont(f)
    return w


def panel(layout=None):
    f=QFrame();f.setObjectName('glass')
    l=layout or QVBoxLayout()
    l.setContentsMargins(22,20,22,20);l.setSpacing(12)
    f.setLayout(l)
    shadow=QGraphicsDropShadowEffect(f);shadow.setBlurRadius(34);shadow.setOffset(0,10);shadow.setColor(QColor(61,91,148,38))
    f.setGraphicsEffect(shadow)
    return f


def btn(text,fn,primary=False,danger=False):
    b=QPushButton(text)
    if primary:b.setObjectName('primary')
    if danger:b.setObjectName('danger')
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(fn)
    return b


def qimage(frame):
    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    h,w,ch=rgb.shape
    return QImage(rgb.data,w,h,ch*w,QImage.Format.Format_RGB888).copy()


class Background(QWidget):
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(self.rect().adjusted(1,1,-1,-1))
        path=QPainterPath();path.addRoundedRect(r,25,25);p.setClipPath(path)
        g=QLinearGradient(0,0,self.width(),self.height())
        g.setColorAt(0,QColor('#D6E8FF'));g.setColorAt(.45,QColor('#F6F6FC'));g.setColorAt(1,QColor('#EFE1F5'))
        p.fillRect(self.rect(),g)
        for x,y,rad,c in [(.10,.12,.6,QColor(144,190,252,93)),(.84,.14,.6,QColor(238,181,224,85)),(.74,.86,.5,QColor(172,196,255,80))]:
            radius=int(min(self.width(),self.height())*rad)
            brush=QRadialGradient(self.width()*x,self.height()*y,radius)
            brush.setColorAt(0,c);brush.setColorAt(1,QColor(c.red(),c.green(),c.blue(),0))
            p.fillRect(self.rect(),brush)
        p.setClipping(False);p.setPen(QPen(QColor(255,255,255,245),1.6));p.drawRoundedRect(r,25,25)


class Titlebar(QFrame):
    def __init__(self,parent):
        super().__init__(parent);self.host=parent;self.setFixedHeight(53)
        l=QHBoxLayout(self);l.setContentsMargins(18,6,18,4);l.setSpacing(10)
        for color,func,tooltip in [('#FF605C',parent.close,'关闭'),('#FFBD44',parent.showMinimized,'最小化'),('#00C84A',parent.toggle_max,'最大化 / 还原')]:
            b=QPushButton('');b.setFixedSize(15,15);b.setToolTip(tooltip)
            b.setStyleSheet('QPushButton {background:'+color+';border:1px solid rgba(40,50,65,35);border-radius:7px;padding:0;} QPushButton:hover {border:1px solid #606D84;}')
            b.clicked.connect(func);l.addWidget(b)
        l.addSpacing(14)
        brand=label('●  Gesture Studio',13);brand.setStyleSheet('color:#354766;font-weight:700;')
        l.addWidget(brand);l.addStretch()
        self.name=label('手势识别 · 本地工作台',dim=True);l.addWidget(self.name)
        l.addStretch()
        l.addWidget(label('v1.4.0',dim=True))
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:self._drag=e.globalPosition().toPoint()-self.host.pos()
    def mouseMoveEvent(self,e):
        if e.buttons() & Qt.MouseButton.LeftButton and hasattr(self,'_drag'):
            if self.host.isMaximized():return
            self.host.move(e.globalPosition().toPoint()-self._drag)
    def mouseDoubleClickEvent(self,e):self.host.toggle_max()


class CaptureDialog(QDialog):
    """Single owner of the camera while capture is open. User-defined shortcuts are scoped here."""
    def __init__(self,host):
        super().__init__(host)
        self.host=host;self.setWindowTitle('采集新图片 · 手势工作台')
        self.resize(960,730);self.setMinimumSize(760,600)
        self.setStyleSheet(STYLES+'QDialog {background:#EEF4FD;}')
        self.cam=None;self.active=False;self.seq=[];self.index=0;self.saved=0;self.last_saved=0
        layout=QVBoxLayout(self);layout.setContentsMargins(22,18,22,18);layout.setSpacing(12)
        layout.addWidget(label('摄像头采集',title=True))
        controls=QGridLayout();controls.setHorizontalSpacing(12)
        self.pick=QComboBox();self.pick.addItems(['全部六类']+类别)
        self.scene=QLineEdit('场景02');self.scene.setPlaceholderText('例如 场景02')
        self.scenes=QSpinBox();self.scenes.setRange(1,30);self.scenes.setValue(1)
        self.fps=QDoubleSpinBox();self.fps.setRange(.2,12);self.fps.setSingleStep(.5);self.fps.setValue(4);self.fps.setSuffix(' 张/秒')
        self.count=QSpinBox();self.count.setRange(1,10000);self.count.setValue(30)
        self.hot_start=QLineEdit('S');self.hot_stop=QLineEdit('E')
        widgets=[('手势类别',self.pick),('场景起始名称',self.scene),('场景数量',self.scenes),('每秒张数',self.fps),('每类张数',self.count),('开始键',self.hot_start),('停止键',self.hot_stop)]
        for i,(name,w) in enumerate(widgets):
            controls.addWidget(label(name,dim=True),i//4*2,i%4)
            controls.addWidget(w,i//4*2+1,i%4)
        layout.addLayout(controls)
        self.preview=QLabel('摄像头初始化中…');self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(330);self.preview.setStyleSheet('background:#13253B;color:white;border-radius:18px;')
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        layout.addWidget(self.preview,1)
        self.info=label('开始后逐类拍摄；到达张数自动切换到下一个手势或场景。',dim=True)
        layout.addWidget(self.info)
        buttons=QHBoxLayout()
        self.go=btn('▶ 开始采集',self.start,primary=True)
        self.stop=btn('■ 停止并保留已拍照片',self.pause)
        buttons.addWidget(self.go);buttons.addWidget(self.stop);buttons.addStretch()
        buttons.addWidget(btn('完成并返回',self.accept))
        layout.addLayout(buttons)
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick)
        self.shortcuts=[];self.hot_start.setText('S');self.hot_stop.setText('E')
        self.open_camera()
        self.timer.start(32)
    def open_camera(self):
        device=int(self.host.settings.get('摄像头编号',0))
        for backend in ([cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_ANY] if sys.platform=='win32' else [cv2.CAP_ANY]):
            cam=cv2.VideoCapture(device,backend)
            if cam.isOpened() and cam.read()[0]:self.cam=cam;break
            cam.release()
        if self.cam is None:self.info.setText('摄像头打不开；检查 VMware USB 设备与占用情况。')
    def bind_shortcuts(self):
        for item in self.shortcuts:item.setEnabled(False);item.deleteLater()
        self.shortcuts=[]
        start,stop=验证快捷键(self.hot_start.text().strip(),self.hot_stop.text().strip())
        for key,fn in [(start,self.start),(stop,self.pause)]:
            sc=QShortcut(QKeySequence(key),self);sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(fn);self.shortcuts.append(sc)
        return start,stop
    def start(self):
        if self.cam is None:QMessageBox.warning(self,'摄像头','没有可用的摄像头');return
        if self.active:return
        if not self.seq:
            try:
                start,stop=self.bind_shortcuts()
                first=验证轮次(self.scene.text().strip())
                classes=类别 if self.pick.currentIndex()==0 else [self.pick.currentText()]
                import re
                m=re.match(r'^(.*?)(\d+)$',first)
                if self.scenes.value()>1 and not m:raise ValueError('多个场景请使用带编号的名称，例如 场景02')
                session_names=[(m.group(1)+str(int(m.group(2))+i).zfill(len(m.group(2))) if m else first) for i in range(self.scenes.value())]
                for session in session_names:验证轮次(session)
                self.seq=[(c,s) for s in session_names for c in classes]
                # Prevent accidental blending of independent sessions with previously collected ones.
                occupied=[f'{c}/{s}' for c,s in self.seq if (数据目录/c/s).is_dir() and any((数据目录/c/s).iterdir())]
                if occupied:
                    raise ValueError('目标采集目录已存在图片：'+', '.join(occupied[:4])+'。请更换场景名称，防止混入旧轮次。')
                for field in [self.pick,self.scene,self.scenes,self.fps,self.count,self.hot_start,self.hot_stop]:field.setEnabled(False)
                self.info.setText(f'采集队列已建立，{len(self.seq)} 个手势/场景组合；{start} 开始 / {stop} 停止')
            except ValueError as e:QMessageBox.warning(self,'参数错误',str(e));return
        self.active=True;self.last_saved=0;self.go.setText('正在采集…')
    def pause(self):
        self.active=False;self.go.setText('▶ 继续采集')
        self.info.setText(f'已停止。保留已拍照片。进度：{self.index+1}/{len(self.seq)}，当前 {self.saved}/{self.count.value()} 张。' if self.seq else '未启动采集')
    def tick(self):
        if not self.cam:return
        ok,frame=self.cam.read()
        if not ok:self.pause();self.info.setText('摄像头读取失败，采集已停止');return
        frame=cv2.flip(frame,1)
        x1,y1,x2,y2=获取识别矩形(frame,float(self.host.settings.get('识别区域占画面短边比例',.78)))
        if self.active and self.index<len(self.seq):
            now=time.monotonic()
            if now-self.last_saved>=1./self.fps.value():
                gesture,session=self.seq[self.index]
                image=裁剪手势(frame,float(self.host.settings.get('识别区域占画面短边比例',.78)))
                folder=数据目录/gesture/session;folder.mkdir(parents=True,exist_ok=True)
                name=folder/f'cap_{time.time_ns()}_{self.saved+1:05d}.jpg'
                image.save(name,quality=92)
                self.saved+=1;self.last_saved=now
                self.info.setText(f'正在拍摄 {gesture} / {session}  ·  {self.saved}/{self.count.value()} 张  ·  任务 {self.index+1}/{len(self.seq)}')
                if self.saved>=self.count.value():
                    self.saved=0;self.index+=1;self.active=False
                    if self.index==len(self.seq):
                        self.info.setText('✓ 全部采集结束，图片已保存。关闭窗口即可在数据页自动看到变化。')
                        self.go.setEnabled(False)
                    else:
                        c,s=self.seq[self.index]
                        self.info.setText(f'下一组：{c}/{s}。调整手势或环境后按开始键，再采集。')
                        self.go.setText('▶ 开始下一组')
        cv2.rectangle(frame,(x1,y1),(x2,y2),(50,210,95) if self.active else (235,179,54),2)
        q=QPixmap.fromImage(qimage(frame))
        self.preview.setPixmap(q.scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def done(self,result):
        self.timer.stop()
        if self.cam:self.cam.release();self.cam=None
        super().done(result)


class GestureWindow(QWidget):
    tabs=['首页','数据','训练','模型','设置']
    def __init__(self):
        super().__init__()
        建立运行目录()
        self.settings=读取配置()
        self.setWindowTitle('Gesture Studio  ·  v1.4.0')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,True)
        self.resize(1350,820);self.setMinimumSize(1080,680)
        self.running=False;self.cam=None;self.infer=None;self.lastcat=None;self.last_action='—'
        self.fps_count=0;self.fps_start=time.monotonic();self.last_fps=0
        self.ctrl=手势控制器(int(self.settings['稳定帧数']),int(self.settings['解除锁定帧数']),float(self.settings['触发冷却秒数']))
        self.smoother=候选框平滑器()
        self.bg=Background(self)
        self.bg.setObjectName('windowShell')
        self.bg.setStyleSheet(STYLES)
        self.bg.setGeometry(self.rect())
        self.build_ui();self.load_model();self.open_camera()
        self.camera_timer=QTimer(self);self.camera_timer.timeout.connect(self.on_frame)
        self.camera_timer.start(max(35,int(self.settings.get('视频刷新毫秒',30))))
        self.data_timer=QTimer(self);self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(1800)
        self.fs_watcher=QFileSystemWatcher(self);self.fs_watcher.directoryChanged.connect(self.refresh_data)
        self.fs_watcher.fileChanged.connect(self.refresh_data)
        self.refresh_data()
        self.apply_backdrop()
    def resizeEvent(self,e):
        self.bg.setGeometry(self.rect());super().resizeEvent(e)
    def apply_backdrop(self):
        if sys.platform!='win32':return
        try:
            # Windows 11 desktop acrylic is not Apple's refractive Liquid Glass.
            hwnd=int(self.winId());value=ctypes.c_int(3)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd),38,ctypes.byref(value),4)
        except (OSError,AttributeError):pass
    def toggle_max(self):self.showNormal() if self.isMaximized() else self.showMaximized()
    def build_ui(self):
        outer=QVBoxLayout(self.bg);outer.setContentsMargins(14,6,14,15);outer.setSpacing(4)
        self.titlebar=Titlebar(self);outer.addWidget(self.titlebar)
        row=QHBoxLayout();row.setSpacing(15);outer.addLayout(row,1)
        self.side=QFrame();self.side.setObjectName('side');self.side.setFixedWidth(68)
        sidebar=QVBoxLayout(self.side);sidebar.setContentsMargins(7,12,7,13);sidebar.setSpacing(8)
        self.collapsed=True
        self.hamburger=btn('☰',self.toggle_nav);sidebar.addWidget(self.hamburger)
        self.navbuttons=[]
        for idx,(ic,name) in enumerate(zip(['⌂','▦','◫','◉','⚙'],self.tabs)):
            b=QPushButton(ic);b.setObjectName('navButton');b.setCheckable(True)
            b.clicked.connect(lambda _,i=idx:self.set_page(i))
            b.setToolTip(name);sidebar.addWidget(b);self.navbuttons.append((b,ic,name))
        sidebar.addStretch();sidebar.addWidget(label('1.4',dim=True))
        row.addWidget(self.side)
        right=QVBoxLayout();right.setSpacing(10);row.addLayout(right,1)
        top=QHBoxLayout();self.heading=label('首页');self.heading.setObjectName('title')
        top.addWidget(self.heading);top.addStretch()
        self.status=label('● 本地 · 正在连接',dim=True);top.addWidget(self.status)
        right.addLayout(top)
        self.stack=QStackedWidget();right.addWidget(self.stack,1)
        self.make_home();self.make_data();self.make_train();self.make_model();self.make_settings()
        footer=QHBoxLayout();footer.addWidget(label('Gesture Studio · Private on-device workspace',dim=True));footer.addStretch()
        footer.addWidget(label('摄像头与私人图片不会自动上传',dim=True));footer.addWidget(QSizeGrip(self));right.addLayout(footer)
        self.set_page(0)
    def toggle_nav(self):
        self.collapsed=not self.collapsed
        self.side.setFixedWidth(68 if self.collapsed else 196)
        for b,ic,name in self.navbuttons:b.setText(ic if self.collapsed else f'{ic}   {name}')
        self.hamburger.setText('☰' if self.collapsed else '☰   收起')
    def set_page(self,index):
        if index!=0 and self.running:self.stop_recognition()
        self.stack.setCurrentIndex(index);self.heading.setText(self.tabs[index])
        for i,(b,_,_) in enumerate(self.navbuttons):b.setChecked(i==index)
        if index==1:self.refresh_data(force=True)
        if index==3:self.refresh_model()
    def page(self,subtitle):
        body=QWidget();v=QVBoxLayout(body);v.setContentsMargins(3,3,12,12);v.setSpacing(14)
        v.addWidget(label(subtitle,dim=True));self.stack.addWidget(body)
        return v
    def make_home(self):
        v=self.page('用摄像头完成手势交互 · 当前识别结果优先展示')
        controls=QHBoxLayout();controls.addStretch()
        controls.addWidget(btn('↻ 重置状态',self.reset))
        self.run_btn=btn('▶ 开始识别',self.toggle_run,primary=True)
        controls.addWidget(self.run_btn);v.addLayout(controls)
        pair=QHBoxLayout();pair.setSpacing(16);v.addLayout(pair,1)
        camera=panel();pair.addWidget(camera,6)
        camera.layout().addWidget(label('实时摄像头',title=True))
        self.camera=QLabel('正在连接摄像头…');self.camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera.setMinimumSize(300,280)
        self.camera.setStyleSheet('background:#142238;color:#DCE5F5;border-radius:16px;')
        self.camera.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        camera.layout().addWidget(self.camera,1)
        self.camera_info=label('固定识别区 · 红框为候选位置',dim=True)
        camera.layout().addWidget(self.camera_info)
        result=panel();pair.addWidget(result,4)
        result.layout().addWidget(label('当前识别结果',title=True))
        self.gesture_icon=QLabel();self.gesture_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gesture_icon.setMinimumHeight(230)
        result.layout().addWidget(self.gesture_icon,1)
        self.gesture_text=label('等待开始');self.gesture_text.setObjectName('hero')
        result.layout().addWidget(self.gesture_text)
        self.action_text=label('点击“开始识别”后，将手放进摄像头区域')
        result.layout().addWidget(self.action_text)
        self.conf=QProgressBar();self.conf.setRange(0,100);self.conf.setValue(0)
        result.layout().addWidget(self.conf)
        self.last_event=label('尚未触发手势指令',dim=True);result.layout().addWidget(self.last_event)
        self.update_gesture('无手')
    def make_data(self):
        v=self.page('实时同步本地文件夹 · 公开训练图与私人采集图分开管理')
        summary=QHBoxLayout();v.addLayout(summary)
        self.totals=[]
        for name in ('公开训练图片','私人采集图片','采集场景数'):
            card=panel();card.layout().addWidget(label(name,dim=True));number=label('0',size=27)
            card.layout().addWidget(number);summary.addWidget(card,1);self.totals.append(number)
        card=panel();v.addWidget(card,1)
        card.layout().addWidget(label('六分类样本统计',title=True))
        self.table=QTableWidget(6,4);self.table.setHorizontalHeaderLabels(['手势类别','公开训练','私人采集','总计'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True);self.table.verticalHeader().hide();self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        card.layout().addWidget(self.table)
        actions=panel();v.addWidget(actions)
        actions.layout().addWidget(label('图片导入与清理',title=True))
        line=QHBoxLayout();actions.layout().addLayout(line)
        self.data_category=QComboBox();self.data_category.addItems(类别)
        self.data_session=QComboBox();self.data_session.setEditable(True);self.data_session.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.data_session.setEditText('场景02')
        line.addWidget(label('类别'));line.addWidget(self.data_category,1)
        line.addWidget(label('场景'));line.addWidget(self.data_session,1)
        line=QHBoxLayout();actions.layout().addLayout(line)
        line.addWidget(btn('＋ 导入图片文件',self.import_files))
        line.addWidget(btn('▣ 导入整个文件夹',self.import_directory))
        line.addWidget(btn('打开数据目录',lambda:self.open_folder(数据目录)))
        line.addWidget(btn('清空所选场景',self.clear_selected,danger=True))
        line.addWidget(btn('清空全部私人图片',self.clear_all,danger=True))
        self.data_note=label('复制图片到指定类别的场景文件夹后，将自动刷新数量；清空先移到本地回收站。',dim=True)
        actions.layout().addWidget(self.data_note)
    def make_train(self):
        v=self.page('统一管理采集与训练 · 训练时保留原模型备份 · 不编造独立测试成绩')
        top=QHBoxLayout();v.addLayout(top)
        collect=panel();top.addWidget(collect,1)
        collect.layout().addWidget(label('摄像头采集',title=True))
        collect.layout().addWidget(label('可设置张数、张/秒、场景数量和开始/停止快捷键。',dim=True))
        collect.layout().addWidget(btn('📷 打开采集工作台',self.capture,primary=True))
        train=panel();top.addWidget(train,1)
        train.layout().addWidget(label('模型训练',title=True))
        train.layout().addWidget(label('全部训练 / 单类专项强化（保留六分类并重放其他类别）',dim=True))
        row=QHBoxLayout();train.layout().addLayout(row)
        self.train_scene=QComboBox();self.train_scene.setEditable(True);self.train_scene.setEditText('场景01')
        row.addWidget(label('训练场景'));row.addWidget(self.train_scene,1)
        row=QHBoxLayout();train.layout().addLayout(row)
        self.train_epoch=QSpinBox();self.train_epoch.setRange(1,200);self.train_epoch.setValue(8)
        self.train_device=QComboBox();self.train_device.addItems(['CPU','CUDA（可用时）'])
        row.addWidget(label('Epoch'));row.addWidget(self.train_epoch)
        row.addWidget(label('设备'));row.addWidget(self.train_device)
        row=QHBoxLayout();train.layout().addLayout(row)
        self.focus_cat=QComboBox();self.focus_cat.addItems(类别)
        row.addWidget(label('专项类别'));row.addWidget(self.focus_cat,1)
        row=QHBoxLayout();train.layout().addLayout(row)
        self.train_all=btn('▶ 一键训练全部',lambda:self.start_training('all'),primary=True)
        self.train_one=btn('专项强化所选手势',lambda:self.start_training('focus'))
        row.addWidget(self.train_all);row.addWidget(self.train_one)
        bottom=panel();v.addWidget(bottom,1)
        bottom.layout().addWidget(label('任务日志',title=True))
        self.train_log=QTextEdit();self.train_log.setReadOnly(True)
        self.train_log.setPlaceholderText('开始训练后显示实时进度；训练将作为独立进程执行，不冻结界面。')
        bottom.layout().addWidget(self.train_log,1)
        line=QHBoxLayout();bottom.layout().addLayout(line)
        self.train_status=label('空闲 · 当前使用现有模型',dim=True);line.addWidget(self.train_status);line.addStretch()
        self.train_cancel=btn('停止任务',self.stop_training,danger=True);self.train_cancel.setEnabled(False);line.addWidget(self.train_cancel)
        self.proc=None
    def make_model(self):
        v=self.page('模型与类别信息 · 训练指标必须来自真实验证集或测试集')
        top=panel();v.addWidget(top)
        self.model_state=label('正在检查模型…',size=17);top.layout().addWidget(self.model_state)
        self.model_info=label('',dim=True);top.layout().addWidget(self.model_info)
        top.layout().addWidget(btn('重新加载模型',self.reload_model))
        cards=panel();v.addWidget(cards,1)
        cards.layout().addWidget(label('手势类别 · 已训练6类 / 预留4类',title=True))
        grid=QGridLayout();cards.layout().addLayout(grid)
        for i,item in enumerate(动作列表):
            b=QFrame();b.setObjectName('inner');sub=QVBoxLayout(b)
            ico=QLabel();ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix=QPixmap(str(素材路径(item.名称)))
            ico.setPixmap(pix.scaled(86,80,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            sub.addWidget(ico)
            sub.addWidget(label(item.名称))
            sub.addWidget(label('已训练' if item.已训练 else '未训练 · 预留',dim=True))
            grid.addWidget(b,i//5,i%5)
        v.addWidget(label('备注：第七种新手势不能仅靠复制图片激活，需要扩展模型输出和重新训练。',dim=True))
    def make_settings(self):
        v=self.page('摄像头及分类设置 · 保存在原有 设置.json，不覆盖私人数据')
        card=panel();v.addWidget(card,1)
        grid=QGridLayout();grid.setVerticalSpacing(17);grid.setHorizontalSpacing(22)
        card.layout().addWidget(label('识别设置',title=True));card.layout().addLayout(grid)
        fields=[('摄像头编号','摄像头编号','0'),('识别区域比例','识别区域占画面短边比例','0.78'),
                ('最小置信度（留空采用模型阈值）','最小置信度',''),('稳定帧数','稳定帧数','4'),
                ('解锁帧数','解除锁定帧数','4'),('冷却时间（秒）','触发冷却秒数','1.0'),
                ('刷新间隔（毫秒）','视频刷新毫秒','30')]
        self.inputs={}
        for i,(text,key,placeholder) in enumerate(fields):
            lbl=label(text,dim=True);w=QLineEdit();w.setPlaceholderText(placeholder)
            grid.addWidget(lbl,i//2*2,i%2);grid.addWidget(w,i//2*2+1,i%2)
            self.inputs[key]=w
        self.show_box=QCheckBox('显示红色候选手部位置框（非精确检测框）')
        card.layout().addWidget(self.show_box)
        row=QHBoxLayout();row.addStretch();row.addWidget(btn('恢复未保存值',self.load_settings));row.addWidget(btn('保存并应用',self.save_settings,primary=True))
        card.layout().addLayout(row)
        card.layout().addStretch()
        self.load_settings()
    def load_settings(self):
        for k,w in self.inputs.items():w.setText('' if self.settings.get(k) is None else str(self.settings[k]))
        self.show_box.setChecked(bool(self.settings.get('显示候选手部框',True)))
    def save_settings(self):
        data={k:w.text().strip() for k,w in self.inputs.items()}
        data['显示候选手部框']=self.show_box.isChecked()
        try:clean=验证设置(data)
        except ValueError as e:QMessageBox.warning(self,'设置错误',str(e));return
        old=dict(self.settings);new={**old,**clean,'版本':'1.4.0'}
        try:安全保存设置(配置文件,new)
        except OSError as e:QMessageBox.critical(self,'写入失败',str(e));return
        self.settings=new;self.stop_recognition()
        self.ctrl=手势控制器(int(new['稳定帧数']),int(new['解除锁定帧数']),float(new['触发冷却秒数']))
        if int(old['摄像头编号'])!=int(new['摄像头编号']):self.open_camera()
        self.reload_model()
        QMessageBox.information(self,'设置','已经保存并应用；识别处于暂停状态。')
    def update_gesture(self,category,conf=None):
        category=category if category in 动作索引 else '无手'
        if self.lastcat!=category:
            pix=QPixmap(str(素材路径(category)))
            self.gesture_icon.setPixmap(pix.scaled(310,270,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.gesture_text.setText(category)
            self.action_text.setText(动作索引[category].操作)
            self.lastcat=category
        self.conf.setValue(round(conf*100) if conf is not None else 0)
        self.conf.setFormat(f'{conf:.1%}' if conf is not None else '—')
    def toggle_run(self):
        if self.running:self.stop_recognition();return
        if not self.infer:
            QMessageBox.warning(self,'模型不可用','先到“训练”执行训练，或到“模型”重新加载已有权重。');return
        if not self.cam:
            QMessageBox.warning(self,'摄像头不可用','请检查 VMware 摄像头连接和设置编号。');return
        self.running=True;self.ctrl.已暂停=False;self.ctrl.处理(None,time.monotonic())
        self.run_btn.setText('Ⅱ 暂停识别')
    def stop_recognition(self):
        self.running=False;self.ctrl.处理(None,time.monotonic())
        if hasattr(self,'run_btn'):self.run_btn.setText('▶ 开始识别')
    def reset(self):
        self.stop_recognition();self.ctrl=手势控制器(int(self.settings['稳定帧数']),int(self.settings['解除锁定帧数']),float(self.settings['触发冷却秒数']))
        self.last_event.setText('已重置，等待识别');self.update_gesture('无手')
    def load_model(self):
        self.infer=None
        try:
            if (模型目录/'正式模型.pt').exists():self.infer=手势推理器()
        except (OSError,ValueError,RuntimeError) as e:self.model_error=str(e)
        if hasattr(self,'model_state'):self.refresh_model()
        self.status.setText(('● 摄像头正常' if self.cam else '○ 摄像头未连接')+'     ·     '+('● 模型就绪' if self.infer else '○ 无模型'))
    def reload_model(self):
        self.stop_recognition();self.load_model()
    def refresh_model(self):
        file=模型目录/'正式模型.pt'
        self.model_state.setText('✓ 六分类模型已加载' if self.infer else '未加载正式模型')
        self.model_info.setText(f'{file.name}  ·  {file.stat().st_size/1024**2:.2f} MiB  ·  阈值 {self.infer.阈值:.2f}' if self.infer else '请先进入训练页。没有独立验证时不展示测试准确率。')
    def open_camera(self):
        if self.cam:self.cam.release()
        self.cam=None
        for backend in ([cv2.CAP_DSHOW,cv2.CAP_MSMF,cv2.CAP_ANY] if sys.platform=='win32' else [cv2.CAP_ANY]):
            cap=cv2.VideoCapture(int(self.settings['摄像头编号']),backend)
            if cap.isOpened() and cap.read()[0]:self.cam=cap;break
            cap.release()
        if self.cam:self.cam.set(cv2.CAP_PROP_FRAME_WIDTH,640);self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        self.status.setText(('● 摄像头正常' if self.cam else '○ 摄像头未连接')+'     ·     '+('● 模型就绪' if self.infer else '○ 无模型'))
    def on_frame(self):
        if not self.cam:return
        ok,frame=self.cam.read()
        if not ok:
            self.stop_recognition();self.camera_info.setText('摄像头读取失败，操作已停止');return
        frame=cv2.flip(frame,1);result=None;detected=None
        now=time.monotonic()
        if self.running and self.stack.currentIndex()==0 and self.infer:
            try:
                result=self.infer.预测(frame)
                detected=result['有效类别'];event=self.ctrl.处理(detected if detected!='无手' else None,now)
                self.update_gesture(detected,result['置信度'])
                self.camera_info.setText(f'FPS {self.last_fps:.1f}    ·    推理 {result["推理毫秒"]:.1f} ms    ·    阈值 {result["阈值"]:.2f}')
                if event:
                    self.last_event.setText(f'✓ {event} · 来自 {detected}')
                    if event in ('已暂停','已恢复'):
                        self.running=(event=='已恢复')
                        self.run_btn.setText('Ⅱ 暂停识别' if self.running else '▶ 开始识别')
            except (ValueError,RuntimeError,OSError) as e:
                self.stop_recognition();self.camera_info.setText('推理停止：'+str(e)[:90])
        if self.stack.currentIndex()==0:
            x,y,x2,y2=获取识别矩形(frame,float(self.settings['识别区域占画面短边比例']))
            cv2.rectangle(frame,(x,y),(x2,y2),(231,160,54),2)
            if self.running and detected and detected!='无手' and self.settings.get('显示候选手部框',True):
                candidate=self.smoother.更新(搜索候选手框(frame,float(self.settings['识别区域占画面短边比例'])))
                if candidate:
                    a,b,c,d=candidate;cv2.rectangle(frame,(a,b),(c,d),(55,67,239),3)
            else:self.smoother.重置()
            pix=QPixmap.fromImage(qimage(frame))
            self.camera.setPixmap(pix.scaled(self.camera.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.fps_count+=1
        if now-self.fps_start>=1:
            self.last_fps=self.fps_count/(now-self.fps_start);self.fps_start=now;self.fps_count=0
    def refresh_data(self,force=False):
        if not hasattr(self,'table'):return
        if not force and self.stack.currentIndex() not in (1,2):return
        result=样本汇总(数据目录)
        for w,n in zip(self.totals,[result['公开合计'],result['本地合计'],len(result['场景'])]):w.setText(str(n))
        for i,c in enumerate(类别):
            for j,v in enumerate([c,result['公开'][c],result['本地'][c],result['公开'][c]+result['本地'][c]]):
                self.table.setItem(i,j,QTableWidgetItem(str(v)))
        current=self.data_session.currentText()
        self.data_session.clear();self.data_session.addItems(sorted(result['场景']))
        self.data_session.setEditText(current or '场景02')
        # Refresh watched directories on new user-created folders.
        paths=[str(数据目录)]
        for c in 类别:
            folder=数据目录/c
            if folder.is_dir():
                paths.append(str(folder))
                paths.extend(str(d) for d in folder.iterdir() if d.is_dir() and not d.is_symlink())
        watched=set(self.fs_watcher.directories());desired=set(paths)
        if watched-desired:self.fs_watcher.removePaths(list(watched-desired))
        if desired-watched:self.fs_watcher.addPaths(list(desired-watched))
        self.data_note.setText(f'实时目录监控中 · 已发现 {len(result["场景"])} 个场景；手动复制后通常 2 秒内刷新。')
    def import_files(self):
        files,_=QFileDialog.getOpenFileNames(self,'选择图片',str(Path.home()),'图像文件 (*.jpg *.jpeg *.png *.bmp *.webp)')
        if files:self._do_import([Path(x) for x in files])
    def import_directory(self):
        folder=QFileDialog.getExistingDirectory(self,'选择图片文件夹',str(Path.home()))
        if folder:self._do_import([p for p in Path(folder).rglob('*') if p.is_file() and p.suffix.lower() in 图片后缀])
    def _do_import(self,files):
        try:stats=导入图片(files,self.data_category.currentText(),self.data_session.currentText().strip(),数据目录)
        except (ValueError,OSError) as e:QMessageBox.warning(self,'导入失败',str(e));return
        self.refresh_data(force=True)
        QMessageBox.information(self,'导入完成',f'新增 {stats["新增"]} 张，重复 {stats["重复"]} 张，无效 {stats["无效"]} 张。')
    def clear_selected(self):
        cat=self.data_category.currentText();ses=self.data_session.currentText().strip()
        if QMessageBox.warning(self,'回收私人数据',f'把 {cat}/{ses} 的私人图片移入本地回收站？\n此操作不会删除公开训练图片。',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:dest=回收本地场景(cat,ses,数据目录)
        except (ValueError,OSError) as e:QMessageBox.warning(self,'操作失败',str(e));return
        self.refresh_data(force=True);QMessageBox.information(self,'已回收',f'已移到：\n{dest}\n可以从文件管理器恢复。')
    def clear_all(self):
        choice,ok=__import__('PySide6.QtWidgets',fromlist=['QInputDialog']).QInputDialog.getText(
            self,'清空全部私人数据','此操作会把六种手势的所有私人场景移至本地回收站。\n请输入“清空全部”确认：')
        if not ok or choice!='清空全部':return
        moved=0;errors=[]
        for c in 类别:
            folder=数据目录/c
            if folder.is_dir():
                for session in list(folder.iterdir()):
                    if not session.is_dir():continue
                    try:回收本地场景(c,session.name,数据目录);moved+=1
                    except (OSError,ValueError) as e:errors.append(str(e))
        self.refresh_data(force=True)
        QMessageBox.information(self,'回收结果',f'已回收 {moved} 个私人场景。'+('\n部分失败：'+';'.join(errors[:2]) if errors else ''))
    def open_folder(self,path):
        Path(path).mkdir(parents=True,exist_ok=True)
        if sys.platform=='win32':os.startfile(str(path))
        else:QMessageBox.information(self,'目录路径',str(path))
    def capture(self):
        self.stop_recognition()
        if self.cam:self.cam.release();self.cam=None
        dialog=CaptureDialog(self)
        try:dialog.exec()
        finally:self.open_camera();self.refresh_data(force=True)
    def start_training(self,mode):
        if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning:return
        scene=self.train_scene.currentText().strip()
        try:验证轮次(scene)
        except ValueError as e:QMessageBox.warning(self,'无效场景',str(e));return
        if self.running:self.stop_recognition()
        if mode=='focus' and not (模型目录/'正式模型.pt').exists():
            QMessageBox.warning(self,'需要模型','请先训练全部六类，再对单个类别进行专项强化');return
        target=self.focus_cat.currentText()
        msg=(f'使用场景 {scene} + 公开数据训练六分类 CNN。' if mode=='all' else f'专项强化 {target}，同时重放其他五类数据。')
        msg+='\n旧模型会备份。没有独立验证集，本次结果只供演示。\n确认开始？'
        if QMessageBox.question(self,'启动训练',msg)!=QMessageBox.StandardButton.Yes:return
        self.proc=QProcess(self)
        self.proc.setWorkingDirectory(str(根目录))
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        args=['-u','-m','手势系统.工作台训练','--mode',mode,'--sessions',scene,'--epochs',str(self.train_epoch.value()),
              '--device','cuda' if self.train_device.currentIndex() else 'cpu']
        if mode=='focus':args+=['--target',target]
        self.proc.readyReadStandardOutput.connect(self.read_training)
        self.proc.finished.connect(self.training_done)
        self.train_log.clear();self.train_log.append('启动：'+sys.executable+' '+' '.join(args))
        self.train_status.setText('训练中，界面仍可操作…')
        self.train_all.setEnabled(False);self.train_one.setEnabled(False);self.train_cancel.setEnabled(True)
        self.proc.start(sys.executable,args)
    def read_training(self):
        text=bytes(self.proc.readAllStandardOutput()).decode('utf-8',errors='replace')
        self.train_log.moveCursor(__import__('PySide6.QtGui',fromlist=['QTextCursor']).QTextCursor.MoveOperation.End)
        self.train_log.insertPlainText(text)
        self.train_log.ensureCursorVisible()
    def training_done(self,code,status):
        self.read_training()
        self.train_all.setEnabled(True);self.train_one.setEnabled(True);self.train_cancel.setEnabled(False)
        self.train_status.setText('✓ 训练完成' if code==0 else f'训练结束，退出码 {code}（请查看日志）')
        if code==0:self.reload_model()
    def stop_training(self):
        if not self.proc or self.proc.state()==QProcess.ProcessState.NotRunning:return
        if QMessageBox.question(self,'中止训练','确认中断训练？已完成的旧正式模型保持不变。')==QMessageBox.StandardButton.Yes:
            self.proc.terminate()
            QTimer.singleShot(3000,lambda:self.proc.kill() if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning else None)
    def closeEvent(self,e):
        if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning:
            QMessageBox.warning(self,'训练进行中','请先停止训练任务，再关闭程序。');e.ignore();return
        if self.cam:self.cam.release();self.cam=None
        self.camera_timer.stop();self.data_timer.stop()
        e.accept()


def run():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Gesture Studio')
    window=GestureWindow();window.show()
    QTimer.singleShot(0,window.apply_backdrop)
    return app.exec()
