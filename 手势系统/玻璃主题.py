"""Liquid Glass inspired asset rendering; no external OS blur or new dependencies.
Tkinter cannot reproduce Apple's native optical refraction: use consistent pre-rendered
translucent gradients, highlights and a softly blurred ambient wallpaper instead.
"""
from __future__ import annotations
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter

INK='#192941'
SUB='#73839A'
BLUE='#2868DA'
BG='#EEF4FC'
CARD='#F8FBFF'
LINE='#DBE6F3'
GREEN='#16856C'
RED='#D95B68'


def _blend(base, tint, alpha):
    return tuple(round(base[i]*(1-alpha)+tint[i]*alpha) for i in range(3))

@lru_cache(maxsize=12)
def 生成壁纸(width:int,height:int):
    width=max(16,min(int(width),3000));height=max(16,min(int(height),2000))
    # Build at lower resolution, then upscale and blur for low CPU and texture continuity.
    rw=max(80,width//5);rh=max(60,height//5)
    background=Image.new('RGB',(rw,rh)); pix=background.load()
    clouds=((.12,.04,.66,(145,200,255)),(.83,.08,.62,(197,184,255)),
            (.70,.93,.73,(183,225,248)),(.11,.90,.42,(243,207,239)))
    for y in range(rh):
        v=y/max(1,rh-1)
        for x in range(rw):
            u=x/max(1,rw-1)
            col=(238+int(4*v),244+int(3*v),252)
            for cx,cy,rad,tint in clouds:
                dist=((u-cx)**2+(v-cy)**2)**.5
                strength=.29*max(0,1-dist/rad)**2
                col=_blend(col,tint,strength)
            pix[x,y]=col
    return background.resize((width,height),Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(18))

@lru_cache(maxsize=80)
def 玻璃板(width:int,height:int,accent=False):
    width=max(50,int(width));height=max(45,int(height))
    radius=24
    img=Image.new('RGBA',(width,height),(0,0,0,0))
    d=ImageDraw.Draw(img)
    d.rounded_rectangle((3,4,width-4,height-5),radius=radius,fill=(255,255,255,184 if not accent else 203),outline=(255,255,255,248),width=2)
    # Specular upper rim and restrained inner border.
    d.rounded_rectangle((5,6,width-6,height-7),radius=radius-1,outline=(187,210,233,115),width=1)
    d.arc((12,8,width-13,height-14),182,339,fill=(255,255,255,225),width=2)
    return img
