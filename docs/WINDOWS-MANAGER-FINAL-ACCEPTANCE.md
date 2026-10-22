# Windows AI总经理：最终验收指令与中文操作方法

日期：2026-10-23。适用于PR #14安全复核后的 `codex/windows-ai-manager-phase1` 分支。验收通过前保持草稿。当前云端没有连接你的Windows电脑；以下是供本机执行的指令，不是已运行结果。

## 直接交给本机Codex的完整指令

复制下面整个文本框到Windows本机Codex：

```text
请对 dong120ask-eng/AIadmin 的 PR #14 执行最终Windows验收。使用 codex/windows-ai-manager-phase1 分支的最新安全修复，不重新开发已有桌面、语音或队列功能。先读取AGENTS.md、docs/PR14-SECURITY-REVIEW.md、docs/WINDOWS-AI-MANAGER.md和两个现有PowerShell脚本。

一、源码与环境
1. 查找本机已有AIadmin-manager工作目录。先查看git status；有未提交改动不要覆盖。不存在或目录有其他任务时，建立独立克隆/工作树。只更新目标分支，不改main、不合并、不解除PR草稿，不自动更改全局Codex配置、认证或执行策略。
2. 记录实际commit SHA、是否dirty、Windows版本/build、Python版本、PowerShell版本。需要Python 3.12+含Tk。诊断已安装Codex；若PATH只有codex.cmd，查找现有官方安装中的真实codex.exe，只在当前会话设置CODEX_BIN；找不到则报告blocked，不自动安装或以cmd/bat替代。
3. 只输出认证是否可用，禁止输出API key、Cookie、auth文件、环境全量或完整配置。核对当前实际模型/提供方/计费来源及自定义配置，不把版本/参数兼容性猜测当作通过。

二、默认先做免费离线验收
执行 powershell -NoProfile -File .\scripts\start-manager.ps1 -CheckOnly
执行 powershell -NoProfile -File .\scripts\accept-manager.ps1
保存输出的证据目录和evidence.json、自动化日志。默认不开启AuthorizeModelCost；离线通过不能标记真实CLI通过。脚本的merge_ready必须保持false。
用Windows PowerShell解析器检查两个脚本语法；若语法/原生stderr/中文编码失败，直接修复并重跑。禁止调整测试期待值来掩盖错误。

三、Windows安全边界（先离线测试程序，再考虑模型）
在专用临时目录演练runner，不使用真实模型，也不触及真实业务文件：
a. 测试程序启动后代，父进程立即退出；后代延迟向本次临时哨兵写入。分别测试正常退出、超时、只强杀本次宿主。检查本次后代PID与创建时间，不能按名称批量杀所有python/codex。当前实现已知不保证Windows父进程退出后的后代清理；确认缺陷后实施并验证Job Object或受限执行宿主等适用方案。只有无残留写入及进程证据才可判通过。
b. 演练manager-runtime目录junction/输出重解析点、硬链接和大文件。沙箱必须禁止修改本次任务目录之外的临时哨兵。先由宿主确认哨兵可写，再在同版本CLI的同一sandbox策略中尝试写入；保留拒绝证据与哨兵哈希。只看CLI参数或文件检查结果不足以判定隔离有效。
c. 审查继承的MCP/插件/钩子/技能/规则/额外可写根/网页搜索及网络出口。不可用一个“空表覆盖”就假定所有配置被清空。发现可绕过通道先在项目内修复隔离方案并补测试，不修改全局设置、不复制认证到仓库。网络探针只访问本次操作者控制的临时本地端点，保留宿主可达、沙箱拒绝的对照；这不替代真实外网/工具出口策略验证。若无可验证边界，标为blocked并保留草稿。

四、真实文字闭环（会使用当前模型权益）
只有操作者本次明确接受“当前配置提供方的一次未知模型费用”，并完成必要安全边界核查后，才执行：
powershell -NoProfile -File .\scripts\accept-manager.ps1 -AuthorizeModelCost
此脚本使用全新数据库，只执行一个明确绑定ID的任务。失败/unknown不自动重跑。检查evidence.json、status.json、readback.log、实际hello.txt的UTF-8精确字节和SHA256，并报告实际退出码。90秒不是金额上限；模型未运行则写not_run/blocked，不能写passed。

五、中文语音和桌面
先执行 powershell -NoProfile -File .\scripts\accept-manager.ps1 -CheckSpeech 做本机识别/播报接口测试（不会调用模型）。识别结果必须由操作者核对，只有实际听到播报才确认；缺少zh-CN识别器/权限则blocked，不自动装语音包。
启动 start-manager.ps1。操作者说“创建文件 hello.txt，内容为你好，AIadmin”，修正hello.txt或标点识别错误，点“识别并登记”，核对具体任务ID/文件名/内容，勾选任务及费用授权，点“执行已核对任务”，检查checked及文件后点“语音汇报”。这次也是独立模型调用，必须有操作者对这次费用的授权，不能沿用上一轮授权。没有现场操作者不得编造听到/看到/确认的结论。

六、真实中断恢复
另建专用数据库及任务。在running时记录本次宿主/CLI/后代PID与创建时间，只中断这次宿主。立刻重开同一数据库：租约未到期不应重新领取；到期后recover应转unknown并保留manager-local-worker锁，不能自动重试。保留原attempt_path。
先确认并停止本次CLI及后代，核对产物与已用费用，再用同一个--db和真实任务ID执行resolve --worker-stopped --reason。确认cancelled才释放锁。新任务用新key/ID且重新授权。自动化时钟测试不能替代Windows现场中断演练；无法安全完成时记blocked。

七、交付
记录每个关卡为passed/failed/blocked/not_run，附实际命令、commit、版本、任务ID、退出码、脱敏日志、文件哈希、进程与哨兵证据。指出“真实Codex模型”和“本地测试程序”的区别。只把已检查的文件内容记为checked。将必要修复提交目标分支，保持PR #14草稿，不合并。所有关键安全、真实文字、语音、中断恢复、费用边界证据齐全后才能提出合并建议，不自行批准或编造观察结果。
```

