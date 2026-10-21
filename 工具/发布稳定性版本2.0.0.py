# -*- coding: utf-8 -*-
"""Gesture Studio 2.0.0 publisher for Windows 11 (sequential safe releases).

Ensures v1.7.1 is published before creating the v2.0.0 commit from the
verified v1.7.1 commit. Changes only a detached Git worktree, never
local working files, data, models, settings, nor local main.
Requires git and authenticated gh CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = 'nljie1103/gesture-intelligent-system'
OWNER = 'nljie1103'
PREVIOUS_SHA = '5056fcec381afb011157594df6a2fd9dc4f7711a'  # GitHub v1.7.0
BASE = ''  # v1.7.1 commit, validated at runtime
TAG = 'v2.0.0'
MESSAGE = 'v2.0.0修复训练数据与模型事务安全并重构实时交互性能'
TITLE = 'v2.0.0 · 稳定性与实时交互升级'
ZIP_NAME = 'gesture-v2.0.0-update.zip'
ZIP_SHA256 = '12d62266d70843de2008e4b17f9063ca721ff1932a98c880fdd9cd60cc3e3da4'
PROJECT = Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统'
UPDATE = Path(__file__).resolve().parent / ZIP_NAME
PUBLISHER = '工具/发布稳定性版本2.0.0.py'
EXPECTED = {
    '手势系统/__init__.py',
    '手势系统/现代界面.py',
    '手势系统/工作台训练.py',
    '手势系统/工作台数据.py',
    '手势系统/训练状态.py',
    '手势系统/推理.py',
    '手势系统/相机线程.py',
    '手势系统/图片交互.py',
    '手势系统/模型发布.py',
    '测试/test_界面v15.py',
    '测试/test_稳定性v200.py',
    '文档/版本说明-2.0.0.txt',
    '版本.txt',
}
CHANGED = EXPECTED | {PUBLISHER}
NOTES = """## Gesture Studio v2.0.0 · 全局稳定性与实时交互修复

- 修复手势暂停后不能通过食指指向恢复的问题，区分手势暂停与手动停止。
- 摄像头采集和推理转移到 QThread 后台线程，减少 UI 主线程阻塞。
- 增加独立图片交互窗口，让翻页、缩放手势有真实操作对象。
- 模型与训练来源记录采用故障恢复发布机制，训练失败时不留半更新状态。
- 运行阈值绑定模型 SHA256，旧模型阈值不再自动作用于新模型。
- 对畸形图片、训练数据被移动和训练快照清理增加防护。
- 统一 2.0.0 版本标识，补充 13 项稳定性回归测试（累计 71 项）。

**验证范围：** 已通过自动化测试、训练事务故障注入与本地安装模拟；发布前脚本将在 Win11-Dev 的项目虚拟环境重新运行全套测试。实际摄像头帧率、硬件断连恢复和 Qt 交互仍应以用户 Windows 11 实测为准。

