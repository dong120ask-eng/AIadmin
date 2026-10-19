# AIadmin / Aladmin 复用审计与安全整合

核查日期：2026-10-20（北京时间）。AIadmin main commit：c5ff4480d2e392a078c839da6c9bd989aa1c3573，tree：c5ff4480d2e392a078c839da6c9bd989aa1c3573。Aladmin main tree：5fed620c5804d6058076773cd749def523b3c73c。仅比较当前源码快照，不代表完整历史授权审计。

## 结论与整合结果

优先保留 AIadmin 既有工作台、队列和技能；新增 reuse/aladmin 可选组件目录，原样复用6个PowerShell安装脚本、1个安装行为测试及其MIT LICENSE，另原样保留唯一明确授权营销技能的4个源文件。总计12个来源文件，逐文件Git blob哈希核验。未修改main、仓库可见性、现有技能清单、发行包或真实客户端。未复制其他18项技能。

## 19项功能对应

| Aladmin技能 | AIadmin对应 | 差异、依赖与处置 |
|---|---|---|
| aladmin-deploy-guide | 现有部署文档、yijian-jineng/tools/deploy.py | 部署说明重复；不复制 |
| apple-keynote-product-video | video-reference-suite、content-short-video | 产品商业视频风格提示词；宿主视频生成 |
| browser-use-automation | workbench/media.py、dispatch.py；PR #12 | Aha专属宿主，不是独立浏览器执行器；等待授权及后端适配 |
| byted-mediakit-motion-graphics | desktop-media-production、video-format-adaptation | 可增加动效渲染；Node>=22.12、FFmpeg/FFprobe、Chromium、gsap 3.14.2、hyperframes 0.8.38、puppeteer-core 25.11.0；依赖与源码许可另审 |
| consistent-style-images | content-image-text、desktop-media-production | 系列一致性与本地排版；不复制未授权脚本 |
| doubao-creative-design | content-image-text、product-market-marketing | 设计与模板重复；字体/SVG/模板须逐项授权 |
| doubao-creative-drama | content-short-drama、short-drama-skills-suite | 短剧策划重复；生成工具和飞书依赖 |
| doubao-creative-video | content-short-video/long-video、video-reference-suite | 视频规划重复；工具映射未完成 |
| doubao-headlines-calendar | topic-viral-research、account-content-calendar | 标题与排期重复 |
| doubao-multiplatform-rewrite | content-media-router、platform-content-adapter | 分发改写重复；强制飞书交付不匹配本地制作包 |
| doubao-newmedia-writing | content-article、content-image-text | 写作重复；飞书写入额外依赖 |
| doubao-product-analysis | skills/product-analysis、product-analysis-local | 决策研究更深但不是可直接执行的产品数据适配器；飞书/HTML块依赖 |
| doubao-questionnaire-designer | product-analysis | 问卷、访谈与VOC补充价值；需授权和文档工具映射 |
| doubao-shortvideo-writing | content-short-video、video-shot-prompts | 分镜重复；在线文档交付额外依赖 |
| doubao-video-extract | video-reference-adapt、desktop-media-production | 视频提取可能补充价值；Python/下载解析依赖、媒体权利与站点能力另审 |
| lark-shortdrama-studio | content-short-drama、short-drama-skills-suite | 飞书四层资产管理有补充价值；Base授权与生成工具未接通 |
| marketing-material-generator | content-image-text、product-market-marketing | 五环节素材流水线可选复用；4文件MIT核实，未接通运行 |
| reference-prompt-iteration | video-reference-adapt、video-shot-prompts | 参考素材迭代重复 |
| seedance-real-selling-video | content-short-video、video-shot-prompts | UGC风格补充；上游无LICENSE，视频示例不得复制 |

以上是功能重叠判断，不表示实现等价。两棵树所有blob精确比较，仅根LICENSE和NOTICE相同；没有发现完全相同的技能或脚本blob。不能把语义重叠当作逐字复制证据。

## 原创与授权证据

