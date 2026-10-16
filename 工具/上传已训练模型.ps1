#Requires -Version 5.1
# 首次训练成功后，手动上传必要的模型交付物到既有 v1.0.0 Release。
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$仓库 = 'nljie1103/gesture-intelligent-system'
$版本 = 'v1.0.0'
$必需 = @('模型/正式模型.pt','模型/运行阈值.json','模型/数据划分.json','输出/实验分析/训练与对比结果.json')
foreach ($路径 in $必需) {
    if (-not (Test-Path -LiteralPath $路径 -PathType Leaf)) { throw "未找到训练产物：$路径。请先真实采集并训练。" }
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw '请先安装 GitHub CLI (gh)' }
$隐私 = (& gh repo view $仓库 --json isPrivate --jq '.isPrivate').Trim()
if ($LASTEXITCODE -ne 0 -or $隐私 -ne 'true') { throw '找不到指定 Private 仓库' }
& gh release view $版本 --repo $仓库 *> $null
if ($LASTEXITCODE -ne 0) { throw '请先发布 v1.0.0 正式 Release' }
$文件名 = '基于手势识别的智能系统-v1.0.0-训练产物.zip'
$已经存在 = & gh release view $版本 --repo $仓库 --json assets --jq '.assets[].name'
if ($已经存在 -contains $文件名) { throw '该版本已经上传过训练产物。为保证可追溯性，请不要覆盖。' }
$暂存 = Join-Path $env:TEMP ('gesture-trained-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $暂存 -Force | Out-Null
try {
    foreach ($文件 in $必需) {
        $目的 = Join-Path $暂存 $文件
        New-Item -ItemType Directory -Path (Split-Path -Parent $目的) -Force | Out-Null
        Copy-Item -LiteralPath $文件 -Destination $目的
    }
    $打包目录 = '.发布'
    New-Item -ItemType Directory -Path $打包目录 -Force | Out-Null
    $包 = Join-Path (Resolve-Path $打包目录).Path $文件名
    if (Test-Path -LiteralPath $包) { Remove-Item -LiteralPath $包 -Force }
    Compress-Archive -Path (Join-Path $暂存 '*') -DestinationPath $包
    Write-Host '这将向私人仓库 Release 上传已训练权重、划分记录和统计指标（不含原始照片）。'
    Write-Host "包：$包"
    Write-Host "SHA256：$((Get-FileHash -LiteralPath $包 -Algorithm SHA256).Hash)"
    if ((Read-Host '确认上传？输入 YES') -cne 'YES') { throw '用户取消上传' }
    & gh release upload $版本 $包 --repo $仓库
    if ($LASTEXITCODE -ne 0) { throw '模型附件上传失败' }
    Write-Host '训练产物已附加到 v1.0.0 Release' -ForegroundColor Green
} finally {
    if (Test-Path -LiteralPath $暂存) { Remove-Item -LiteralPath $暂存 -Recurse -Force }
}