公开仓库沿用原有 Public 权限；只提交版本白名单代码、测试和文档。不提交私人图片、训练权重、个人设置与运行日志。
"""



def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def call(*args: str, cwd: Path = PROJECT, check: bool = True, timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(list(map(str, args)), cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout,
                           env={**os.environ, 'GIT_TERMINAL_PROMPT':'0'})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError('执行失败：'+str(args[0])+'；'+str(e)) from e
    output = p.stdout.decode('utf-8', errors='replace').strip()
    if check and p.returncode:
        raise RuntimeError(f'命令失败 ({p.returncode}): {args[0]} {str(args[1:])[:130]}\n{output[-1800:]}')
    return p.returncode, output


def git(*args: str, cwd: Path = PROJECT) -> str:
    return call('git', *args, cwd=cwd)[1]


def gh(*args: str, cwd: Path = PROJECT) -> str:
    return call('gh', *args, cwd=cwd)[1]


def bytes_from_git(revision: str, name: str, cwd: Path = PROJECT) -> bytes:
    p = subprocess.run(['git','show',f'{revision}:{name}'], cwd=cwd,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE, timeout=60)
    if p.returncode:
        raise RuntimeError('读取原始 Git 文件对象失败：'+name+'；'+p.stderr.decode('utf-8','replace')[-400:])
    return p.stdout


def diff_names(before: str, after: str, cwd: Path = PROJECT) -> set[str]:
    p = subprocess.run(['git','-c','core.quotepath=false','diff','--name-only','-z',before,after],
                       cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    if p.returncode:
        raise RuntimeError('无法检查 Commit 变更文件：'+p.stderr.decode('utf-8','replace')[-400:])
    return {name.decode('utf-8') for name in p.stdout.split(b'\0') if name}


def remote_ref(name: str) -> str | None:
    result = git('ls-remote','origin',name)
    rows = [line.split()[0] for line in result.splitlines()
            if len(line.split()) == 2 and line.split()[1] == name]
    if len(rows) > 1:
        raise RuntimeError('重复远程引用 '+name)
    return rows[0] if rows else None


def release_status() -> str:
    code, out = call('gh','api','-i',f'repos/{REPO}/releases/tags/{TAG}',check=False)
    matches = re.findall(r'^HTTP/\d(?:\.\d+)?\s+(\d{3})(?:\s|$)',out,flags=re.M|re.I)
    http = matches[-1] if matches else None
    if code == 0 and http in ('200',None):
        return 'exists'
    if code != 0 and http == '404':
        return 'absent'
    raise RuntimeError('无法确认 Release 是否存在，拒绝发布：'+out[:650])


def verify_zip() -> tuple[dict[str, bytes],dict]:
    if not UPDATE.is_file():
        raise RuntimeError('未找到 v2.0.0 配套 ZIP：' + str(UPDATE))
    actual=sha_file(UPDATE)
    if actual!=ZIP_SHA256:
        raise RuntimeError('v2.0.0 ZIP SHA256 不匹配；实际 '+actual+'；预期 '+ZIP_SHA256)
    with zipfile.ZipFile(UPDATE) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=EXPECTED|{'manifest.json'}:
            raise RuntimeError('v2.0.0 ZIP 文件白名单不一致')
        manifest=json.loads(z.read('manifest.json'))
        if (manifest.get('version')!='2.0.0'
                or manifest.get('package_revision')!='stable-20261021-a'
                or manifest.get('base_version')!='1.7.1'
                or set(manifest.get('files',{}))!=EXPECTED
                or set(manifest.get('base_files',{}))!=EXPECTED
                or manifest.get('commit_title')!=MESSAGE):
            raise RuntimeError('v2.0.0 ZIP 版本、基线或清单不匹配')
        files={}
        for name in EXPECTED:
            if '..' in name.split('/') or name.startswith('/') or '\\' in name:
                raise RuntimeError('非法路径：'+name)
            info=z.getinfo(name)
            if info.is_dir() or info.file_size>250000:
                raise RuntimeError('更新文件大小异常：'+name)
            data=z.read(name)
            if sha_bytes(data)!=manifest['files'][name]:
                raise RuntimeError('文件哈希校验失败：'+name)
            files[name]=data
    return files,manifest


def verify_environment() -> None:
    if not PROJECT.is_dir() or not (PROJECT/'.git').exists():
        raise RuntimeError('找不到项目 Git 工作目录：'+str(PROJECT))
    origin=git('remote','get-url','origin')
    allowed={f'https://github.com/{REPO}',f'https://github.com/{REPO}.git',f'git@github.com:{REPO}.git'}
    if origin not in allowed:
        raise RuntimeError('origin 不是预期仓库：'+origin)
    if gh('api','user','--jq','.login') != OWNER:
        raise RuntimeError('当前 GitHub CLI 登录用户不是 '+OWNER)
    if gh('api',f'repos/{REPO}','--jq','.permissions.push').lower()!='true':
        raise RuntimeError('没有仓库推送权限')
    visibility=gh('api',f'repos/{REPO}','--jq','.private').lower()
    if visibility not in ('true','false'):
        raise RuntimeError('无法确认仓库公开状态')
    print('[权限] 仓库 '+('Private' if visibility=='true' else 'Public（由用户主动公开）'),flush=True)
    if not (PROJECT/'.venv'/'Scripts'/'python.exe').is_file():
        raise RuntimeError('找不到项目 .venv Python，无法运行发布前单元测试')
    print('[保护] 本机 main、源码、私人场景图片和权重均不会修改',flush=True)
    # Fetch only after repo/account validation. No reset, checkout or add in PROJECT.
    git('fetch','origin','main')


def verify_base(manifest: dict, cwd: Path) -> None:
    for name,expected in manifest['base_files'].items():
        code,_=call('git','cat-file','-e',f'{BASE}:{name}',cwd=cwd,check=False)
        if expected is None:
            if code==0:
                raise RuntimeError('新增文件已存在于 v1.7.1：'+name)
            continue
        if code!=0:
            raise RuntimeError('GitHub v1.7.1 缺少基础文件：'+name)
        actual=sha_bytes(bytes_from_git(BASE,name,cwd))
        if actual!=expected:
            raise RuntimeError('GitHub v1.7.1 的文件与 v2.0.0 更新包不匹配：'+name+'；SHA256='+actual)


def verify_published_commit(sha: str, files: dict[str,bytes]) -> None:
    if git('rev-parse',sha+'^')!=BASE:
        raise RuntimeError('远程 v2.0.0 的父提交不是已发布 v1.7.1')
    if git('log','-1','--format=%s',sha)!=MESSAGE:
        raise RuntimeError('远程 Commit 标题不匹配')
    changed=diff_names(BASE,sha)
    if changed!=CHANGED:
        raise RuntimeError('远程变更文件超出/缺少白名单：'+repr(changed))
    for name,data in files.items():
        if sha_bytes(bytes_from_git(sha,name)) != sha_bytes(data):
            raise RuntimeError('远程文件内容与安装包不一致：'+name)
    publisher=bytes_from_git(sha,PUBLISHER)
    if publisher!=Path(__file__).read_bytes():
        raise RuntimeError('远程发布脚本与当前文件不一致')


def make_commit(files: dict[str,bytes], manifest: dict, folder: Path) -> str:
    git('worktree','add','--detach',str(folder),BASE)
    try:
        verify_base(manifest,folder)
        for name,data in files.items():
            path=folder/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
        publisher=folder/PUBLISHER
        publisher.parent.mkdir(parents=True,exist_ok=True)
        publisher.write_bytes(Path(__file__).read_bytes())
        # Explicitly disable autocrlf for *this staging operation* so the index
        # contains exactly the bytes from the verified v1.7.1 ZIP on Windows.
        git('-c','core.autocrlf=false','add','--',*sorted(CHANGED),cwd=folder)
        p=subprocess.run(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],
                         cwd=folder,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
        if p.returncode:
            raise RuntimeError('无法读取 Git 暂存列表')
        staged={name.decode('utf-8') for name in p.stdout.split(b'\0') if name}
        if staged!=CHANGED:
            raise RuntimeError('Git 暂存文件与白名单不一致：'+repr(staged))
        for name,data in files.items():
            if sha_bytes(bytes_from_git('',name,folder)) != sha_bytes(data):
                raise RuntimeError('Git 暂存时发生了文件字节变换：'+name)
        if bytes_from_git('',PUBLISHER,folder)!=Path(__file__).read_bytes():
            raise RuntimeError('发布脚本暂存字节不一致')
        runner=PROJECT/'.venv'/'Scripts'/'python.exe'
        print('[测试] 独立 v2.0.0 工作区运行全部自动化测试...',flush=True)
        proc=subprocess.run([str(runner),'-m','unittest','discover','-s','测试','-v'],
                            cwd=folder,timeout=300,stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            env={**os.environ,'PYTHONIOENCODING':'utf-8:backslashreplace','PYTHONUTF8':'1'})
        result=proc.stdout.decode('utf-8',errors='replace').replace('\r\n','\n')
        print(result[-2500:],flush=True)
        if proc.returncode or not re.search(r'\bRan 71 tests in ',result) or not result.rstrip().endswith('OK'):
            raise RuntimeError('v2.0.0 必须通过完整 71 项测试；未执行推送')
        print('[测试通过] 71/71；开始 Qt 模块导入检查',flush=True)
        print('[验证] 使用项目虚拟环境检查 Qt 程序导入...',flush=True)
        call(str(runner),'-c',
             'from 手势系统.现代界面 import GestureWindow; '
             'from 手势系统.相机线程 import CameraWorker; '
             'from 手势系统.图片交互 import ImageControlDialog',
             cwd=folder,timeout=90)
        git('commit','-m',MESSAGE,cwd=folder)
        new_sha=git('rev-parse','HEAD',cwd=folder)
        if git('rev-parse','HEAD^',cwd=folder)!=BASE:
            raise RuntimeError('创建的 Commit 父提交错误')
        if diff_names(BASE,new_sha,cwd=folder)!=CHANGED:
            raise RuntimeError('Commit 文件范围错误')
        return new_sha
    finally:
        git('worktree','remove','--force',str(folder))


def ensure_tag(sha: str) -> None:
    remote=remote_ref('refs/tags/'+TAG)
    if remote:
        local=git('tag','--list',TAG)
        if local and git('rev-parse',TAG+'^{}')!=sha:
            raise RuntimeError('本地同名标签与远程版本冲突')
        if not local:
            git('fetch','origin','tag',TAG)
        if git('rev-parse',TAG+'^{}')!=sha:
            raise RuntimeError('远程 v2.0.0 标签指向其他 Commit')
        return
    local=git('tag','--list',TAG)
    if local:
        if git('rev-parse',TAG+'^{}')!=sha:
            raise RuntimeError('本地 v2.0.0 标签已存在但指向错误 Commit')
    else:
        git('tag','-a',TAG,sha,'-m','v2.0.0 全局稳定性与实时交互升级')
    git('push','origin','refs/tags/'+TAG)
    if not remote_ref('refs/tags/'+TAG):
        raise RuntimeError('远程标签推送未得到确认')


def ensure_release(sha: str, directory: Path) -> tuple[str,str]:
    archive=directory/'gesture-intelligent-system-v2.0.0-source.zip'
    git('archive','--format=zip',f'--output={archive}',sha)
    digest=sha_file(archive)
    notes=directory/'release-notes.md'
    notes.write_text(NOTES,encoding='utf-8')
    if release_status()=='absent':
        gh('release','create',TAG,str(archive),'--repo',REPO,'--verify-tag',
           '--title',TITLE,'--notes-file',str(notes))
    info=json.loads(gh('release','view',TAG,'--repo',REPO,'--json','name,tagName,isDraft,assets,url'))
    if info.get('name')!=TITLE or info.get('tagName')!=TAG or info.get('isDraft'):
        raise RuntimeError('远程 Release 版本/标题不一致')
    assets={item['name']:item for item in info.get('assets',[])}
    if archive.name not in assets:
        gh('release','upload',TAG,str(archive),'--repo',REPO)
        info=json.loads(gh('release','view',TAG,'--repo',REPO,'--json','name,tagName,isDraft,assets,url'))
        assets={item['name']:item for item in info.get('assets',[])}
    if archive.name not in assets or assets[archive.name]['size']!=archive.stat().st_size:
        raise RuntimeError('远程 Release 源码附件缺失或大小不一致')
    # GitHub REST API publishes the *server-calculated* SHA256 (assets[].digest).
    # A release download uses release-assets.githubusercontent.com/CDN, which may
    # be blocked or extremely slow on some Windows networks.  Do NOT require
    # downloading the same ~10MB asset just to verify what the server recorded.
    meta = release_metadata(TAG)
    if meta.get('tag_name') != TAG or meta.get('draft') or meta.get('name') != TITLE:
        raise RuntimeError('Release API 元数据校验失败')
    matching = [a for a in meta.get('assets', []) if a.get('name') == archive.name]
    if len(matching) != 1:
        raise RuntimeError('GitHub Release 中源码附件不存在或存在同名重复文件')
    asset = matching[0]
    if asset.get('state') != 'uploaded' or asset.get('size') != archive.stat().st_size:
        raise RuntimeError('GitHub 源码附件状态或大小与本地归档不一致')
    if asset.get('digest') != 'sha256:' + digest:
        raise RuntimeError('GitHub 服务器 SHA256 与本地归档不一致：远程='+str(asset.get('digest'))+'；本地='+digest)
    print('[校验] GitHub API 确认远程附件大小与 SHA256 完全一致（无需重新下载）', flush=True)
    return info['url'],digest



def release_metadata(tag: str) -> dict:
    """Fetch canonical GitHub release data including server-side asset digest."""
    obj = json.loads(gh('api', f'repos/{REPO}/releases/tags/{tag}'))
    if not isinstance(obj, dict) or obj.get('tag_name') != tag or obj.get('draft'):
        raise RuntimeError('GitHub Release 元数据不存在、Tag 不符或仍为草稿：' + tag)
    return obj


def verify_v171_release_asset() -> None:
    """Check already-published 1.7.1 without repeatedly downloading its ZIP."""
    meta = release_metadata('v1.7.1')
    if meta.get('name') != 'v1.7.1 · Windows中文训练日志修复':
        raise RuntimeError('已有 v1.7.1 Release 标题不是预期内容')
    name = 'gesture-intelligent-system-v1.7.1-source.zip'
    assets = [a for a in meta.get('assets',[]) if a.get('name') == name]
    if len(assets) != 1 or assets[0].get('state') != 'uploaded' or assets[0].get('size', 0) < 9000000:
        raise RuntimeError('已有 v1.7.1 Release 源码附件不完整')
    expected = 'sha256:158d4ace735b3d687c79ebacbac11439d5ba50792a2de9fff96da32048771d0a'
    if assets[0].get('digest') != expected:
        raise RuntimeError('已有 v1.7.1 Release 附件 SHA256 与 GitHub 核验值不一致')
    print('[历史检查] v1.7.1 的 Commit/Tag/Release/源码 SHA256 已确认，无需重新发布或下载',flush=True)


def ensure_v171_published() -> str:
    """Run the existing verified publisher to complete v1.7.1 when necessary.

    Incomplete prior attempts are resumed by the original v1.7.1 script; we do
    not bypass its commit verification, and never force-push.
    """
    current=remote_ref('refs/heads/main')
    previous=remote_ref('refs/tags/v1.7.1^{}')
    # A previously pushed v2.0.0 is also valid: v1.7.1 remains the base tag.
    # Its parentage and contents are checked below by verify_published_commit.
    complete=(previous is not None and gh_release_exists('v1.7.1'))
    if not complete:
        path=Path(__file__).resolve().parent/'publish-gesture-v1.7.1.py'
        companion=Path(__file__).resolve().parent/'gesture-v1.7.1-fixed-update.zip'
        expected_pub='b029f5dd07af81151754789fb1e52f2806db80fea7863277513d39a4cebd0225'
        expected_zip='672ed681a85090fad1bd7a7e53dfc339198a2055d0e37c1946e7763f24855a24'
        if not path.is_file() or sha_file(path)!=expected_pub:
            raise RuntimeError('必须先发布 v1.7.1：请把配套 publish-gesture-v1.7.1.py 放入 Downloads（SHA256 不匹配）')
        if not companion.is_file() or sha_file(companion)!=expected_zip:
            raise RuntimeError('必须先发布 v1.7.1：找不到正确的 gesture-v1.7.1-fixed-update.zip')
        if current != PREVIOUS_SHA and previous is None:
            # The v1.7.1 publisher can validate and resume an incomplete push.
            print('[检查] v1.7.1 可能曾中断，将使用原发布脚本校验和续传。',flush=True)
        else:
            print('[顺序发布] v1.7.1 尚未完整发布，将先运行已有 v1.7.1 发布脚本。',flush=True)
        child=subprocess.run([sys.executable,str(path)],cwd=PROJECT,timeout=900)
        if child.returncode:
            raise RuntimeError('v1.7.1 未成功完成；请先解决其报错，v2.0.0 没有推送')
        git('fetch','origin','main')
        current=remote_ref('refs/heads/main')
        previous=remote_ref('refs/tags/v1.7.1^{}')
    if previous is None or current!=previous or not gh_release_exists('v1.7.1'):
        raise RuntimeError('v1.7.1 未完整发布：远程 main/Tag/Release 不一致')
    verify_v171_release_asset()
    git('fetch','origin','tag','v1.7.1')
    if git('rev-parse','v1.7.1^{}')!=previous:
        raise RuntimeError('本机已存在冲突的 v1.7.1 Tag，拒绝发布 v2.0.0')
    if git('cat-file','-t',previous)!='commit':
        raise RuntimeError('找不到已发布的 v1.7.1 Commit')
    if git('rev-parse',previous+'^')!=PREVIOUS_SHA:
        raise RuntimeError('v1.7.1 父提交不是已经验证的 v1.7.0')
    print('[基线] v1.7.1 Commit='+previous,flush=True)
    return previous


def gh_release_exists(tag: str) -> bool:
    code,out=call('gh','api','-i',f'repos/{REPO}/releases/tags/{tag}',check=False)
    statuses=re.findall(r'^HTTP/\d(?:\.\d+)?\s+(\d{3})(?:\s|$)',out,flags=re.M|re.I)
    status=statuses[-1] if statuses else None
    if code==0 and status in ('200',None): return True
    if code!=0 and status=='404':return False
    raise RuntimeError('查询 GitHub '+tag+' Release 失败：'+out[:500])


def main() -> None:
    global BASE
    print('[修复] v2.0.0 安全续传：改用 GitHub 服务器 SHA256 校验，不再下载 Release 附件',flush=True)
    files,manifest=verify_zip()
    verify_environment()
    BASE=ensure_v171_published()
    remote=remote_ref('refs/heads/main')
    if remote==BASE:
        if remote_ref('refs/tags/'+TAG) or release_status()!='absent':
            raise RuntimeError('v2.0.0 Tag/Release 已存在，但 main 未更新；请检查远程状态')
        print('[提交]',MESSAGE)
        print('[清单] 仅提交 v2.0.0 的 13 个更新文件和一个发布脚本；不上传私人数据')
        if input('确认正式发布 v2.0.0？输入 YES：').strip()!='YES':
            print('已取消；没有向 GitHub 推送 v2.0.0')
            return
        with tempfile.TemporaryDirectory(prefix='gesture-v200-work-') as tmp:
            sha=make_commit(files,manifest,Path(tmp)/'repo')
        if remote_ref('refs/heads/main')!=BASE:
            raise RuntimeError('远程 main 被其他操作更新，本次停止推送')
        print('[推送] 从 v1.7.1 快进更新远程 main（不强制推送）...',flush=True)
        git('push','origin',sha+':refs/heads/main')
        if remote_ref('refs/heads/main')!=sha:
            raise RuntimeError('推送后无法确认 main 目标 SHA')
    else:
        print('[续传] GitHub main 已变化，检查是否为此前中断的 v2.0.0...',flush=True)
        git('fetch','origin','main')
        verify_published_commit(remote,files)
        sha=remote
        print('[续传] Commit 已存在，继续校验 Tag 与 Release',flush=True)
    ensure_tag(sha)
    with tempfile.TemporaryDirectory(prefix='gesture-v200-asset-') as tmp:
        url,digest=ensure_release(sha,Path(tmp))
    print('\n[发布成功] v2.0.0 '+sha)
    print('Release：'+url)
    print('Source SHA256：'+digest)
    print('本机工作区、main 指针、照片、模型权重和设置均未修改；GitHub 保持 Public。')


if __name__=='__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as err:
        print('[发布中止]',type(err).__name__+':',err,file=sys.stderr,flush=True)
        raise SystemExit(1)
