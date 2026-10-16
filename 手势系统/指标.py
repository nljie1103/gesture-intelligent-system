"""不依赖 sklearn 的分类指标，保证轻量离线评估。"""
import numpy as np
from .配置 import 类别


def 计算分类指标(真值, 预测, 类别数=len(类别)) -> dict:
    混淆 = np.zeros((类别数, 类别数), dtype=int)
    for 实际, 输出 in zip(真值, 预测):
        混淆[int(实际), int(输出)] += 1
    总数 = int(混淆.sum())
    准确率 = float(np.trace(混淆) / 总数) if 总数 else 0.0
    逐类 = []
    for i in range(类别数):
        tp, fp, fn = int(混淆[i, i]), int(混淆[:, i].sum() - 混淆[i, i]), int(混淆[i].sum() - 混淆[i, i])
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        逐类.append({"类别": 类别[i], "精确率": round(p, 4), "召回率": round(r, 4), "F1": round(f, 4), "样本数": int(混淆[i].sum())})
    return {"样本数": 总数, "准确率": round(准确率, 4), "宏平均F1": round(float(np.mean([x['F1'] for x in 逐类])), 4),
            "逐类指标": 逐类, "混淆矩阵": 混淆.tolist()}


def 选择验证阈值(真值, 概率矩阵) -> dict:
    """仅对验证集网格选阈值；惩罚将无手误触发为有效指令。"""
    概率 = np.asarray(概率矩阵, dtype=float)
    真值 = np.asarray(真值, dtype=int)
    if len(真值) == 0:
        raise ValueError("验证集不能为空")
    最优 = None
    for 阈值 in [.60, .70, .80, .85, .90, .95]:
        预测 = 概率.argmax(axis=1)
        通过 = 概率.max(axis=1) >= 阈值
        正例 = 真值 != 类别.index("无手")
        负例 = ~正例
        正确执行率 = float(np.mean((预测[正例] == 真值[正例]) & 通过[正例])) if 正例.any() else 0.
        空白误触率 = float(np.mean((预测[负例] != 类别.index("无手")) & 通过[负例])) if 负例.any() else 0.
        得分 = 正确执行率 - 4 * 空白误触率
        候选 = {"阈值": 阈值, "验证正确指令通过率": round(正确执行率, 4), "验证无手误触发率": round(空白误触率, 4), "评分": round(得分, 4)}
        if 最优 is None or (得分, 阈值) > (最优["评分"], 最优["阈值"]):
            最优 = 候选
    return 最优
