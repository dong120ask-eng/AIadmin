# DispatchQueue 跨模块安全集成（2026-10-23）

## 已核对的基线

| 来源 | 固定提交 | 基线与状态（检查时） |
| --- | --- | --- |
| main | c5ff4480d2e392a078c839da6c9bd989aa1c3573 | 未改变 |
| [PR #8](https://github.com/dong120ask-eng/AIadmin/pull/8) | 7ede2e32db246c73b2142ee2df778b67afb11e13 | main；open / draft |
| [PR #11](https://github.com/dong120ask-eng/AIadmin/pull/11) | e9b6131d138d13fdba315e878bd397f993fa7b68 | #8；open / draft |
| [PR #12](https://github.com/dong120ask-eng/AIadmin/pull/12) | b0e1c02624400df476112456248aad570c5fc501 | #11；open / draft |
| [PR #14](https://github.com/dong120ask-eng/AIadmin/pull/14) | 7ee2eec97db00050a5b1ee924c51b6751f4ef299 | main；open / draft |

在新检出目录从固定 main 建立隔离分支，依次 `git merge --no-ff` #8、#11、#12、#14。
前三步成功，最后一步在 `workbench/dispatch.py` 的 claim 签名及候选查询处产生实际文本冲突。
这确认需要联合解决冲突；不再只依赖单分支补丁推断。
原 #12 与 #14 分别在独立 worktree 重跑，115项与101项测试通过，均0跳过。
GitHub 的 PR 事件工作流查询在检查时对四个原始 head 均返回空列表；这不排除其他触发类型或历史运行。

## 接口及安全边界

```python
claim(tenant, worker, lease_seconds=120, action='inspect_only',
      max_browser_sessions=2, profile_ref=None, *, expected_task=None)
```

| 执行器 | action | 指定任务与载荷处理 |
| --- | --- | --- |
| Android检查 | inspect_only（默认） | 只领取此类型，不读取浏览器专用Profile字段 |
| AI总经理 | local_file | 必须给 expected_task；run_next 保留两项显式授权、合同哈希和宿主文件验收 |
| 公众号草稿 | draft | 仅公众号通道；已配置端口按Profile过滤；继续审核、意图去重、保存及重新打开回读 |
| 多账号只读 | browser_read | 继续按Profile过滤、授权撤销检查、身份前后核对及只读摘要 |

tenant、action、expected_task、Profile是同时满足的限制。指定任务不可领取时返回None，不改领另一任务。
expected_task为关键字参数；不把第四个位置参数解释成任务授权。
本地文件任务不含binding，claim不会访问它的浏览器字段。
浏览器任务重新验证绑定的企业、项目、路由、资源和通道，错误绑定以Problem拒绝并回滚，不取得锁。

浏览器Profile锁、公众号唯一账号别名锁、其他平台账号别名锁在同一 `BEGIN IMMEDIATE` 事务内取得。
公众号草稿和公众号只读共用相同账号别名，避免不同Profile同时操作同一个账号。
浏览器并发统计覆盖同一SQLite队列的所有企业和两类浏览器动作，硬上限2，每次领取可进一步收紧到1。
本地文件任务不占浏览器配额。未知状态保留的Profile锁也占配额；超时不会自动释放或重排。
租约token、到期时间、旧worker写入拒绝、手动确认停止后的取消恢复均沿用原实现。
真实端口继续使用ProfileLease操作系统文件锁，本轮不更改它的实现。

## 新增20项跨模块回归

入口：`python -X utf8 -m unittest tests.test_dispatch_integration -v`。
每个场景使用临时目录、合成账号和真实SQLite文件；不同队列对象连接同一个数据库。
浏览器端口是显式隔离fixture；模型调用被替换为本地精确字节输出fixture，未发模型请求。

- 三种任务全部6种入队顺序；三个执行器均走实际队列及各自完成路径。
- 三个独立连接并发领取：两个不同账号浏览器任务与一个本地任务共同运行；第三个浏览器任务被上限阻止。
- 指定任务领取、不同企业、错误类型、重复授权、已取消任务不回退、两项调用授权缺失时拒绝。
- Profile与指定ID交集；草稿执行器按端口Profile领取；同Profile跨动作排他；同账号不同Profile排他。
- 全队列跨企业并发上限1/2；本地任务不受浏览器配额阻塞。
- 只读会话授权在执行前、读取中、关闭浏览器后被撤销：均不能提交成功；其他模块可继续执行。
- 三类任务同时超时、重启恢复、所有锁保留、旧token拒绝、人工停止确认及取消后不自动重发。
- 浏览器读取和草稿回读中租约到期；不提交成功，不重新保存草稿，不释放隔离锁。
- 错误账号隔离不影响其他账号；OS Profile锁阻止端口连接；非法动作/参数及错误载荷拒绝。

同时调整原AI总经理的底层claim测试，明确使用local_file与其已授权任务ID；原安全断言仍保留。
原有公众号、会话、Android、manager及进程/文件安全测试完整重跑。

## 实际验证与CI

| 验证 | 实际结果 |
| --- | --- |
| 原 #12 独立Linux worktree | 115项通过，0跳过 |
| 原 #14 独立Linux worktree | 101项通过，0跳过 |
| 联合实现、原工作台全部测试 | 144项通过，0跳过 |
| 新增跨模块测试 | 20项通过，0跳过 |
| 最终完整工作台：Linux / Python 3.12.14 | 164项通过，0跳过 |
| CLI帮助：工作台、manager、browser_sessions | 均正常退出 |
| git diff --check | 通过 |

新增 `.github/workflows/dispatch-integration.yml`，针对Ubuntu/Windows与Python3.12/3.13四组运行完整工作台测试。
仅有contents:read权限；不安装浏览器、不调用模型、不保存或发布真实平台内容。
提交后的运行结论以集成PR的GitHub Actions链接及实际日志为准，本表记录本地验证时点。
即使Windows托管CI通过，也仅证明隔离代码和本地进程fixture，不代表用户Windows桌面及真实Codex/浏览器验收。

## 安全集成顺序与后续验收

1. 逻辑顺序为 main → #8 → #11 → #12 → #14；最后一步必须采用本分支联合claim及manager调用，禁止整段覆盖为任一旧版本。
2. 本集成候选包含固定main、#12及#14的祖先（#8/#11已包含在#12中）。它提供可整体审查和测试的合并树；原四个PR保持草稿。
3. 未来只有完成下述现场验收并获准合入后，才考虑整体集成候选进入main，或把相同解决方案同步到届时最新的分支重新测试。不要先把未修复的#14与#12同时放入main。
4. 任一来源head变化，重新取得最新提交、模拟合并、审核claim门禁并跑全套四组CI；本次结论只覆盖表中的固定提交。

现场验收继续按 `docs/WECHAT-WINDOWS-ACCEPTANCE.md`、`docs/BROWSER-SESSIONS.md`、
`docs/WINDOWS-MANAGER-FINAL-ACCEPTANCE.md` 执行。要求在用户Windows环境：
真实Codex本地文本任务与指定ID授权、取消/旧进程恢复；PowerShell入口；Chromium与OS Profile锁；
两个明确授权账号的错号拒绝、只读回读、撤销和并发；已审核公众号文章的一次保存、稳定草稿ID及重新打开回读。
本次没有连接上述真实环境，没有实际草稿ID，没有合并main，也没有执行真实平台发布。

共享SQLite是显式配置的能力；现有三个CLI的默认路径不同，不会自动合并已有生产数据。
应先在仓库外空目录对三个入口显式指定同一dispatch数据库，并让store使用独立数据库。
这仍是同机本地工具，tenant只是资料分区，不是公网身份系统；没有多机全局锁。
AI总经理的授权仍是指定任务的单次调用许可，并未新增运行中模型的远程撤销协议；
本轮撤销测试覆盖只读会话授权以及manager取消后的旧授权不再领取。
