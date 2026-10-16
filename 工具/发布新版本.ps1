#Requires -Version 5.1
# 每个后续正式版本一次提交+独立 tag+独立 Release；不更改旧 tag。
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$NotesFile
)
$ErrorActionPreference = 'Stop'
$项目 = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $项目
$仓库 = 'nljie1103/gesture-intelligent-system'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw '版本格式示例：1.0.1 或 1.1.0' }
$标签 = "v$Version"
if (-not (Get-Command git -ErrorAction SilentlyContinue) -or -not (Get-Command gh -ErrorAction SilentlyContinue)) { throw '未检测到 git 或 gh' }
if (-not (Test-Path -LiteralPath $NotesFile)) { throw "请先编写中文发布说明：$NotesFile" }
if ((& git branch --show-current).Trim() -ne 'main') { throw '必须在 main 分支发布' }
if ((& git tag --list $标签)) { throw "$标签 已存在，不能覆盖历史发布" }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw '请先登录 gh auth login' }
$账号 = (& gh api user --jq '.login').Trim()
if ($账号 -ne 'nljie1103') { throw "当前账号不符合预期：$账号" }
$隐私 = (& gh repo view $仓库 --json isPrivate --jq '.isPrivate').Trim()
if ($LASTEXITCODE -ne 0 -or $隐私 -ne 'true') { throw '找不到指定 Private 仓库，或仓库非私人' }
$远程地址 = (& git remote get-url origin).Trim()
if ($远程地址 -notmatch 'nljie1103/gesture-intelligent-system(\.git)?$') { throw 'origin 仓库不匹配' }
# 修改集中版本元信息，再提交一份具备可追溯性的版本。
Set-Content -LiteralPath '版本.txt' -Value $Version -Encoding UTF8
$设置 = Get-Content -LiteralPath '设置.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$设置.版本 = $Version
$设置 | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath '设置.json' -Encoding UTF8
$入口 = '手势系统/__init__.py'
$原文 = Get-Content -LiteralPath $入口 -Raw -Encoding UTF8
$原文 = [regex]::Replace($原文, '__version__\s*=\s*"[^"]+"', ('__version__ = "' + $Version + '"'))
Set-Content -LiteralPath $入口 -Value $原文 -Encoding UTF8
& git add --all
if ($LASTEXITCODE -ne 0) { throw 'git add 失败' }
$变更 = & git diff --cached --name-only
$变更 | ForEach-Object { Write-Host $_ }
if ($变更 | Where-Object { $_ -match '(^|/)(数据|模型|输出|\.venv)/' }) { throw '检测到本地数据将被提交，已中止' }
$确认 = Read-Host "检查以上变更。输入 YES 发布 $标签"
if ($确认 -cne 'YES') { throw '用户取消发布' }
& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { throw '没有可提交的变更' }
& git commit -m "发布：$标签 正式版本"
if ($LASTEXITCODE -ne 0) { throw 'Commit 创建失败' }
& git tag -a $标签 -m "$标签 正式发布"
if ($LASTEXITCODE -ne 0) { throw 'Tag 创建失败' }
& git push origin main
if ($LASTEXITCODE -ne 0) { throw 'main 推送失败' }
& git push origin $标签
if ($LASTEXITCODE -ne 0) { throw 'Tag 推送失败' }
$目录 = Join-Path $项目 '.发布'
New-Item -ItemType Directory -Path $目录 -Force | Out-Null
$包 = Join-Path $目录 "基于手势识别的智能系统-$标签-源码.zip"
& git archive --format=zip "--output=$包" $标签
if ($LASTEXITCODE -ne 0) { throw '源码包生成失败' }
& gh release create $标签 $包 --repo $仓库 --title "$标签 · 手势识别智能系统" --notes-file $NotesFile --verify-tag
if ($LASTEXITCODE -ne 0) { throw 'Release 发布失败；Tag 已保留，可检查后续传' }
Write-Host "发布成功：$标签 | Commit: $(& git rev-parse HEAD)" -ForegroundColor Green
Write-Host "SHA256: $((Get-FileHash $包 -Algorithm SHA256).Hash)"
