"""PySide6 桌面工作台入口（使用现有 CNN 模型）。"""
try:
    from 手势系统.现代界面 import run
except ImportError as e:
    if 'PySide6' in str(e):
        raise SystemExit('当前虚拟环境缺少 PySide6。请执行：.\\.venv\\Scripts\\python.exe -m pip install "PySide6>=6.10,<6.13"') from e
    raise
if __name__ == '__main__':
    raise SystemExit(run())
