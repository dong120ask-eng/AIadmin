---
name: platform-content-adapter
description: 为简书、美篇、豆瓣日记及YouTube、TikTok、X验证体裁、真实素材交接和任务绑定的平台设置，输出可核验交接单并阻止缺设置的自动执行。
---

# 平台内容交接

读取 [能力表](references/capabilities.json)；能力表中的体裁是本工具实现范围，不代表平台全部能力。先用已有内容工厂生成并保存文件、登记真实任务，按对应平台技能观察当前编辑页。

在 publishing-profile/v1 中增加 content_format 和 platform_review：后者含精确 task_id、fingerprint、reviewer、confirmed 字段布尔核验表、真实 evidence 文件指纹。哪些字段必填由能力表给出；不得把默认样例当观察结果。

运行 scripts/adapter.py --root 工作目录 --task 任务ID --profile 配置相对路径 --output 交接单相对路径。工具验证实际素材指纹、平台身份、体裁、文字步骤和网页上传步骤，只保存交接单。任务仍须质检、真实页面校准、草稿预览和明确提交许可。

共享发布执行器会再次核验平台审核与证据，缺少受众、原创、版权或可见性等记录则停止。用户只是要求开发时不操作真实账号；结果不明不重发。
