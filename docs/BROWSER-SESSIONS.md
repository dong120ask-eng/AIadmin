# 多账号浏览器会话原型：执行与验收

2026-10-19。基于 main `c5ff4480d2e392a078c839da6c9bd989aa1c3573` 的工作台，以及 PR #11 head `e9b6131d138d13fdba315e878bd397f993fa7b68`。独立分支 `codex/multi-account-browser-sessions`，依赖 #8/#11，不能跳过依赖直接合并 main。

## 实际交付

- 复用 Store 的企业、项目、账号记录，DispatchQueue 的 SQLite 表、幂等摘要、租约、资源锁、事件与 unknown 恢复。不新建第二套任务系统。
- 在同一 dispatch.sqlite3 增加 browser_sessions 注册表。账号与 Profile 不可重新分配；平台渠道与身份摘要也唯一，防止同一注册身份使用两套 Profile。初次注册只是操作者授权，不能作为页面身份核验结果。
- 通用 browser_read 任务只在显式注册后从 blocked 晋级 queued。media.execution_plan 继续保持通用发布能力 blocked；没有把平台规划错误地全局标成可执行。
- 全队列浏览器并发硬上限 2，worker 可用 --limit 1 降低；上限包含草稿任务、跨企业及 unknown 隔离资源。所有 worker 必须共用一个 dispatch.sqlite3；多数据库或多机器不能提供全局互斥，不支持多机同时运营同一账号。
- 会话排他由队列持久锁和 PR #11 的 ProfileLease 操作系统锁共同提供。公众号 browser_read 与 draft 共享公众号账号别名锁及 Profile 锁，登录入口也共享 Profile 锁。不会删除 Chromium 自带锁。
- worker按配置的 profile_ref 领取自己的任务；任务前后核对页面唯一账号ID。缺失/错号/过期/选择器变化均失败关闭，标记 needs_login_or_review 和 unknown，不自动扫码、切换账号或重试。具体原因须在本机观察，不能单凭选择器失败断言一定登录过期。
- 官方浏览器适配器只在固定渠道官方入口读取两个现场核实的唯一元素，检查同源，不接受任意 URL、JS、命令或发布按钮。读取结果仅保留 SHA256，不保存正文、完整网页、URL或凭证。事件和任务结果是本机结构化执行日志。回读摘要用于一致性核对，尚未实现电商指标字段采集。
- 仅使用独立持久 Profile，不导入日常浏览器，不调用 cookies/storage_state，不导出认证令牌。Windows脚本设置专用目录当前用户ACL；不能防御同一操作系统用户权限下的恶意程序。本机备份、云同步工具须排除此目录。
- 没有新增发布入口。公众号草稿仍使用既有已审核文章、素材、保存意图与列表重开回读协议；接通须另过平台实测。其他平台的草稿和发布适配未实现。

## Windows 11 安装与检查

在本机 PowerShell 执行（Windows 11、Git、Python 3.12，首次需下载依赖）：

```powershell
$ErrorActionPreference = 'Stop'
$checkout = Join-Path $env:USERPROFILE ('AIadmin-Browser-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
git clone --single-branch --branch codex/multi-account-browser-sessions https://github.com/dong120ask-eng/AIadmin.git $checkout
if ($LASTEXITCODE -ne 0) { throw '下载失败' }
Set-Location $checkout
git rev-parse HEAD
.\scripts\browser-sessions-windows.ps1 -Stage Setup
```

如果组织策略禁止执行脚本，停止并由管理员按本机策略处理；不要关闭安全策略。脚本建立 `.venv-browser`，安装固定 Playwright 1.55.0 及配套 Chromium，运行隔离测试，依赖可用性以本机实际输出为准。脚本及 PowerShell 5.1、Windows锁尚未实机验证。

