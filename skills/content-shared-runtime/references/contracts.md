# 企业内容共享数据契约

## 项目与事实
用assets/project-template.json初始化；tenant_id与project_id必须唯一，字符限字母数字下划线连字符。product.facts每条保存fact_id、text、source_type、evidence_ref、verified_at、scope；证据单独存product.evidence。照片可见事实不等于验证真伪或功效。audience.hypotheses与evidence分开。

assets/suite-manifest.json保存技能名称、所在目录、依赖、版本及开发和实测状态；assets/platform-catalog.json保存平台多重分类和候选类型。它不是全部中国媒体名单；新增平台先调查官方创作者／商家入口，记录是否普通投稿、商家专用、邀请制、客户端专用或无可用入口。APP指数可以发现线索，不证明投稿能力。

## 账号与授权
用assets/account-template.json；账号绑定企业、项目、platform_id及external_id。display_name不是唯一身份依据。账号档案只保存credential_ref/browser_context_ref；凭证留在执行环境安全配置。混合经营保持账号各自人设、目标和许可，避免同质内容与虚假互动。

publish_scope的mode取draft_only/review_then_publish/auto_publish；allowed、目标平台、账号、形式、话题、时间与数量都需实际用户授权。既有范围内无需反复批准；新账号、超额、付费投放、协议或权利转让不包含在旧授权。

## 任务与产物
用assets/job-template.json；一条job只对应一个平台账号版本。母稿与多个平台job用content_id关联；幂等键含企业项目、平台账号、内容及版本。单个用户问题可以产出多形式，但不要默认所有选题都生成小说、歌曲或短剧。

每个artifact保存相对path、kind、sha256、size、created_at和limitations。kind区分production_brief/text_draft/script/image/audio/video。文字与提示词不是实际媒体。完整artifact_digest与审核和批准关联；任何改变导致旧审核失效。共享脚本管理的是本地证据状态，不独立证明外部平台事实。

## 能力与成本
capabilities逐项保存available/unavailable/unverified和工具名、最后验证时间：检索、图像理解、文件保存、图片、视频、配音、音乐、剪辑、浏览器、平台接口、调度、计费。安装不等于执行成功。未接入模型时仍可由当前具备创作能力的宿主生成文本；未接入媒体工具时交付制作包。

预算需要估算及真实计费记录；不确定时保持null。没有用户授权不能新增费用；未知计费只有得到对应授权才能调用。成本上限字段不能伪装供应商硬性扣费机制。失败可能仍有供应商成本，不自动宣称免费或全额退款。

## 保存与复用
在宿主指定的持久化项目位置保存数据，不能把临时目录当永远存在。共享脚本可在明确本机root建立SQLite账本；它是单操作者工具，tenant字段仅防资料串用，不是身份认证或公网多租户权限系统。遵守当前宿主的文件保存与安全要求。
