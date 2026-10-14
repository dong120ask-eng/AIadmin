---
name: selfmedia-analytics
description: 导入真实平台CSV导出，按账号、平台和2h/24h/72h观察窗汇总阅读互动，保留来源文件指纹。
---

# 发布后数据复盘

CSV字段platform/account_id/content_id/window/published_at/collected_at/views/likes/comments/saves/shares。时间带时区，指标非负；同作品同观察窗不能重复。无阅读量时互动率为null。CSV真实性由来源核对，不伪造平台抓取完成。

使用实际Python执行 [脚本](scripts/analytics.py)：

```text
python scripts/analytics.py --root 工作区 --csv 平台导出CSV --output 数据报告JSON
```

输出保存当前工作区；需要API或真实UI的动作只在明确配置和apply后执行。失败时记录可核验结果，按对应阶段恢复。
