# Windows AI总经理：第一阶段原型

初版：2026-10-21；安全复核：2026-10-23（北京时间）。基线 main：`c5ff4480d2e392a078c839da6c9bd989aa1c3573`。

## 当前能力

原生 Tk 桌面窗口 + 完整文字 CLI。输入→确定性结构化分类→人工任务/未知费用授权→既有 Codex 进程适配器→SQLite 队列/租约/排他→宿主独立字节及 SHA256 检查→文字与可选系统语音汇报。

首轮只接受 `创建文件 hello.txt，内容为你好，AIadmin` 这种明确合同，仅生成 `.txt/.md`。其他自然语言、代码开发、外部发布/支付请求返回“不支持”，不会交给模型自行扩展权限。不是通用自然语言任务规划器。正文被当作文件数据，执行提示不能替代操作系统沙箱。

`ManagerQueue` 继承现有 `DispatchQueue`，沿用表结构、原子 claim、租约 token、资源排他、事件、恢复及人工核销。单独的本机数据库避免领取内容/安卓队列任务，未重建任务系统。`runner.codex_binary/invoke/doctor` 原样复用，不把本地文件任务伪装成内容草稿。PR #5 已核实仍为开放草稿，未盲目合并其旧版本依赖。

## Windows 启动

需要可信本机、Python 3.12+（包含 Tcl/Tk）、git，以及已安装并认证的 Codex CLI。脚本不自动下载依赖、登录、修改全局配置或购买服务。

```powershell
git clone --branch codex/windows-ai-manager-phase1 https://github.com/dong120ask-eng/AIadmin.git AIadmin-manager
cd AIadmin-manager
powershell -NoProfile -File .\scripts\start-manager.ps1
```

如已克隆，请使用独立目录或 worktree，避免覆盖未提交修改。若 PowerShell 执行策略阻止脚本，可直接运行：

```powershell
python -m workbench.manager doctor
python -m workbench.manager desktop
```

若 PATH 中仅有 `codex.cmd`，将 `CODEX_BIN` 设置为本机真实原生 `codex.exe` 的完整路径；本适配器刻意不通过 shell 执行 cmd 包装器。不在指令里填写令牌。先在本机确认现有 Codex 安装与认证；未发现 CLI 时保持排队，不假报执行成功。

界面操作：输入文字或点“语音输入”→检查识别文字→“识别并登记”→查看下方具体任务ID、文件名/内容（旧任务先点“核对待执行任务”）→勾选本次任务授权与未知费用→“执行已核对任务”→查看 checked 及实际产物路径→“语音汇报”。任务运行期间刷新可观察持久化 running；当前未解析逐条模型事件，没有百分比进度估算。操作界面不提供任意命令输入。

## 可复制中文指令

```text
创建文件 hello.txt，内容为你好，AIadmin
```

文字命令等价入口（仅最后一行调用模型）：

```powershell
python -m workbench.manager submit '创建文件 hello.txt，内容为你好，AIadmin' --key first-local-file
python -m workbench.manager status
# 将下一行的真实任务ID替换为submit/status返回的id；不会领取其他任务
python -m workbench.manager run --task-id manager-替换真实任务ID --authorize-local-task --allow-unknown-cost --timeout 90
```

数据默认保存于用户目录的 `AIadmin-manager`，数据库及任务产物保留供本机核验；不上传账号、日志或语音。录音由系统识别器处理。任务文本及内容会发送至当前已配置的 Codex 模型；费用未知，无费用上限估算。

## 自动与真实验收

```powershell
# 不调用模型：测试 + 环境诊断
powershell -NoProfile -File .\scripts\accept-manager.ps1
# 明确接受本轮模型费用，使用全新的验收数据库调用真实Codex
powershell -NoProfile -File .\scripts\accept-manager.ps1 -AuthorizeModelCost
```

