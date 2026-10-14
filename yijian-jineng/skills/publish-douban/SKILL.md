---
name: publish-douban
description: 为豆瓣日记自有账号准备电脑稿件、验证体裁与必要平台设置，经真实校准执行草稿和单次提交，记录作品结果。
---

# 豆瓣日记内容发布

候选入口：[官网](https://www.douban.com/)；平台参考：[官方资料](https://help.douban.com/diary?app=1)。候选URL不是已经校准的编辑器URL。开发范围为 article，其他体裁明确报告未实现。

本实现仅做自有账号日记，不做小组自动群发、书影音评分或虚构评论；核对当前日记编辑页和原创声明条件。

先登记真实账号和设备，电脑生成并保存内容，由 [内容质检](../content-quality-gate/SKILL.md)核验事实与素材。使用 [平台交接](../platform-content-adapter/SKILL.md)检查真实文件及平台设置。publishing-profile/v1 增加 content_format 与 platform_review，核验字段包括 diary_entry,originality,visibility，逐项 true 必须来自实际页面检查，并绑定当前任务ID、素材指纹、审核者和证据。

按 [页面校准](../publishing-calibration/SKILL.md)观察真实身份、文字/文件控件、可见性和提交按钮；不提供固定坐标或猜测App包名。[共享执行器](../publishing-workflow-runner/SKILL.md)调用 prepare 前检查设置，claim后执行真实草稿步骤。图文顺序、视频上传完成、富文本视觉预览要依据真实页面核验，不能只检查上传文件存在。

展示精确草稿、账号与可见性，取得当前任务提交许可后 approve→begin→submit一次。用真实作品ID、链接和页面证据核验结果；结果不明用 [恢复技能](../publishing-recovery/SKILL.md)，不重发。发布后可导入真实平台数据进行复盘。

本技能与共享脚本已开发；当前账号、真实界面及公开发布尚未验收。页面不提供可验证草稿或身份锚点时停止，保留电脑文件供人工交接。
