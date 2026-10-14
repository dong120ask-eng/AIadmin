---
name: content-quality-gate
description: 检查真实任务的事实审核、使用权、平台规则、文本占位、图片及视频证据，生成与当前素材指纹绑定的质检报告。
---

# 内容发布质检

审核JSON必须绑定task_id/fingerprint，facts_reviewed、rights_reviewed、reviewer、platform_rules及带path/sha256的evidence。健康类另需health_reviewed及required_disclaimer。apply仅在passed时把任务转reviewed；人工事实判断不能由脚本假装完成。

使用实际Python执行 [脚本](scripts/quality.py)：

```text
python scripts/quality.py --root 工作区 --task 任务ID --review 审核JSON --output 质检JSON [--apply]
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