默认私有目录是 `%LOCALAPPDATA%\AIadmin-Browser`，数据库在 data、会话在 profiles。复用已有工作台时通过 -PrivateRoot 指向其父目录（必须同样有 data/workbench.sqlite3 和 data/dispatch.sqlite3），先备份非认证业务记录，不复制认证目录。所有命令需使用同一 PrivateRoot 和 Tenant。未有账号时打开现有工作台创建真实项目和账号，禁止用测试记录代替：

```powershell
& .\.venv-browser\Scripts\python.exe -m workbench --data-dir "$env:LOCALAPPDATA\AIadmin-Browser\data" serve --open-browser
```

## 两个授权账号与现场配置

将下面整段交给在上述checkout中运行的本机Codex：

```text
读取 AGENTS.md、docs/BROWSER-SESSIONS.md、docs/WECHAT-WINDOWS-ACCEPTANCE.md 与 WECHAT-BROWSER-DRAFT.md。复用现有项目、账号与数据库，不改main，不合并，不正式发布。
1. 记录源码SHA、Windows build、Python/Playwright/Chromium版本，执行Setup和Tests。检查私有目录ACL与非链接属性。不得读取、上传或打包浏览器Profile、Cookie、认证文件、原始URL和数据库。不要把Linux隔离测试当Windows通过。
2. 从现有工作台选择两个用户明确授权的测试账号，核对企业/项目/平台/唯一ID，不以昵称作身份。没有两个授权账号就停在真实账号关卡，不生成假记录冒充。为每个账号生成不同profile_ref，仅含字母数字下划线短横线。在本机仓库外写binding-a.json/binding-b.json，字段以validate_binding为准；tenant_id/project_id/account_id须引用现有工作台，account_unique_id须与工作台external_id一致。每个平台渠道从media-index.json实际读取，不能猜测。真实ID尚待页面核验时明确标注未验证，不设置成功结论。
3. 逐个Register，再Inspect。由用户在官方网页首次授权扫码；Inspector只用于观察账号唯一ID和最小只读数据元素，不点击保存/发布。核对官方域名、稳定唯一ID及两个元素的唯一性，配置文件写profile_ref、identity_selector、read_selector、verified_at四个字段。selector只从现场观察取得。配置和binding仅存在受保护目录。若页面身份与已登记ID不一致，停止；不可覆盖注册表绕过一对一绑定，先核查原工作台账号是否填错。无法观察浏览器或无法取得唯一ID则停止并报告缺口。
4. 每个账号写request-a.json/request-b.json，字段tenant_id/project_id/account_id/channel_id与binding完全一致，content_type从渠道forms选，publish_mode=draft_only。该字段不授权草稿，当前动作仍只读。分别Enqueue不同key，然后用对应config各Run一次；应产生real_browser_read、identity_verified=true、摘要、draft_saved=false、publishing_verified=false。关闭并重新打开同一Profile再提交新的只读key，验证登录复用；同key重复入队应返回原任务且不重复执行。记录后台观察与摘要，禁止伪造成功。
5. 先运行离线双账号测试，再用真实账号进行只读故障演练：同时启动相同Profile应拒绝；两Profile受全队列并发上限约束；用错误身份期望应拒绝；官方界面注销后再次运行应隔离，重新扫码不自动重跑旧任务。中断进程后等待租约到期，Recover应标unknown且资源保留；确认旧进程停止且只读无副作用后Resolve，仅取消旧任务，重新核验后使用新的只读key。不以复制Profile或删除数据库解除隔离。
6. 按下方关卡记录真实结果。只读通过后，公众号草稿严格按已有文档和已审核版本接通，不把只读成功当草稿成功。其他平台须逐个平台写适配器、测试、审核和回读，保持blocked直至验收。正式发布另需明确授权、适配、内容版本、权限与结果核对，本轮不执行。
```

绑定JSON字段：tenant_id、project_id、account_id、account_unique_id、channel_id、route="browser"、profile_ref。不要添加密码、Cookie或token。配置JSON四字段如上，不能照抄示例选择器。Windows JSON保存为UTF-8，支持BOM。以下 $private 中的文件须由本机Codex基于真实记录与现场观察创建：

