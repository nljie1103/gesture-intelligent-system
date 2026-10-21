# -*- coding: utf-8 -*-
"""Gesture Studio v1.7.1 GitHub release publisher for Win11-Dev.

Publishes the verified v1.7.1 fixed ZIP atop the *already published* remote
v1.7.0 commit. Local source checkout, current branch, user pictures, settings,
training reports and model weights are never staged, reset, or modified.
Requirements: existing project Git repository, its .venv, git and gh CLI auth.
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
BASE = '5056fcec381afb011157594df6a2fd9dc4f7711a'  # published v1.7.0
TAG = 'v1.7.1'
MESSAGE = 'v1.7.1彻底修复Windows训练日志中文乱码问题'
TITLE = 'v1.7.1 · Windows中文训练日志修复'
ZIP_NAME = 'gesture-v1.7.1-fixed-update.zip'
ZIP_SHA256 = '672ed681a85090fad1bd7a7e53dfc339198a2055d0e37c1946e7763f24855a24'
PROJECT = Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统'
UPDATE = Path(__file__).resolve().parent / ZIP_NAME
PUBLISHER = '工具/发布日志编码版本1.7.1.py'
EXPECTED = {
    '手势系统/现代界面.py',
    '手势系统/训练日志编码.py',
    '手势系统/训练日志自检.py',
    '手势系统/工作台训练.py',
    '手势系统/__init__.py',
    '测试/test_训练日志编码v17.py',
    '测试/test_训练日志编码v171.py',
    '测试/test_界面v15.py',
    '文档/版本说明-1.7.1.txt',
    '版本.txt',
}
CHANGED = EXPECTED | {PUBLISHER}
NOTES = '''## v1.7.1 · Windows 中文训练日志修复

- 统一训练子进程的 UTF-8 标准输出与错误输出，并兼容 Windows GBK/CP936。
- 通过增量解码处理 Qt 日志的任意分块，避免汉字截断乱码。
- 新增“测试中文日志”功能：无需重新训练，也不修改模型权重。
- 更新中文路径、跨平台换行、Windows 子进程等回归测试。

已在 Windows 11 实际运行“测试中文日志”并确认中文显示正常；不将该自检视为完整训练准确率或独立模型评估。

只提交白名单内的源码、文档和测试；不上传私人摄像头照片、训练权重、个人设置或本地日志。
'''


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
        raise RuntimeError('未找到配套更新包：'+str(UPDATE))
    actual = sha_file(UPDATE)
    if actual != ZIP_SHA256:
        raise RuntimeError('更新包 SHA256 不匹配；实际 '+actual+'；预期 '+ZIP_SHA256)
    with zipfile.ZipFile(UPDATE) as z:
        names = z.namelist()
        if len(names)!=len(set(names)) or set(names)!=EXPECTED | {'manifest.json'}:
            raise RuntimeError('更新包文件白名单不一致，拒绝发布')
        m = json.loads(z.read('manifest.json'))
        if m.get('version') != '1.7.1' or set(m.get('files',{}))!=EXPECTED:
            raise RuntimeError('更新包版本或清单不正确')
        if set(m.get('new_files',[])) != {
            '手势系统/训练日志自检.py','测试/test_训练日志编码v171.py',
            '文档/版本说明-1.7.1.txt'}:
            raise RuntimeError('新增文件清单不正确')
        if not isinstance(m.get('baseline_files'),dict):
            raise RuntimeError('缺少 Git 基线清单')
        files = {}
        for name in EXPECTED:
            data = z.read(name)
            if sha_bytes(data)!=m['files'][name]:
                raise RuntimeError('更新包文件校验失败：'+name)
            files[name]=data
    return files,m


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
    if git('cat-file','-t',BASE)!='commit':
        raise RuntimeError('Git 中找不到已发布的 v1.7.0 Commit')


def verify_base(manifest: dict, cwd: Path) -> None:
    baselines=manifest['baseline_files']
    alternates=manifest.get('baseline_alternatives',{})
    for name,expected in baselines.items():
        allowed={expected,*alternates.get(name,[])}
        source=bytes_from_git(BASE,name,cwd)
        digest=sha_bytes(source)
        if digest not in allowed:
            raise RuntimeError('GitHub v1.7.0 基线与补丁不一致：'+name+'；实际 '+digest)
    for name in manifest['new_files']:
        if call('git','cat-file','-e',f'{BASE}:{name}',cwd=cwd,check=False)[0]==0:
            raise RuntimeError('准备新增的文件已存在于旧版：'+name)


def verify_published_commit(sha: str, files: dict[str,bytes]) -> None:
    if git('rev-parse',sha+'^')!=BASE:
        raise RuntimeError('远程 v1.7.1 的父提交不是已发布 v1.7.0')
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
        print('[测试] 独立 v1.7.1 工作区运行全部自动化测试...',flush=True)
        proc=subprocess.run([str(runner),'-m','unittest','discover','-s','测试','-v'],
                            cwd=folder,timeout=300)
        if proc.returncode:
            raise RuntimeError('v1.7.1 自动测试未通过；未执行推送')
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
            raise RuntimeError('远程 v1.7.1 标签指向其他 Commit')
        return
    local=git('tag','--list',TAG)
    if local:
        if git('rev-parse',TAG+'^{}')!=sha:
            raise RuntimeError('本地 v1.7.1 标签已存在但指向错误 Commit')
    else:
        git('tag','-a',TAG,sha,'-m','v1.7.1 Windows 中文训练日志修复')
    git('push','origin','refs/tags/'+TAG)
    if not remote_ref('refs/tags/'+TAG):
        raise RuntimeError('远程标签推送未得到确认')


def ensure_release(sha: str, directory: Path) -> tuple[str,str]:
    archive=directory/'gesture-intelligent-system-v1.7.1-source.zip'
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
    with tempfile.TemporaryDirectory(prefix='gesture171-verify-') as tmp:
        gh('release','download',TAG,'--repo',REPO,'--pattern',archive.name,'--dir',tmp)
        if sha_file(Path(tmp)/archive.name)!=digest:
            raise RuntimeError('GitHub 源码附件重新下载后 SHA256 不匹配')
    return info['url'],digest


def main() -> None:
    files,manifest=verify_zip()
    verify_environment()
    remote=remote_ref('refs/heads/main')
    if not remote:
        raise RuntimeError('找不到远程 main')
    if remote==BASE:
        if remote_ref('refs/tags/'+TAG) or release_status()!='absent':
            raise RuntimeError('v1.7.1 Tag/Release 已存在但 main 未更新，请检查异常')
        print('[基线] GitHub main=v1.7.0 '+BASE[:12])
        print('[提交]',MESSAGE)
        print('[清单] 仅提交 v1.7.1 的 10 个更新文件和 1 个发布脚本，不包含私人数据')
        if input('确认正式发布 v1.7.1？输入 YES：').strip()!='YES':
            print('已取消；没有修改 GitHub')
            return
        with tempfile.TemporaryDirectory(prefix='gesture-v171-work-') as tmp:
            sha=make_commit(files,manifest,Path(tmp)/'repo')
        if remote_ref('refs/heads/main')!=BASE:
            raise RuntimeError('远程 main 被其他操作更新，本次停止推送')
        print('[推送] 正在从 v1.7.0 快进更新远程 main...',flush=True)
        git('push','origin',sha+':refs/heads/main')  # fast-forward only; no force
        if remote_ref('refs/heads/main')!=sha:
            raise RuntimeError('远程 main 推送后未得到确认')
    else:
        print('[续传] GitHub main 已变化，核验是否为之前发布一半的 v1.7.1...',flush=True)
        git('fetch','origin','main')
        verify_published_commit(remote,files)
        sha=remote
        print('[续传] Commit 已存在，继续检查 Tag 与 Release',flush=True)
    ensure_tag(sha)
    with tempfile.TemporaryDirectory(prefix='gesture-v171-asset-') as tmp:
        url,digest=ensure_release(sha,Path(tmp))
    print('\n[发布成功] v1.7.1 '+sha)
    print('Release：'+url)
    print('Source SHA256：'+digest)
    print('本机已安装软件、本地 main、私人采集数据、模型权重均未修改。')


if __name__=='__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as err:
        print('[发布中止]',type(err).__name__+':',err,file=sys.stderr,flush=True)
        raise SystemExit(1)
