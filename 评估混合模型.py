"""只读冻结测试划分，不会重新训练、随机划分或重选阈值。"""
import argparse
import json
import time
from pathlib import Path
from torch.utils.data import DataLoader
from 手势系统.配置 import 模型目录, 输出目录, 数据目录
from 手势系统.数据 import 手势数据集
from 手势系统.模型 import 加载分类模型
from 手势系统.训练 import 批量评估

if __name__ == '__main__':
    p=argparse.ArgumentParser(description='仅对已冻结的本地测试集重新评估')
    p.add_argument('--model',choices=['正式','混合基线','混合微调'],default='正式')
    a=p.parse_args()
    path=模型目录/'混合数据划分.json'
    if not path.exists():
        raise FileNotFoundError('尚未完成混合训练：找不到混合数据划分.json')
    split=json.loads(path.read_text(encoding='utf-8'))
    model,shape,meta=加载分类模型(模型目录/f'{a.model}模型.pt','cpu')
    samples=手势数据集(split['测试'],目录=数据目录,尺寸=shape)
    start=time.perf_counter()
    result,loss,_,_=批量评估(model,DataLoader(samples,batch_size=32,num_workers=0),'cpu')
    result.update({'模型':a.model,'交叉熵损失':round(loss,5),'处理耗时秒':round(time.perf_counter()-start,3),
                   '冻结测试轮次':split['本地轮次']['测试']})
    folder=输出目录/'混合训练实验';folder.mkdir(parents=True,exist_ok=True)
    dest=folder/f'{a.model}-独立重评.json'
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{a.model}：测试样本{result["样本数"]}；准确率{result["准确率"]:.4f}；F1={result["宏平均F1"]:.4f}')
    print('结果：',dest)
