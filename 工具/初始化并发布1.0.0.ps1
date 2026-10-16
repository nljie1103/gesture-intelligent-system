#Requires -Version 5.1
# 私人仓库初始化、版本提交、标签、上传 Release 源码压缩包。
$ErrorActionPreference = 'Stop'
$项目 = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $项目
$仓库 = 'nljie1103/gesture-intelligent-system'
$版本 = 'v1.0.0'

function Check-Command($命令) {
    if (-not (Get-Command $命令 -ErrorAction SilentlyContinue)) { throw "请先安装 $命令 并重新打开 PowerShell（GitHub CLI 为 gh）" }
}
function Check-Git($步骤) { if ($LASTEXITCODE -ne 0) { throw "Git 操作失败：$步骤" } }
Check-Command 'git'
Check-Command 'gh'
& gh auth status
Check-Git 'GitHub CLI 登录检查。请先 gh auth login'
$登录名 = (& gh api user --jq '.login').Trim()
Check-Git '获取 GitHub 账号'
if ($登录名 -ne 'nljie1103') { throw "当前 gh 账号是 $登录名，本项目指定账号为 nljie1103，请切换账号以免建错仓库" }

if (-not (Test-Path -LiteralPath '.git')) {
    & git init -b main
    Check-Git '初始化 Git'
}
$分支 = (& git branch --show-current).Trim()
if ($分支 -ne 'main') { throw "当前分支是 $分支；仅允许在 main 执行首次发布" }
if (-not (& git config user.name)) {
    & git config --local user.name 'nljie1103'
}
if (-not (& git config user.email)) {
    # GitHub 提供的 no-reply 地址，避免泄露私人邮箱；可自行更换本仓库配置。
    & git config --local user.email '59471244+nljie1103@users.noreply.github.com'
}
& git add --all
Check-Git '暂存代码'
$暂存文件 = & git diff --cached --name-only
Write-Host '即将提交以下项目文件：'
$暂存文件 | ForEach-Object { Write-Host "  $_" }
if ($暂存文件 | Where-Object { $_ -match '(^|/)(数据|模型|输出|\.venv)/' }) {
    throw '检测到不应提交的个人数据/模型/缓存路径，发布已中止'
}
$确认 = Read-Host '确认以上文件均可上传私人仓库？输入 YES 继续'
if ($确认 -cne 'YES') { throw '已取消提交' }
& git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    & git commit -m '发布：v1.0.0 初始完整课程项目'
    Check-Git '创建首个 Commit'
} elseif ($LASTEXITCODE -ne 0) { throw '无法检查 Git 变更' }
$头 = (& git rev-parse HEAD).Trim()
$现有标签 = & git tag --list $版本
if (-not $现有标签) {
    & git tag -a $版本 -m 'v1.0.0：首个可训练、可评估、可演示版本'
    Check-Git '创建标签'
} else {
    $标签提交 = (& git rev-list -n 1 $版本).Trim()
    if ($标签提交 -ne $头) { throw "标签 $版本 已指向其他提交，禁止覆盖正式版本" }
}
# 已存在的仓库也必须是 Private，不能误将代码推到公开仓库。
& gh repo view $仓库 --json isPrivate --jq '.isPrivate' 2>$null | Out-Null
$远程存在 = $LASTEXITCODE -eq 0
if ($远程存在) {
    $隐私 = (& gh repo view $仓库 --json isPrivate --jq '.isPrivate').Trim()
    if ($隐私 -ne 'true') { throw '同名仓库不是 Private。拒绝发布。' }
    $已有Origin = (& git remote 2>$null | Where-Object { $_ -eq 'origin' })
    if (-not $已有Origin) {
        & git remote add origin "https://github.com/$仓库.git"
        Check-Git '添加远程 origin'
    }
} else {
    & gh repo create $仓库 --private --description '计算机视觉课程项目：基于自训练卷积神经网络的静态手势识别与实时交互' --source . --remote origin
    Check-Git '创建 GitHub 私人仓库'
}
$当前远程 = (& git remote get-url origin).Trim()
if ($当前远程 -notmatch '(^https://github\.com/|^git@github\.com:|^ssh://git@github\.com/)' -or $当前远程 -notmatch 'nljie1103/gesture-intelligent-system(\.git)?$') {
    throw "origin 地址与预定仓库不符：$当前远程"
}
& git push -u origin main
Check-Git '推送 main 分支'
& git push origin $版本
Check-Git '推送版本标签'
$发布目录 = Join-Path $项目 '.发布'
New-Item -ItemType Directory -Path $发布目录 -Force | Out-Null
$发布包 = Join-Path $发布目录 '基于手势识别的智能系统-v1.0.0-源码.zip'
& git archive --format=zip "--output=$发布包" $版本
Check-Git '生成与标签完全一致的版本源码包'
$摘要 = (Get-FileHash -LiteralPath $发布包 -Algorithm SHA256).Hash
Write-Host "源码包 SHA256：$摘要"
& gh release view $版本 --repo $仓库 *> $null
if ($LASTEXITCODE -eq 0) { throw "GitHub Release $版本 已存在。为避免覆盖，停止操作。" }
& gh release create $版本 $发布包 --repo $仓库 --title 'v1.0.0 · 手势识别智能系统' --notes-file '文档/发布说明-1.0.0.txt' --verify-tag
Check-Git '创建 GitHub Release'
Write-Host "仓库：https://github.com/$仓库" -ForegroundColor Green
Write-Host "Release：https://github.com/$仓库/releases/tag/$版本" -ForegroundColor Green
Write-Host "Commit：$头"
Write-Host "源码 SHA256：$摘要"
