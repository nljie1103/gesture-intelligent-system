"""HaGRIDv2 精简包导入：严格标签映射、手部裁剪和来源记录。不会把 no_gesture 当作无手。"""
from __future__ import annotations
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from PIL import Image, ImageOps, UnidentifiedImageError
from .配置 import 数据目录, 类别

来源名称 = 'GestureDetectionConnoisseurs/hagrid_subsets (HaGRIDv2 派生子集)'
来源地址 = 'https://huggingface.co/datasets/GestureDetectionConnoisseurs/hagrid_subsets'
标签映射 = {'palm': '张开手掌', 'fist': '握拳', 'like': '点赞', 'peace': '剪刀手', 'one': '食指指向'}
图像格式 = {'.jpg', '.jpeg', '.png'}


def 安全图像路径(名称: str) -> bool:
    if '\\' in 名称 or '\x00' in 名称:
        return False
    path = PurePosixPath(名称)
    return not path.is_absolute() and '..' not in path.parts and ':' not in 名称


def _裁剪手部(图像: Image.Image, 标注: dict, 来源类名: str, 边距系数: float) -> Image.Image | None:
    """选取对应标签的单手框，并保留一定上下文；避免图像分类时训练到整幅人像。"""
    标签 = 标注.get('labels', [])
    框 = 标注.get('bboxes', [])
    if not isinstance(标签, list) or not isinstance(框, list) or len(标签) != len(框):
        return None
    可选 = []
    for 标签名, b in zip(标签, 框):
        if 标签名 != 来源类名 or not isinstance(b, (list, tuple)) or len(b) != 4:
            continue
        try:
            x, y, w, h = map(float, b)
        except (ValueError, TypeError):
            continue
        if not all(0 <= v <= 1 for v in (x, y, w, h)) or w < .02 or h < .02:
            continue
        if x + w > 1.01 or y + h > 1.01:
            continue
        可选.append((w*h, x, y, w, h))
    if not 可选:
        return None
    # 避免多手混合标签污染。只接收一个目标手、画面中没有另一只被标注的手。
    if len(标签) != 1 or len(可选) != 1:
        return None
    _, x, y, w, h = max(可选)
    宽, 高 = 图像.size
    边 = max(w * 宽, h * 高) * 边距系数
    cx, cy = (x+w/2)*宽, (y+h/2)*高
    左, 上 = max(0, int(cx-边/2)), max(0, int(cy-边/2))
    右, 下 = min(宽, int(cx+边/2)), min(高, int(cy+边/2))
    if 右 - 左 < 28 or 下 - 上 < 28:
        return None
    return 图像.crop((左, 上, 右, 下)).convert('RGB')


def 导入公开子集(压缩包: Path, 每类最多: int = 100, 边距系数: float = 2.6,
           数据根目录: Path = 数据目录) -> dict:
    """导入 ZIP 内五种明确标签。输入数据不可信，禁止路径穿越、炸弹文件或覆写。"""
    if not 1 <= 每类最多 <= 2000:
        raise ValueError('每类数量应在 1~2000 之间')
    if not 1.2 <= 边距系数 <= 5.0:
        raise ValueError('手部裁剪倍率应在 1.2~5.0 之间')
    压缩包 = Path(压缩包)
    if not 压缩包.is_file():
        raise FileNotFoundError(f'公开数据压缩包不存在：{压缩包}')
    数据根目录 = Path(数据根目录)
    清单路径 = 数据根目录 / '公开数据清单.json'
    目的根 = 数据根目录 / '公开训练'
    if 清单路径.exists() or 目的根.exists():
        raise FileExistsError('已存在公开训练数据或清单，为保护训练可复现性，不能覆盖。请先核查原始数据。')
    with 压缩包.open('rb') as f:
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
    已导入 = {类名: [] for 类名 in 标签映射.values()}
    跳过 = Counter()
    待写 = []
    with zipfile.ZipFile(压缩包) as zipf:
        列表 = zipf.infolist()
        注释候选 = [i for i in 列表 if i.filename == 'annotations.json' and i.file_size <= 120*1024*1024]
        if len(注释候选) != 1:
            raise ValueError('无法找到官方精简子集附带的 annotations.json，请确认下载的 ZIP 类型')
        with zipf.open(注释候选[0]) as f:
            标注表 = json.load(f)
        if not isinstance(标注表, dict):
            raise ValueError('annotations.json 结构不符合预期')
        for item in 列表:
            if item.is_dir() or not 安全图像路径(item.filename):
                continue
            p = PurePosixPath(item.filename)
            if len(p.parts) != 2 or p.suffix.lower() not in 图像格式:
                continue
            源类别 = p.parts[0]
            if 源类别 not in 标签映射:
                continue
            中文 = 标签映射[源类别]
            if len(已导入[中文]) >= 每类最多:
                continue
            if item.file_size > 14*1024*1024 or item.file_size < 256:
                跳过['文件尺寸异常'] += 1
                continue
            详情 = 标注表.get(源类别, {}).get(p.stem)
            if not isinstance(详情, dict):
                跳过['缺少匹配标注'] += 1
                continue
            try:
                with zipf.open(item) as f:
                    raw = f.read(14*1024*1024 + 1)
                if len(raw) > 14*1024*1024:
                    跳过['图像体积异常'] += 1
                    continue
                with Image.open(io.BytesIO(raw)) as 图片:
                    图片 = ImageOps.exif_transpose(图片)
                    if 图片.width * 图片.height > 16_000_000:
                        跳过['图像像素过大'] += 1
                        continue
                    局部 = _裁剪手部(图片, 详情, 源类别, 边距系数)
                if 局部 is None:
                    跳过['无合格单手框'] += 1
                    continue
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                跳过['图像读取失败'] += 1
                continue
            相对路径 = f'公开训练/{中文}/{len(已导入[中文]):04d}.jpg'
            tmp = io.BytesIO()
            局部.save(tmp, format='JPEG', quality=91)
            待写.append((相对路径, tmp.getvalue()))
            已导入[中文].append({'路径': 相对路径, '来源类别': 源类别,
                          '来源文件': p.as_posix(), 'subject_id': str(详情.get('user_id') or '')})
    if any(len(图片) < min(5, 每类最多) for 图片 in 已导入.values()):
        raise ValueError('某类别有效样本少于要求，请检查压缩包内的标注和手势框。'
                         + str({k: len(v) for k,v in 已导入.items()}))
    # 全部校验成功后才写入；如部分写入失败则回滚新创建的数据文件。
    try:
        for 相对路径, 内容 in 待写:
            目标 = 数据根目录 / 相对路径
            目标.parent.mkdir(parents=True, exist_ok=True)
            with 目标.open('xb') as file:
                file.write(内容)
        清单 = {'来源': 来源名称, '原始URL': 来源地址, '来源文件名': 压缩包.name, '来源ZIP_SHA256': sha,
              '五类映射': 标签映射, '无手来源': '仅限本地空白视频',
              '公开数据用途': '仅基础训练，不进入独立本地测试集',
              '样本': 已导入, '跳过统计': dict(跳过)}
        清单路径.write_text(json.dumps(清单, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        import shutil
        if 目的根.exists():
            shutil.rmtree(目的根)
        清单路径.unlink(missing_ok=True)
        raise
    return {'各类数量': {k: len(v) for k, v in 已导入.items()}, '跳过': dict(跳过),
            '源压缩包SHA256': sha, '清单': str(清单路径)}
