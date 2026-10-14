---
name: publishing-calibration
description: 将真实账号、页面观察与审核者绑定成可复用的Android或网页发布配置，供平台执行器使用。
---

# 发布页面校准

先用publishing-workflow-runner的observe --apply取得真实截图与结构证据，再填实际唯一定位、账号、可见性及draft_steps。校准时核验绑定任务与证据指纹。页面/版本变化时重新观察和校准，不猜选择器。

使用实际Python执行 [脚本](scripts/calibrate.py)：

```text
python scripts/calibrate.py --root 工作区 --task 任务ID --profile 原始配置JSON --observation 观察JSON --reviewer 审核者 --output 校准配置JSON
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
