---
name: drama-growth
description: 导入短剧观看与互动数据，按平台人群和观察窗口计算留存完播及续看指标，输出下一轮样片与导演修改建议。
---

# 短剧数据复盘与迭代

用scripts/growth.py读取平台后台导出的CSV，输出metrics-report.json与director-feedback.md。脚本不自动抓取账号数据、不创建定时监控、不制造曝光或互动。CSV字段见assets/metrics.example.csv；content_id、platform、account、language、genre、variant、cohort、window_hours、episode_seconds定义对象和比较条件；plays/starts/retained_starts/completions/next_episode_clicks/likes是实际计数。缺失填空，不把未测量当0；不混用点赞、收藏、播放、热度。

```text
python <skill>/scripts/growth.py --csv <metrics.csv> --out <report-directory>
```

仅在同平台、账号、语言、题材、人群、时长和观察窗口内对比；指标按实际对应分母加权，拒绝重复快照及非法计数。小样本不选赢家；置信区间是统计不确定性提示，不证明因果。样本来源、曝光渠道、时间变化和推荐差异必须另查；默认输出descriptive_only，不将相关性报告成A/B实验结论。

复盘区分开场理解/承诺、集内任务与兑现、下集承接、标题封面匹配、配音与画面问题。优先选一个可修改变量做下一轮样片，主线和版权边界保留。反馈交cn-drama-director，新版本另建run，不原地改写已发布作品；需要替换/重发先征求用户本次发布授权。没有数据时不能宣称“爆款率提升”。