## 人工在Windows快速操作

在目标仓库根目录打开PowerShell。首次检查：

```powershell
powershell -NoProfile -File .\scripts\start-manager.ps1 -CheckOnly
powershell -NoProfile -File .\scripts\accept-manager.ps1
```

如脚本被执行策略拒绝，报告具体错误；不要全局降低执行策略。可先运行等价文字检查：

```powershell
$env:PYTHONUTF8 = '1'
python -m unittest discover -v
python -m workbench.manager doctor
```

完成安全边界验收且明确接受一次未知费用后，执行：

```powershell
powershell -NoProfile -File .\scripts\accept-manager.ps1 -AuthorizeModelCost
```

该命令不会顺带执行已有业务队列；会新建验收目录，结束时显示证据路径。失败则停止核查，不连续重试。`evidence.json`中只有 `text_cli_file_readback=passed` 能表示这一轮文件闭环通过；`merge_ready`依然为false。

语音接口与桌面分别启动：

```powershell
powershell -NoProfile -File .\scripts\accept-manager.ps1 -CheckSpeech
powershell -NoProfile -File .\scripts\start-manager.ps1
```

桌面：文字输入/语音输入 → 人工修正 → 识别并登记 → 核对任务ID和内容 → 本次任务/费用授权 → 执行已核对任务 → checked/实际文件回读 → 语音汇报。恢复已有queued任务先点“核对待执行任务”。识别接口成功不等于整条语音业务通过。

## 恢复命令模板

**必须用对应验收数据库，不能误操作默认库。** 先停止该次旧进程并核查文件与费用，才能核销：

```powershell
$db = '替换为该次验收目录的manager.db完整路径'
python -m workbench.manager --db $db status
python -m workbench.manager --db $db recover
python -m workbench.manager --db $db resolve manager-替换真实任务ID --worker-stopped --reason '已停止本次旧进程并核对产物和费用'
```

真实文件任务已强制指定ID：

```powershell
python -m workbench.manager --db $db run --task-id manager-替换已核对任务ID --authorize-local-task --allow-unknown-cost --timeout 90
```

该模板不是重复执行授权。已checked/cancelled/unknown的ID不能被重新领取；需要重新执行时，先完成未知任务核查，再创建新任务并重新授权。
