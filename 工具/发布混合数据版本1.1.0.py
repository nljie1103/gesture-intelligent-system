# -*- coding: utf-8 -*-
"""v1.1.0 首次正式发布：GitHub 私人仓库 + 389 张 HaGRID 衍生公开训练图。

不上传自采图像、模型权重、录像、日志及本地训练输出。要求原始 v1.0.0
提交为父提交，防止误覆盖已经发布的历史。适用于 Windows + Python 3.14。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPO = 'nljie1103/gesture-intelligent-system'
BASE = '0016f58d14ddecb03f7020c0ec1f50928f803374'
TAG = 'v1.1.0'
SUBJECT = '加入公开手势数据与摄像头场景微调功能'
SOURCE_HASH = '72ada2959c117d23e98c8c4da2c9009580554d12163a6db8f78de50312cbdc47'
DEMO_HASH = '75bddd2ec5f5c250a4781519ec2e938d4344d3f3d27ef1c952d458c581ad2b83'
ASSET = 'gesture-intelligent-system-v1.1.0-source.zip'
EXPECTED = {'张开手掌':73,'握拳':80,'点赞':71,'剪刀手':86,'食指指向':79}
ROOT = Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统'
CODE_FILES = [
    '.gitignore', '版本.txt', '设置.json', '手势系统/__init__.py', '文档/版本记录.txt',
    '手势系统/公开数据.py', '手势系统/混合训练.py', '导入公开数据.py',
    '训练混合模型.py', '评估混合模型.py', '测试/test_公开与混合数据.py',
    '文档/混合数据实施说明.txt', '文档/发布说明-1.1.0.txt',
    '文档/公开数据来源与授权说明.txt', '工具/发布混合数据版本1.1.0.py',
    '训练演示模型.py',
]
ORIG_PUBLISH_HASH = '49683d326a22b7e6f9b20c15d5a9d0b0c42c0b2626bc465e7186c8b0c32eaa02'
ORIG_DOC_HASH = 'faf2a32cd4ff1b1b0750339d480050754f0fa6d6280a472144903420a0eab98b'
ORIG_NOTES_HASH = '3fd0bc74580d7a689430c08a5b91e2c00e076bdae716424011eee58523cb78de'
ENV = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
           GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM=os.environ.get('GIT_CONFIG_NOSYSTEM', '0'))
GIT = GH = None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def executable(name: str) -> str:
    x = shutil.which(name)
    if x:
        return x
    choices = ([r'C:\Dev\Git\cmd\git.exe', r'C:\Program Files\Git\cmd\git.exe'] if name == 'git'
               else [r'C:\Program Files\GitHub CLI\gh.exe'])
    for choice in choices:
        if Path(choice).is_file():
            return choice
    raise RuntimeError(f'未找到 {name}，请确认已安装')


def run(name: str, *args: str, ok=(0,), data: bytes | None = None):
    p = subprocess.run([GIT if name == 'git' else GH, *args], cwd=ROOT,
                       env=ENV, input=data, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False)
    if p.returncode not in ok:
        raise RuntimeError(f'{name} {args[:3]} 返回 {p.returncode}：\n'
                           + p.stderr.decode('utf-8','replace')[-1600:])
    return p.stdout.decode('utf-8','replace').strip(), p.returncode


def git(*args):
    return run('git', *args)[0]


def gh(*args):
    return run('gh', *args)[0]


def api(endpoint: str) -> dict:
    return json.loads(gh('api', endpoint))


def tracked_changes() -> list[str]:
    # -z 禁止中文文件名的 Git 引号转义；只解析标准 M / ?? 情形。
    p = subprocess.run([GIT, 'status', '--porcelain=v1', '-z', '--untracked-files=all'],
                       cwd=ROOT, env=ENV, capture_output=True, check=True)
    names = []
    for s in p.stdout.decode('utf-8', 'strict').split('\x00'):
        if not s:
            continue
        if len(s) < 4 or s[:2] in {'R ', ' R', 'C ', ' C'}:
            raise RuntimeError(f'工作区有重命名/不支持的状态：{s}')
        names.append(s[3:].replace('\\','/'))
    return names


def remote_sha(ref: str) -> str | None:
    r = git('ls-remote','origin',ref)
    return r.split()[0] if r else None


def file_valid(path: Path, top: Path) -> bool:
    if not path.is_file() or path.is_symlink() or top.is_symlink():
        return False
    # Windows junction / symlink 均不允许把数据导向项目外。
    try:
        if not path.resolve().is_relative_to(top.resolve()):
            return False
        if any(parent.is_symlink() for parent in path.parents if parent != top and top in parent.parents):
            return False
    except (OSError, RuntimeError):
        return False
    return True


def inspect_public_data() -> tuple[list[str], int]:
    data = ROOT / '数据'
    manifest = data / '公开数据清单.json'
    if not file_valid(manifest, data):
        raise RuntimeError('缺少有效的 数据/公开数据清单.json')
    raw = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if raw.get('来源ZIP_SHA256') != SOURCE_HASH:
        raise RuntimeError('公开数据来源 ZIP 哈希与本次已核验的 HaGRID 精简子集不一致')
    expected_all = set()
    bytes_total = 0
    for cls, count in EXPECTED.items():
        records = raw.get('样本', {}).get(cls)
        if not isinstance(records, list) or len(records) != count:
            raise RuntimeError(f'{cls} 样本数量不一致：预期 {count}，实际 {len(records) if isinstance(records,list) else "不存在"}')
        for item in records:
            value = item.get('路径') if isinstance(item,dict) else None
            if not isinstance(value, str) or '\\' in value or ':' in value or '\x00' in value:
                raise RuntimeError('公开清单存在不安全路径')
            pp = PurePosixPath(value)
            if len(pp.parts) != 3 or pp.parts[:2] != ('公开训练',cls) or '..' in pp.parts or pp.suffix.lower() != '.jpg':
                raise RuntimeError('公开清单存在错误路径或标签：'+str(value))
            rel = '数据/' + value
            if rel in expected_all:
                raise RuntimeError('公开数据包含重复路径')
            f = data.joinpath(*pp.parts)
            if not file_valid(f, data) or f.stat().st_size < 256 or f.stat().st_size > 12*1024*1024:
                raise RuntimeError('公开训练图片缺失、文件异常或链接到外部目录：'+rel)
            bytes_total += f.stat().st_size
            expected_all.add(rel)
    folder = data / '公开训练'
    actual = set()
    for f in folder.rglob('*'):
        if f.is_file():
            actual.add(f.relative_to(ROOT).as_posix())
    if actual != expected_all:
        raise RuntimeError(f'公开目录存在非清单文件或缺失图片：多 {len(actual-expected_all)}，少 {len(expected_all-actual)}')
    if bytes_total > 150*1024*1024:
        raise RuntimeError(f'公开裁剪图片约 {bytes_total/1024**2:.1f} MiB，超出本脚本 150 MiB 安全上限；需重新设计大文件存储')
    return sorted(expected_all)+['数据/公开数据清单.json'], bytes_total


def prepare_text_updates(script_file: Path) -> None:
    # 针对已成功安装的 v1.1.0 固定基线，绝不覆盖用户自己修改的文档。
    publisher = ROOT / '工具' / '发布混合数据版本1.1.0.py'
    orig_script = publisher.read_bytes()
    new_script = script_file.read_bytes()
    if sha(orig_script) not in {ORIG_PUBLISH_HASH, sha(new_script)}:
        raise RuntimeError('项目自带的发布程序曾被修改，拒绝覆盖。')
    doc = ROOT / '文档' / '混合数据实施说明.txt'
    notes = ROOT / '文档' / '发布说明-1.1.0.txt'
    doc_bytes = doc.read_bytes()
    notes_bytes = notes.read_bytes()
    notice = ROOT / '文档' / '公开数据来源与授权说明.txt'
    new_notice = (
        'HaGRIDv2 衍生公开训练数据：来源与许可说明\n'
        '============================================\n'
        '本目录不涉及项目自有代码的许可证，也不替代上游数据集许可。\n'
        '数据来源：HaGRID / HaGRIDv2，原项目 https://github.com/hukenovs/hagrid\n'
        '精简包来源：GestureDetectionConnoisseurs/hagrid_subsets\n'
        'https://huggingface.co/datasets/GestureDetectionConnoisseurs/hagrid_subsets\n'
        '原始归档：hagrid-export_100_images.zip\n'
        f'原始 ZIP SHA256：{SOURCE_HASH}\n'
        '上游 HaGRID 数据集采用其特定的 CC BY-SA 4.0 变体，实际权利和限制以其官方许可文件为准：\n'
        'https://github.com/hukenovs/hagrid/tree/master/license\n'
        '精简分发页面标注 CC BY-SA 4.0：https://creativecommons.org/licenses/by-sa/4.0/\n'
        '这里仅存储从公开照片按标注框裁剪、转换为 JPEG 的 389 张五类训练样本。\n'
        '变更说明：只保留单手标注框，并在裁剪周围保留部分上下文；按固定中文类别重命名。\n'
        'palm=张开手掌(73)，fist=握拳(80)，like=点赞(71)，peace=剪刀手(86)，one=食指指向(79)。\n'
        '没有把 no_gesture 等同于无手，亦未上传任何自采摄像头照片。\n'
        '样本路径和来源映射参见 数据/公开数据清单.json。\n'
        '本数据的许可不意味着原作者认可或参与此项目。后续共享、商业使用或转分发\n'
        '应遵循 HaGRID 原始许可、署名和相同方式共享等条款，并留意肖像与隐私权。\n'
    ).encode('utf-8')
    if notice.exists() and notice.read_bytes() != new_notice:
        raise RuntimeError('公开数据来源说明已存在且不一致，拒绝覆盖')
    if sha(doc_bytes) == ORIG_DOC_HASH:
        old = '仅本地保存第三方图片；不要将其打包上传到 GitHub 私人仓库或公开 Release。'
        replacement = ('本次按用户要求，将 389 张经过裁剪的公开训练样本与来源清单提交到 Private 仓库，'
                       '不提交 402 MB 原始 ZIP；使用和再分发受上游 HaGRID 特定许可约束。')
        txt=doc_bytes.decode('utf-8')
        if old not in txt:
            raise RuntimeError('原实施说明内容不符合预期，拒绝修改')
        doc.write_text(txt.replace(old,replacement),encoding='utf-8')
    elif '389 张经过裁剪' not in doc.read_text(encoding='utf-8'):
        raise RuntimeError('实施说明已被其他修改，拒绝覆盖')
    if sha(notes_bytes) == ORIG_NOTES_HASH:
        with notes.open('a', encoding='utf-8') as fp:
            fp.write('\n【此版本公开数据归档】\n'
                     '本次将经标注框裁剪的 HaGRIDv2 公开五类训练图（共389张）与来源清单保存在私人仓库，'
                     '不包含自采的“场景01”照片或模型权重。详见 文档/公开数据来源与授权说明.txt。\n'
                     '目前仅完成单采集轮次的功能演示，未取得独立验证/测试准确率；'
                     '食指、剪刀手的真实场景识别仍有待改进。\n')
    elif '【此版本公开数据归档】' not in notes.read_text(encoding='utf-8'):
        raise RuntimeError('发布说明已被其他修改，拒绝覆盖')
    ignore = ROOT / '.gitignore'
    t = ignore.read_text(encoding='utf-8-sig')
    if '\n数据/\n' in '\n'+t and '\n!数据/公开训练/\n' not in t:
        t = t.replace('数据/\n', '数据/*\n!数据/公开训练/\n!数据/公开数据清单.json\n', 1)
        ignore.write_text(t, encoding='utf-8')
    elif '数据/*\n!数据/公开训练/' not in t:
        raise RuntimeError('.gitignore 与预期不符，不能安全开启公开数据白名单')
    notice.write_bytes(new_notice)
    if publisher.resolve() != script_file.resolve():
        publisher.write_bytes(new_script)
    demo_source = Path.home() / 'Downloads' / 'train-gesture-demo-v1.1.0.py'
    demo_dest = ROOT / '训练演示模型.py'
    if demo_dest.exists():
        if sha(demo_dest.read_bytes()) != DEMO_HASH:
            raise RuntimeError('训练演示模型.py 已有其他内容，拒绝覆盖')
    else:
        if not demo_source.is_file() or sha(demo_source.read_bytes()) != DEMO_HASH:
            raise RuntimeError('请将之前使用的 train-gesture-demo-v1.1.0.py 保存在 Downloads，再重新发布。')
        demo_dest.write_bytes(demo_source.read_bytes())


def stage_and_verify(public_files: list[str]):
    # 明确路径白名单，不使用 git add --all，避免把“场景01”等用户照片加入索引。
    git('add','--',*CODE_FILES)
    git('add','--',*public_files)
    staged = {x for x in run('git','diff','--cached','--name-only','-z')[0].split('\x00') if x}
    accepted = set(CODE_FILES) | set(public_files)
    if not staged or not staged <= accepted or not set(public_files) <= staged:
        raise RuntimeError('待提交索引文件包含异常路径/缺少公开数据。已停止，未推送。')
    bad = [x for x in staged if x.startswith(('数据/张开手掌/','数据/握拳/','数据/点赞/','数据/剪刀手/','数据/食指指向/','数据/无手/'))]
    if bad:
        raise RuntimeError('发现自采照片进入索引，停止：'+repr(bad[:3]))
    other = set(tracked_changes()) - accepted
    if other:
        raise RuntimeError('发现超出本版本的改动：'+repr(sorted(other)[:20]))
    git('diff','--cached','--check')
    return len(staged)


def create_portable_source_archive(tag: str, output: Path):
    """从已提交的工作树打包，并用 ZipFile 写入标准 UTF-8 文件名。"""
    if git('status', '--porcelain'):
        raise RuntimeError('生成归档前工作区发生变更，已停止')
    names = [s for s in git('ls-tree', '-r', '-z', '--name-only', tag).split('\x00') if s]
    if not names:
        raise RuntimeError('提交树中未找到文件')
    tempzip = output.with_suffix('.tmp.zip')
    if tempzip.exists():
        raise RuntimeError('存在遗留的临时归档包，请先核对：' + str(tempzip))
    try:
        with zipfile.ZipFile(tempzip, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as archive:
            for name in names:
                pp = PurePosixPath(name)
                if (pp.is_absolute() or '..' in pp.parts or '\\' in name
                        or any(part in {'', '.', '..'} for part in pp.parts)):
                    raise RuntimeError('Git 文件树中存在异常路径：' + name)
                file = ROOT.joinpath(*pp.parts)
                if not file.is_file() or file.is_symlink():
                    raise RuntimeError('版本文件不存在或为软链接：' + name)
                archive.write(file, arcname=name)
        with zipfile.ZipFile(tempzip, 'r') as archive:
            if set(archive.namelist()) != set(names) or archive.testzip() is not None:
                raise RuntimeError('版本归档完整性或中文文件名核验失败')
        tempzip.replace(output)
    finally:
        tempzip.unlink(missing_ok=True)


def publish():
    global GIT, GH
    GIT, GH = executable('git'), executable('gh')
    if not ROOT.is_dir() or not (ROOT/'.git').is_dir():
        raise RuntimeError('无法找到固定项目目录和本地 Git 仓库')
    if git('branch','--show-current') != 'main':
        raise RuntimeError('必须在 main 分支发布')
    origin = git('remote','get-url','origin')
    if origin not in {f'https://github.com/{REPO}.git',f'https://github.com/{REPO}',f'git@github.com:{REPO}.git'}:
        raise RuntimeError('origin 不是指定仓库')
    if api('user').get('login') != 'nljie1103' or api(f'repos/{REPO}').get('private') is not True:
        raise RuntimeError('GitHub 账户不匹配或仓库不是 Private')
    public_files, public_size = inspect_public_data()
    print('公开裁剪照片：389 张；占用约 %.1f MiB' % (public_size/1024**2))
    print('私人摄像头图片：完全排除（数据/场景XX 等本地目录不会加入 Git）')
    print('原始 402 MB HaGRID ZIP：不上传，只记录来源和 SHA256')
    print('目前是单轮摄像头调试，不是独立测试成绩。')
    head = git('rev-parse','HEAD')
    if head == BASE:
        if remote_sha('refs/heads/main') != BASE or remote_sha(f'refs/tags/{TAG}'):
            raise RuntimeError('远程已有不同的 main 或 v1.1.0 标签，拒绝覆盖')
        prepare_text_updates(Path(__file__).resolve())
        count = stage_and_verify(public_files)
        print(f'准备提交 {count} 个文件（其中 389 张公开 JPG）；不会上传私有采集样本。')
        # 本地 11 项单元测试，在提交之前执行，防止带错误源码创建标签。
        py = ROOT / '.venv' / 'Scripts' / 'python.exe'
        if not py.exists():
            raise RuntimeError('未找到现有 Python 虚拟环境，拒绝发布')
        p = subprocess.run([str(py),'-m','unittest','discover','-s','测试','-p','test_*.py','-v'],
                           cwd=ROOT, env=ENV)
        if p.returncode != 0:
            raise RuntimeError('自动化测试失败，未提交/推送')
        if input('确认发布 Private v1.1.0（含389张公开照片）？输入 YES：').strip().upper() != 'YES':
            print('已取消。文件变更仍留在本地，未推送。')
            return
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(SUBJECT.encode('utf-8'))
            msg = f.name
        try:
            git('-c','i18n.commitEncoding=utf-8','commit','-F',msg)
        finally:
            Path(msg).unlink(missing_ok=True)
        head = git('rev-parse','HEAD')
    else:
        if git('log','-1','--format=%s') != SUBJECT:
            raise RuntimeError('本地不是预定的 v1.1.0 提交，拒绝变更')
    parent = git('rev-parse','HEAD^')
    if parent != BASE or git('log','-1','--format=%s') != SUBJECT:
        raise RuntimeError('提交父节点或提交说明不符合预期')
    if git('status','--porcelain'):
        raise RuntimeError('项目工作区仍存在未提交变更，请确认后再继续')
    remote = remote_sha('refs/heads/main')
    if remote == BASE:
        print('正在推送 main 分支...')
        git('push','origin','main')
    elif remote != head:
        raise RuntimeError(f'远程 main 已被其他操作更新：{remote}；不会强推')
    if not git('tag','-l',TAG):
        git('tag','-a',TAG,'-m',TAG,head)
    if git('rev-list','-n','1',TAG) != head:
        raise RuntimeError('本地 v1.1.0 标签指向其他提交')
    remote_tag = remote_sha(f'refs/tags/{TAG}')
    if not remote_tag:
        print('正在推送 v1.1.0 标签...')
        git('push','origin',TAG)
    peeled=remote_sha(f'refs/tags/{TAG}^{{}}')
    if peeled != head or remote_sha('refs/heads/main') != head:
        raise RuntimeError('远程 Tag 或 main 未与新提交一致')
    out = ROOT / '.发布'
    out.mkdir(exist_ok=True)
    asset = out / ASSET
    create_portable_source_archive(TAG, asset)
    asset_hash = sha(asset.read_bytes())
    release = run('gh','api',f'repos/{REPO}/releases/tags/{TAG}',ok=(0,1))
    if release[1] == 1:
        # 只有真正的 API 404 才能新建，网络异常绝不当作“不存在”。
        p = subprocess.run([GH,'api',f'repos/{REPO}/releases/tags/{TAG}'],cwd=ROOT,env=ENV,
                           capture_output=True)
        if b'404' not in p.stderr and b'Not Found' not in p.stderr:
            raise RuntimeError('Release 查询失败（非404），先检查网络再续传')
        gh('release','create',TAG,str(asset),'--repo',REPO,'--verify-tag',
           '--title','v1.1.0 · 混合数据训练与场景微调',
           '--notes-file',str(ROOT/'文档/发布说明-1.1.0.txt'))
    else:
        r=json.loads(release[0])
        if not any(x['name']==ASSET for x in r.get('assets',[])):
            gh('release','upload',TAG,str(asset),'--repo',REPO)
    result=api(f'repos/{REPO}/releases/tags/{TAG}')
    if (result.get('draft') or not any(x.get('name')==ASSET for x in result.get('assets',[]))
            or remote_sha('refs/heads/main') != head or remote_sha(f'refs/tags/{TAG}^{{}}') != head
            or api(f'repos/{REPO}').get('private') is not True):
        raise RuntimeError('发布后校验失败，需要进一步核对；勿重建仓库')
    print('\n' + '='*63)
    print('GitHub v1.1.0 代码、389 张公开图像、Tag、Release 已核验成功')
    print('Commit：', SUBJECT, head)
    print('Release：', result.get('html_url'))
    print('源码归档：', ASSET, 'SHA256：', asset_hash)
    print('私人场景01数据：未提交。模型权重：未提交。')
    print('='*63)


if __name__ == '__main__':
    try:
        publish()
    except Exception as ex:
        print('[发布中止]',type(ex).__name__ + ':',ex,file=sys.stderr)
        sys.exit(1)
