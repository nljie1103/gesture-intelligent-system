# -*- coding: utf-8 -*-
"""Gesture Studio v1.5.0 安全发布程序。

用法：放到 Downloads，与 gesture-ui-polish-v1.5.0-update.zip 同目录，
在 Win11-Dev 执行：
  & "C:\\Dev\\python\\python314\\python.exe" "$env:USERPROFILE\\Downloads\\publish-gesture-v1.5.0.py"
只暂存已验证的五个升级文件和此发布脚本；不提交私人采集数据、模型或本地设置。
支持推送 main、Tag、Release 附件时中断后的原状态继续执行。
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
BASE = '4bcb42a46927f05ab62bb7eb3b9cef827d1b2459'
TAG = 'v1.5.0'
MESSAGE = 'v1.5.0修复窗口圆角并统一导航与控件样式'
TITLE = 'v1.5.0 · 窗口与界面细节优化'
ZIP_SHA256 = 'cb009ce1f828a3c2f4ae77fab3fad83af959bbc00152cf38b8957dbb663b1c5b'
PROJECT = Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统'
UPDATE = Path.home() / 'Downloads' / 'gesture-ui-polish-v1.5.0-update.zip'
PUBLISHER_REL = '工具/发布界面优化版本1.5.0.py'
EXPECTED_FILES = {
    '手势系统/现代界面.py',
    '手势系统/__init__.py',
    '版本.txt',
    '文档/版本说明-1.5.0.txt',
    '测试/test_界面v15.py',
}
RELEASE_NOTES = '''## v1.5.0 · 窗口与界面细节优化

本次仅优化 Qt 界面，不修改既有六分类 CNN、摄像头采集、数据导入和训练流程。

- 修复无边框窗口四角圆弧外出现白色方角的问题，调整透明窗口和圆角裁剪方式；取消覆盖透明区域的整窗 Acrylic。
- 侧边栏改为约 185ms 展开/收起动画，统一图标线条风格。
- 统一按钮的高度、内边距、圆角与悬停反馈。
- 修复「一键训练全部」按钮文字被截断的问题。
- 统一下拉框箭头、弹出菜单和选中状态的视觉样式。

### 数据保护

保留此前已提交的 389 张 HaGRID 公开训练图和来源信息；不提交本地场景照片、训练权重、个性化设置、采集日志或虚拟环境。

### 验证说明

更新包附带 v1.5.0 UI 回归测试。源码及自动化测试通过不等于已确认所有 Windows 11 / VMware 图形渲染行为；圆角、窗口拖动与侧栏动画仍以实机测试为准。
'''


def call(*argv: str, check: bool = True, cwd: Path = PROJECT) -> tuple[int, str]:
    try:
        p = subprocess.run([str(a) for a in argv], cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, timeout=180)
    except FileNotFoundError as e:
        raise RuntimeError(f'找不到命令：{argv[0]}。请确认 git 和 gh 均已安装并在 PATH 中。') from e
    output = p.stdout.decode('utf-8', errors='replace').strip()
    if check and p.returncode:
        raise RuntimeError(f'{argv[0]} 执行失败（{p.returncode}）：{output[-2300:]}')
    return p.returncode, output


def git(*args: str) -> str:
    return call('git', *args)[1]


def gh(*args: str) -> str:
    return call('gh', *args)[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git_names(*args: str) -> set[str]:
    p = subprocess.run(['git', *args], cwd=PROJECT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    if p.returncode:
        raise RuntimeError('读取 Git 文件名失败：'+p.stderr.decode('utf-8', errors='replace'))
    return {v.decode('utf-8') for v in p.stdout.split(b'\0') if v}


def remote_ref(name: str) -> str | None:
    lines = git('ls-remote', 'origin', name).splitlines()
    matches = [line.split()[0] for line in lines if len(line.split()) == 2 and line.split()[1] == name]
    if len(matches) > 1:
        raise RuntimeError('远程存在重复引用：'+name)
    return matches[0] if matches else None


def release_state() -> str:
    # HTTP/2.0 404 Not Found / HTTP/2 404 / HTTP/1.1 404 均应识别。
    rc, output = call('gh', 'api', '-i', f'repos/{REPO}/releases/tags/{TAG}', check=False)
    matches = re.findall(r'^HTTP/\d(?:\.\d+)?\s+(\d{3})(?:\s|$)', output, flags=re.I | re.M)
    status = matches[-1] if matches else None
    if rc == 0 and (status is None or status == '200'):
        return 'exists'
    if rc != 0 and status == '404':
        return 'missing'
    raise RuntimeError('无法明确确认 GitHub Release 状态；已停止，避免重复发布：'+output[:700])


def verify_zip() -> list[str]:
    if not UPDATE.is_file():
        raise RuntimeError('请先把 v1.5.0 更新 ZIP 放到 Downloads：'+str(UPDATE))
    if sha256(UPDATE) != ZIP_SHA256:
        raise RuntimeError('更新包 SHA256 不匹配，禁止发布')
    with zipfile.ZipFile(UPDATE) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('version') != '1.5.0' or manifest.get('base_commit') != BASE:
            raise RuntimeError('更新包版本或基础 Commit 不正确')
        files = manifest.get('files', {})
        if not isinstance(files, dict) or set(files) != EXPECTED_FILES:
            raise RuntimeError('更新包文件清单不匹配')
        if set(z.namelist()) != EXPECTED_FILES | {'manifest.json'}:
            raise RuntimeError('ZIP 含有不属于 v1.5.0 的文件')
        for name, digest in files.items():
            parts = Path(name).parts
            if not name or name.startswith('/') or '\\' in name or ':' in name or '..' in parts:
                raise RuntimeError('更新包路径非法：'+name)
            local = PROJECT / name
            if not local.is_file() or local.is_symlink():
                raise RuntimeError('未完整安装 v1.5.0；缺失或非普通文件：'+name)
            if sha256(local) != digest or hashlib.sha256(z.read(name)).hexdigest() != digest:
                raise RuntimeError('本机文件与 v1.5.0 安装包不一致：'+name)
    return sorted(EXPECTED_FILES)


def check_environment() -> tuple[str, bool]:
    if git('branch', '--show-current') != 'main':
        raise RuntimeError('当前不是 main 分支')
    allowed_urls = {f'https://github.com/{REPO}', f'https://github.com/{REPO}.git',
                    f'git@github.com:{REPO}.git'}
    if git('remote', 'get-url', 'origin') not in allowed_urls:
        raise RuntimeError('origin 指向了非预期的 GitHub 仓库')
    if gh('api', 'user', '--jq', '.login') != OWNER:
        raise RuntimeError('GitHub CLI 登录账户不是 nljie1103')
    if gh('api', f'repos/{REPO}', '--jq', '.private').lower() != 'true':
        raise RuntimeError('目标仓库不是 Private')
    head = git('rev-parse', 'HEAD')
    resumed = head != BASE
    if resumed:
        if git('log', '-1', '--format=%s') != MESSAGE or git('rev-parse', 'HEAD^') != BASE:
            raise RuntimeError('本地 HEAD 不是 v1.4.0，也不是本脚本已创建的 v1.5.0 Commit')
        delta = git_names('diff', '--name-only', '-z', BASE, head)
        if delta != EXPECTED_FILES | {PUBLISHER_REL}:
            raise RuntimeError('已创建的 v1.5.0 Commit 文件范围异常：'+str(delta))
    main_ref = remote_ref('refs/heads/main')
    if main_ref not in ({BASE, head} if resumed else {BASE}):
        raise RuntimeError('远程 main 已经发生变化，禁止覆盖：'+str(main_ref))
    local_tag = git('tag', '-l', TAG)
    remote_tag = remote_ref('refs/tags/'+TAG)
    if not resumed and (local_tag or remote_tag):
        raise RuntimeError('v1.5.0 Tag 已存在，但本地仍停留旧 Commit，需要人工核查')
    if resumed:
        if local_tag:
            if git('rev-parse', f'{TAG}^{{}}') != head:
                raise RuntimeError('本地 Tag 指向错误的 Commit')
            if remote_tag and remote_tag != git('rev-parse', 'refs/tags/'+TAG):
                raise RuntimeError('远程 Tag 与本地 Tag 不一致')
        elif remote_tag:
            raise RuntimeError('远程 Tag 已存在但本地没有，拒绝推断远程版本')
    return head, resumed


def check_dirty(files: list[str], resumed: bool) -> None:
    if git_names('diff', '--cached', '--name-only', '-z'):
        raise RuntimeError('暂存区有其他修改，请清空暂存区后重试')
    modified = git_names('diff', '--name-only', '-z', 'HEAD')
    allowed = set(files) | {'设置.json'}
    unexpected = modified - allowed
    if unexpected:
        raise RuntimeError('发现与发布无关的已跟踪修改：'+', '.join(sorted(unexpected)))
    if resumed and modified & set(files):
        raise RuntimeError('本地 v1.5.0 Commit 已建立，但发布文件又被修改')
    publisher = PROJECT / PUBLISHER_REL
    if publisher.exists() and publisher.read_bytes() != Path(__file__).read_bytes():
        raise RuntimeError('工程中已有不同的发布程序，避免覆盖，已停止')


def verify_tree(commit: str) -> None:
    names = git_names('ls-tree', '-r', '-z', '--name-only', commit)
    bad = [n for n in names if n.startswith(('模型/', '输出/', '素材/图片/', '.venv/'))
           or (n.startswith('数据/') and n != '数据/公开数据清单.json' and not n.startswith('数据/公开训练/'))]
    if bad:
        raise RuntimeError('Commit 中发现本不应提交的私人数据：'+', '.join(bad[:10]))


def run_tests() -> None:
    python = PROJECT / '.venv' / 'Scripts' / 'python.exe'
    if not python.is_file():
        raise RuntimeError('找不到工程虚拟环境 Python：'+str(python))
    print('[测试] 运行全部单元测试...', flush=True)
    proc = subprocess.run([str(python), '-m', 'unittest', 'discover', '-s', '测试', '-v'], cwd=PROJECT, timeout=180)
    if proc.returncode:
        raise RuntimeError('单元测试未通过，禁止发布')
    call(str(python), '-c', 'from 手势系统.现代界面 import GestureWindow, GlassComboBox, unified_icon; print("Qt import OK")')


def create_commit(files: list[str]) -> str:
    path = PROJECT / PUBLISHER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        shutil.copy2(Path(__file__), path)
    expected = set(files) | {PUBLISHER_REL}
    git('add', '--', *sorted(expected))  # 不使用 git add .
    staged = git_names('diff', '--cached', '--name-only', '-z')
    if staged != expected:
        git('reset', '--mixed', 'HEAD')
        raise RuntimeError('Git 暂存文件与白名单不一致：'+str(staged))
    git('commit', '-m', MESSAGE)
    sha = git('rev-parse', 'HEAD')
    if git('rev-parse', 'HEAD^') != BASE:
        raise RuntimeError('提交父节点与 v1.4.0 不一致，已停止推送')
    return sha


def push_refs(sha: str) -> None:
    current = remote_ref('refs/heads/main')
    if current == BASE:
        print('[推送] main...', flush=True)
        git('push', 'origin', 'main')
    elif current != sha:
        raise RuntimeError('远程 main 与预期不一致，拒绝强制推送')
    if remote_ref('refs/heads/main') != sha:
        raise RuntimeError('远程 main 校验失败')
    if not git('tag', '-l', TAG):
        git('tag', '-a', TAG, '-m', 'v1.5.0 窗口圆角与导航控件样式优化')
    if git('rev-parse', f'{TAG}^{{}}') != sha:
        raise RuntimeError('本地 v1.5.0 Tag 指向错误')
    local_object = git('rev-parse', 'refs/tags/'+TAG)
    remote_object = remote_ref('refs/tags/'+TAG)
    if not remote_object:
        print('[推送] v1.5.0 Tag...', flush=True)
        git('push', 'origin', f'refs/tags/{TAG}')
    elif remote_object != local_object:
        raise RuntimeError('远程 v1.5.0 Tag 对象不匹配')
    if remote_ref('refs/tags/'+TAG) != local_object:
        raise RuntimeError('远程 Tag 校验失败')


def publish_release() -> tuple[str, str]:
    out = PROJECT / '.发布'
    out.mkdir(parents=True, exist_ok=True)
    archive = out / 'gesture-intelligent-system-v1.5.0-source.zip'
    git('archive', '--format=zip', f'--output={archive}', TAG)
    expected_digest = sha256(archive)
    note_file = out / 'v1.5.0-release-notes.md'
    note_file.write_text(RELEASE_NOTES, encoding='utf-8')
    if release_state() == 'missing':
        print('[Release] 创建并上传 v1.5.0 源码附件...', flush=True)
        gh('release', 'create', TAG, str(archive), '--repo', REPO, '--verify-tag',
           '--title', TITLE, '--notes-file', str(note_file), '--latest')
    info = json.loads(gh('release', 'view', TAG, '--repo', REPO,
                         '--json', 'name,tagName,isDraft,assets,url'))
    if info.get('tagName') != TAG or info.get('name') != TITLE or info.get('isDraft'):
        raise RuntimeError('Release 的版本号、标题或草稿状态不正确')
    assets = {a.get('name'):a for a in info.get('assets', [])}
    if archive.name not in assets:
        print('[Release] 上传遗漏的源码附件...', flush=True)
        gh('release', 'upload', TAG, str(archive), '--repo', REPO)
        info = json.loads(gh('release', 'view', TAG, '--repo', REPO, '--json', 'assets,url'))
        assets = {a.get('name'):a for a in info.get('assets', [])}
    if archive.name not in assets or int(assets[archive.name].get('size', -1)) != archive.stat().st_size:
        raise RuntimeError('Release 源码附件大小与本地版本不匹配')
    # 重新下载并校验附件，避免只验证名称/大小却忽略内容差异。
    with tempfile.TemporaryDirectory(prefix='gesture-v150-release-') as temp:
        gh('release', 'download', TAG, '--repo', REPO, '--pattern', archive.name, '--dir', temp)
        downloaded = Path(temp) / archive.name
        if not downloaded.is_file() or sha256(downloaded) != expected_digest:
            raise RuntimeError('Release 附件 SHA256 核验失败')
    return info['url'], expected_digest


def main() -> None:
    if not PROJECT.is_dir():
        raise RuntimeError('找不到 Win11-Dev 项目目录：'+str(PROJECT))
    print('[检查] Gesture Studio v1.5.0 · GitHub Private 正式发布', flush=True)
    files = verify_zip()
    head, resumed = check_environment()
    check_dirty(files, resumed)
    if not resumed and release_state() != 'missing':
        raise RuntimeError('Release 已存在，但本地没有对应 Commit，需要人工核查')
    run_tests()
    print(f'[范围] 仅 {len(files)} 个升级文件与 1 个发布脚本；不提交本地设置、私人照片、模型权重。', flush=True)
    print('[Commit]', MESSAGE, flush=True)
    if input('确认发布 Private v1.5.0？输入 YES：').strip() != 'YES':
        print('已取消；没有修改 GitHub。')
        return
    if not resumed:
        head = create_commit(files)
        print('[创建] Commit:', head, flush=True)
    else:
        print('[恢复] 沿用现有 v1.5.0 Commit：', head, flush=True)
    verify_tree(head)
    push_refs(head)
    url, digest = publish_release()
    print('\n'+'='*64)
    print('完成：GitHub v1.5.0 Commit、Tag、Release 及源码附件已核对。')
    print('Commit:', head, MESSAGE)
    print('Release:', url)
    print('源码 ZIP SHA256:', digest)
    print('没有提交私人照片、训练模型、本地设置或训练日志。')
    print('='*64)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as e:
        print('[发布中止]', type(e).__name__ + ':', e, file=sys.stderr, flush=True)
        raise SystemExit(1)
