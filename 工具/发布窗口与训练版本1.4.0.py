# -*- coding: utf-8 -*-
"""安全发布 Gesture Studio v1.4.0 至 nljie1103 私人 GitHub。

使用：将本文件和 gesture-studio-v1.4.0-update.zip 放在用户 Downloads，
      使用项目 .venv Python 执行本文件。支持分支/标签/Release 中途失败后重试。
只按 ZIP 清单提交源码，禁止添加私人采集照片、模型、输出文件和自定义设置。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = 'nljie1103/gesture-intelligent-system'
OWNER = 'nljie1103'
BASE = '33d3a3d17c5c460593d3671ea8661926b006636f'
TAG = 'v1.4.0'
MESSAGE = 'v1.4.0重构原生窗口并完善数据采集与训练工作台'
TITLE = 'v1.4.0 · Qt窗口与数据训练工作台'
ZIP_SHA = '3c2683abe39a95ac57f6899476d36ddc1dbdda98fdc5cf65dca3538126be3d16'
PROJECT = Path.home() / 'Desktop' / 'niit' / '计算机视觉' / '基于手势识别的智能系统'
UPDATE = Path.home() / 'Downloads' / 'gesture-studio-v1.4.0-update.zip'
PUBLISHER_REL = '工具/发布窗口与训练版本1.4.0.py'

RELEASE_NOTES = '''## Gesture Studio v1.4.0

**Qt 窗口与数据训练工作台**

- 使用 PySide6 / Qt 重构桌面应用，采用 macOS 风格无边框窗口、红黄绿窗口控制键及 Windows 玻璃视觉效果。Windows 并不提供 Apple 原生 Liquid Glass 合成器。
- 统一五页导航：首页、数据、训练、模型和设置，默认收起侧边栏；首页使用一个开始／暂停切换按钮。
- 数据页支持手动或文件夹导入图片、按类别和场景统计、SHA256 去重、定期重新扫描；私人场景清理移动至本地回收站。
- 训练页支持摄像头采集参数、开始／停止快捷键、连续场景、全部六类训练及针对已有类别的专项强化。
- 训练结果保存到本地，旧正式模型先备份；不把同一场景的训练准确率冒充独立测试结果。

### 数据和隐私

本仓库继续保留此前获准归档的 389 张 HaGRID 公开裁剪图及来源清单；**不上传**私人摄像头采集照片、模型权重、运行日志、本地自定义设置或虚拟环境。

### 验证边界

已运行项目单元测试。Qt 在 Windows 11 / VMware 的实际玻璃视觉效果、摄像头采集和快捷键交互仍以最终用户设备测试为准；本次发布不宣称已完成 Windows 实机验收，也不提供未经独立评估的识别准确率。
'''


def run(*args: str, ok: bool = True, data: bytes | None = None, cwd: Path = PROJECT):
    proc = subprocess.run(list(map(str, args)), cwd=cwd, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    out = proc.stdout.decode('utf-8', errors='replace').strip()
    if ok and proc.returncode:
        raise RuntimeError(f'{args[0]} 返回代码 {proc.returncode}: {out[-1800:]}')
    return proc.returncode, out


def git(*args: str) -> str:
    return run('git', *args)[1]


def gh(*args: str) -> str:
    return run('gh', *args)[1]


def remote_ref(ref: str) -> str | None:
    value = git('ls-remote', 'origin', ref)
    entries = [line.split() for line in value.splitlines() if line.strip()]
    exact = [x[0] for x in entries if len(x) >= 2 and x[1] == ref]
    if len(exact) > 1:
        raise RuntimeError('远程出现重复引用：' + ref)
    return exact[0] if exact else None


def release_state() -> str:
    # gh api -i outputs HTTP/2.0 404, HTTP/2 404, or HTTP/1.1 404.
    rc, response = run('gh', 'api', '-i', f'repos/{REPO}/releases/tags/{TAG}', ok=False)
    status = re.search(r'^HTTP/\d(?:\.\d+)?\s+(\d{3})(?:\s|$)', response, re.M | re.I)
    if rc == 0 and (status is None or status.group(1) == '200'):
        return 'exists'
    if rc != 0 and status and status.group(1) == '404':
        return 'missing'
    raise RuntimeError('不能可靠核实 Release 状态：' + response[:900])


def verify_package() -> list[str]:
    if not UPDATE.is_file():
        raise RuntimeError('缺少更新 ZIP，请放在 Downloads：' + str(UPDATE))
    if hashlib.sha256(UPDATE.read_bytes()).hexdigest() != ZIP_SHA:
        raise RuntimeError('v1.4.0 更新包 SHA256 不匹配，禁止发布')
    with zipfile.ZipFile(UPDATE) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        if manifest.get('version') != '1.4.0' or manifest.get('base') != BASE:
            raise RuntimeError('ZIP manifest 版本或基准不匹配')
        files = list(manifest['files'])
        for rel, expected in manifest['files'].items():
            path = Path(rel)
            if path.is_absolute() or '..' in path.parts or '\\' in rel or ':' in rel:
                raise RuntimeError('不安全的包路径：' + rel)
            full = PROJECT / rel
            if not full.is_file() or full.is_symlink():
                raise RuntimeError('本机 v1.4.0 未完整安装或出现符号链接：' + rel)
            contents = full.read_bytes()
            digest = hashlib.sha256(contents).hexdigest()
            if digest != expected or hashlib.sha256(bundle.read(rel)).hexdigest() != expected:
                raise RuntimeError('本地文件不等于正式 v1.4.0 更新包，拒绝发布：' + rel)
        return files


def check_git_base() -> tuple[str, bool]:
    if git('branch', '--show-current').strip() != 'main':
        raise RuntimeError('仅允许在 main 分支发布')
    origin = git('remote', 'get-url', 'origin').strip()
    urls = {f'https://github.com/{REPO}.git', f'https://github.com/{REPO}', f'git@github.com:{REPO}.git'}
    if origin not in urls:
        raise RuntimeError('origin 不是指定仓库：' + origin)
    if gh('api', 'user', '--jq', '.login').strip() != OWNER:
        raise RuntimeError('gh 未登录指定的 GitHub 账户 nljie1103')
    if gh('api', f'repos/{REPO}', '--jq', '.private').strip().lower() != 'true':
        raise RuntimeError('仓库不是 Private，拒绝发布')
    head = git('rev-parse', 'HEAD').strip()
    if head == BASE:
        resumed = False
    else:
        msg = git('log', '-1', '--pretty=%s').strip()
        parents = git('rev-list', '--parents', '-n', '1', 'HEAD').split()
        if msg != MESSAGE or len(parents) != 2 or parents[1] != BASE:
            raise RuntimeError('本地 HEAD 既不是 v1.3.0，也不是本程序创建的 v1.4.0 Commit')
        resumed = True
    remote = remote_ref('refs/heads/main')
    if remote not in {BASE, head}:
        raise RuntimeError('远程 main 已被其他提交更新，不允许覆盖：' + str(remote))
    remote_tag = remote_ref(f'refs/tags/{TAG}')
    local_tag = git('tag', '-l', TAG).strip()
    if not resumed and (remote_tag or local_tag):
        raise RuntimeError('Tag 已存在但本地仍在 v1.3.0，需先核对，禁止重复发布')
    if resumed and remote_tag and not local_tag:
        raise RuntimeError('远程 v1.4.0 Tag 已存在，但本地无标签；请先核查历史')
    if resumed and local_tag:
        if git('rev-parse', f'{TAG}^{{}}').strip() != head:
            raise RuntimeError('本地 v1.4.0 Tag 未指向预期 Commit')
        if remote_tag and remote_tag != git('rev-parse', f'refs/tags/{TAG}').strip():
            raise RuntimeError('远程 Tag 与本地 Tag 不同，拒绝覆盖')
    return head, resumed


def validate_worktree(allowed: list[str], resumed: bool):
    rc, staged = run('git', 'diff', '--cached', '--name-only', '-z')
    if staged:
        raise RuntimeError('Git 暂存区已有内容，发布前请先处理，避免误提交')
    changed_raw = subprocess.run(['git', 'diff', '--name-only', 'HEAD', '-z'],
                                 cwd=PROJECT, capture_output=True, check=True).stdout
    changed = {name.decode('utf-8') for name in changed_raw.split(b'\0') if name}
    unexpected = changed - set(allowed) - {'设置.json'}
    if unexpected:
        raise RuntimeError('检测到与本次发布无关的已跟踪源码修改：' + ', '.join(sorted(unexpected)))
    if resumed and changed & set(allowed):
        raise RuntimeError('已创建 v1.4.0 Commit，但部分发布文件又被改动，拒绝继续')
    path = PROJECT / PUBLISHER_REL
    if path.exists() and path.read_bytes() != Path(__file__).read_bytes():
        raise RuntimeError('工程内已有不同版本的 v1.4.0 发布脚本，拒绝覆盖')


def validate_tree(head: str):
    # Read NUL-delimited raw paths: Git may C-quote Chinese paths in text mode.
    output = subprocess.run(['git', 'ls-tree', '-r', '-z', '--name-only', head],
                            cwd=PROJECT, capture_output=True, check=True).stdout
    names = {item.decode('utf-8') for item in output.split(b'\0') if item}
    for rel in names:
        if rel.startswith(('模型/', '输出/', '.venv/', '素材/图片/')):
            raise RuntimeError('Git 提交包含不应公开归档的本地文件：' + rel)
        if rel.startswith('数据/') and not (rel.startswith('数据/公开训练/') or rel == '数据/公开数据清单.json'):
            raise RuntimeError('Git 提交含私人采集或非公开训练数据：' + rel)


def do_tests():
    python = PROJECT / '.venv' / 'Scripts' / 'python.exe'
    if not python.is_file():
        raise RuntimeError('缺少工程虚拟环境 .venv\\Scripts\\python.exe')
    print('[测试] 正在执行项目自动化测试…', flush=True)
    proc = subprocess.run([str(python), '-m', 'unittest', 'discover', '-s', '测试', '-p', 'test_*.py', '-v'],
                          cwd=PROJECT)
    if proc.returncode:
        raise RuntimeError('项目测试失败，停止发布')
    # Python 3.14 needs PySide6 installed to run the GUI; import check catches installation gaps.
    run(str(python), '-c', 'from PySide6.QtWidgets import QApplication; import 手势系统.现代界面; print("Qt 模块导入成功")')


def prepare_commit(files: list[str]) -> str:
    # This happens ONLY after user confirms. Stage an exact allowlist.
    dest = PROJECT / PUBLISHER_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(Path(__file__), dest)
    expected = set(files) | {PUBLISHER_REL}
    git('add', '--', *sorted(expected))
    raw = subprocess.run(['git', 'diff', '--cached', '--name-only', '-z'], cwd=PROJECT,
                         capture_output=True, check=True).stdout
    actual = {name.decode('utf-8') for name in raw.split(b'\0') if name}
    if actual != expected:
        git('reset', '--mixed', 'HEAD')
        raise RuntimeError('Git 暂存清单异常，已取消暂存；实际：' + ', '.join(sorted(actual)))
    git('commit', '-m', MESSAGE)
    sha = git('rev-parse', 'HEAD').strip()
    if git('rev-parse', 'HEAD^').strip() != BASE:
        raise RuntimeError('父提交不是 v1.3.0，已停止后续推送')
    return sha


def ensure_remote_commit(sha: str):
    current = remote_ref('refs/heads/main')
    if current == BASE:
        print('[推送] main 分支…', flush=True)
        git('push', 'origin', 'main')
    elif current != sha:
        raise RuntimeError('main 发生变化，禁止强制推送')
    if remote_ref('refs/heads/main') != sha:
        raise RuntimeError('远程 main Commit 核验失败')
    local_tag = git('tag', '-l', TAG).strip()
    if not local_tag:
        git('tag', '-a', TAG, '-m', f'{TAG} Qt窗口与数据训练工作台')
    if git('rev-parse', f'{TAG}^{{}}') != sha:
        raise RuntimeError('Tag 指向错误 Commit')
    remote_tag = remote_ref(f'refs/tags/{TAG}')
    local_tag_object = git('rev-parse', f'refs/tags/{TAG}')
    if not remote_tag:
        print('[推送] v1.4.0 Tag…', flush=True)
        git('push', 'origin', f'refs/tags/{TAG}')
    elif remote_tag != local_tag_object:
        raise RuntimeError('远程 Tag 与本地 Tag 不一致，拒绝覆盖')
    if remote_ref(f'refs/tags/{TAG}') != local_tag_object:
        raise RuntimeError('远程 Tag 校验失败')


def release(sha: str) -> tuple[Path, str]:
    out = PROJECT / '.发布'
    out.mkdir(parents=True, exist_ok=True)
    archive = out / 'gesture-intelligent-system-v1.4.0-source.zip'
    git('archive', '--format=zip', f'--output={archive}', TAG)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    notes = out / 'v1.4.0-release-notes.md'
    notes.write_text(RELEASE_NOTES, encoding='utf-8')
    state = release_state()
    if state == 'missing':
        print('[Release] 创建 v1.4.0 并附加完整源码 ZIP…', flush=True)
        gh('release', 'create', TAG, str(archive), '--repo', REPO, '--verify-tag',
           '--title', TITLE, '--notes-file', str(notes), '--latest')
    result = json.loads(gh('release', 'view', TAG, '--repo', REPO,
                           '--json', 'name,tagName,isDraft,assets,url'))
    if result.get('tagName') != TAG or result.get('name') != TITLE or result.get('isDraft'):
        raise RuntimeError('Release 标题/Tag/状态与预期不符')
    assets = {a.get('name'): a for a in result.get('assets', [])}
    if archive.name not in assets:
        print('[Release] 恢复上传遗漏的源码 ZIP…', flush=True)
        gh('release', 'upload', TAG, str(archive), '--repo', REPO)
        result = json.loads(gh('release', 'view', TAG, '--repo', REPO, '--json', 'assets,url'))
        assets = {a.get('name'): a for a in result.get('assets', [])}
    if archive.name not in assets:
        raise RuntimeError('Release 附件上传后仍未检出，请检查网络状态')
    size = assets[archive.name].get('size')
    if size is not None and int(size) != archive.stat().st_size:
        raise RuntimeError('Release 源码附件大小不匹配，拒绝声称发布完成')
    return archive, digest


def main():
    if not PROJECT.is_dir():
        raise RuntimeError('找不到项目文件夹：' + str(PROJECT))
    print('[检查] 私人 GitHub v1.4.0 发布前验证', flush=True)
    files = verify_package()
    head, resumed = check_git_base()
    validate_worktree(files, resumed)
    if not resumed and release_state() != 'missing':
        raise RuntimeError('远程已有 v1.4.0 Release 但当前尚未创建新版 Commit，需人工核对')
    do_tests()
    print(f'[范围] {len(files)} 个升级文件 + 1 个发布脚本；私人数据和模型绝不暂存。', flush=True)
    print('[Commit]', MESSAGE, flush=True)
    print('[说明] 这次 Qt Windows 实机视觉和摄像头仍需用户验收，不宣称已验证。', flush=True)
    if input('确认正式推送 GitHub Private v1.4.0？输入 YES：').strip() != 'YES':
        print('已取消，未修改远程仓库。')
        return
    if not resumed:
        head = prepare_commit(files)
        print('[创建] Commit', head, flush=True)
    else:
        print('[继续] 检测到此前已经创建的 v1.4.0 Commit：', head, flush=True)
    validate_tree(head)
    ensure_remote_commit(head)
    archive, digest = release(head)
    print('\n' + '=' * 64)
    print('完成：GitHub Private v1.4.0 的 Commit、Tag、Release 和源码附件已核验。')
    print('Commit：', head, MESSAGE)
    print('Release：', f'https://github.com/{REPO}/releases/tag/{TAG}')
    print('Source SHA256：', digest)
    print('未提交私人照片、模型权重、本地设置及训练输出。')
    print('=' * 64)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print('[发布中止]', type(exc).__name__ + ':', exc, file=sys.stderr, flush=True)
        raise SystemExit(1)