```powershell
$private = Join-Path $env:LOCALAPPDATA 'AIadmin-Browser'
.\scripts\browser-sessions-windows.ps1 -Stage Register -Binding "$private\binding-a.json"
.\scripts\browser-sessions-windows.ps1 -Stage Inspect -Profile account-a
# 在官方界面观察核验后，再生成config-a.json、request-a.json；account-a必须与binding一致
.\scripts\browser-sessions-windows.ps1 -Stage Enqueue -Profile account-a -Request "$private\request-a.json" -Key read-a-001
.\scripts\browser-sessions-windows.ps1 -Stage Run -Config "$private\config-a.json" -Limit 2
.\scripts\browser-sessions-windows.ps1 -Stage Status
# 账号B按相同步骤使用account-b及对应文件，不能交叉使用config
.\scripts\browser-sessions-windows.ps1 -Stage Tests
# 只有故障后执行：
.\scripts\browser-sessions-windows.ps1 -Stage Recover
# 确认旧进程停止且核查完毕后，填入Status返回的真实任务ID：
# .\scripts\browser-sessions-windows.ps1 -Stage Resolve -Task $taskId -WorkerStopped
```

Run每次最多执行一个任务；两个PowerShell窗口可分别运行两个Profile。Inspect必须关闭后再Run。manual_login_only明确不表示身份已核验。未知任务的资源锁不会仅因重新登录自动释放。

需要停止授权时：`.\scripts\browser-sessions-windows.ps1 -Stage Revoke -Profile account-a`。撤销后拒绝新检查，执行中的只读操作在回读后再检查授权，不能升级为成功。关闭现有窗口；本原型不自动恢复撤销授权，重新授权须人工审核后开发显式流程，不能靠重复Register绕过。

## 本轮证据与剩余关卡

Linux `python -m unittest discover -q`：**115项通过、0跳过**，其中100项继承PR #11、15项新增。新增测试在临时目录创建两个明确标识的合成账号，覆盖一对一绑定、授权/租户、幂等、Profile选择、并发上限、错号隔离、故障不重试、过期租约、旧worker拒绝、恢复取消、符号链接和只读域名/元素/摘要。PR #11已有操作系统进程锁测试。本机测试不需要网络或平台凭证。

| 关卡 | 本轮结果 | 下一步证据 |
|---|---|---|
| 双账号调度与异常恢复 | 隔离测试通过 | tests/test_browser_sessions.py |
| Linux完整回归 | 115通过 | 上述命令实际输出；非CI证明 |
| Windows安装、ACL、PowerShell、msvcrt锁 | 未执行 | 本机版本、ACL及测试记录 |
| 真实Chromium启动与会话重启 | 未执行 | 本机浏览器观察；当前云端未安装Playwright |
| 两个真实授权账号、唯一身份及过期检测 | 未执行 | 用户本机扫码与身份前后核对 |
| 真实平台只读及数据回读 | 未执行 | real_browser_read、脱敏摘要与观察记录 |
| 公众号草稿保存及列表重开 | 未执行 | 已审核文章、素材、真实草稿ID、独立回读 |
| 其他平台草稿/电商数据字段 | 未接通 | 各平台适配和实测 |
| 正式发布 | 未执行 | 单独授权、发布适配和后台结果核对 |

剩余限制：目前会话健康是按任务检查，没有后台续期器，不承诺登录永久有效；身份选择器必须指向唯一ID可见文本，隐藏属性、iframe和特殊富文本页需新适配；渠道级去重不能自动识别同平台不同渠道ID的账号别名，操作者不得为同一账号分配多个渠道Profile；不同数据库/设备无全局协调。平台可改变页面、登录期限和访问条件，遇验证码或访问拒绝由操作者在官方界面处理，不绕过。通用只读读取固定入口，不是任意页面采集系统。