退出码非0或没有 checked 都不能验收通过。检查实际 hello.txt 精确为 `你好，AIadmin`，结果记录含真实路径、字节数、SHA256 和 `host_exact_bytes`。验收脚本保存本机 evidence.json、status.json、自动化日志和二次独立回读结果。无费用授权时只运行离线检查，不能代表真实模型调用成功。不要将单元测试中的 fake 执行器结果当作模型执行。

语音适配器接口见 `SpeechPort.listen/speak`；默认 `WindowsSpeech` 使用 Windows PowerShell/System.Speech，本机 zh-CN 识别器、语音包与麦克风权限缺失时显示失败，文字入口继续可用。没有云语音依赖与自动下载。语音识别15秒，进程超时40秒；语音识别结果必须人工检查，不能直接触发任务授权。标准听写识别器不保证保留文件名和标点，失败可用文字修正。语音播报是用户主动点击触发。

现场语音验收：说出上述指令→核对/修正文字→登记及授权→真实 checked→点击汇报并实际听到正确结果。只有这些步骤有现场证据才能标记语音闭环通过。

## 中断与恢复

正常退出会等待当前后台操作完成；强杀或重启后任务可能保持 running。租约最长540秒；到期执行 `recover` 会标记 unknown，保留资源锁，不自动重跑。立即恢复不能跳过仍有效租约。先核查并停止旧 Codex 及子进程，核对任务目录、费用，再执行：

```powershell
python -m workbench.manager recover
python -m workbench.manager status
python -m workbench.manager resolve manager-替换真实任务ID --reason '已停止旧进程并核对产物与费用' --worker-stopped
```

人工核销为 cancelled 后才释放资源；重做须新幂等键并重新授权。unknown 不会被当作成功。自动化已验证租约到期、重开数据库、拒绝旧token完成与人工核销；Windows真实强杀、断电、重启仍待本机演练。

## 交付证据与下一阶段条件

初版 Linux/Python 实测记录见 `MANAGER-VERIFICATION.json`；本次修复的测试、风险及合并关卡见 `PR14-SECURITY-REVIEW.md` 和 `PR14-SECURITY-VERIFICATION.json`；最终可交给本机Codex的指令见 `WINDOWS-MANAGER-FINAL-ACCEPTANCE.md`。未连接用户Windows，无可用Codex可执行文件，故未作付费模型调用。Tk窗口、PowerShell、系统语音包、原生Windows沙箱与语音闭环尚未现场验收。

进入下一阶段前：①本机真实文字→CLI执行成功；②语音识别/播报现场通过；③强杀/重启及旧进程停止演练；④确认CLI沙箱及网络出口限制，禁止不可信全权限配置；⑤确定模型预算策略。再扩展可审查的任务分类、代码补丁与独立测试适配器、PR #5专家阶段、取消进程与实时事件，不在本轮增加移动端或硬件。

本机用户权限是信任边界；提示词不构成禁网安全边界，继承的 Codex 配置可能影响执行行为。生产应用前仍需独立受限账户/沙箱与网络策略实测。当前独立检查只证明输出文件符合合同，不证明整个进程没有外部副作用，也不是独立QA智能体。

## 本次安全修复的范围

授权已绑定具体任务ID；任务目录坐标在调用前持久化。禁用继承的额外可写根、临时目录豁免和网页搜索。拒绝任务目录祖先中的链接/Windows重解析点，验证输出为单链接普通文件，并限长读取；最终入库前宿主再次核对。Windows仅接受原生`.exe`入口。共用进程适配器将stdin发送纳入超时、退出后再次检查输出上限，POSIX正常退出也清理同组子进程。

这些限制不构成完整安全隔离：继承的MCP/插件/技能/钩子、可读文件、Windows退出父进程后仍存活的子进程，以及原生沙箱有效性仍需单独验收。`checked`仅表示当次文件回读正确，不能升级为“无系统副作用”。未知费用授权没有金额上限，90秒超时也不构成费用上限。保留PR草稿，合并条件详见审查报告。
