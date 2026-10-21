"""Optional separate image control window, never embedded in the gesture home page."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap,QImageReader
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QScrollArea

IMAGE_SUFFIXES={'.jpg','.jpeg','.png','.bmp','.webp'}


def 下一索引(index:int,count:int,step:int)->int:
    if count<=0:raise ValueError('尚未加载可浏览的图片')
    return (index+step)%count


def 缩放倍率(value:float,action:str)->float:
    if action=='放大':return min(5.0,round(value*1.25,3))
    if action=='缩小':return max(.2,round(value/1.25,3))
    return value


class ImageControlDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('图片交互 · Gesture Studio')
        self.resize(760,560)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,False)
        self.paths=[];self.index=0;self.zoom=1.
        v=QVBoxLayout(self)
        self.status=QLabel('请选择一个图片文件夹，手势才能切换、缩放图片')
        v.addWidget(self.status)
        self.image=QLabel('尚未加载图片');self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(400,350);self.image.setStyleSheet('background:#1d2a40;color:white;')
        self.scroll=QScrollArea();self.scroll.setWidget(self.image);self.scroll.setWidgetResizable(False)
        v.addWidget(self.scroll,1)
        row=QHBoxLayout();v.addLayout(row)
        for name,fn in [('打开文件夹',self.choose_folder),('上一张',lambda:self.operate('上一张')),
                        ('下一张',lambda:self.operate('下一张')),('放大',lambda:self.operate('放大')),
                        ('缩小',lambda:self.operate('缩小'))]:
            b=QPushButton(name);b.clicked.connect(fn);row.addWidget(b)

    def choose_folder(self):
        directory=QFileDialog.getExistingDirectory(self,'选择本地图片文件夹',str(Path.home()))
        if not directory:return
        self.paths=sorted(p for p in Path(directory).iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in IMAGE_SUFFIXES)
        self.index=0;self.zoom=1.
        self.render()

    def operate(self,action:str)->bool:
        if not self.paths or not self.isVisible():return False
        if action=='下一张':self.index=下一索引(self.index,len(self.paths),1);self.zoom=1.
        elif action=='上一张':self.index=下一索引(self.index,len(self.paths),-1);self.zoom=1.
        elif action in ('放大','缩小'):self.zoom=缩放倍率(self.zoom,action)
        else:return False
        self.render()
        return True

    def render(self):
        if not self.paths:
            self.status.setText('该文件夹没有受支持的图片');self.image.setText('没有可显示的图片');return
        source=self.paths[self.index]
        reader=QImageReader(str(source))
        reader.setAutoTransform(True)
        original=reader.size()
        if original.isValid():
            if original.width()*original.height()>24_000_000:
                self.status.setText('图片过大，拒绝加载：'+source.name);return
            if max(original.width(),original.height())>2560:
                from PySide6.QtCore import QSize
                reader.setScaledSize(original.scaled(QSize(2560,2560),Qt.AspectRatioMode.KeepAspectRatio))
        pix=QPixmap.fromImage(reader.read())
        if pix.isNull():
            self.status.setText('图片无法读取：'+source.name);return
        base_w=min(self.scroll.viewport().width(),pix.width())
        base_h=min(self.scroll.viewport().height(),pix.height())
        fitted=pix.size().scaled(max(100,base_w),max(100,base_h),Qt.AspectRatioMode.KeepAspectRatio)
        w=max(32,round(fitted.width()*self.zoom));h=max(32,round(fitted.height()*self.zoom))
        self.image.setPixmap(pix.scaled(w,h,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.image.resize(w,h)
        self.status.setText(f'{self.index+1}/{len(self.paths)} · {source.name} · {self.zoom:.0%}')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.paths:self.render()
