"""动作素材与展示文案集中管理，预留类别不参与当前 CNN 推理。"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .配置 import 根目录, 类别, 操作映射

动作图目录 = 根目录 / '素材' / '手势图标'

@dataclass(frozen=True)
class 动作项:
    名称: str
    资源名: str
    操作: str
    颜色: str
    已训练: bool

动作列表 = (
    动作项('张开手掌', 'palm.png', '下一张图片', '#44bfff', True),
    动作项('握拳', 'fist.png', '上一张图片', '#d1adff', True),
    动作项('点赞', 'like.png', '放大图片', '#f9bf52', True),
    动作项('剪刀手', 'peace.png', '缩小图片', '#8bddc1', True),
    动作项('食指指向', 'one.png', '暂停 / 恢复', '#ff9cae', True),
    动作项('无手', 'none.png', '待机，不执行操作', '#9aabc0', True),
    动作项('OK 手势', 'ok.png', '预留动作', '#9aabc0', False),
    动作项('停止手势', 'stop.png', '预留动作', '#9aabc0', False),
    动作项('摇滚手势', 'rock.png', '预留动作', '#9aabc0', False),
    动作项('比心手势', 'heart.png', '预留动作', '#9aabc0', False),
)
动作索引 = {项.名称: 项 for 项 in 动作列表}


def 素材路径(名称: str) -> Path:
    """文件与动作索引绑定；不允许外部输入拼接任意路径。"""
    return 动作图目录 / 动作索引[名称].资源名


def 验证动作资源() -> None:
    assert len(动作列表) == 10 and len(动作索引) == len(动作列表)
    assert [x.名称 for x in 动作列表 if x.已训练] == 类别
    for 手势 in 操作映射:
        assert 动作索引[手势].已训练
    assert all(素材路径(项.名称).is_file() for 项 in 动作列表)
