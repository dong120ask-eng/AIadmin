# 本地辅助脚本用法

这些脚本只读取技能资料、复制明确授权的本机技能目录、组合提示词或记账，不调用模型、不登录、不付款、不对外发布。所有真实外部步骤由具备工具且已获授权的宿主执行。

## 技能列表与媒体分类
在本技能目录执行：

```bash
python3 scripts/suite_tools.py list
python3 scripts/suite_tools.py catalog --type short_video
```

## Codex目录安装
选一个明确的本机目标目录，例如项目.agents/skills。先只生成计划；--apply才写入。选择总控与一个平台会自动包含依赖。已有同名目标目录一律不覆盖，先检查实际版本和身份，不让复制流程破坏用户文件。

```bash
python3 scripts/suite_tools.py install-codex --skill enterprise-content-orchestrator --skill platform-douyin --destination /absolute/project/.agents/skills
# 确认该目标和复制操作已获用户授权后，追加--apply实际写入。
```

ChatGPT Work中的技能保存走当前技能仓库；不要用上面命令冒充用户Windows电脑已经安装。WorkBuddy走其实际“上传技能”界面，本脚本不伪造其安装器。

## 对话环境规则移植

```bash
python3 scripts/suite_tools.py compose --skill enterprise-content-orchestrator --skill platform-xiaohongshu --executor doubao --output /absolute/new-prompt.md
```

executor可选codex/workbuddy/doubao/qianwen。输出包含依赖及需要的文档、契约，没有认证文件。文件生成后按宿主要求持久化。提示词不能授予宿主不存在的工具；不把提示词粘贴说成原生安装成功。

## 工作流账本
先把项目模板填成真实资料；tenant_id/project_id必填。job-template需content_id、topic和content_type，平台与账号为可选目标；账号必须属于该项目。

```bash
python3 scripts/workflow_ledger.py --root /absolute/content-project create-project --file /absolute/project.json
python3 scripts/workflow_ledger.py --root /absolute/content-project plan --file /absolute/job.json
python3 scripts/workflow_ledger.py --root /absolute/content-project show --tenant COMPANY --job JOB_ID
python3 scripts/workflow_ledger.py --root /absolute/content-project advance --tenant COMPANY --job JOB_ID --state researched --evidence /absolute/research-evidence.json
```

script_ready/assets_ready/rendered需要真实artifacts列表；每项path是root/jobs/JOB_ID内的相对路径，kind为实际产物类型。文件哈希由脚本计算；不接收外部绝对路径或路径越界。后续质量与发布状态遵守authorization-and-states.md。

quality_checked证据包含review.artifact_digest、method以及七项checks。approved证据包含approval.approved、confirmed_at、artifact_digest；须有真实用户批准或既有自动发布授权。submitting还要求真实对应类型成品、明确time_window（start/end带时区或显式any）与daily_limit。账本按UTC日保守记数量；平台实际时区／排期由执行器核对，未知或定时任务先协调而不扩大限制。

提交及发布记录用publication对象。字段从真实页面／接口取得，不能生成假的平台证据来通过记账。unknown只允许凭查证结果更新submitted/under_review/scheduled/published或草稿，不能直接回到submitting重复提交。blocked/failed需先定位问题，再建明确的新版本任务；脚本不会自动重发。

```bash
python3 scripts/workflow_ledger.py --root /absolute/content-project export --tenant COMPANY --job JOB_ID --output /absolute/new-delivery.zip
```

导出只包含当前任务的产物及任务记录，不含项目数据库、其他企业数据或凭证。发布证据仍需执行器真实核验；通过字段检查不意味着独立证实已发布。
