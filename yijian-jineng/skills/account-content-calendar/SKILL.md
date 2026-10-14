---
name: account-content-calendar
description: 按带时区的起始时间、账号日上限与设备串行时段规划内容任务，不直接执行定时发帖。
---

# 混合账号内容日历

输入jobs每项含id/account_id/device_id；policy含start(时区)、account_gap_minutes、device_slot_minutes、account_daily_cap。所有间隔由用户或当前平台规则确定。输出不是发布许可；真正定时唤醒使用宿主支持的调度能力，届时再次核对台账。

使用实际Python执行 [脚本](scripts/calendar.py)：

```text
python scripts/calendar.py --root 工作区 --spec 日历JSON --output 日历计划JSON
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
