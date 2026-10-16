# -*- coding: utf-8 -*-
"""Private v1.3.0 publisher. Explicit staging, safe 404 handling, canonical settings."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
REPO='nljie1103/gesture-intelligent-system'
BASE='b438ba8a24abd0712928781fe9c50c727a13f523'
TAG='v1.3.0'
MESSAGE='v1.3.0重构液态玻璃四页工作台并统一识别控制'
STAGED=[
 '手势系统/图形界面.py','手势系统/玻璃界面.py','手势系统/玻璃主题.py','手势系统/界面数据.py',
 '手势系统/__init__.py','测试/test_四页玻璃界面.py','版本.txt',
 '文档/界面重构说明-1.3.0.txt','文档/发布说明-1.3.0.txt','文档/版本记录.txt',
 '工具/发布四页界面版本1.3.0.py',
]

def run(*args,ok=True,input=None):
    p=subprocess.run(list(map(str,args)),cwd=PROJECT,capture_output=True,input=input,
       env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
    out=(p.stdout+b'\n'+p.stderr).decode('utf-8','replace').strip()
    if ok and p.returncode:raise RuntimeError(f'{args[0]} 返回代码 {p.returncode}: {out[:1000]}')
    return p.returncode,out

def git(*args):return run('git',*args)[1]
def gh(*args):return run('gh',*args)[1]

def release_not_found():
    # GitHub CLI may print HTTP/2.0, HTTP/2, or HTTP/1.1. Parse response,
    # not a fragile literal substring. We do not treat auth errors as 404.
    rc,data=run('gh','api','-i',f'repos/{REPO}/releases/tags/{TAG}',ok=False)
    if rc==0:raise RuntimeError('Release 已存在，禁止重发')
    if not re.search(r'^HTTP/\d(?:\.\d+)?\s+404(?:\s|$)',data,re.M|re.I):
        raise RuntimeError('无法核实 Release 尚不存在，停止：'+data[:500])
    return True

def stage_canonical_settings():
    # Local settings are customized by the user; avoid committing them.
    base=run('git','show','HEAD:设置.json')[1]
    cfg=json.loads(base.lstrip('\ufeff'))
    cfg['版本']='1.3.0'
    blob=json.dumps(cfg,ensure_ascii=False,indent=2).encode('utf-8')+b'\n'
    _,sha=run('git','hash-object','-w','--stdin',input=blob)
    git('update-index','--add','--cacheinfo','100644',sha.strip(),'设置.json')
    return sha.strip()

def main():
    if git('rev-parse','HEAD')!=BASE:raise RuntimeError('本地 HEAD 不是 v1.2.0 正式提交，禁止继续')
    if git('branch','--show-current')!='main':raise RuntimeError('必须在 main 发布')
    origin=git('remote','get-url','origin')
    if origin not in [f'https://github.com/{REPO}.git',f'https://github.com/{REPO}',f'git@github.com:{REPO}.git']:
        raise RuntimeError('origin 不是指定私人仓库')
    if gh('api','user','--jq','.login').strip()!='nljie1103':raise RuntimeError('GitHub 登录账号不是 nljie1103')
    if gh('api',f'repos/{REPO}','--jq','.private').strip()!='true':raise RuntimeError('仓库权限不是 Private')
    remote=git('ls-remote','origin','refs/heads/main').split()[0]
    if remote!=BASE:raise RuntimeError('远程 main 已变化；拒绝覆盖')
    if git('tag','-l',TAG) or git('ls-remote','origin',f'refs/tags/{TAG}'):
        raise RuntimeError('v1.3.0 Tag 已存在')
    release_not_found()
    if (PROJECT/'版本.txt').read_text('utf-8-sig').strip()!='1.3.0':
        raise RuntimeError('本地尚未成功升级 v1.3.0')
    if not all((PROJECT/name).is_file() for name in STAGED):
        raise RuntimeError('缺少 v1.3.0 安装文件')
    dirty=subprocess.run(['git','diff','--name-only','-z','HEAD'],cwd=PROJECT,capture_output=True,check=True).stdout
    changed={x.decode('utf-8') for x in dirty.split(b'\0') if x}
    unexpected=changed-set(STAGED)-{'设置.json'}
    if unexpected:raise RuntimeError('有非本版本的源码修改，停止：'+', '.join(sorted(unexpected)))
    staged=subprocess.run(['git','diff','--cached','--name-only','-z'],cwd=PROJECT,capture_output=True,check=True).stdout
    if staged:raise RuntimeError('Git 暂存区不为空，停止')
    print('[验证] v1.3.0 · 四页玻璃界面，GitHub Private 账户正确。',flush=True)
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','测试','-p','test_*.py','-v'],cwd=PROJECT)
    if test.returncode:raise RuntimeError('自动化测试失败，停止')
    print('[提交] 只提交指定源码、文档和测试，配置使用公共默认值，不提交私人采集照片或权重。')
    print('Commit：'+MESSAGE)
    if input('确认正式发布？输入 YES：').strip().upper()!='YES':
        print('取消发布，没有创建 Commit/Tag/Release。');return
    git('add','--',*STAGED)
    stage_canonical_settings()
    after=subprocess.run(['git','diff','--cached','--name-only','-z'],cwd=PROJECT,capture_output=True,check=True).stdout
    selected={x.decode('utf-8') for x in after.split(b'\0') if x}
    if selected != (set(STAGED)|{'设置.json'}):
        git('reset','--mixed','HEAD')
        raise RuntimeError('暂存文件异常，已取消暂存：'+str(selected))
    git('commit','-m',MESSAGE)
    head=git('rev-parse','HEAD')
    git('tag','-a',TAG,'-m',TAG)
    git('push','origin','main')
    git('push','origin',TAG)
    folder=PROJECT/'.发布';folder.mkdir(exist_ok=True)
    archive=folder/'gesture-intelligent-system-v1.3.0-source.zip'
    git('archive','--format=zip',f'--output={archive}',TAG)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    gh('release','create',TAG,str(archive),'--repo',REPO,'--verify-tag',
       '--title','v1.3.0 · 液态玻璃四页工作台',
       '--notes-file',str(PROJECT/'文档/发布说明-1.3.0.txt'))
    if git('ls-remote','origin','refs/heads/main').split()[0]!=head:
        raise RuntimeError('远程 Commit 校验不通过')
    if archive.name not in gh('release','view',TAG,'--repo',REPO,'--json','assets','--jq','.assets[].name'):
        raise RuntimeError('Release 源码附件尚未核验成功')
    print('[完成] 私人 GitHub v1.3.0 已发布')
    print('Commit：',head,MESSAGE)
    print('Release：',f'https://github.com/{REPO}/releases/tag/{TAG}')
    print('Source SHA256：',digest)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('[发布中止]',exc,file=sys.stderr)
        raise SystemExit(1)