- 安装脚本与行为测试：各文件明确标注 SPDX-License-Identifier: MIT 和天津智慧筑基科技有限公司版权；Aladmin NOTICE 的自有原创范围声明与根LICENSE共同支持复用。保留源文件不改写署名。没有对所有历史贡献者做独立身份调查。
- marketing-material-generator：重新读取公开上游树 https://github.com/cuiabner1-ux/marketing-material-generator/tree/948ca893593587f6517262ec837dd7b50731a81e ，4个blob与私有副本完全匹配；原MIT版权 cuiabner1-ux 原样保留。文件级证据在 reuse/aladmin/PROVENANCE.json。
- Aladmin RIGHTS_REVIEW.json 当前仍将其余18项标为 pending_redistribution_rights。根MIT不会覆盖豆包工作台复制品。Seedance来源树没有LICENSE的审计结论仍未被新授权替代。
- 外部飞书模板、在线服务、字体、SVG、MP4和运行时依赖不因技能源码MIT而获准使用或公开。

## 安装器差异与取舍

| 组件 | 已有实现 | 复用判断 |
|---|---|---|
| AIadmin yijian-jineng/tools/deploy.py | Python标准库；计划预览、差异备份、整个skills目录暂存交换、锁 | 保留入口；与PowerShell锁协议不同，不并行运行 |
| AIadmin video-reference-suite/tools/install_codex.py | 项目.agents/skills；预检冲突、失败清理 | 保留六技能专用安装，不重复开发 |
| AIadmin ecommerce-suite/安装Codex.py | 电商独立安装入口；PR #9另有增强 | 本次不替换；避免与待合并PR重复工作 |
| Aladmin install-shared.ps1 | 默认跳过已有目录；显式Update；SHA256暂存核对、保留备份、按技能回滚、拒绝链接、进程文件锁 | 原样复用为可选Windows入口；不是全批次事务，也不是签名分发 |
| Aladmin wrappers | Codex CODEX_HOME/.codex；WorkBuddy .codebuddy兼容.workbuddy；DSH DSH_HOME；豆包显式目标 | AIadmin支持项目.agents目标，用TargetDir指定；不依据文件复制宣称客户端可加载 |

不引入第二套工作台/队列或重写安装引擎；主入口统一须在Windows与客户端验收后另议。营销技能未加入自动路由，先作为可选源组件，避免强制飞书模板或固定模型污染标准库工作台。

## 浏览器与进行中的工作

AIadmin main 的 media.execution_plan 仍为blocked；Aladmin browser-use-automation只包含Aha宿主调用契约，未提供可独立启动的通用后端。不能通过复制该技能解决浏览器能力缺口。重新列举PR确认 #8公众号草稿、#11 Windows扫码流程、#12多账号会话原型仍open；本次不重做这些分支。#7已合并。Aladmin #1已合并。

## 验证与边界

- 本地Python3.12：12个来源文件Git blob精确匹配；唯一技能目录与4文件白名单一致；18项排除清单保留。
- 新增4项离线校验测试：正常快照、MIT文件篡改、夹带未审技能、缺失安装源码。结果见PR与CI。
- 环境无PowerShell，本地未执行Windows行为测试；新增独立CI运行Windows PowerShell及pwsh复用的12项临时目录行为检查。其通过状态必须查实际运行，不能沿用Aladmin历史通过记录。
- 未执行模型调用、飞书写入、素材生成、浏览器登录或发布；未证明用户Windows安装及四端加载成功。

## 尚需授权与下一验收

18项技能逐项保留私有，需取得原始作者/权利方再分发条款、准确版本、适用资产范围与许可证副本；视频/字体/模板/依赖分别核实，不能用方法论引用的MIT替代整体授权。先为浏览器后端与视频提取补齐来源证据，产品分析与分镜等重复项无需为整合而整合。营销流程若要启用，需确认飞书副本和字段权限、工具映射、成本、尺寸、模型可用性、失败恢复和真实产物验收。

## 来源

- https://github.com/dong120ask-eng/AIadmin/tree/c5ff4480d2e392a078c839da6c9bd989aa1c3573
- https://github.com/dong120ask-eng/Aladmin/blob/main/RIGHTS_REVIEW.json （私有）
- https://github.com/dong120ask-eng/Aladmin/blob/main/NOTICE.md （私有）
- https://github.com/dong120ask-eng/Aladmin/pull/1 （私有）
- https://github.com/dong120ask-eng/AIadmin/pull/12

