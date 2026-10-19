# 公众号草稿：Windows 11 本机执行与验收

日期：2026-10-19。基于PR #8 head `7ede2e32db246c73b2142ee2df778b67afb11e13`；补充分支 `codex/wechat-windows-acceptance`。本文件不是实机通过证明。

## 本轮实际结果

- PR #8重新读取：open、draft=true、未合并。本轮不改变其状态。
- 已审核三条草稿CLI及工作台/队列保护；原有账号和会话双锁、保存前持久化意图、相同内容去重、unknown隔离、已知ID只读恢复保留。
- 原代码确实没有首次扫码入口。新增 `python -m workbench.wechat_session`，只打开官方后台，等待用户本机扫码；不自动填写或保存。初次不提供身份配置时仅返回manual_login_only，不声称身份已验证。
- 新增ProfileLease操作系统文件锁，扫码入口和现有驱动共享，进程退出由操作系统释放。不删除或绕过Chromium自身锁。该锁不是跨机器账号锁；不同机器/不同数据目录不得并行运营同一账号。
- Windows脚本将profiles、工作台数据库、素材、binding和UI配置放在仓库外的LOCALAPPDATA专用目录，设置当前Windows用户ACL。浏览器状态仅存本机，不导出storage_state、Cookie、密码或token。扫码窗口必须关闭后再运行worker。
- 本环境Linux运行 `python -m unittest discover -q`：100项通过，0跳过（既有94+新增6）。进程锁在Linux验证；Windows msvcrt锁、PowerShell脚本及真实Chromium尚未实机验证。没有安装浏览器或访问微信。
- 尚无真实草稿ID、素材ID、截图或后台记录；所有真实业务关卡待验收。未执行正式发布。

## 先在本机PowerShell执行

需要Windows 11、Git、Python 3.12（含py启动器）、可访问官方后台的正常网络。本脚本不升级系统、不修改全局Codex配置；缺少前置工具时由本机Codex先检查现有安装，再按用户机器情况安装。禁止关闭系统安全策略或绕过站点访问限制。首次安装依赖需要联网。

使用一个新的独立目录，不覆盖已有工作区：

```powershell
$ErrorActionPreference = 'Stop'
$checkout = Join-Path $env:USERPROFILE ('AIadmin-Wechat-QA-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
git clone --single-branch --branch codex/wechat-windows-acceptance https://github.com/dong120ask-eng/AIadmin.git $checkout
if ($LASTEXITCODE -ne 0) { throw '下载失败，停止' }
Set-Location $checkout
git rev-parse HEAD
# Process作用域，不修改系统长期执行策略；组织策略禁止时停止并交本机管理员处理。
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\wechat-windows.ps1 -Stage Setup
if ($LASTEXITCODE -ne 0) { throw '环境检查失败，停止' }
.\scripts\wechat-windows.ps1 -Stage Inspect -ProfileRef wechat-primary
```

Setup检查Git、Python 3.12，建立独立 `.venv-wechat`，安装Playwright和其Chromium，显示实际依赖版本，运行隔离测试。安装版本以本机输出为准；验收报告记录Python/Playwright/浏览器/Windows build与源码SHA，不能把本轮Linux测试数冒充本机结果。

Inspect打开专用浏览器。用户仅在 `https://mp.weixin.qq.com/` 官方界面扫码；若被拒绝停止。扫码后回终端按回车，打开本地Playwright Inspector。用元素拾取/DevTools现场检查，不运行codegen，不保存全页HTML、trace、带token的URL或登录态。Inspector可人工导航核验，但不要点击发布、群发或保存未审核内容。观察完关闭Inspector/浏览器，释放会话。

## 交给本机Codex的完整指令

将下面整段交给在上述checkout中运行、具有浏览器观察能力的本机Codex；若该Codex不能观察浏览器，则停在DOM关卡，不声称能自动完成实测。

