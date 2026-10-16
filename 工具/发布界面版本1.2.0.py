# -*- coding: utf-8 -*-
"""v1.2.0 正式发布。先完成安装和真实摄像头验收，再运行。只暂存指定源码和手势插画。"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = 'nljie1103/gesture-intelligent-system'
BASE = 'b6d162ffc3511872a744090210a2872e08335e35'
VERSION = 'v1.2.0'
MESSAGE = 'v1.2.0优化手势反馈界面与候选手部框显示'
STAGED = [
    '手势系统/图形界面.py','手势系统/动作资源.py','手势系统/手部候选框.py',
    '手势系统/__init__.py','测试/test_动作与定位.py','版本.txt','设置.json',
    '文档/界面优化说明-1.2.0.txt','文档/发布说明-1.2.0.txt','文档/版本记录.txt',
    '工具/发布界面版本1.2.0.py',
] + [f'素材/手势图标/{n}.png' for n in ['palm','fist','like','peace','one','none','ok','stop','rock','heart']]

def cmd(*args, ok=True):
    p=subprocess.run(list(map(str,args)),cwd=PROJECT,capture_output=True,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
    out=(p.stdout+b'\n'+p.stderr).decode('utf-8','replace').strip()
    if ok and p.returncode: raise RuntimeError(f'{args[0]} 退出码 {p.returncode}: {out}')
    return p.returncode,out

def git(*args): return cmd('git',*args)[1]
def gh(*args): return cmd('gh',*args)[1]

def main():
    if git('rev-parse','HEAD')!=BASE: raise RuntimeError('当前 HEAD 不是已核实的 v1.1.0，禁止创建新历史')
    if git('branch','--show-current')!='main': raise RuntimeError('请切换至 main')
    url=git('remote','get-url','origin')
    if url not in [f'https://github.com/{REPO}.git',f'https://github.com/{REPO}',f'git@github.com:{REPO}.git']:
        raise RuntimeError('当前 origin 不是指定私人仓库')
    if gh('api','user','--jq','.login')!='nljie1103': raise RuntimeError('gh 登录账号不正确')
    if gh('api',f'repos/{REPO}','--jq','.private')!='true': raise RuntimeError('仓库并非 Private')
    remote=git('ls-remote','origin','refs/heads/main').split()[0]
    if remote!=BASE: raise RuntimeError('远程 main 已有其他提交，停止以防覆盖')
    for name in STAGED:
        if not (PROJECT/name).is_file(): raise RuntimeError('缺少发布文件：'+name)
    if (PROJECT/'版本.txt').read_text(encoding='utf-8-sig').strip()!='1.2.0':
        raise RuntimeError('当前版本不是 1.2.0')
    if git('tag','--list',VERSION) or git('ls-remote','origin',f'refs/tags/{VERSION}'):
        raise RuntimeError('v1.2.0 标签已存在；禁止重复创建或覆盖')
    check,out=cmd('gh','release','view',VERSION,'--repo',REPO,ok=False)
    if check==0: raise RuntimeError('Release 已存在，停止以防覆盖')
    # 其他网络错误可能与不存在无关，先再通过 REST 检查状态码。
    code, resp=cmd('gh','api','-i',f'repos/{REPO}/releases/tags/{VERSION}',ok=False)
    if code==0 or 'HTTP/2.0 404' not in resp and 'HTTP/1.1 404' not in resp:
        raise RuntimeError('不能明确证明 Release 不存在；请检查网络或权限。'+resp[:250])
    print('开始测试：16 项自动化测试。',flush=True)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','测试','-p','test_*.py','-v'],cwd=PROJECT)
    if result.returncode: raise RuntimeError('自动化测试未通过，停止发布')
    # 使用 NUL 分隔检查 Git 受追踪变更。避免 Git core.quotePath 的八进制路径转义。
    dirty=subprocess.run(['git','diff','--name-only','-z','HEAD'],cwd=PROJECT,capture_output=True,check=True).stdout
    changed={part.decode('utf-8') for part in dirty.split(b'\0') if part}
    extra=changed-set(STAGED)
    if extra: raise RuntimeError('发现与当前版本无关的已追踪改动：'+', '.join(sorted(extra)))
    staged=subprocess.run(['git','diff','--cached','--name-only','-z'],cwd=PROJECT,capture_output=True,check=True).stdout
    if staged: raise RuntimeError('Git 暂存区不是空的；请先处理现有暂存内容')
    print(f'准备提交 {len(STAGED)} 个指定文件；不包括 数据/场景01、模型/、输出/ 或原始 ZIP。')
    print('Commit：',MESSAGE)
    if input('确认正式发布？输入 YES：').strip().upper()!='YES': raise RuntimeError('已取消')
    git('add','--',*STAGED)
    now=subprocess.run(['git','diff','--cached','--name-only','-z'],cwd=PROJECT,capture_output=True,check=True).stdout
    names={part.decode('utf-8') for part in now.split(b'\0') if part}
    if not names or not names <= set(STAGED):
        git('reset','--mixed','HEAD')
        raise RuntimeError('暂存区包含非预期文件，已取消暂存')
    git('commit','-m',MESSAGE)
    head=git('rev-parse','HEAD')
    git('tag','-a',VERSION,'-m',VERSION)
    print('[发布] 推送 main 和 Tag...')
    git('push','origin','main')
    git('push','origin',VERSION)
    target=PROJECT/'.发布'
    target.mkdir(exist_ok=True)
    zipfile=target/'gesture-intelligent-system-v1.2.0-source.zip'
    git('archive','--format=zip',f'--output={zipfile}',VERSION)
    digest=hashlib.sha256(zipfile.read_bytes()).hexdigest()
    print('[发布] SHA256：',digest)
    gh('release','create',VERSION,str(zipfile),'--repo',REPO,'--verify-tag',
       '--title','v1.2.0 · 手势反馈与界面优化','--notes-file',str(PROJECT/'文档/发布说明-1.2.0.txt'))
    if git('ls-remote','origin','refs/heads/main').split()[0]!=head:
        raise RuntimeError('远程 main 校验不通过')
    if zipfile.name not in gh('release','view',VERSION,'--repo',REPO,'--json','assets','--jq','.assets[].name'):
        raise RuntimeError('Release 附件未查到')
    print('[完成] GitHub Private v1.2.0 已发布。')
    print('Commit：',head, MESSAGE)
    print('Release：',f'https://github.com/{REPO}/releases/tag/{VERSION}')
    print('SHA256：',digest)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('[发布中止]',exc,file=sys.stderr)
        raise SystemExit(1)
