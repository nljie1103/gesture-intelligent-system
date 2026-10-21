#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)


function Find-Python {
    $preferred = 'C:\Dev\python\python314\python.exe'
    if (Test-Path -LiteralPath $preferred) { return $preferred }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @('-3.14', '-3.13', '-3.12', '-3.11', '-3.10')) {
            & py $ver -c 'import sys; print(sys.executable)' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $exe = (& py $ver -c 'import sys; print(sys.executable)')
                if ($LASTEXITCODE -eq 0 -and $exe) { return ($exe | Select-Object -First 1).Trim() }
            }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $exe = (& python -c 'import sys; print(sys.executable)')
        if ($LASTEXITCODE -eq 0 -and $exe) { return ($exe | Select-Object -First 1).Trim() }
    }
    throw '未发现 Python 3.10~3.14，请先安装 CPython 后重试。'
}

$python = Find-Python
$appVersion = (& $python -c 'from 手势系统.版本 import DISPLAY_VERSION; print(DISPLAY_VERSION)' | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or -not $appVersion) { throw '读取软件版本失败' }
Write-Host "=== 手势识别系统 $appVersion：独立虚拟环境安装 ===" -ForegroundColor Cyan
Write-Host "已选择 Python: $python"
& $python -c 'import sys; assert sys.version_info[:2] >= (3,10) and sys.version_info[:2] <= (3,14), "仅支持 Python 3.10~3.14"'
if ($LASTEXITCODE -ne 0) { throw 'Python 版本不符合要求' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
}
$venvPy = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip 更新失败' }
Write-Host '安装 PyTorch CPU 版：避免误安装体积较大的 CUDA 套件…'
& $venvPy -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'PyTorch CPU 安装失败；请核对网络或代理后重试' }
& $venvPy -m pip install -r '依赖清单.txt'
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
Write-Host '运行单元测试…'
& $venvPy -m unittest discover -s '测试' -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw '自动化测试未通过，请勿发布' }
Write-Host '环境安装完成。运行：.\.venv\Scripts\python.exe 启动系统.py' -ForegroundColor Green
Write-Host '尚未训练模型时，界面只提供手动控制，不会虚构识别结果。'
