---
name: content-package-export
description: 把一个已质检任务的正文与媒体打包为指纹可核验交接ZIP，供USB手机、模拟器或其他执行宿主接续。
---

# 电脑素材发布交接

仅导出当前任务成果和身份/可见性，不带登录状态、SQLite、审批或设备锁。新工作区重新登记、质检与核对账号；导出不表示已发布。ZIP内部逐文件验证并返回整个ZIP指纹。

使用实际Python执行 [脚本](scripts/export.py)：

```text
python scripts/export.py --root 工作区 --task 任务ID --output 交接ZIP
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
