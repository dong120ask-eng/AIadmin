---
name: content-experiment-lab
description: 可重复分配创意方案，对带真实来源的二项指标计算区间并识别样本不足，供选题、标题与结构优化。
---

# 内容框架实验复盘

assign用items(id)、variants和seed；compare用groups(variant/events/trials)、minimum_trials。events须是真实二项人数/次数，不能把点赞评论总和当点击人数。差异区间重叠或样本不足时不宣布胜者，观察差异不自动证明因果。

使用实际Python执行 [脚本](scripts/experiment.py)：

```text
python scripts/experiment.py assign/compare --root 工作区 --spec 实验JSON --output 报告JSON
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
