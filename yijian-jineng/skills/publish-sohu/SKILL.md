---
name: publish-sohu
description: 为搜狐号自有账号适配文章、图文或视频，调用经真实校准的发布执行器准备草稿、核对发布确认与结果。
---

# 搜狐号发布

后台候选入口：[创作者平台](https://mp.sohu.com/)。先确认当前可用入口、账号权限与具体体裁；入口可打开不代表账号发布已验收。

读取 [质检](../content-quality-gate/SKILL.md)、[页面校准](../publishing-calibration/SKILL.md)、[执行器](../publishing-workflow-runner/SKILL.md)。实际观察账号和编辑页面，为本平台建立publishing-profile/v1，不提供未经观察的固定控件。

电脑保存成果后质检、claim、按校准步骤准备草稿；核对标题、正文、媒体、来源/原创标记与可见性。用户确认该精确任务后approve/begin，再submit一次。用真实作品ID和证据核验；结果不明按 [恢复技能](../publishing-recovery/SKILL.md)处理，不直接重发。

数据导出交给 [复盘](../selfmedia-analytics/SKILL.md)。平台页面、规则、账号及验证码校准需在后续真实测试完成；开发包不宣称本平台已成功发帖。
