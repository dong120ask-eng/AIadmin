---
name: content-shared-runtime
description: "维护企业内容技能共用的项目、产品证据、账号、人群、预算、授权和任务状态；用于初始化档案、技能路由、能力检查与本地工作流记账。不自行生成成片或对外发布。"
---

# 内容项目共享底座

读取 references/contracts.md 初始化企业与项目；用 assets/project-template.json、account-template.json 和 job-template.json。未知字段保留null。把事实来源、账号唯一身份和调用预算作为下游任务的输入。

读取 assets/suite-manifest.json 查技能名称、依赖和实际开发状态；读取 assets/platform-catalog.json 查平台候选。候选不等于已核实支持，不将规则开发状态写成生成或发布验收成功。

读取 references/authorization-and-states.md 管理任务推进、幂等、审核、批准和发布核验；按需用 scripts/workflow_ledger.py 在用户指定目录记账。脚本只管理本地任务，不能代替浏览器、模型、调度器或支付系统。

首次运行辅助脚本时读取 references/helper-usage.md 的命令、输入结构、依赖复制与状态限制。把当前宿主实际技能路径作为脚本根，不虚构用户本机路径。

涉及Codex、WorkBuddy、豆包、千问时读取 references/executor-adapters.md；检查具体产品、版本与可用工具。普通对话环境用提示词与交接资料，能力不足时保留阻塞，不虚构技能安装路径或API。需要移植规则时用 scripts/suite_tools.py compose；需要Codex本机安装时用其install-codex命令，仅在明确目标目录执行。

遵守宿主保存方式和账号操作要求。只存凭证引用，不保存密码、密钥和Cookies。输出技能与能力清单、实际产物、状态、成本及缺失项。不自动创建持续调度；用户明确要求且调度器可用时才配置。
