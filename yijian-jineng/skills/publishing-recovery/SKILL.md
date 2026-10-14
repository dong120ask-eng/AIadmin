---
name: publishing-recovery
description: 审计中断与结果不明任务，依据精确任务、作品身份和真实证据恢复台账，避免重复投稿。
---

# 发布异常恢复

无核验JSON时只给阶段。核验记录含task_id/fingerprint/account_id/verified/reviewer/outcome/evidence(path/sha256)；published另需result_id、精确title，可附result_url。先实际查询作品后记录；not-published只在核验未发布后退回draft，必须重新确认才能再提交。

使用实际Python执行 [脚本](scripts/recovery.py)：

```text
python scripts/recovery.py --root 工作区 --task 任务ID [--verified-result 核验JSON]
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
