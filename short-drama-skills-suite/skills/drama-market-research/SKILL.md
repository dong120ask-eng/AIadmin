---
name: drama-market-research
description: 短剧选题前的市场证据研究，按同题材同人群拆解案例与反例，把可核验观察和原创试验假设交给导演技能。
---

# 短剧市场证据研究

用于新话题策划、用户提供对标链接或要求复盘市场适配。与同级 cn-drama-director 联合使用；不依赖特定宿主工具。

先确定平台、观众、主类型、影像风格和研究窗口。使用当前宿主合法可用的搜索或浏览器读取原始页面，记录访问日期和链接；用户提供影片、字幕或有权使用的剧本时，才做逐集镜头分析。不能从分享简介推断整剧结构。研究建议取同类型近期作品、普通表现作品和失效例子；缺少样本就明确限制，不为填表编造排名。

每个案例记录 observation、episode、timecode、evidence_level（A=可访问片段/字幕加可核验指标；B=片段或字幕；C=仅简介/方法假设）、metrics（指标名、值、单位、时间窗、来源、缺失原因）。点赞、热度和播放分别记录，缺失为 null。只学抽象机制，不复制人物、台词、标志性情节。A 级仍然不证明因果或代表市场。

从案例中提出“人群需求→具体冲突→主角行动→局部兑现→追剧问题”的原创方案，说明对该题材的适用边界、反例、制作成本与差异化。为开场/封面/片尾承接提出可测的 A/B 假设；同平台、账号、时段和投放条件尽量可比。没有随机实验就不报告因果效果。

读取 [研究输入示例](assets/research.example.json)，执行 scripts/research.py 将证据整理为 market-brief.json。脚本校验结构和来源，不代替观看或联网核验。

```text
python <skill>/scripts/research.py --input <research.json> --out <market-brief.json>
```

导演将 market-brief 的来源、观察、限制、反例与试验假设写进 director-brief.json 的 evidence、constraints、market_research；生产技能已经将整个导演指令传入编剧和审稿上下文。这是显式文件交接，不自动下载平台影片或调用付费榜单。无来源材料时先交通用框架候选，并标记市场验证待完成。
