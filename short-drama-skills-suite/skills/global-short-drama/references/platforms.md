# 全球发布接入

本技能的 Python 部分实现制作与发布资料导出；当前没有内置平台上传 SDK。真实分发由 Codex 在用户授权后，通过官方连接器/平台后台完成。不要给未接入的平台打上“自动发布已实现”。平台最新规格以用户实际后台与官方文档为准；运行时记录 verified_at、入口、账号、权限、时长/画幅/大小限制、字幕方式、披露规则。

| 平台 | 当前路线 | 接入所需 |
|---|---|---|
| 红果 | 商务/创作者后台供片，未核验公开上传 API | 用户提供实际创作者后台或合作文档，主体、版权与审核资料；签约与确认单独停下 |
| 抖音、快手 | 创作者后台或已批准官方接口 | 登录/授权；普通短视频与短剧内容库分别验收 |
| B站、小红书、视频号 | 创作者后台 | 登录、账号权限、分集/合集与标题封面预览 |
| YouTube | 已授权 Data API 或 Studio | OAuth、项目状态、频道、上传与可见性权限 |
| TikTok | Content Posting API 或创作者后台 | video.publish 权限、应用审核、账号地区与可见性 |
| Instagram、Facebook | Meta 官方内容发布接口或后台 | 合格账号类型、页面关联和发布权限，分别确认两平台回执 |
| ReelShort、DramaBox 及其他专业短剧应用 | 合作供片 | 平台合作联系人/后台/正式文档，发行地区与版权条款 |

红果入口尚未用官方来源核验，不引用搜索结果里的不明网站要求用户登录。用户提供真实后台后通过工具访问验证，记录可用能力；没有接口时导出供片材料并报告 blocked_access。新增平台采用相同能力发现方法，而非枚举虚构 endpoint。

## 供片/发布资料

全剧简介、逐集简介、人物表、集数与实际分钟数、封面/海报、各语言标题和简介、视频及字幕、版权证明、音乐/音色许可、制作主体、演职员信息、必要备案/许可及 AI 内容标识。无法证明的材料标为缺失，不生成虚假编号。project.example.json 的 rights 默认 false，需证据支持后由用户/代理更新。

国内微短剧备案审核条件在实际提交前重新核查。2026-10-14已核验正式《微短剧发展管理办法》自2026-09-01施行，不再以6月征求意见稿作为当前依据。针对项目类别、题材和播出路径核验现行要求及平台材料，不简单用投资金额推断所有项目可播。特殊题材的创作/供片路径须结合实际制作主体与主管部门要求；不能将模型审稿当作平台或行政审核。

官方核验起点：
- [广电总局现有通知](https://www.nrta.gov.cn/art/2025/2/5/art_113_70148.html)
- [2026 正式微短剧发展管理办法](https://www.nrta.gov.cn/art/2026/7/31/art_1588_73827.html)
- [抖音入驻说明](https://developer.open-douyin.com/docs/resource/zh-CN/developer/join/join-into-developer-platform)
- [YouTube videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- [TikTok Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-get-started)
- [Meta 内容发布](https://developers.facebook.com/docs/instagram-platform/content-publishing)

## 回执与重复提交

每次提交前展示平台、账号、集数/语言、文件哈希、标题、可见性、计划时间和材料缺口并获得确认。记录至项目 publish-log.jsonl：platform、account_id、episode、language、asset_sha256、status、remote_id、url、submitted_at、last_checked_at。去重键是账号+平台+集+语言+文件哈希。状态分别为 prepared/uploaded/submitted/in_review/published/rejected/unknown；生成资料只能是 prepared。

网络结果不确定先查后台，不盲目重发；发布点击不确定标 unknown。审核未通过保留原因，修改具体问题后再请求本次提交确认。没有作品 URL/ID 或明确后台上线证据不可标 published；一次平台失败不删除其他已完成结果。后续数据复盘需用户另行授权或当前任务明确要求，不自动创建监控。
