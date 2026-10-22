"""Gesture Studio: PySide6 macOS-inspired Windows workbench.

This imitates macOS traffic-light window controls and translucent panels; it is
not Apple's system Liquid Glass compositor. No synthetic detection results.
"""
from __future__ import annotations
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QPoint, QTimer, QThread, Signal, QProcess, QProcessEnvironment, QFileSystemWatcher, QSize, QRectF, QEasingCurve, QPropertyAnimation, QParallelAnimationGroup, QAbstractAnimation, QByteArray
from PySide6.QtGui import (QColor,QFont,QIcon,QImage,QKeySequence,QLinearGradient,
                           QPainter,QPainterPath,QPixmap,QRadialGradient,QShortcut,QPen)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFrame,QLabel,QPushButton,
    QStackedWidget,QScrollArea,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QProgressBar,
    QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QMessageBox,QDialog,QTextEdit,
    QGraphicsDropShadowEffect,QSizePolicy,QGridLayout,QToolButton,QListView,QAbstractButton)

from .配置 import 根目录,数据目录,模型目录,输出目录,配置文件,类别,读取配置,建立运行目录
from .版本 import VERSION, DISPLAY_VERSION, APP_TITLE
from .控制 import 手势控制器
from .推理 import 手势推理器
from .预处理 import 获取识别矩形,裁剪手势
from .手部候选框 import 搜索候选手框,候选框平滑器
from .动作资源 import 素材路径,动作索引,动作列表
from .界面数据 import 验证设置,安全保存设置
from .工作台数据 import (样本汇总,场景明细,导入图片,回收本地场景,回收整个场景,验证轮次,验证快捷键,图片后缀,推荐新场景名称)
from .训练状态 import 训练记录状态
from .训练日志编码 import 训练日志解码器, 配置训练子进程编码
from .相机线程 import CameraWorker
from .公开资源线程 import PublicImportWorker
from .公开数据 import 导入公开子集
from .公开数据管理 import 公开数据状态, 回收公开数据
from .手部定位 import 包含定位资源,读取训练输入策略,策略标识
from .图片交互 import ImageControlDialog

NAVY='#25334C'; MUTED='#63718B'; BLUE='#3978EF'; GREEN='#1DAA79'

