# -*- coding: utf-8 -*-
"""Publish v1.7.0 from its verified ZIP (portable newline test corrected) without downgrading v1.7.1.

Place this file and gesture-v1.7.0-releasefix.zip together in Downloads, then run
with C:\\Dev\\python\\python314\\python.exe on Win11-Dev.

A detached, temporary Git worktree is used. Git baseline checks read committed
blob bytes (not platform-specific LF/CRLF checkout bytes). Nothing in the installed project,
including models, photos, local settings, or uncommitted v1.7.1 files, is modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = 'nljie1103/gesture-intelligent-system'
OWNER = 'nljie1103'
BASE = '017c2dd35de38437a2e791dd26cf620157a8b475'
TAG = 'v1.7.0'
MESSAGE = 'v1.7.0修复训练日志中文编码与实时显示问题'
TITLE = 'v1.7.0 · 训练日志中文编码修复'
ZIP_SHA = 'b63904fbc9107cdb889e502762c0434d656a3d957d775c65ed0db529a9f78d71'
PROJECT = Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统'
UPDATE = Path(__file__).resolve().parent / 'gesture-v1.7.0-releasefix.zip'
PUBLISHER = '工具/发布日志编码版本1.7.0.py'
EXPECTED = {
    '手势系统/__init__.py',
    '手势系统/现代界面.py',
    '手势系统/训练日志编码.py',
    '文档/版本说明-1.7.0.txt',
    '测试/test_界面v15.py',
    '测试/test_训练日志编码v17.py',
    '版本.txt',
}
EXPECTED_CHANGE = EXPECTED | {PUBLISHER}
NOTES = '''## v1.7.0 · 训练日志中文编码修复

- 为 Windows 训练进程指定 UTF-8 输出编码。
- 使用 UTF-8 增量解码以处理 Qt 接收的分块中文字节。
- 新增编码回归测试，修正 Windows CRLF 与 Unix LF 的跨平台断言。

该版本是历史修复版本；真实 Windows 训练日志仍可能存在乱码，后续由 v1.7.1 进一步修正。

仅提交源代码与测试，不提交本地摄像头照片、模型权重、个人设置和训练日志。
'''


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def call(*args: str, cwd: Path = PROJECT, check: bool = True, timeout: int = 180) -> tuple[int, str]:
    try:
        proc = subprocess.run(list(map(str,args)), cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT':'0'})
    except FileNotFoundError as e:
        raise RuntimeError('未找到执行工具：'+str(args[0])) from e
    output = proc.stdout.decode('utf-8', errors='replace').strip()
    if check and proc.returncode:
        raise RuntimeError(f'命令失败 ({proc.returncode}): {args[0]} {str(args[1:])[:140]}\n{output[-1400:]}')
    return proc.returncode, output


def git(*args: str, cwd: Path = PROJECT) -> str:
    return call('git', *args, cwd=cwd)[1]


def gh(*args: str, cwd: Path = PROJECT) -> str:
    return call('gh', *args, cwd=cwd)[1]


def remote_ref(name: str) -> str | None:
    output = git('ls-remote', 'origin', name)
    matches = [v.split()[0] for v in output.splitlines() if len(v.split()) == 2 and v.split()[1] == name]
    if len(matches) > 1:raise RuntimeError('重复远程引用 '+name)
    return matches[0] if matches else None


def status_release() -> str:
    rc, output = call('gh', 'api', '-i', f'repos/{REPO}/releases/tags/{TAG}', check=False)
    m = re.findall(r'^HTTP/\d(?:\.\d+)?\s+(\d{3})(?:\s|$)', output, flags=re.M|re.I)
    status = m[-1] if m else None
    if rc == 0 and status in ('200',None):return 'exists'
    if rc != 0 and status == '404':return 'absent'
    raise RuntimeError('Release 查询不是正常的 200/404，拒绝继续：'+output[:550])


def validate_zip() -> tuple[dict[str,bytes],dict]:
    if not UPDATE.is_file():raise RuntimeError('缺少下载文件 '+str(UPDATE))
    if sha_file(UPDATE) != ZIP_SHA:raise RuntimeError('ZIP SHA256 不匹配，已停止')
    with zipfile.ZipFile(UPDATE) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != EXPECTED | {'manifest.json'}:
            raise RuntimeError('ZIP 文件名单异常')
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('version') != '1.7.0' or manifest.get('base_commit') != BASE:
            raise RuntimeError('ZIP 基线版本错误')
        if set(manifest.get('files',{})) != EXPECTED:raise RuntimeError('ZIP 白名单有误')
        if not isinstance(manifest.get('baseline_files'),dict):raise RuntimeError('缺少基础校验清单')
        files={}
        for p in EXPECTED:
            data=z.read(p)
            if sha_bytes(data)!=manifest['files'][p]:raise RuntimeError('ZIP 内文件校验失败 '+p)
            files[p]=data
    return files,manifest


def verify_environment() -> None:
    if not PROJECT.is_dir() or not (PROJECT/'.git').exists():
        raise RuntimeError('找不到原始 Git 工作目录：'+str(PROJECT))
    remote = git('remote','get-url','origin')
    allowed={f'https://github.com/{REPO}',f'https://github.com/{REPO}.git',f'git@github.com:{REPO}.git'}
    if remote not in allowed:raise RuntimeError('origin 不是指定仓库：'+remote)
    if gh('api','user','--jq','.login')!=OWNER:
        raise RuntimeError('gh 登录用户不是 '+OWNER)
    p=gh('api',f'repos/{REPO}','--jq','.permissions.push')
    if p.lower()!='true':raise RuntimeError('当前账号没有 Push 权限')
    visible=gh('api',f'repos/{REPO}','--jq','.private')
    if visible.lower() not in ('true','false'):raise RuntimeError('无法确认仓库权限')
    print('[权限] GitHub 仓库当前为 '+('Private' if visible.lower()=='true' else 'Public（用户主动公开）'))
    git('cat-file','-e',BASE+'^{commit}')
    if git('branch','--show-current')!='main':raise RuntimeError('本地当前分支不是 main')
    # Local HEAD may be v1.6.0 (uncommitted v1.7.1), or a previously created v1.7.0 commit.
    # This script never resets, stages or updates the user's local main worktree.


def verify_remote_commit(sha: str, files: dict[str,bytes]) -> None:
    # Remote must be exact expected version, with correct parent/message and files.
    if git('rev-parse',sha+'^')!=BASE:raise RuntimeError('远程 v1.7.0 的父 Commit 不正确')
    if git('log','-1','--format=%s',sha)!=MESSAGE:raise RuntimeError('远程 v1.7.0 Commit 标题不正确')
    # git outputs quoted Chinese filepaths by default; use raw -z bytes instead for verification.
    names = set(s.decode('utf-8') for s in subprocess.check_output(
        ['git','-c','core.quotepath=false','diff','--name-only','-z',BASE,sha],cwd=PROJECT).split(b'\0') if s)
    if names != EXPECTED_CHANGE:raise RuntimeError('远程 v1.7.0 变更文件范围异常：'+repr(names))
    for p,data in files.items():
        got=subprocess.check_output(['git','show',f'{sha}:{p}'],cwd=PROJECT)
        if sha_bytes(got)!=sha_bytes(data):raise RuntimeError('远程源码与 ZIP 不一致：'+p)
    source=subprocess.check_output(['git','show',f'{sha}:{PUBLISHER}'],cwd=PROJECT)
    if source!=Path(__file__).read_bytes():raise RuntimeError('远程发布脚本内容与当前文件不一致')


def create_commit(files: dict[str,bytes], manifest: dict, folder: Path) -> str:
    # Isolated detached worktree. Nothing is copied into the real local project.
    git('worktree','add','--detach',str(folder),BASE)
    try:
        # Check the *committed Git blobs*, not checkout bytes. On Windows,
        # Git core.autocrlf can change LF to CRLF in worktrees even though
        # the canonical Git tree is byte-for-byte identical to the ZIP base.
        for name,expected_sha256 in manifest['baseline_files'].items():
            proc = subprocess.run(['git','show',f'{BASE}:{name}'], cwd=folder,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if proc.returncode != 0:
                raise RuntimeError('读取 Git v1.6.0 原始文件失败：'+name+'；'+
                                   proc.stderr.decode('utf-8',errors='replace')[-400:])
            if sha_bytes(proc.stdout) != expected_sha256:
                raise RuntimeError('Git v1.6.0 原始提交内容与补丁基线不一致：'+name)
        for name,data in files.items():
            p=folder/name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(data)
        publisher=folder/PUBLISHER
        publisher.parent.mkdir(parents=True,exist_ok=True)
        publisher.write_bytes(Path(__file__).read_bytes())
        git('add','--',*sorted(EXPECTED_CHANGE),cwd=folder)
        staged=set(s.decode('utf-8') for s in subprocess.check_output([
          'git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=folder).split(b'\0') if s)
        if staged!=EXPECTED_CHANGE:raise RuntimeError('暂存文件不符合白名单：'+repr(staged))
        runner=PROJECT/'.venv'/'Scripts'/'python.exe'
        if not runner.is_file():raise RuntimeError('项目虚拟环境不存在：'+str(runner))
        print('[测试] 在独立的 v1.7.0 工作区运行项目测试...',flush=True)
        r=subprocess.run([str(runner),'-m','unittest','discover','-s','测试','-v'],cwd=folder,timeout=240)
        if r.returncode:raise RuntimeError('v1.7.0 单元测试未通过，未推送')
        git('commit','-m',MESSAGE,cwd=folder)
        sha=git('rev-parse','HEAD',cwd=folder)
        if git('rev-parse','HEAD^',cwd=folder)!=BASE:raise RuntimeError('父 Commit 不匹配')
        # The detached worktree owns this commit and will be cleaned in finally.
        return sha
    finally:
        git('worktree','remove','--force',str(folder))


def ensure_tag(sha: str) -> None:
    existing=remote_ref('refs/tags/'+TAG)
    if existing:
        # Tag can be annotated (an object SHA different from commit SHA).
        git('fetch','origin','tag',TAG)
        if git('rev-parse',TAG+'^{}') != sha:
            raise RuntimeError('已存在的远程 Tag 指向不同 Commit')
        return
    # If local tag exists but remote does not, validate and push it; otherwise create fresh annotated tag.
    local=git('tag','--list',TAG)
    if local:
        if git('rev-parse',TAG+'^{}')!=sha:raise RuntimeError('本地已有错误的 v1.7.0 Tag')
    else:
        git('tag','-a',TAG,sha,'-m','v1.7.0 训练日志中文编码修复')
    git('push','origin','refs/tags/'+TAG)
    if not remote_ref('refs/tags/'+TAG):raise RuntimeError('远程标签推送失败')


def ensure_release(sha: str, folder: Path) -> tuple[str,str]:
    archive=folder/'gesture-intelligent-system-v1.7.0-source.zip'
    git('archive','--format=zip',f'--output={archive}',sha)
    digest=sha_file(archive)
    note=folder/'notes.md'
    note.write_text(NOTES,encoding='utf-8')
    if status_release()=='absent':
        gh('release','create',TAG,str(archive),'--repo',REPO,'--verify-tag',
           '--title',TITLE,'--notes-file',str(note))
    info=json.loads(gh('release','view',TAG,'--repo',REPO,'--json','name,tagName,isDraft,assets,url'))
    if info.get('name')!=TITLE or info.get('tagName')!=TAG or info.get('isDraft'):
        raise RuntimeError('Release 版本/标题不正确')
    assets={a['name']:a for a in info.get('assets',[])}
    if archive.name not in assets:
        gh('release','upload',TAG,str(archive),'--repo',REPO)
        info=json.loads(gh('release','view',TAG,'--repo',REPO,'--json','name,tagName,isDraft,assets,url'))
        assets={a['name']:a for a in info.get('assets',[])}
    if archive.name not in assets or assets[archive.name]['size']!=archive.stat().st_size:
        raise RuntimeError('Release ZIP 附件缺失或大小错误')
    with tempfile.TemporaryDirectory(prefix='gesture-v170-check-') as temp:
        gh('release','download',TAG,'--repo',REPO,'--pattern',archive.name,'--dir',temp)
        if sha_file(Path(temp)/archive.name)!=digest:
            raise RuntimeError('GitHub 重新下载的 ZIP 校验失败')
    return info['url'],digest


def main() -> None:
    files,manifest=validate_zip()
    verify_environment()
    remote=remote_ref('refs/heads/main')
    if not remote:raise RuntimeError('远程 main 不存在')
    resumed=False
    if remote!=BASE:
        print('[恢复] main 已变化，核查是否为此前发布到一半的 v1.7.0...',flush=True)
        # Fetch that exact head rather than trusting stale tracking refs.
        git('fetch','origin','main')
        verify_remote_commit(remote,files)
        sha=remote
        resumed=True
    else:
        if remote_ref('refs/tags/'+TAG) or status_release()!='absent':
            raise RuntimeError('v1.7.0 标签/Release 已存在，但 main 仍是 v1.6.0，停止人工核查')
        print('[检查] v1.7.0 ZIP 内容合法；Git 原始对象校验；单元测试兼容 Windows CRLF。')
        print('[提交]',MESSAGE)
        print('[保护] 当前项目安装、未提交修改、数据与模型完全不变。')
        if input('确认发布 v1.7.0 到当前 GitHub 仓库？输入 YES：').strip()!='YES':
            print('已取消，未修改远程仓库')
            return
        with tempfile.TemporaryDirectory(prefix='gesture-v170-work-') as tmp:
            sha=create_commit(files,manifest,Path(tmp)/'repo')
        if remote_ref('refs/heads/main') != BASE:
            raise RuntimeError('远程 main 已变化，未执行推送')
        print('[推送] 从独立 Commit 快进更新远程 main...',flush=True)
        git('push','origin',sha+':refs/heads/main')  # never force
        if remote_ref('refs/heads/main')!=sha:raise RuntimeError('main 推送校验失败')
    if resumed: print('[恢复] 沿用已有 Commit',sha,flush=True)
    ensure_tag(sha)
    with tempfile.TemporaryDirectory(prefix='gesture-v170-asset-') as tmp:
        url,digest=ensure_release(sha,Path(tmp))
    print('\n[成功] v1.7.0 已发布：',sha,'\nRelease:',url,'\nSHA256:',digest)
    print('[提醒] 本机安装未变动。若已安装 v1.7.1，保留它；本机 main 分支指针也未改动。')
    print('[后续] v1.7.1 需要基于新 v1.7.0 提交继续发布。')

if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:
        print('[发布中止]',type(e).__name__+':',e,file=sys.stderr,flush=True)
        raise SystemExit(1)
