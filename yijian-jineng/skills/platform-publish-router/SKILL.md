---
name: platform-publish-router
description: 把电脑已保存的成果按账号与平台入队，恢复发布进度并调度专用平台、USB手机、模拟器或网页控制技能。
---

# 多平台发布路由
scripts/queue.py enroll --root ROOT --plan PLAN --output state/批次映射.json 默认只核对产物；apply才建任务。入队验证正文、实际图片/视频、实例平台，重复的相同素材/身份任务复用。
next --root ROOT --task TASK 给出下一阶段，读取任务状态与账号、设备、素材指纹。不跳过QA，不用人工改数据库绕过锁。
读取config/platforms.json中的平台条目与对应publish-*技能。候选包名须由devices/apps实测确认。公众号、视频号与微信账号不是同一业务身份；网页后台与手机App能力分别验证。
每个任务先claim，观察真实账号，编辑并保存草稿；只有明确当前批次逐任务确认才记录批准。所有提交前先记录attempt，结果未知保留锁，核验后complete/reconcile或not-published重新确认。
生成、草稿、提交审核、公开可见分别留证；published台账不是推荐或收益承诺。