STYLES='''
* {font-family:"Segoe UI","Microsoft YaHei UI"; color:#263149; font-size:13px;}
QWidget#windowShell {background:transparent;}
QFrame#glass {background-color:rgba(255,255,255,194); border:1px solid rgba(255,255,255,232); border-radius:24px;}
QFrame#inner {background-color:rgba(247,249,255,210); border:1px solid rgba(220,228,246,150); border-radius:17px;}
QFrame#side {background-color:rgba(250,250,255,155); border:1px solid rgba(255,255,255,230); border-radius:22px;}
QPushButton {background-color:rgba(255,255,255,205); border:1px solid rgba(204,216,232,220); border-radius:13px; padding:0px 16px; min-height:42px; font-weight:600;}
QPushButton:hover {background-color:rgba(255,255,255,245); border-color:#B0C5E2;}
QPushButton:pressed {background-color:#DBE9FC;}
QPushButton:disabled {color:#9FAEC4; background-color:#E8EDF5;}
QPushButton#primary {background:#3978EF; color:white; border:none; border-radius:14px; padding:0px 20px; min-height:46px; font-size:14px;}
QPushButton#primary:hover {background:#2869D5;}
QPushButton#danger {color:#B34A59; border-color:#F0CBD2;}
QToolButton#navButton {background:transparent; border:0px; border-radius:12px; padding:0px 12px; min-height:44px; font-weight:600; text-align:left;}
QToolButton#navButton:hover {background:rgba(223,234,250,145);}
QToolButton#navButton:checked {background:rgba(216,232,252,220); color:#1E65CE;}
QLabel#title {font-size:25px; font-weight:700; color:#273752;}
QLabel#h2 {font-size:17px; font-weight:700; color:#263750;}
QLabel#meta {color:#708097; font-size:12px;}
QLabel#hero {font-size:32px; font-weight:700; color:#24334D;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {background:rgba(255,255,255,225); border:1px solid #D0DCEB; border-radius:12px; padding:7px 11px; min-height:27px; selection-background-color:#D8E8FF;}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus {border:1px solid #74A0ED;}
QComboBox {padding-right:36px;}
QComboBox::drop-down {subcontrol-origin:padding; subcontrol-position:top right; width:36px; border:0px; border-top-right-radius:12px; border-bottom-right-radius:12px;}
QComboBox::down-arrow {image:none; width:0px; height:0px;}
QComboBox:on {background:#FFFFFF; border-color:#74A0ED;}
QSpinBox::up-button,QDoubleSpinBox::up-button {width:24px; background:#EEF3FB; border:0px; border-top-right-radius:10px;}
QSpinBox::down-button,QDoubleSpinBox::down-button {width:24px; background:#EEF3FB; border:0px; border-bottom-right-radius:10px;}
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
    """真实透明圆角：先清空整个 RGBA 面，再仅向圆角路径内部绘制。"""
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(),QColor(0,0,0,0))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        radius=0 if self.window().isMaximized() else 25
        r=QRectF(self.rect().adjusted(1,1,-1,-1))
        path=QPainterPath();path.addRoundedRect(r,radius,radius)
        p.setClipPath(path)
        g=QLinearGradient(0,0,self.width(),self.height())
        g.setColorAt(0,QColor('#D6E8FF'));g.setColorAt(.45,QColor('#F6F6FC'));g.setColorAt(1,QColor('#EFE1F5'))
        p.fillPath(path,g)
        for x,y,rad,c in [(.10,.12,.6,QColor(144,190,252,93)),(.84,.14,.6,QColor(238,181,224,85)),(.74,.86,.5,QColor(172,196,255,80))]:
            area=int(min(self.width(),self.height())*rad)
            brush=QRadialGradient(self.width()*x,self.height()*y,area)
            brush.setColorAt(0,c);brush.setColorAt(1,QColor(c.red(),c.green(),c.blue(),0))
            p.fillPath(path,brush)
        p.setClipping(False)
        p.setPen(QPen(QColor(255,255,255,170),1.3));p.drawRoundedRect(r,radius,radius)


# 同一组 24px 线性 SVG，避免混用字体符号、emoji 和不同来源图标。
ICONS={
 'menu':'<path d="M4 7h16M4 12h16M4 17h16"/>',
 'home':'<path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-8h6v8"/>',
 'data':'<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8.5" cy="9" r="1.4"/><path d="m4 17 5-5 4 4 3-3 4 4"/>',
 'train':'<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
 'model':'<path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/>',
 'settings':'<path d="M12 3v2m0 14v2M3 12h2m14 0h2M5.7 5.7l1.4 1.4m9.8 9.8 1.4 1.4M18.3 5.7l-1.4 1.4m-9.8 9.8-1.4 1.4"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.7"/>',
}


def unified_icon(name,color='#53637D',size=22):
    """矢量图标按屏幕比例渲染，折叠/展开都不替换字符。"""
    if name not in ICONS:raise ValueError('未知导航图标：'+str(name))
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'
    renderer=QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pix=QPixmap(size*2,size*2);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix)
    renderer.render(painter,QRectF(0,0,size*2,size*2))
    painter.end();pix.setDevicePixelRatio(2)
    return QIcon(pix)


class GlassComboBox(QComboBox):
    """统一编辑框、箭头、下拉列表；禁止回退到原生 Windows 下拉边框。"""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.setMaxVisibleItems(9)
        view=QListView(self)
        view.setObjectName('glassOptions')
        view.setUniformItemSizes(True)
        view.setSpacing(3)
        view.setStyleSheet("""
            QListView#glassOptions {background:#F7F9FE; border:1px solid #CDDBEC;
                border-radius:12px; padding:7px; outline:none; font-size:13px;}
            QListView#glassOptions::item {min-height:32px; padding-left:10px;
                border:0px; border-radius:8px; color:#293854;}
            QListView#glassOptions::item:hover {background:#EDF3FD;}
            QListView#glassOptions::item:selected {background:#DCEBFE; color:#2066C5;}
        """)
        self.setView(view)
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor('#657993'),1.75))
        x=self.width()-22;y=self.height()/2
        path=QPainterPath();path.moveTo(x-4,y-2);path.lineTo(x,y+2);path.lineTo(x+4,y-2)
        p.drawPath(path)
        p.end()


class TrafficLight(QAbstractButton):
    """不继承 QPushButton 的全局最小高度和 padding，三色圆点永远按圆形绘制。"""
    def __init__(self,color,tooltip,callback,parent=None):
        super().__init__(parent)
        self.color=QColor(color)
        self.setFixedSize(20,20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip);self.setAccessibleName(tooltip)
        self.clicked.connect(callback)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        p.setPen(QPen(QColor(48,51,61,60),0.75))
        color=QColor(self.color)
        if not self.isEnabled():color.setAlpha(90)
        elif self.underMouse():color=color.lighter(109)
        p.setBrush(color)
        p.drawEllipse(QRectF(3,3,14,14))
        p.end()


class CornerResizeHandle(QWidget):
    """透明尺寸调整控件，不使用会在某些 Windows 主题绘出白底的 QSizeGrip。"""
    def __init__(self,host):
        super().__init__(host);self.host=host
        self.setFixedSize(23,23)
        self.setToolTip('拖动调整窗口大小')
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and not self.host.isMaximized():
            handle=self.host.windowHandle()
            if handle and handle.startSystemResize(Qt.Edge.RightEdge|Qt.Edge.BottomEdge):
                event.accept();return
        super().mousePressEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(124,142,167,115),1.5))
        for k in (0,5,10):p.drawLine(11+k,19,19,11+k)
        p.end()


class Titlebar(QFrame):
    def __init__(self,parent):
        super().__init__(parent);self.host=parent;self.setFixedHeight(53)
        l=QHBoxLayout(self);l.setContentsMargins(18,6,18,4);l.setSpacing(10)
        self.lights=[]
        for color,func,tooltip in [('#FF5F57',parent.close,'关闭'),('#FEBC2E',parent.showMinimized,'最小化'),('#28C840',parent.toggle_max,'最大化 / 还原')]:
            light=TrafficLight(color,tooltip,func,self)
            self.lights.append(light);l.addWidget(light)
        l.addSpacing(14)
        brand=label('●  Gesture Studio',13);brand.setStyleSheet('color:#354766;font-weight:700;')
        l.addWidget(brand);l.addStretch()
        self.name=label('手势识别 · 本地工作台',dim=True);l.addWidget(self.name)
        l.addStretch()
        l.addWidget(label(DISPLAY_VERSION,dim=True))
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:self._drag=e.globalPosition().toPoint()-self.host.pos()
    def mouseMoveEvent(self,e):
        if e.buttons() & Qt.MouseButton.LeftButton and hasattr(self,'_drag'):
            if self.host.isMaximized():return
            self.host.move(e.globalPosition().toPoint()-self._drag)
    def mouseDoubleClickEvent(self,e):self.host.toggle_max()


class HandSetupWorker(QThread):
    message=Signal(str)
    stage=Signal(str)
    progress=Signal(int,int)
    succeeded=Signal(bool)
    failed=Signal(str)
    def run(self):
        try:
            from .手部组件安装 import 安装
            needs_restart=安装(on_progress=self.message.emit,on_stage=self.stage.emit,
                  on_bytes=lambda done,total:self.progress.emit(done,total))
            self.succeeded.emit(bool(needs_restart))
        except Exception as exc:self.failed.emit(str(exc))


class CaptureDialog(QDialog):
    """Single owner of the camera while capture is open. User-defined shortcuts are scoped here."""
    def __init__(self,host):
        super().__init__(host)
        self.host=host;self.setWindowTitle('采集新图片 · 手势工作台')
        self.resize(960,730);self.setMinimumSize(760,600)
        self.setStyleSheet(STYLES+'QDialog {background:#EEF4FD;}')
        self.cam=None;self.capture_worker=None;self.camera_ready=False
        self.active=False;self.preparing=False;self.seq=[];self.index=0;self.saved=0;self.last_saved=0
        self.countdown_timer=QTimer(self);self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self._countdown_tick);self.countdown_end=0.
        layout=QVBoxLayout(self);layout.setContentsMargins(22,18,22,18);layout.setSpacing(12)
        layout.addWidget(label('摄像头采集',title=True))
        controls=QGridLayout();controls.setHorizontalSpacing(12)
        self.pick=GlassComboBox();self.pick.addItems(['全部六类']+类别)
        self.scene=QLineEdit(推荐新场景名称(数据目录));self.scene.setPlaceholderText('自动推荐下一个新场景，例如 场景05')
        self.scenes=QSpinBox();self.scenes.setRange(1,30);self.scenes.setValue(1)
        self.fps=QDoubleSpinBox();self.fps.setRange(.2,12);self.fps.setSingleStep(.5);self.fps.setValue(4);self.fps.setSuffix(' 张/秒')
        self.count=QSpinBox();self.count.setRange(1,10000);self.count.setValue(30)
        self.hot_start=QLineEdit('S');self.hot_stop=QLineEdit('E')
        widgets=[('手势类别',self.pick),('场景起始名称',self.scene),('场景数量',self.scenes),('每秒张数',self.fps),('每类张数',self.count),('开始键',self.hot_start),('停止键',self.hot_stop)]
        for i,(name,w) in enumerate(widgets):
            controls.addWidget(label(name,dim=True),i//4*2,i%4)
            controls.addWidget(w,i//4*2+1,i%4)
        layout.addLayout(controls)
        self.hand_capture=QCheckBox('采用手部关键点定位采集：只保存手附近区域（需先在设置页安装定位组件）')
        self.hand_capture.setChecked(False)
        layout.addWidget(self.hand_capture)
        layout.addWidget(label('建议把手完整放进绿色区域，手离镜头适当远；头和上半身可出现，但不要遮挡手。开启关键点采集后，必须在训练页选相同裁剪模式并从零训练。',dim=True))
        self.preview=QLabel('摄像头初始化中…');self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(330);self.preview.setStyleSheet('background:#13253B;color:white;border-radius:18px;')
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        layout.addWidget(self.preview,1)
        self.capture_prompt=label('准备采集：先将手伸入识别区域',title=True)
        self.capture_prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_prompt.setMinimumHeight(76)
        self.capture_prompt.setStyleSheet('QLabel {background:#233D64; color:white; border-radius:15px; font-size:21px; font-weight:700; padding:9px;}')
        layout.addWidget(self.capture_prompt)
        self.info=label('开始后逐类拍摄；到达张数自动切换到下一个手势或场景。',dim=True)
        layout.addWidget(self.info)
        buttons=QHBoxLayout()
        self.go=btn('▶ 开始采集（3秒准备）',self.start,primary=True)
        self.stop=btn('■ 暂停采集',self.pause)
        self.done_btn=btn('✓ 完成采集 · 返回数据页',self.accept,primary=True)
        self.done_btn.setStyleSheet('QPushButton {background:#148B68; color:white; border:0; border-radius:14px; min-height:48px; padding:0px 18px; font-weight:700;}')
        self.done_btn.setVisible(False)
        buttons.addWidget(self.go,2);buttons.addWidget(self.stop,1);buttons.addStretch()
        buttons.addWidget(self.done_btn,2)
        layout.addLayout(buttons)
        self.shortcuts=[];self.hot_start.setText('S');self.hot_stop.setText('E')
        self.hand_capture.toggled.connect(self._switch_capture_mode)
        self.open_camera()
    def _switch_capture_mode(self,checked):
        if self.active or self.preparing or self.seq:
            QMessageBox.information(self,'先结束采集','正在采集时不能修改手部裁剪模式。')
            self.hand_capture.blockSignals(True);self.hand_capture.setChecked(not checked);self.hand_capture.blockSignals(False)
            return
        if checked and not 包含定位资源():
            QMessageBox.warning(self,'缺少定位组件','请先返回设置页，点击“安装手部定位组件”。')
            self.hand_capture.blockSignals(True);self.hand_capture.setChecked(False);self.hand_capture.blockSignals(False)
            return
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.requestInterruption()
            if not self.capture_worker.wait(3500):
                QMessageBox.warning(self,'摄像头未释放','摄像头仍在关闭，请重新打开采集窗口。');return
        self.open_camera()
    def open_camera(self):
        self.capture_worker=CameraWorker(int(self.host.settings.get('摄像头编号',0)),
            33,float(self.host.settings.get('识别区域占画面短边比例',.78)),capture_mode=True,
            hand_capture=self.hand_capture.isChecked(),parent=self)
        self.capture_worker.camera_state.connect(self._camera_state)
        self.capture_worker.frame_ready.connect(self.tick)
        self.capture_worker.start()
    def _camera_state(self,ready,message):
        self.camera_ready=ready
        if not ready:
            self.active=False;self._cancel_countdown();self.info.setText(message)
            if self.index<len(self.seq) or not self.seq:self.go.setEnabled(True)
    def bind_shortcuts(self):
        for item in self.shortcuts:item.setEnabled(False);item.deleteLater()
        self.shortcuts=[]
        start,stop=验证快捷键(self.hot_start.text().strip(),self.hot_stop.text().strip())
        for key,fn in [(start,self.start),(stop,self.pause)]:
            sc=QShortcut(QKeySequence(key),self);sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(fn);self.shortcuts.append(sc)
        return start,stop
    def start(self):
        if not self.camera_ready:QMessageBox.warning(self,'摄像头','没有可用的摄像头');return
        if self.seq and self.index>=len(self.seq):self.accept();return
        if self.active or self.preparing:return
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
                proposed=[(c,s) for s in session_names for c in classes]
                # Prevent accidental blending of independent sessions with previously collected ones.
                occupied=[f'{c}/{s}' for c,s in proposed if (数据目录/c/s).is_dir() and any((数据目录/c/s).iterdir())]
                if occupied:
                    raise ValueError('目标采集目录已存在图片：'+', '.join(occupied[:4])+'。请更换场景名称，防止混入旧轮次。')
                self.seq=proposed
                for field in [self.pick,self.scene,self.scenes,self.fps,self.count,self.hot_start,self.hot_stop,self.hand_capture]:field.setEnabled(False)
                self.info.setText(f'采集队列已建立，{len(self.seq)} 个手势/场景组合；{start} 开始 / {stop} 停止')
            except ValueError as e:QMessageBox.warning(self,'参数错误',str(e));return
        self._begin_countdown()

    def _begin_countdown(self):
        if not self.seq or self.index>=len(self.seq):return
        gesture,session=self.seq[self.index]
        self.preparing=True;self.active=False;self.countdown_end=time.monotonic()+3.0
        self.capture_prompt.setText(f'请准备【{gesture}】  ·  {session}  ·  3 秒后采集')
        self.info.setText(f'第 {self.index+1}/{len(self.seq)} 组：保持【{gesture}】在框内；倒计时期间不会保存图片')
        self.go.setEnabled(False);self.go.setText('准备中：3…')
        self.countdown_timer.start()

    def _countdown_tick(self):
        if not self.preparing:return
        remaining=self.countdown_end-time.monotonic()
        gesture,session=self.seq[self.index]
        if remaining>0:
            seconds=max(1,__import__('math').ceil(remaining))
            self.capture_prompt.setText(f'请做【{gesture}】  ·  {session}  ·  {seconds} 秒后采集')
            self.go.setText(f'准备中：{seconds}…')
            return
        self._cancel_countdown()
        if not self.camera_ready:return
        self.active=True;self.last_saved=0
        self.go.setText('● 正在采集');self.go.setEnabled(False)
        self.capture_prompt.setText(f'● 正在拍摄【{gesture}】  ·  {session}')

    def _cancel_countdown(self):
        self.preparing=False;self.countdown_timer.stop()

    def pause(self):
        self._cancel_countdown();self.active=False
        if self.seq and self.index>=len(self.seq):return
        self.go.setEnabled(True);self.go.setText('▶ 继续采集（3秒准备）')
        self.capture_prompt.setText('已暂停 · 已拍照片均已保存')
        self.info.setText(f'已暂停。进度：{self.index+1}/{len(self.seq)}，当前 {self.saved}/{self.count.value()} 张。' if self.seq else '尚未启动采集')
    def tick(self,image,payload):
        try:
            frame=payload.get('raw_frame')
            if frame is None:return
            # Refresh preview even when a sample is skipped because the detected hand is absent.
            q=QPixmap.fromImage(image)
            self.preview.setPixmap(q.scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            x1,y1,x2,y2=获取识别矩形(frame,float(self.host.settings.get('识别区域占画面短边比例',.78)))
            if self.active and self.index<len(self.seq):
                now=time.monotonic()
                if now-self.last_saved>=1./self.fps.value():
                    gesture,session=self.seq[self.index]
                    hand_box=payload.get('hand_box')
                    if self.hand_capture.isChecked():
                        # Positive classes: never silently save a whole body when hand detection misses.
                        if gesture!='无手' and hand_box is None:
                            self.info.setText(f'等待检测到【{gesture}】的手部… 请在绿色框内保持完整手掌')
                            return
                        # For the negative class, a detected hand would be a mislabeled sample.
                        if gesture=='无手' and hand_box is not None:
                            self.info.setText('无手采集中：检测到手，请把双手移出画面后再采集')
                            return
                        if hand_box is not None:
                            a,b,c,d=hand_box
                            import cv2
                            from PIL import Image
                            cropped=Image.fromarray(cv2.cvtColor(frame[b:d,a:c],cv2.COLOR_BGR2RGB))
                        else:
                            cropped=裁剪手势(frame,float(self.host.settings.get('识别区域占画面短边比例',.78)))
                    else:
                        cropped=裁剪手势(frame,float(self.host.settings.get('识别区域占画面短边比例',.78)))
                    folder=数据目录/gesture/session;folder.mkdir(parents=True,exist_ok=True)
                    name=folder/f'cap_{time.time_ns()}_{self.saved+1:05d}.jpg'
                    if self.hand_capture.isChecked():
                        marker=folder/'.输入策略.json'
                        if not marker.exists():
                            marker.write_text(json.dumps({'输入策略':策略标识,'来源':'手部定位采集'},ensure_ascii=False),encoding='utf-8')
                    cropped.save(name,quality=92)
                    self.saved+=1;self.last_saved=now
                    self.info.setText(f'正在拍摄 {gesture} / {session}  ·  {self.saved}/{self.count.value()} 张  ·  任务 {self.index+1}/{len(self.seq)}')
                    if self.saved>=self.count.value():
                        self.saved=0;self.index+=1;self.active=False
                        if self.index==len(self.seq):
                            self.info.setText('✓ 六类/全部场景采集完成，图片已保存；点击绿色按钮返回数据页。')
                            self.capture_prompt.setText('✓ 全部采集完成')
                            self.go.setVisible(False);self.stop.setVisible(False)
                            self.done_btn.setVisible(True);self.done_btn.setFocus()
                        else:
                            c,s=self.seq[self.index]
                            self.capture_prompt.setText(f'下一组：请准备【{c}】 · {s}')
                            self.info.setText(f'✓ 上一组完成！请先调整姿势为【{c}】，点击下一组后还有 3 秒准备时间。')
                            self.go.setEnabled(True);self.go.setText('▶ 开始下一组（3秒准备）')
        finally:
            if self.capture_worker:self.capture_worker.acknowledge()
    def done(self,result):
        self._cancel_countdown()
        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.requestInterruption()
            if not self.capture_worker.wait(2500):
                QMessageBox.warning(self,'摄像头忙','摄像头仍在关闭，请稍后再试。')
                return
        super().done(result)


class GestureWindow(QWidget):
    tabs=['首页','数据','训练','模型','设置']
    def __init__(self):
        super().__init__()
        建立运行目录()
        self.settings=读取配置()
        self.setWindowTitle(APP_TITLE)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground,True)
        self.setAutoFillBackground(False)
        self.resize(1350,820);self.setMinimumSize(1080,680)
        self.running=False;self.camera_worker=None;self.camera_online=False;self.infer=None
        self.lastcat=None;self.last_action='—';self._pending_capture=False;self._reopen_camera=False
        self.image_dialog=None
        self.fps_count=0;self.fps_start=time.monotonic();self.last_fps=0
        self.ctrl=手势控制器(int(self.settings['稳定帧数']),int(self.settings['解除锁定帧数']),float(self.settings['触发冷却秒数']))
        self.smoother=候选框平滑器()
        self.bg=Background(self)
        self.bg.setObjectName('windowShell')
        self.bg.setStyleSheet(STYLES)
        self.bg.setGeometry(self.rect())
        self.build_ui();self.load_model();self.open_camera()
        self.data_timer=QTimer(self);self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(1800)
        self.fs_watcher=QFileSystemWatcher(self);self.fs_watcher.directoryChanged.connect(self.refresh_data)
        self.fs_watcher.fileChanged.connect(self.refresh_data)
        self.refresh_data()
        self._region_scheduled=False
        self.apply_backdrop()
        QTimer.singleShot(0,self._set_native_corner_region)
    def resizeEvent(self,e):
        self.bg.setGeometry(self.rect());self.bg.update();super().resizeEvent(e)
        if not getattr(self,'_region_scheduled',False):
            self._region_scheduled=True
            QTimer.singleShot(0,self._set_native_corner_region)
    def apply_backdrop(self):
        """Windows DWM 背景不能涂满无边框 HWND，否则四角会成为矩形白底。"""
        if sys.platform!='win32':return
        try:
            hwnd=ctypes.c_void_p(int(self.winId()))
            # DWM_SYSTEMBACKDROP_TYPE: 1=NONE, 3=TRANSIENTWINDOW/Acrylic。
            # 顶层 HWND 不添加整窗 Acrylic，透过 WA_TranslucentBackground 保留真透明角。
            off=ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,38,ctypes.byref(off),ctypes.sizeof(off))
            # DWMWA_WINDOW_CORNER_PREFERENCE: 2=ROUND（系统支持时）。
            corners=ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,33,ctypes.byref(corners),ctypes.sizeof(corners))
        except (OSError,AttributeError,ValueError):pass
    def _set_native_corner_region(self):
        """Qt 的内容圆角 + Win32 真实窗口形状；两层裁剪确保四角无原生白色矩形。"""
        self._region_scheduled=False
        if sys.platform!='win32':return
        try:
            hwnd=ctypes.c_void_p(int(self.winId()))
            user32=ctypes.windll.user32;gdi32=ctypes.windll.gdi32
            user32.SetWindowRgn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
            user32.SetWindowRgn.restype=ctypes.c_int
            if self.isMaximized():
                user32.SetWindowRgn(hwnd,None,True);return
            class RECT(ctypes.Structure):
                _fields_=[('left',ctypes.c_long),('top',ctypes.c_long),('right',ctypes.c_long),('bottom',ctypes.c_long)]
            rect=RECT()
            if not user32.GetWindowRect(hwnd,ctypes.byref(rect)):return
            w=rect.right-rect.left;h=rect.bottom-rect.top
            if w<=0 or h<=0:return
            dpi=user32.GetDpiForWindow(hwnd) if hasattr(user32,'GetDpiForWindow') else 96
            diameter=max(8,round(50*dpi/96))
            gdi32.CreateRoundRectRgn.argtypes=[ctypes.c_int]*6
            gdi32.CreateRoundRectRgn.restype=ctypes.c_void_p
            region=gdi32.CreateRoundRectRgn(0,0,w+1,h+1,diameter,diameter)
            if not region:return
            if not user32.SetWindowRgn(hwnd,region,True):
                gdi32.DeleteObject(ctypes.c_void_p(region))
        except (OSError,AttributeError,ValueError):
            pass
    def toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
        self.bg.update()
        QTimer.singleShot(0,self._set_native_corner_region)
    def build_ui(self):
        outer=QVBoxLayout(self.bg);outer.setContentsMargins(14,6,14,15);outer.setSpacing(4)
        self.titlebar=Titlebar(self);outer.addWidget(self.titlebar)
        row=QHBoxLayout();row.setSpacing(15);outer.addLayout(row,1)
        self.side=QFrame();self.side.setObjectName('side')
        self.side.setMinimumWidth(68);self.side.setMaximumWidth(68)
        sidebar=QVBoxLayout(self.side);sidebar.setContentsMargins(7,12,7,13);sidebar.setSpacing(8)
        self.collapsed=True
        self.hamburger=QToolButton();self.hamburger.setObjectName('navButton')
        self.hamburger.setIcon(unified_icon('menu'));self.hamburger.setIconSize(QSize(22,22))
        self.hamburger.setToolTip('展开 / 收起导航栏')
        self.hamburger.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.hamburger.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hamburger.clicked.connect(self.toggle_nav)
        sidebar.addWidget(self.hamburger)
        self.navbuttons=[]
        for idx,(name,icon_name) in enumerate(zip(self.tabs,['home','data','train','model','settings'])):
            b=QToolButton();b.setObjectName('navButton');b.setCheckable(True)
            b.setIcon(unified_icon(icon_name));b.setIconSize(QSize(22,22))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _,i=idx:self.set_page(i))
            b.setToolTip(name);sidebar.addWidget(b);self.navbuttons.append((b,icon_name,name))
        sidebar.addStretch();sidebar.addWidget(label(DISPLAY_VERSION,dim=True))
        self.nav_transition=QParallelAnimationGroup(self)
        self.nav_min=QPropertyAnimation(self.side,b'minimumWidth',self)
        self.nav_max=QPropertyAnimation(self.side,b'maximumWidth',self)
        for motion in (self.nav_min,self.nav_max):
            motion.setDuration(185)
            motion.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.nav_transition.addAnimation(motion)
        self.nav_transition.finished.connect(self._sync_navigation)
        row.addWidget(self.side)
        right=QVBoxLayout();right.setSpacing(10);row.addLayout(right,1)
        top=QHBoxLayout();self.heading=label('首页');self.heading.setObjectName('title')
        top.addWidget(self.heading);top.addStretch()
        self.status=label('● 本地 · 正在连接',dim=True);top.addWidget(self.status)
        right.addLayout(top)
        self.stack=QStackedWidget();right.addWidget(self.stack,1)
        self.make_home();self.make_data();self.make_train();self.make_model();self.make_settings()
        footer=QHBoxLayout();footer.addWidget(label('Gesture Studio · 本地运行工作台',dim=True));footer.addStretch()
        footer.addWidget(label('摄像头与私人图片不会自动上传',dim=True));footer.addWidget(CornerResizeHandle(self));right.addLayout(footer)
        self.set_page(0)
    def _sync_navigation(self):
        style=(Qt.ToolButtonStyle.ToolButtonIconOnly if self.collapsed
               else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for b,_,name in self.navbuttons:
            b.setText('' if self.collapsed else name)
            b.setToolButtonStyle(style)
        self.hamburger.setText('' if self.collapsed else '收起导航')
        self.hamburger.setToolButtonStyle(style)

    def toggle_nav(self):
        # 动画过程中不重新排版文本；完成后才切换图标旁的文字。
        if self.nav_transition.state()==QAbstractAnimation.State.Running:
            self.nav_transition.stop()
        start=self.side.width()
        self.collapsed=not self.collapsed
        if self.collapsed:
            self._sync_navigation()
        target=68 if self.collapsed else 196
        for motion in (self.nav_min,self.nav_max):
            motion.setStartValue(start);motion.setEndValue(target)
        self.nav_transition.start()
    def set_page(self,index):
        if index!=0 and self.running:self.stop_recognition()
        if self.camera_worker:self.camera_worker.preview_enabled=(index==0)
        self.stack.setCurrentIndex(index);self.heading.setText(self.tabs[index])
        for i,(b,icon_name,_) in enumerate(self.navbuttons):
            b.setChecked(i==index)
            b.setIcon(unified_icon(icon_name,'#2E74DC' if i==index else '#53637D'))
        if index==1:self.refresh_data(force=True)
        if index==2:
            self.refresh_data(force=True);self.refresh_training_status()
        if index==3:self.refresh_model()
    def page(self,subtitle):
        body=QWidget();v=QVBoxLayout(body);v.setContentsMargins(3,3,12,12);v.setSpacing(14)
        v.addWidget(label(subtitle,dim=True));self.stack.addWidget(body)
        return v
    def make_home(self):
        v=self.page('用摄像头完成手势交互 · 当前识别结果优先展示')
        controls=QHBoxLayout();controls.addStretch()
        controls.addWidget(btn('打开图片交互窗口',self.open_image_dialog))
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
    def _scroll_content(self,root):
        """较低的虚拟机分辨率也能看到页面下方按钮，不依赖窗口被强行拉高。"""
        scroller=QScrollArea();scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        scroller.setStyleSheet('QScrollArea {background:transparent;border:0;} QScrollArea > QWidget > QWidget {background:transparent;}')
        inner=QWidget();layout=QVBoxLayout(inner)
        layout.setContentsMargins(3,4,12,10);layout.setSpacing(14)
        scroller.setWidget(inner);root.addWidget(scroller,1)
        return layout

    def make_data(self):
        base=self.page('摄像头采集、批次明细、图片导入及回收 · 所有私人样本仅存本机')
        v=self._scroll_content(base)
        summary=QHBoxLayout();v.addLayout(summary)
        self.totals=[]
        for name in ('公开训练图片','私人采集图片','采集场景数'):
            card=panel();card.layout().addWidget(label(name,dim=True));number=label('0',size=24)
            card.layout().addWidget(number);summary.addWidget(card,1);self.totals.append(number)
        capture=panel();v.addWidget(capture)
        capture.layout().addWidget(label('摄像头采集',title=True))
        line=QHBoxLayout();capture.layout().addLayout(line)
        line.addWidget(label('设置采集场景、动作、张数、频率和快捷键，直接保存到私人样本文件夹。',dim=True),1)
        line.addWidget(btn('打开摄像头采集',self.capture,primary=True))
        matrix=panel();v.addWidget(matrix)
        matrix.layout().addWidget(label('采集批次 · 场景 × 手势',title=True))
        matrix.layout().addWidget(label('单击表格中的数字选中对应手势；可只回收这一类，也可回收同一场景的全部六类。',dim=True))
        self.batch_table=QTableWidget(0,8)
        self.batch_table.setHorizontalHeaderLabels(['场景','合计']+类别)
        self.batch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.batch_table.verticalHeader().hide()
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.batch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.batch_table.setMinimumHeight(205)
        self.batch_table.cellClicked.connect(self._choose_batch_cell)
        matrix.layout().addWidget(self.batch_table)
        line=QHBoxLayout();matrix.layout().addLayout(line)
        self.data_session=GlassComboBox();self.data_session.setEditable(True)
        self.data_session.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.data_session.setEditText('场景01')
        self.data_category=GlassComboBox();self.data_category.addItems(类别)
        line.addWidget(label('选中场景'));line.addWidget(self.data_session,2)
        line.addWidget(label('手势'));line.addWidget(self.data_category,2)
        line=QHBoxLayout();matrix.layout().addLayout(line)
        line.addWidget(btn('回收所选手势批次',self.clear_selected,danger=True))
        line.addWidget(btn('回收整个场景',self.clear_scene,danger=True))
        line.addStretch()
        line.addWidget(btn('打开回收站',lambda:self.open_folder(数据目录/'回收站')))
        imports=panel();v.addWidget(imports)
        imports.layout().addWidget(label('导入与自动监控',title=True))
        imports.layout().addWidget(label('使用上方的场景和手势选择目标目录；支持直接复制图片到文件夹。',dim=True))
        line=QHBoxLayout();imports.layout().addLayout(line)
        line.addWidget(btn('导入图片',self.import_files))
        line.addWidget(btn('导入文件夹',self.import_directory))
        line.addWidget(btn('打开数据目录',lambda:self.open_folder(数据目录)))
        line.addStretch()
        self.data_note=label('每约 2 秒重新统计；回收的私人照片保留在本地回收站。',dim=True)
        imports.layout().addWidget(self.data_note)
        public=panel();v.addWidget(public)
        public.layout().addWidget(label('HaGRID 公开训练数据 · 手动获取',title=True))
        public.layout().addWidget(label('不自动下载。点击下方按钮才会联网下载约 402 MB 的公开 ZIP，校验 SHA256 后只导入五类手部裁剪样本。已有公开数据不会重复下载。',dim=True))
        line=QHBoxLayout();public.layout().addLayout(line)
        self.public_download_btn=btn('下载并导入公开数据',self.download_public)
        line.addWidget(self.public_download_btn)
        self.public_import_btn=btn('从本地 ZIP 导入',self.import_public_zip)
        line.addWidget(self.public_import_btn)
        self.public_delete_btn=btn('删除公开数据',self.delete_public,danger=True)
        line.addWidget(self.public_delete_btn)
        self.public_cancel_btn=btn('取消下载',self.cancel_public);self.public_cancel_btn.setEnabled(False)
        line.addWidget(self.public_cancel_btn);line.addStretch()
        self.public_progress=QProgressBar();self.public_progress.setRange(0,100);self.public_progress.setValue(0)
        public.layout().addWidget(self.public_progress)
        self.public_status=label('正在检查公开数据安装状态…',dim=True)
        public.layout().addWidget(self.public_status)
        self.public_worker=None
        self.refresh_public_state()
        v.addStretch()

    def refresh_public_state(self):
        if not hasattr(self,'public_download_btn'):return
        state=公开数据状态(数据目录)
        busy=bool(self.public_worker and self.public_worker.isRunning())
        installed=state['状态']=='已安装'
        incomplete=state['状态']=='残留或不完整'
        self.public_download_btn.setVisible(not installed)
        self.public_download_btn.setText('清理残留并重新下载' if incomplete else '下载并导入公开数据')
        self.public_import_btn.setVisible(not installed)
        self.public_delete_btn.setVisible(installed or incomplete)
        self.public_delete_btn.setText('清理残留' if incomplete else '删除公开数据')
        self.public_delete_btn.setEnabled(not busy and not self.training_active())
        self.public_download_btn.setEnabled(not busy)
        self.public_import_btn.setEnabled(not busy)
        if not busy:
            if installed:
                self.public_status.setText(f'✓ 已安装公开数据：{state["合计"]} 张；可手动删除或在训练页选择是否参与。')
                self.public_progress.setRange(0,100);self.public_progress.setValue(100)
            elif incomplete:
                self.public_status.setText('检测到旧版残留或不完整数据：'+','.join(state['原因'])+'。可点击清理残留并重新下载，旧文件先移入本地回收站。')
                self.public_progress.setRange(0,100);self.public_progress.setValue(0)
            else:
                self.public_status.setText('未安装公开数据；仅点击下载后才会联网。')
                self.public_progress.setRange(0,100);self.public_progress.setValue(0)

    def delete_public(self):
        if self.training_active():
            QMessageBox.warning(self,'训练进行中','训练期间不能删除公开数据。');return
        if self.public_worker and self.public_worker.isRunning():return
        state=公开数据状态(数据目录)
        if state['状态']=='未安装':self.refresh_public_state();return
        if QMessageBox.question(self,'删除公开数据',
            f'将本地公开训练数据（{state["合计"]} 张）和来源清单移入本地回收站？\n'
            '不会删除私人采集图片、模型或旧模型权重。')!=QMessageBox.StandardButton.Yes:return
        try:
            dest=回收公开数据(数据目录)
        except (OSError,ValueError) as err:
            QMessageBox.warning(self,'删除失败',str(err));return
        self.refresh_data(force=True)
        self.refresh_public_state()
        QMessageBox.information(self,'公开数据已移入回收站','备份目录：'+str(dest))

    def _public_progress(self,done,total):
        self.public_status.setText(f'公开数据已下载 {done/1048576:.1f} MB'+(f' / {total/1048576:.1f} MB' if total>0 else '；总大小未知'))
        if total>0:
            self.public_progress.setRange(0,100)
            self.public_progress.setValue(min(100,round(done*100/total)))
        else:self.public_progress.setRange(0,0)

    def _public_phase(self,message):
        self.public_status.setText(message)
        self.public_progress.setRange(0,0)

    def download_public(self):
        if self.training_active():
            QMessageBox.warning(self,'训练进行中','请先完成训练再导入公开数据。');return
        if self.public_worker and self.public_worker.isRunning():return
        state=公开数据状态(数据目录)
        if state['状态']=='已安装':self.refresh_public_state();return
        if state['状态']=='残留或不完整':
            if QMessageBox.question(self,'修复公开数据残留',
                '发现旧版公开数据残留或目录不完整。是否先移动至本地回收站，再重新下载？'
                '该操作只处理公开训练目录和来源清单。')!=QMessageBox.StandardButton.Yes:return
            try:回收公开数据(数据目录)
            except (OSError,ValueError) as err:
                QMessageBox.warning(self,'清理残留失败',str(err));return
        if QMessageBox.question(self,'手动下载公开数据',
            '这将从 Hugging Face 下载约 402 MB 的 HaGRID 数据 ZIP，校验后导入五类图片。继续？')!=QMessageBox.StandardButton.Yes:
            self.refresh_public_state();return
        self._start_public_worker(PublicImportWorker(self))

    def _start_public_worker(self,worker):
        self.public_worker=worker
        self.public_download_btn.setEnabled(False)
        self.public_import_btn.setEnabled(False)
        self.public_delete_btn.setEnabled(False)
        self.public_cancel_btn.setEnabled(True)
        self.public_progress.setRange(0,0)
        self.public_status.setText('正在准备公开数据导入…')
        worker.progress.connect(self._public_progress)
        worker.phase.connect(self._public_phase)
        worker.success.connect(self._public_success)
        worker.failed.connect(self._public_failed)
        worker.finished.connect(self._public_finished)
        worker.start()

    def _public_success(self,stats):
        self.refresh_data(force=True)
        self.public_status.setText('✓ 公开数据导入完成：'+str(stats.get('各类数量',{})))
        QMessageBox.information(self,'导入完成','成功导入：'+str(stats.get('各类数量',{})))

    def _public_failed(self,message):
        self.public_status.setText('导入中止：'+message[:170])
        QMessageBox.warning(self,'公开数据导入未完成',message[:750])

    def _public_finished(self):
        self.public_cancel_btn.setEnabled(False)
        worker=self.public_worker;self.public_worker=None
        if worker:worker.deleteLater()
        self.refresh_public_state()

    def cancel_public(self):
        if self.public_worker:
            self.public_worker.request_cancel()
            self.public_status.setText('正在取消下载…')
            self.public_cancel_btn.setEnabled(False)

    def import_public_zip(self):
        if self.training_active():
            QMessageBox.warning(self,'训练进行中','请先完成训练再导入。');return
        if self.public_worker and self.public_worker.isRunning():return
        state=公开数据状态(数据目录)
        if state['状态']!='未安装':
            QMessageBox.warning(self,'公开数据待清理','请先点击清理残留，或删除已有公开数据。');return
        path,_=QFileDialog.getOpenFileName(self,'选择 HaGRID 公开压缩包',str(Path.home()),'ZIP 文件 (*.zip)')
        if not path:return
        self._start_public_worker(PublicImportWorker(self,local_zip=Path(path)))

    def _choose_batch_cell(self,row,column):
        if row<0 or row>=self.batch_table.rowCount():return
        name=self.batch_table.item(row,0)
        if name:self.data_session.setEditText(name.text())
        if 2<=column<2+len(类别):self.data_category.setCurrentIndex(column-2)

    def make_train(self):
        base=self.page('专注模型训练 · 按场景训练全部六类，或专项强化某一种手势')
        v=self._scroll_content(base)
        train=panel();v.addWidget(train)
        train.layout().addWidget(label('选择训练数据',title=True))
        train.layout().addWidget(label('默认累计使用全部私人场景；公开数据是可选项，只有勾选才参与。继续训练已有六分类模型。',dim=True))
        row=QHBoxLayout();train.layout().addLayout(row)
        self.train_scene=GlassComboBox();self.train_scene.setEditable(False);self.train_scene.addItem('全部场景（累计训练）')
        self.focus_cat=GlassComboBox();self.focus_cat.addItems(类别)
        row.addWidget(label('场景'));row.addWidget(self.train_scene,2)
        row.addWidget(label('专项动作'));row.addWidget(self.focus_cat,2)
        self.train_include_public=QCheckBox('本轮训练包含已手动导入的 HaGRID 公开样本（默认不选）')
        self.train_include_public.setChecked(False)
        train.layout().addWidget(self.train_include_public)
        self.train_from_scratch=QCheckBox('从零训练：不加载旧模型参数（彻底消除旧训练来源的影响）')
        train.layout().addWidget(self.train_from_scratch)
        self.train_hand_crop=QCheckBox('实验性手部关键点裁剪：五种手势只提取手部；无手保留背景（需安装 MediaPipe，且必须从零训练）')
        train.layout().addWidget(self.train_hand_crop)
        self.train_hand_crop.toggled.connect(lambda checked:self.train_from_scratch.setChecked(True) if checked else None)
        row=QHBoxLayout();train.layout().addLayout(row)
        self.train_epoch=QSpinBox();self.train_epoch.setRange(1,200);self.train_epoch.setValue(8)
        self.train_device=GlassComboBox();self.train_device.addItems(['CPU','CUDA（可用时）'])
        row.addWidget(label('训练轮数'));row.addWidget(self.train_epoch)
        row.addWidget(label('设备'));row.addWidget(self.train_device,1)
        row.addStretch()
        row=QHBoxLayout();train.layout().addLayout(row)
        self.train_all=btn('一键训练所选场景全部六类',lambda:self.start_training('all'),primary=True)
        self.train_one=btn('只强化选中的一个手势',lambda:self.start_training('focus'))
        for button in (self.train_all,self.train_one):
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text())+60)
            button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding,QSizePolicy.Policy.Fixed)
        row.addWidget(self.train_all,1);row.addWidget(self.train_one,1)
        state=panel();v.addWidget(state)
        state.layout().addWidget(label('模型训练状态',title=True))
        self.train_record=label('正在读取模型训练来源…',dim=True)
        state.layout().addWidget(self.train_record)
        self.train_classes=QTableWidget(len(类别),3)
        self.train_classes.setHorizontalHeaderLabels(['类别','本场景样本','当前模型状态'])
        self.train_classes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.train_classes.verticalHeader().hide()
        self.train_classes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.train_classes.setMinimumHeight(215)
        state.layout().addWidget(self.train_classes)
        self.train_scene.currentTextChanged.connect(lambda _:self.refresh_training_status())
        bottom=panel();v.addWidget(bottom,1)
        bottom.layout().addWidget(label('训练日志',title=True))
        self.train_log=QTextEdit();self.train_log.setReadOnly(True)
        self.train_log.setMinimumHeight(160)
        self.train_log.setPlaceholderText('启动训练后显示真实进度；不将训练准确率当成独立测试准确率。')
        bottom.layout().addWidget(self.train_log,1)
        line=QHBoxLayout();bottom.layout().addLayout(line)
        self.train_status=label('空闲',dim=True);line.addWidget(self.train_status);line.addStretch()
        self.train_cancel=btn('停止训练',self.stop_training,danger=True);self.train_cancel.setEnabled(False)
        self.train_selftest=btn('测试中文日志',self.test_training_log)
        line.addWidget(self.train_selftest)
        line.addWidget(self.train_cancel)
        self.proc=None
        v.addStretch()

    def refresh_training_status(self):
        if not hasattr(self,'train_classes'):return
        state=训练记录状态()
        session=self.train_scene.currentText().strip()
        batches={b['场景']:b['手势'] for b in 场景明细(数据目录)}
        is_all=(session=='全部场景（累计训练）')
        counts=({c:sum(b.get(c,0) for b in batches.values()) for c in 类别}
                if is_all else batches.get(session,{}))
        trained=set(state.get('场景',[]))
        for i,c in enumerate(类别):
            if is_all:
                status=(state['类别'][c]+' · 模型记录场景 '+str(len(trained)))
            elif state['状态']=='已记录':
                status=('已参与当前模型训练' if session in trained and state['类别'][c]=='已训练'
                        else '此场景未参与当前模型训练')
            else:status=state['类别'][c]
            for j,val in enumerate((c,str(counts.get(c,0)),status)):
                self.train_classes.setItem(i,j,QTableWidgetItem(val))
        details=(' · 数据来源：'+','.join(state['场景'])) if state['场景'] else ''
        self.train_record.setText('模型状态：'+state['状态']+details+'。当前表格中的样本数量与已训练来源分别核验。')

    def make_model(self):
        v=self.page('模型与类别信息 · 训练指标必须来自真实验证集或测试集')
        top=panel();v.addWidget(top)
        self.model_state=label('正在检查模型…',size=17);top.layout().addWidget(self.model_state)
        self.model_info=label('',dim=True);top.layout().addWidget(self.model_info)
        top.layout().addWidget(btn('重新加载模型',self.reload_model))
        cards=panel();v.addWidget(cards,1)
        cards.layout().addWidget(label('模型类别 · 六个输出类别 / 四个未训练预留动作',title=True))
        grid=QGridLayout();cards.layout().addLayout(grid)
        self.model_gesture_labels={}
        for i,item in enumerate(动作列表):
            b=QFrame();b.setObjectName('inner');sub=QVBoxLayout(b)
            ico=QLabel();ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix=QPixmap(str(素材路径(item.名称)))
            ico.setPixmap(pix.scaled(86,80,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            sub.addWidget(ico)
            sub.addWidget(label(item.名称))
            status=label('来源未记录' if item.已训练 else '未训练 · 预留',dim=True)
            sub.addWidget(status);self.model_gesture_labels[item.名称]=status
            grid.addWidget(b,i//5,i%5)
        v.addWidget(label('备注：第七种新手势不能仅靠复制图片激活，需要扩展模型输出和重新训练。',dim=True))
    def make_settings(self):
        base=self.page('摄像头及分类设置 · 保存在原有 设置.json，不覆盖私人数据')
        v=self._scroll_content(base)
        card=panel();v.addWidget(card)
        card.layout().addWidget(label('识别设置',title=True))
        grid=QGridLayout();grid.setVerticalSpacing(14);grid.setHorizontalSpacing(22)
        card.layout().addLayout(grid)
        fields=[('摄像头编号','摄像头编号','0'),('识别区域比例','识别区域占画面短边比例','0.78'),
                ('最小置信度（留空采用模型阈值）','最小置信度',''),('稳定帧数','稳定帧数','4'),
                ('解锁帧数','解除锁定帧数','4'),('冷却时间（秒）','触发冷却秒数','1.0'),
                ('刷新间隔（毫秒）','视频刷新毫秒','30')]
        self.inputs={}
        # Each field is a single vertical unit, not two separate grid rows. This
        # prevents QLabel rows from being squeezed into QLineEdit rows on Windows.
        for i,(text,key,placeholder) in enumerate(fields):
            cell=QWidget();col=QVBoxLayout(cell)
            col.setContentsMargins(0,0,0,0);col.setSpacing(7)
            caption=label(text,dim=True);caption.setWordWrap(False)
            caption.setMinimumHeight(21)
            w=QLineEdit();w.setPlaceholderText(placeholder)
            w.setMinimumHeight(45)
            w.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
            col.addWidget(caption);col.addWidget(w)
            cell.setMinimumHeight(79)
            grid.addWidget(cell,i//2,i%2)
            self.inputs[key]=w
        self.show_box=QCheckBox('显示红色候选手部位置框（非精确检测框）')
        card.layout().addWidget(self.show_box)
        self.gesture_pause_box=QCheckBox('允许食指指向暂停/恢复手势指令（默认关闭，防止误识别触发）')
        card.layout().addWidget(self.gesture_pause_box)
        row=QHBoxLayout();row.addStretch()
        row.addWidget(btn('恢复未保存值',self.load_settings))
        row.addWidget(btn('保存并应用',self.save_settings,primary=True))
        card.layout().addLayout(row)

        component=panel();v.addWidget(component)
        component.layout().addWidget(label('手部精确定位组件（可选；不随软件自动下载）',title=True))
        from .手部组件安装 import _dependencies_available
        ready=包含定位资源() and _dependencies_available()
        self.hand_setup_status=label('✓ 已安装手部定位组件' if ready else '未安装完整组件：普通固定区域识别仍可正常使用',dim=True)
        component.layout().addWidget(self.hand_setup_status)
        self.hand_setup_btn=btn('下载并安装手部定位组件',self.install_hand_component)
        component.layout().addWidget(self.hand_setup_btn)
        self.hand_setup_progress=QProgressBar();self.hand_setup_progress.setRange(0,100);self.hand_setup_progress.setValue(0)
        component.layout().addWidget(self.hand_setup_progress)
        self.hand_setup_log=QTextEdit();self.hand_setup_log.setReadOnly(True)
        self.hand_setup_log.setMinimumHeight(140)
        component.layout().addWidget(self.hand_setup_log)
        state_file=根目录/'.发布'/'手部组件安装状态.json'
        if state_file.is_file():
            try:
                status=json.loads(state_file.read_text(encoding='utf-8'))
                if not status.get('成功'):
                    self.hand_setup_status.setText('上次独立安装失败；可重新点击安装，详细日志位于 .发布 目录')
                self.hand_setup_log.append('上次安装：'+('成功' if status.get('成功') else '失败')+' · '+status.get('时间',''))
                self.hand_setup_log.append('日志文件：'+status.get('日志路径',''))
            except (OSError, ValueError, TypeError):pass
        self.hand_setup_worker=None
        self._hand_setup_requires_restart=False
        v.addStretch()
        self.load_settings()

    def install_hand_component(self):
        if self.hand_setup_worker and self.hand_setup_worker.isRunning():return
        if self.training_active():
            QMessageBox.warning(self,'训练进行中','请先完成训练，再安装手部组件。');return
        if self.public_worker and self.public_worker.isRunning():
            QMessageBox.warning(self,'下载进行中','请先完成或取消公开数据下载。');return
        if QMessageBox.question(self,'安装手部定位组件',
            '将先在软件内下载并缓存依赖与手部模型。若需更新 OpenCV，下载完成后软件会自动关闭，'
            '独立安装窗口执行安装并自动重新启动。过程中不需要输入 YES。继续？')!=QMessageBox.StandardButton.Yes:return
        worker=HandSetupWorker(self);self.hand_setup_worker=worker
        self._hand_setup_requires_restart=False
        self.hand_setup_btn.setEnabled(False)
        self.hand_setup_progress.setRange(0,0)
        self.hand_setup_log.clear()
        worker.message.connect(self._hand_setup_message)
        worker.stage.connect(self._hand_setup_stage)
        worker.progress.connect(self._hand_setup_progress)
        worker.succeeded.connect(self._hand_setup_success)
        worker.failed.connect(self._hand_setup_failed)
        worker.finished.connect(lambda w=worker:self._hand_setup_finished(w))
        worker.start()

    def _hand_setup_message(self,message):
        self.hand_setup_log.append(message)
        self.hand_setup_status.setText(message[:180])

    def _hand_setup_stage(self,message):
        self.hand_setup_status.setText(message)
        self.hand_setup_log.append('【'+message+'】')
        self.hand_setup_progress.setRange(0,100 if message=='已安装' else 0)
        if message=='已安装':self.hand_setup_progress.setValue(100)

    def _hand_setup_progress(self,done,total):
        if total>0:
            self.hand_setup_progress.setRange(0,100)
            self.hand_setup_progress.setValue(min(100,round(done*100/total)))
        else:self.hand_setup_progress.setRange(0,0)
        self.hand_setup_status.setText(f'下载手部模型：{done/1048576:.1f} MB'+(f' / {total/1048576:.1f} MB' if total else ''))

    def _hand_setup_success(self,needs_restart=False):
        self._hand_setup_requires_restart=bool(needs_restart)
        self.hand_setup_progress.setRange(0,100);self.hand_setup_progress.setValue(100)
        if needs_restart:
            self.hand_setup_status.setText('依赖缓存完成；即将关闭软件并在独立窗口安装')
            self.hand_setup_log.append('缓存完成。主程序退出后才会替换被占用的 cv2.pyd。')
        else:
            self.hand_setup_status.setText('✓ 手部组件安装完成；手部输入策略需要重新训练模型')
            self.hand_setup_log.append('✓ 已安装')

    def _hand_setup_failed(self,message):
        self._hand_setup_requires_restart=False
        self.hand_setup_progress.setRange(0,100);self.hand_setup_progress.setValue(0)
        self.hand_setup_status.setText('安装准备失败：请查看下方日志')
        self.hand_setup_log.append('× 失败：'+message)
        QMessageBox.warning(self,'手部组件准备失败',message[-2000:])

    def _hand_setup_finished(self,worker):
        if self.hand_setup_worker is worker:self.hand_setup_worker=None
        self.hand_setup_btn.setEnabled(True)
        worker.deleteLater()
        if self._hand_setup_requires_restart:
            self._hand_setup_requires_restart=False
            QTimer.singleShot(0,self._launch_hand_setup_after_exit)

    def _launch_hand_setup_after_exit(self):
        from .手部组件安装 import WHEEL_DIR
        if self.training_active() or (self.public_worker and self.public_worker.isRunning()):
            self.hand_setup_status.setText('其他任务正在运行，请完成后重新点击安装。')
            return
        command=[sys.executable,'-X','utf8','-m','手势系统.手部组件离线安装',
                 '--parent-pid',str(os.getpid()),'--wheel-dir',str(WHEEL_DIR),'--root',str(根目录)]
        # v2.3.4: do not create the sidecar until the Qt event loop has returned.
        # Closing the last GUI window is not, by itself, a guarantee that cv2.pyd
        # has been released by the Python process.
        self._pending_hand_setup_command=command
        self.hand_setup_status.setText('正在关闭摄像头并退出主程序…')
        if not self.close():
            self._pending_hand_setup_command=None
            return
        QApplication.instance().quit()

    def load_settings(self):
        for k,w in self.inputs.items():w.setText('' if self.settings.get(k) is None else str(self.settings[k]))
        self.show_box.setChecked(bool(self.settings.get('显示候选手部框',True)))
        self.gesture_pause_box.setChecked(bool(self.settings.get('允许食指手势暂停',False)))
    def save_settings(self):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间不能修改设置。');return
        data={k:w.text().strip() for k,w in self.inputs.items()}
        data['显示候选手部框']=self.show_box.isChecked()
        try:clean=验证设置(data)
        except ValueError as e:QMessageBox.warning(self,'设置错误',str(e));return
        old=dict(self.settings);new={**old,**clean,'版本':VERSION,
                '允许食指手势暂停':bool(self.gesture_pause_box.isChecked())}
        try:安全保存设置(配置文件,new)
        except OSError as e:QMessageBox.critical(self,'写入失败',str(e));return
        self.settings=new;self.stop_recognition()
        self.ctrl=手势控制器(int(new['稳定帧数']),int(new['解除锁定帧数']),float(new['触发冷却秒数']))
        self.reload_model()
        # Reopening in reload_model applies changed camera ID / interval in worker thread.
        QMessageBox.information(self,'设置','设置已保存并应用；当前识别已停止，请点击开始识别。')
    def update_gesture(self,category,conf=None):
        if category is None:category='未达阈值'
        icon_category=category if category in 动作索引 else '无手'
        if self.lastcat!=category:
            pix=QPixmap(str(素材路径(icon_category)))
            self.gesture_icon.setPixmap(pix.scaled(310,270,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.gesture_text.setText(category)
            self.action_text.setText('候选手势尚未达到确认阈值' if category=='未达阈值' else 动作索引[icon_category].操作)
            self.lastcat=category
        self.conf.setValue(round(conf*100) if conf is not None else 0)
        self.conf.setFormat(f'{conf:.1%}' if conf is not None else '—')
    def open_image_dialog(self):
        if self.image_dialog is None:
            self.image_dialog=ImageControlDialog(self)
        self.image_dialog.show();self.image_dialog.raise_();self.image_dialog.activateWindow()

    def toggle_run(self):
        if self.running:self.stop_recognition();return
        if not self.infer:
            QMessageBox.warning(self,'模型不可用','请先在训练页训练模型，或在模型页重新加载。');return
        if not self.camera_online or not self.camera_worker:
            QMessageBox.warning(self,'摄像头不可用','请检查 VMware 摄像头连接或编号。');return
        self.running=True;self.ctrl.已暂停=False;self.ctrl.处理(None,time.monotonic())
        self.camera_worker.recognizing=True
        self.run_btn.setText('■ 停止识别')

    def stop_recognition(self):
        self.running=False;self.ctrl.已暂停=False;self.ctrl.处理(None,time.monotonic())
        if self.camera_worker:self.camera_worker.recognizing=False
        if hasattr(self,'run_btn'):self.run_btn.setText('▶ 开始识别')

    def reset(self):
        self.stop_recognition()
        self.ctrl=手势控制器(int(self.settings['稳定帧数']),int(self.settings['解除锁定帧数']),float(self.settings['触发冷却秒数']))
        self.last_event.setText('已重置，等待识别');self.update_gesture('无手')

    def load_model(self):
        self.infer=None;self.model_error=''
        try:
            if (模型目录/'正式模型.pt').exists():self.infer=手势推理器()
        except (OSError,ValueError,RuntimeError) as e:self.model_error=str(e)
        if hasattr(self,'model_state'):self.refresh_model()
        if getattr(self,'_pending_after_training',False):
            self._pending_after_training=False
            if self.infer:
                from .训练状态 import 文件哈希
                self.train_status.setText('✓ 新模型已热加载，无需重启 · SHA256 '+文件哈希(模型目录/'正式模型.pt')[:12])
            else:
                self.train_status.setText('× 训练已保存，但加载新模型失败：'+self.model_error)
        self.update_status()

    def update_status(self):
        self.status.setText(('● 摄像头正常' if self.camera_online else '○ 摄像头未连接')+
            '     ·     '+('● 模型就绪' if self.infer else '○ 无模型'))

    def reload_model(self):
        self.stop_recognition()
        # A CameraWorker holds the inference object only while started; restart before reloading.
        if self.camera_worker and self.camera_worker.isRunning():
            self._reopen_camera=True
            self.camera_worker.requestInterruption()
        else:
            self.load_model();self.open_camera()

    def refresh_model(self):
        file=模型目录/'正式模型.pt'
        self.model_state.setText('✓ 六分类模型已加载' if self.infer else '未加载正式模型')
        self.model_info.setText(f'{file.name} · {file.stat().st_size/1024**2:.2f} MiB · 阈值 {self.infer.阈值:.2f}' if self.infer else '没有独立验证时不展示测试准确率。'+getattr(self,'model_error',''))
        state=训练记录状态()
        for c,w in getattr(self,'model_gesture_labels',{}).items():
            w.setText(state['类别'].get(c,'未训练 · 预留'))

    def open_camera(self):
        if self.camera_worker and self.camera_worker.isRunning():
            self._reopen_camera=True
            self.camera_worker.requestInterruption()
            return
        self.camera_online=False;self.update_status()
        worker=CameraWorker(int(self.settings['摄像头编号']),int(self.settings.get('视频刷新毫秒',30)),
            float(self.settings['识别区域占画面短边比例']),self.infer,
            draw_candidate=bool(self.settings.get('显示候选手部框',True)),parent=self)
        self.camera_worker=worker
        worker.preview_enabled=(self.stack.currentIndex()==0)
        worker.camera_state.connect(self._camera_state)
        worker.frame_ready.connect(self.on_frame)
        worker.finished.connect(lambda w=worker:self._camera_finished(w))
        worker.start()

    def _camera_state(self,ready,message):
        self.camera_online=ready;self.update_status()
        if not ready:
            self.stop_recognition()
            self.camera_info.setText(message)

    def _camera_finished(self,worker):
        if self.camera_worker is not worker:return
        self.camera_worker=None;self.camera_online=False
        self.update_status()
        worker.deleteLater()
        if self._pending_capture:
            self._pending_capture=False
            QTimer.singleShot(0,self._show_capture_dialog)
        elif self._reopen_camera:
            self._reopen_camera=False
            self.load_model()
            QTimer.singleShot(0,self.open_camera)

    def on_frame(self,image,payload):
        worker=self.camera_worker
        try:
            # During sidebar animation, don't scale a high-resolution QPixmap on the GUI thread.
            if self.nav_transition.state()==QAbstractAnimation.State.Running:return
            if self.stack.currentIndex()!=0:return
            result=payload.get('inference')
            now=payload.get('t',time.monotonic())
            if self.running and result is not None:
                detected=result['有效类别']
                # Keep the camera/inference running during gesture pause so the same gesture can resume.
                # Finger pointing is a valid class, but it must not pause controls unless the user opted in.
                candidate=detected if detected!='无手' else None
                if candidate=='食指指向' and not self.settings.get('允许食指手势暂停',False):
                    candidate=None
                event=self.ctrl.处理(candidate,now)
                self.update_gesture(detected if detected is not None else '未达阈值',result['置信度'])
                self.camera_info.setText(f'FPS {self.last_fps:.1f} · 推理 {result["推理毫秒"]:.1f} ms · 候选 {result["原始类别"]} {result["置信度"]:.1%} · 阈值 {result["阈值"]:.2f}' + ('（未达阈值，不执行）' if not detected else ''))
                if event:
                    if event in ('已暂停','已恢复'):
                        self.run_btn.setText('■ 结束识别（指令已暂停）' if event=='已暂停' else '■ 停止识别')
                        self.last_event.setText(('指令已暂停，摄像头仍在识别；食指可恢复'
                                                 if event=='已暂停' else '指令已恢复，摄像头持续识别'))
                    elif self.image_dialog is not None and self.image_dialog.operate(event):
                        self.last_event.setText(f'✓ 已执行 {event} · 图片窗口')
                    else:
                        self.last_event.setText(f'检测到 {event}，但未打开含图片的交互窗口')
            self.camera.setPixmap(QPixmap.fromImage(image).scaled(self.camera.size(),
                Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            self.fps_count+=1
            if now-self.fps_start>=1:
                self.last_fps=self.fps_count/max(.01,now-self.fps_start)
                self.fps_start=now;self.fps_count=0
        finally:
            if worker:worker.acknowledge()

    def refresh_data(self,force=False):
        if not hasattr(self,'batch_table'):return
        if not force and self.stack.currentIndex() not in (1,2):return
        result=样本汇总(数据目录)
        batches=场景明细(数据目录)
        for w,n in zip(self.totals,[result['公开合计'],result['本地合计'],len(batches)]):w.setText(str(n))
        existing_scene=self.data_session.currentText().strip()
        existing_train=self.train_scene.currentText().strip()
        current_cat=self.data_category.currentText()
        names=[entry['场景'] for entry in batches]
        self.batch_table.setUpdatesEnabled(False)
        self.batch_table.setRowCount(len(batches))
        for i,entry in enumerate(batches):
            vals=[entry['场景'],entry['合计']]+[entry['手势'][c] for c in 类别]
            for j,val in enumerate(vals):
                self.batch_table.setItem(i,j,QTableWidgetItem(str(val)))
        self.batch_table.setUpdatesEnabled(True)
        self.data_session.blockSignals(True)
        self.data_session.clear();self.data_session.addItems(names)
        self.data_session.setEditText(existing_scene if existing_scene in names else (names[0] if names else '场景01'))
        self.data_session.blockSignals(False)
        self.train_scene.blockSignals(True)
        self.train_scene.clear();self.train_scene.addItems(['全部场景（累计训练）']+names)
        self.train_scene.setCurrentText(existing_train if existing_train in names else '全部场景（累计训练）')
        self.train_scene.blockSignals(False)
        self.data_category.setCurrentText(current_cat)
        paths=[str(数据目录)]
        for c in 类别:
            folder=数据目录/c
            if folder.is_dir() and not folder.is_symlink():
                paths.append(str(folder))
                paths.extend(str(d) for d in folder.iterdir() if d.is_dir() and not d.is_symlink())
        watched=set(self.fs_watcher.directories());desired=set(paths)
        if watched-desired:self.fs_watcher.removePaths(list(watched-desired))
        if desired-watched:self.fs_watcher.addPaths(list(desired-watched))
        self.data_note.setText(f'已检测到 {len(batches)} 个场景 · 导入或手动复制图片后通常 2 秒内刷新')
        if hasattr(self,'public_download_btn') and not (self.public_worker and self.public_worker.isRunning()):self.refresh_public_state()
        if self.stack.currentIndex()==2:self.refresh_training_status()
    def import_files(self):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间不能修改数据。');return
        files,_=QFileDialog.getOpenFileNames(self,'选择图片',str(Path.home()),'图像文件 (*.jpg *.jpeg *.png *.bmp *.webp)')
        if files:self._do_import([Path(x) for x in files])
    def import_directory(self):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间不能修改数据。');return
        folder=QFileDialog.getExistingDirectory(self,'选择图片文件夹',str(Path.home()))
        if folder:self._do_import([p for p in Path(folder).rglob('*') if p.is_file() and p.suffix.lower() in 图片后缀])
    def _do_import(self,files):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间不可修改采集数据。');return
        try:stats=导入图片(files,self.data_category.currentText(),self.data_session.currentText().strip(),数据目录)
        except (ValueError,OSError) as e:QMessageBox.warning(self,'导入失败',str(e));return
        self.refresh_data(force=True)
        QMessageBox.information(self,'导入完成',f'新增 {stats["新增"]} 张，重复 {stats["重复"]} 张，无效 {stats["无效"]} 张。')
    def clear_selected(self):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间禁止回收数据。');return
        cat=self.data_category.currentText();ses=self.data_session.currentText().strip()
        if QMessageBox.warning(self,'回收私人数据',f'将 {cat} / {ses} 的私人照片移入本地回收站？\n只有这一种手势会被回收，其余五类和公开图片保留。',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:dest=回收本地场景(cat,ses,数据目录)
        except (ValueError,OSError) as e:QMessageBox.warning(self,'操作失败',str(e));return
        self.refresh_data(force=True);QMessageBox.information(self,'已回收',f'已移到：\n{dest}\n可以从文件管理器恢复。')
    def clear_scene(self):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间禁止回收数据。');return
        scene=self.data_session.currentText().strip()
        batch=next((b for b in 场景明细(数据目录) if b['场景']==scene),None)
        if batch is None:
            QMessageBox.warning(self,'找不到批次','请选择已经采集的场景');return
        message=f'将 {scene} 中全部六类私人数据（共 {batch["合计"]} 张）移入本地回收站？\n公开训练数据不受影响。'
        if QMessageBox.warning(self,'回收整个场景',message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Yes:return
        try:result=回收整个场景(scene,数据目录)
        except (ValueError,OSError) as e:QMessageBox.warning(self,'回收失败',str(e));return
        self.refresh_data(force=True)
        QMessageBox.information(self,'回收完成',f'已回收 {result["回收类别数"]} 类，位置：\n{result["回收目录"]}')

    def clear_all(self):
        if self.training_active():
            QMessageBox.warning(self,'训练中','训练期间禁止回收数据。');return
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
        if self.training_active():
            QMessageBox.warning(self,'训练占用数据','训练期间不能采集或修改图片，请等待训练结束。');return
        self.stop_recognition();self._pending_capture=True
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.requestInterruption()
        else:
            self._pending_capture=False;self._show_capture_dialog()

    def _show_capture_dialog(self):
        dialog=CaptureDialog(self)
        try:dialog.exec()
        finally:
            self.open_camera();self.refresh_data(force=True)

    def training_active(self):
        return (getattr(self,'proc',None) is not None and
                self.proc.state()!=QProcess.ProcessState.NotRunning and
                not getattr(self,'_train_log_testing',False))
    def start_training(self,mode):
        if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning:return
        selection=self.train_scene.currentText().strip()
        batches=场景明细(数据目录)
        all_scenes=[entry['场景'] for entry in batches]
        sessions=all_scenes if selection=='全部场景（累计训练）' else [selection]
        if not sessions:
            QMessageBox.warning(self,'没有训练场景','请先在「数据」页采集或导入手势图片。');return
        try:
            for scene in sessions:验证轮次(scene)
        except ValueError as e:QMessageBox.warning(self,'无效场景',str(e));return
        chosen=[b for b in batches if b['场景'] in sessions]
        if len(chosen)!=len(sessions):
            QMessageBox.warning(self,'找不到场景','选定场景尚无本地样本');return
        combined={c:sum(b['手势'].get(c,0) for b in chosen) for c in 类别}
        if mode=='all':
            missing=[c for c in 类别 if combined[c]==0]
            if missing:
                QMessageBox.warning(self,'缺少本地图片','以下手势没有本地图片：'+', '.join(missing));return
        else:
            focus=self.focus_cat.currentText()
            if combined[focus]==0:
                QMessageBox.warning(self,'缺少专项图片',f'{focus} 尚无私人照片');return
        if self.running:self.stop_recognition()
        if mode=='focus' and not (模型目录/'正式模型.pt').exists():
            QMessageBox.warning(self,'需要模型','请先训练全部六类，再对单个类别进行专项强化');return
        target=self.focus_cat.currentText()
        use_public=self.train_include_public.isChecked()
        from_scratch=self.train_from_scratch.isChecked()
        hand_crop=self.train_hand_crop.isChecked()
        if mode=='focus' and from_scratch:
            QMessageBox.warning(self,'训练选项冲突','专项强化需要旧模型权重，不能同时选择从零训练。');return
        if hand_crop and not 包含定位资源():
            QMessageBox.warning(self,'缺少手部模型','请到设置页点击“安装手部定位组件”，完成后再选择手部裁剪训练。');return
        if use_public and not (数据目录/'公开训练').is_dir():
            QMessageBox.warning(self,'没有公开数据','请先在数据页点击“下载并导入公开数据”，或取消勾选。');return
        msg=(f'使用 {len(sessions)} 个本地场景（{"、".join(sessions)}）继续训练六分类 CNN。' if mode=='all' else f'专项强化 {target}；使用 {len(sessions)} 个本地场景并重放其余类别。')
        msg+='\n公开数据：'+('本轮参加' if use_public else '本轮不参加')
        msg+='\n旧模型权重：'+('从零开始，不继承旧数据的训练影响' if from_scratch else '继续使用旧权重（即使不选公开数据，也可能继承之前训练的特征）')
        if hand_crop:msg+='\n输入方式：真实关键点定位手部；未定位正样本将跳过。'
        msg+='\n旧模型会备份。没有独立验证集，本次结果只供演示。\n确认开始？'
        if QMessageBox.question(self,'启动训练',msg)!=QMessageBox.StandardButton.Yes:return
        args=['-X','utf8','-u','-m','手势系统.工作台训练','--mode',mode,'--sessions',*sessions,'--epochs',str(self.train_epoch.value()),
              '--device','cuda' if self.train_device.currentIndex() else 'cpu']
        if use_public:args+=['--include-public']
        if from_scratch:args+=['--from-scratch']
        if hand_crop:args+=['--hand-crop']
        if mode=='focus':args+=['--target',target]
        self._launch_training_process(args,testing=False)

    def test_training_log(self):
        """一键验证真实 Qt 子进程日志通道；不读取数据、不训练或覆盖权重。"""
        if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning:return
        self._launch_training_process(['-X','utf8','-u','-m','手势系统.训练日志自检'],testing=True)

    def _launch_training_process(self,args,*,testing):
        self.proc=QProcess(self)
        self.proc.setWorkingDirectory(str(根目录))
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process_env=QProcessEnvironment.systemEnvironment()
        配置训练子进程编码(process_env)
        self.proc.setProcessEnvironment(process_env)
        self._train_log_decoder=训练日志解码器()
        self._train_log_testing=testing
        self._train_log_plain=''
        self.proc.readyReadStandardOutput.connect(self.read_training)
        self.proc.finished.connect(self.training_done)
        self.train_log.clear()
        self.train_log.append('启动：'+sys.executable+' '+' '.join(args)+'\n')
        self.train_status.setText('正在验证中文日志（不训练）…' if testing else '训练中，界面仍可操作…')
        self.train_all.setEnabled(False);self.train_one.setEnabled(False)
        self.train_selftest.setEnabled(False);self.train_cancel.setEnabled(True)
        self.proc.start(sys.executable,args)
    def read_training(self,final=False):
        if self.proc is None:return
        data=bytes(self.proc.readAllStandardOutput())
        # 即便 Qt 恰好将一个汉字的三字节分在不同 readyRead 事件中，也必须正确复原。
        text=self._train_log_decoder.输入(data,结束=final)
        self._train_log_plain+=text
        if not text:return
        self.train_log.moveCursor(__import__('PySide6.QtGui',fromlist=['QTextCursor']).QTextCursor.MoveOperation.End)
        self.train_log.insertPlainText(text)
        self.train_log.ensureCursorVisible()
    def training_done(self,code,status):
        self.read_training(final=True)
        self.train_all.setEnabled(True);self.train_one.setEnabled(True)
        self.train_selftest.setEnabled(True);self.train_cancel.setEnabled(False)
        if self._train_log_testing:
            passed=(code==0 and all(x in self._train_log_plain for x in ('读取有效样本', '剪刀手', '食指指向', '训练准确率', '中文目录'))
                    and '\ufffd' not in self._train_log_plain)
            self.train_status.setText('✓ 中文日志显示正常；没有训练模型' if passed else '× 日志自检未通过，请复制日志反馈')
            return
        self.train_status.setText('✓ 训练完成' if code==0 else f'训练结束，退出码 {code}（请查看日志）')
        if code==0:
            self._pending_after_training=True
            self.train_status.setText('训练成功，正在替换运行中的模型…')
            self.reload_model();self.refresh_training_status()
    def stop_training(self):
        if not self.proc or self.proc.state()==QProcess.ProcessState.NotRunning:return
        if QMessageBox.question(self,'中止训练','确认中断训练？已完成的旧正式模型保持不变。')==QMessageBox.StandardButton.Yes:
            self.proc.terminate()
            QTimer.singleShot(3000,lambda:self.proc.kill() if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning else None)
    def closeEvent(self,e):
        if self.proc and self.proc.state()!=QProcess.ProcessState.NotRunning:
            QMessageBox.warning(self,'训练进行中','请先停止训练任务，再关闭程序。');e.ignore();return
        if self.hand_setup_worker and self.hand_setup_worker.isRunning():
            QMessageBox.warning(self,'定位组件安装中','请等待组件安装完成再退出。');e.ignore();return
        if self.public_worker and self.public_worker.isRunning():
            QMessageBox.warning(self,'下载进行中','请先取消公开数据下载，完成线程退出后再关闭。');e.ignore();return
        self.data_timer.stop()
        if self.image_dialog:self.image_dialog.close()
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.requestInterruption()
            if not self.camera_worker.wait(3000):
                QMessageBox.warning(self,'摄像头关闭中','摄像头线程仍在退出，请稍后关闭。')
                e.ignore();return
        e.accept()


def run():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Gesture Studio')
    window=GestureWindow();window.show()
    QTimer.singleShot(0,window.apply_backdrop)
    exit_code=app.exec()
    command=getattr(window,'_pending_hand_setup_command',None)
    if command:
        # Qt and camera workers have already exited. Spawn the sidecar and
        # terminate this interpreter so Windows will unload cv2.pyd for pip.
        try:
            subprocess.Popen(command,cwd=str(根目录),stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0),
                close_fds=True)
        except OSError as exc:
            logfile=根目录/'.发布'/'手部组件最近安装.log'
            logfile.parent.mkdir(parents=True,exist_ok=True)
            with logfile.open('a',encoding='utf-8') as stream:
                stream.write('无法启动独立安装器：'+str(exc)+'\n')
            raise
        sys.stdout.flush();sys.stderr.flush()
        os._exit(0)
    return exit_code