```text
请读取AGENTS.md、WECHAT-BROWSER-DRAFT.md、docs/WECHAT-WINDOWS-ACCEPTANCE.md和scripts/wechat-windows.ps1，在当前独立分支继续完成公众号草稿实机验收。不要从头搭建，不改main，不合并PR #8，不正式发布。

1. 检查Windows版本、Git、py -3.12、当前源码SHA、干净工作树和本机Codex浏览器能力。运行脚本Setup，记录真实测试与版本。所有会话、数据库、配置和素材仅放LOCALAPPDATA\AIadmin-Wechat，不导入用户日常浏览器profile。不要读取或上传Cookie/密码/token/全页HTML/认证文件，不修改全局Codex模型或认证配置。
2. 运行Inspect，由用户在官方页面扫码。通过已授权的本机浏览器观察实际页面。记录选择器含义、元素唯一性和检查时间，但不复制带token URL。核验官方页面的唯一账号标识，不能用昵称、推测ID或URL token。必须现场确认该标识在编辑/上传/回读各页面可读；否则实现必要的安全导航/身份核验改动并测试后再继续。
3. 在本机建立verified-ui.json，字段profile_ref、ui_verified_at、selectors。selectors完整键：identity,new_article,title,body,save,draft_list,draft_rows,row_title,row_open,draft_id,cover_input,cover_confirm,cover_image,inline_input,inline_images。值只用现场观察、唯一匹配的选择器，不填写示例或猜测DOM。原驱动假设草稿列表/草稿/素材有稳定data-id、正文可fill和inner_text；逐一现场验证。若不成立，先在当前分支按实际DOM修订驱动及离线测试，禁止伪造data-id或把当前编辑器值作为保存后回读证据。save只能绑定草稿保存控件。检查异步上传完成、重复标题、草稿列表分页与实际富文本框架；不具备可靠唯一定位时停止。
4. 关闭Inspect，用Verify和现场唯一ID检查同一profile。在工作台绑定对应企业/项目/账号，external_id必须与实际页面一致。写binding.json，按现有validate_binding格式；channel_id=wechat-official-draft、route=browser、profile_ref与专用会话一致。核对租户/项目/账号关联。不要把手工输入ID当作实测通过证据。
5. 先查当前工作台是否已有符合要求的真实已审核文章与素材，复用其审核版本。数据位置不在默认目录时显式指定PrivateRoot并使用同一data目录；不要复制整套未知凭证目录。没有可用产物时请用户选定一篇用于草稿测试的文章和有使用权的封面/图片，不能替用户勾选事实/权利/格式/AI声明四项审核。可使用既有生成流程prepare-job/run-job并让用户实际审核；先核实模型调用授权和费用设置，不默认接受未知费用。result.json必须按验收文档写入真实文章和browser_assets；放入素材并核对SHA256后再审核。禁止SQL改状态、伪造checked或将brief当成文章。
6. 只有第2至5步均通过才运行Run一次。确认隔离data目录没有其他queued草稿任务，worker当前按队列领取而非按Job领取。保存仅一次；保存后取真实草稿ID，按列表重新打开，核对标题/规范化正文/封面及图片稳定ID与顺序。任何异常停止，不循环重试。无ID的unknown必须人工查草稿箱，不换key重建。
7. 重复验证先在隔离测试通过，再对同一已保存审核版本使用同key和不同key分别验证不会新增草稿，记录后台草稿数量和队列结果。不得通过修改内容绕过去重。故障演练使用单独授权测试文章：保存前/后断线都可能留下自动保存草稿，先人工核对；已记录ID的unknown仅在旧进程停止后执行Reconcile只读回读；未记录ID不得重建。账号隔离：至少验证错误预期ID的Verify拒绝及不同专用profile的锁拒绝；若有第二个已授权账号再做真实切换，不能借用未授权账号。区分离线测试和真实UI结果。
8. 报告源码SHA、运行时版本、测试数量、task/job、审核摘要、真实草稿ID、内容哈希、回读结果、去重/断线/隔离证据与缺口。截图只保留脱敏必要区域（草稿标题/记录），遮掉二维码、手机号、账号私密信息和地址栏；绝不打包profiles/数据库/原始网页/日志/令牌。完整草稿ID只交用户私下报告，公开仓库仅放脱敏或哈希标识。未全部通过保持草稿PR。无需发布文章。
```

## 核验后执行命令

以下变量在本机从实际已审核任务/页面取得，不提供虚假默认值：

```powershell
$private = Join-Path $env:LOCALAPPDATA 'AIadmin-Wechat'
$accountUniqueId = Read-Host '输入刚从官方页面核对的唯一账号ID（不是昵称或token）'
.\scripts\wechat-windows.ps1 -Stage Verify -ExpectedId $accountUniqueId
# 先核对private\binding.json、verified-ui.json与data中的真实审核任务
$jobId = Read-Host '输入已审核文章Job ID'
$versionKey = Read-Host '输入该审核版本幂等Key'
.\scripts\wechat-windows.ps1 -Stage Run -Job $jobId -Key $versionKey
# 异常时先人工检查；仅限已有草稿ID的unknown且确认旧worker停止后：
# .\scripts\wechat-windows.ps1 -Stage Reconcile -Task $taskId -WorkerStopped
```

工作台查看/生成审核使用同一数据目录，另开PowerShell运行：

```powershell
& .\.venv-wechat\Scripts\python.exe -m workbench --data-dir "$env:LOCALAPPDATA\AIadmin-Wechat\data" serve --open-browser
# 只有已获模型调用授权时才增加--enable-cli；不要自动开启。
```

binding格式与文章结构以WECHAT-BROWSER-DRAFT.md、workbench/media.py和现有工作台记录为准。Windows PowerShell 5.1写JSON请用UTF-8无BOM（旧CLI使用utf-8读取），例如 `[IO.File]::WriteAllText($path,$json,(New-Object Text.UTF8Encoding($false)))`。不要将未知值复制为有效配置。

## 实机验收记录（留空表示未完成）

| 关卡 | 当前结果 | 合格证据 |
|---|---|---|
| Windows依赖/脚本/进程锁 | 未执行 | 版本、实际测试结果、并发拒绝记录 |
| 扫码与重启会话 | 未执行 | 官方界面扫码、重启后唯一ID再次匹配 |
| DOM/账号/素材稳定标识 | 未核验 | 本机观察记录与驱动测试 |
| 已审核文章/素材 | 未提供 | 对应产物摘要、素材哈希、真实审核 |
| 填写保存/列表重开 | 未执行 | 真实草稿ID、内容与素材回读摘要 |
| 同key及跨key去重 | 仅隔离测试 | 后台无新增草稿、队列结果 |
| 断线/只读恢复 | 仅隔离测试 | unknown及锁保留、只读核对记录 |
| 账号隔离 | 仅隔离测试 | 错号拒绝、授权会话隔离记录 |

真实草稿ID：**未取得**。正式发布：**未执行**。本文件及自动化测试均不构成真实业务验收。
